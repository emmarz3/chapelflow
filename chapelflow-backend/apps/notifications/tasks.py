from celery import shared_task

from .models import Notification, NotificationChannel, NotificationStatus
from .providers import email_provider, push_provider, sms_provider


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
    return NotificationStatus.SENT


@shared_task(bind=True, max_retries=3, default_retry_delay=30)
def deliver_notification(self, notification_id):
    notification = Notification.objects.select_related("recipient").get(id=notification_id)

    try:
        if notification.channel == NotificationChannel.EMAIL and notification.recipient and notification.recipient.email:
            response = email_provider.send(
                to=notification.recipient.email, subject=notification.title, body=notification.body
            )
        elif notification.channel == NotificationChannel.SMS and notification.recipient and notification.recipient.phone_number:
            response = sms_provider.send(to=notification.recipient.phone_number, body=notification.body)
        elif notification.channel == NotificationChannel.PUSH:
            response = push_provider.send(device_token="", title=notification.title, body=notification.body)
        else:
            notification.status = NotificationStatus.FAILED
            notification.provider_response = {"error": "No valid recipient address for this channel."}
            notification.save(update_fields=["status", "provider_response"])
            return

        from django.utils import timezone
        status = _status_for_provider_response(response)
        notification.status = status
        notification.provider_response = response
        # Only a real (non-stubbed) send actually left this system, so
        # only that counts as sent_at for reporting purposes — a stubbed
        # "send" never reached a real user and shouldn't look like it did.
        notification.sent_at = timezone.now() if status == NotificationStatus.SENT else None
        notification.save(update_fields=["status", "provider_response", "sent_at"])
    except Exception as exc:
        notification.status = NotificationStatus.FAILED
        notification.provider_response = {"error": str(exc)}
        notification.save(update_fields=["status", "provider_response"])
        raise self.retry(exc=exc)


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

    members = Member.objects.filter(id__in=member_ids).select_related("user")
    for member in members:
        if not member.user_id:
            continue
        notification = Notification.objects.create(
            recipient=member.user, recipient_member=member, channel=channel, title=title, body=body,
            source_announcement_id=announcement_id,
        )
        deliver_notification.delay(str(notification.id))
