from celery import shared_task
from datetime import timedelta
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from .models import Notification, NotificationCategory, NotificationChannel, NotificationStatus
from .preferences import delivery_eligibility, queue_notification
from .providers import email_provider, sms_provider


def _status_for_provider_response(response: dict) -> str:
    """
    Spec section 13: "Do not mark an SMS/push delivery as 'sent' when the
    provider is only stubbed." Every stub provider in providers.py returns
    {"status": "stubbed", ...} specifically so this can be detected here,
    in one place, rather than every call site having to know which
    providers are real. Real providers return {"status": "sent"} (or
    whatever their SDK gives back) and are treated as actually sent.
    """
    if response.get("status") == "stubbed":
        return NotificationStatus.STUBBED
    if response.get("status") == "sent":
        return NotificationStatus.SENT
    return NotificationStatus.FAILED


@shared_task(bind=True, max_retries=3, default_retry_delay=30, retry_backoff=True, retry_jitter=True)
def deliver_notification(self, notification_id):
    with transaction.atomic():
        notification = Notification.objects.select_related("recipient").select_for_update(of=("self",)).get(id=notification_id)
        if notification.status not in {NotificationStatus.PENDING, NotificationStatus.FAILED}:
            return {"status": "skipped", "reason": "already processed"}
        now = timezone.now()
        if notification.scheduled_for and notification.scheduled_for > now:
            return {"status": "deferred"}
        allowed, quiet_end = delivery_eligibility(notification.recipient, notification.category, notification.channel, now)
        if not allowed:
            notification.status = NotificationStatus.SKIPPED
            notification.provider_response = {"reason": "notification preference or account eligibility"}
            notification.save(update_fields=["status", "provider_response"])
            return {"status": "skipped", "reason": "preference"}
        if quiet_end:
            notification.status = NotificationStatus.PENDING
            notification.scheduled_for = quiet_end
            notification.save(update_fields=["status", "scheduled_for"])
            return {"status": "deferred"}
        notification.status = NotificationStatus.SENDING
        notification.attempts += 1
        notification.scheduled_for = None
        notification.save(update_fields=["status", "attempts", "scheduled_for"])

    try:
        if notification.channel == NotificationChannel.EMAIL and notification.recipient and notification.recipient.email:
            response = email_provider.send(
                to=notification.recipient.email, subject=notification.title, body=notification.body
            )
        elif notification.channel == NotificationChannel.SMS and notification.recipient and notification.recipient.phone_number:
            response = sms_provider.send(to=notification.recipient.phone_number, body=notification.body)
        elif notification.channel == NotificationChannel.PUSH:
            # There is no device subscription or browser permission lifecycle yet.
            # Legacy PUSH rows must never be sent with an empty device token.
            response = {"status": "stubbed", "reason": "no device subscription"}
        elif notification.channel == NotificationChannel.IN_APP:
            # The persisted notification is the in-app delivery itself; no external
            # provider is involved and it is immediately available in the inbox.
            notification.status = NotificationStatus.DELIVERED
            notification.provider_response = {"status": "delivered", "provider": "in_app"}
            notification.sent_at = timezone.now()
            notification.save(update_fields=["status", "provider_response", "sent_at"])
            return {"status": "delivered"}
        else:
            notification.status = NotificationStatus.FAILED
            notification.provider_response = {"error": "No valid recipient address for this channel."}
            notification.save(update_fields=["status", "provider_response"])
            return {"status": "failed", "reason": "missing address"}

        status = _status_for_provider_response(response)
        if status == NotificationStatus.FAILED:
            raise RuntimeError("Notification provider rejected or failed the delivery.")
        notification.status = status
        notification.provider_response = response
        # Only a real (non-stubbed) send actually left this system, so
        # only that counts as sent_at for reporting purposes — a stubbed
        # "send" never reached a real user and shouldn't look like it did.
        notification.sent_at = timezone.now() if status == NotificationStatus.SENT else None
        notification.save(update_fields=["status", "provider_response", "sent_at"])
        return {"status": status.lower()}
    except Exception as exc:
        notification.status = NotificationStatus.FAILED
        notification.provider_response = {"error": str(exc)[:500]}
        notification.save(update_fields=["status", "provider_response"])
        raise self.retry(exc=exc)


@shared_task
def dispatch_due_notifications():
    """Requeue notifications deferred for quiet hours or an earlier broker failure."""
    now = timezone.now()
    due_ids = list(Notification.objects.filter(status=NotificationStatus.PENDING).filter(
        Q(scheduled_for__lte=now) | Q(scheduled_for__isnull=True, created_at__lte=now - timedelta(minutes=5))
    ).values_list("id", flat=True)[:500])
    for notification_id in due_ids:
        deliver_notification.delay(str(notification_id))
    return {"queued": len(due_ids)}


@shared_task
def mark_notification_delivered(notification_id, provider_metadata=None):
    """
    Delivery-confirmation handler (spec section 13's "delivered" state).
    Intended to be called from a provider's delivery-confirmation webhook
    once a real (non-stub) SMS/push/email provider is wired up — most
    providers confirm delivery asynchronously, separately from the
    initial send. Only a notification currently in SENT can transition to
    DELIVERED; anything else (PENDING/FAILED/STUBBED) is left alone,
    since "delivered" only makes sense after a real send actually
    happened.
    """
    updated = Notification.objects.filter(id=notification_id, status=NotificationStatus.SENT).update(
        status=NotificationStatus.DELIVERED,
        provider_response={"delivered": True, **(provider_metadata or {})},
    )
    return {"updated": bool(updated)}


@shared_task
def send_notification_to_members(member_ids, title, body, channel=NotificationChannel.EMAIL, announcement_id=None):
    from apps.members.models import Member
    from apps.communications.models import Announcement
    from apps.communications.services import resolve_audience_members

    members = Member.objects.filter(id__in=member_ids).select_related("user")
    announcement = Announcement.objects.prefetch_related("target_groups").filter(pk=announcement_id).first() if announcement_id else None
    if announcement_id and announcement is None:
        return {"created": 0}
    if announcement:
        members = members.filter(id__in=resolve_audience_members(announcement).values("id"))
        category = NotificationCategory.FELLOWSHIP if announcement.target_groups.exists() else NotificationCategory.ANNOUNCEMENT
    else:
        category = NotificationCategory.OTHER
    created = 0
    for member in members:
        if not member.user_id:
            continue
        existing = Notification.objects.filter(
            source_announcement=announcement, recipient=member.user, channel=channel,
        ).first() if announcement else None
        if existing:
            if existing.status == NotificationStatus.FAILED:
                transaction.on_commit(lambda notification_id=str(existing.id): deliver_notification.delay(notification_id))
                created += 1
            continue
        notification = queue_notification(
            recipient=member.user, recipient_member=member, category=category, channel=channel,
            title=title, body=body, source_announcement=announcement,
            idempotency_key=f"announcement:{announcement.id}:{member.user_id}:{channel}" if announcement else None,
        )
        if notification:
            created += 1
    return {"created": created}


@shared_task
def send_birthday_notifications():
    """Create one private in-app birthday notification for each active branch user."""
    from django.contrib.auth import get_user_model
    from django.db import IntegrityError, transaction
    from apps.members.models import Member, MembershipStatus
    from .models import BirthdayAnnouncement
    from .preferences import delivery_eligibility

    today = timezone.localdate()
    celebrants = Member.objects.filter(
        membership_status=MembershipStatus.ACTIVE,
        date_of_birth__month=today.month,
        date_of_birth__day=today.day,
    ).select_related("branch")
    User = get_user_model()
    celebrations_created = 0
    notifications_created = 0

    for member in celebrants.iterator():
        try:
            with transaction.atomic():
                birthday, created = BirthdayAnnouncement.objects.get_or_create(
                    member=member,
                    celebrated_on=today,
                )
                if not created:
                    continue
                recipients = [user for user in User.objects.filter(branch_id=member.branch_id, is_active=True).only("id")
                              if delivery_eligibility(user, NotificationCategory.BIRTHDAY, NotificationChannel.IN_APP)[0]]
                Notification.objects.bulk_create([
                    Notification(
                        recipient=recipient,
                        birthday_announcement=birthday,
                        channel=NotificationChannel.IN_APP,
                        category=NotificationCategory.BIRTHDAY,
                        href="/app",
                        title=f"Happy birthday, {member.first_name}!",
                        body=f"Join the ChapelFlow community in celebrating {member.full_name} today.",
                        status=NotificationStatus.DELIVERED,
                        provider_response={"status": "delivered", "provider": "in_app", "kind": "birthday"},
                        sent_at=timezone.now(),
                    )
                    for recipient in recipients
                ])
                celebrations_created += 1
                notifications_created += len(recipients)
        except IntegrityError:
            # The unique constraint makes a retry or overlapping worker safe.
            continue

    return {
        "celebrations_created": celebrations_created,
        "notifications_created": notifications_created,
    }


# Celery autodiscovers tasks.py; importing registers the live-service task too.
from .live import notify_live_service_published  # noqa: E402,F401
