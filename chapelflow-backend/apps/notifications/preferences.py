from datetime import datetime, timedelta, timezone as dt_timezone
from zoneinfo import ZoneInfo

from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.communications.models import CommunicationPreference

from .models import Notification, NotificationCategory, NotificationChannel


CATEGORY_FIELDS = {
    NotificationCategory.ANNOUNCEMENT: "announcements_enabled",
    NotificationCategory.EVENT: "events_enabled",
    NotificationCategory.SERVICE: "service_reminders_enabled",
    NotificationCategory.DEVOTIONAL: "devotional_enabled",
    NotificationCategory.PRAYER: "prayer_updates_enabled",
    NotificationCategory.PUBLIC_PRAYER: "prayer_notifications_enabled",
    NotificationCategory.FELLOWSHIP: "fellowship_enabled",
    NotificationCategory.LIVE_SERVICE: "live_service_enabled",
    NotificationCategory.ADMIN_ALERT: "admin_alerts_enabled",
    NotificationCategory.BIRTHDAY: "birthday_enabled",
}
CHANNEL_FIELDS = {
    NotificationChannel.EMAIL: "email_enabled",
    NotificationChannel.SMS: "sms_enabled",
    NotificationChannel.PUSH: "push_enabled",
    NotificationChannel.IN_APP: "in_app_enabled",
}
DEFAULT_HREFS = {
    NotificationCategory.ANNOUNCEMENT: "/app/announcements",
    NotificationCategory.EVENT: "/app/events",
    NotificationCategory.SERVICE: "/app/events",
    NotificationCategory.PRAYER: "/app/care",
    NotificationCategory.PUBLIC_PRAYER: "/app/care",
    NotificationCategory.FELLOWSHIP: "/app/communities",
    NotificationCategory.LIVE_SERVICE: "/app",
    NotificationCategory.ADMIN_ALERT: "/app",
    NotificationCategory.BIRTHDAY: "/app",
    NotificationCategory.DEVOTIONAL: "/app",
    NotificationCategory.OTHER: "/app/notifications",
}


def preference_for(user):
    if not user:
        return None
    preference = CommunicationPreference.objects.filter(user=user).first()
    if preference:
        return preference
    member = getattr(user, "member_profile", None)
    if member:
        return CommunicationPreference.objects.filter(member=member).first()
    return None


def get_or_create_preference(user):
    with transaction.atomic():
        preference = preference_for(user)
        if preference:
            if preference.user_id is None:
                preference.user = user
                preference.save(update_fields=["user", "updated_at"])
            return preference
        member = getattr(user, "member_profile", None)
        try:
            with transaction.atomic():
                return CommunicationPreference.objects.create(user=user, member=member)
        except IntegrityError:
            return preference_for(user)


def quiet_until(preference, now=None):
    if not preference or not preference.quiet_hours_enabled:
        return None
    start, end = preference.quiet_hours_start, preference.quiet_hours_end
    if not start or not end or start == end:
        return None
    now = now or timezone.now()
    zone = ZoneInfo(preference.timezone_name)
    local = now.astimezone(zone)
    clock = local.timetz().replace(tzinfo=None)
    if start < end:
        in_quiet = start <= clock < end
        end_day = local.date()
    else:
        in_quiet = clock >= start or clock < end
        end_day = local.date() + timedelta(days=1) if clock >= start else local.date()
    if not in_quiet:
        return None
    return datetime.combine(end_day, end, zone).astimezone(dt_timezone.utc)


def delivery_eligibility(user, category, channel, now=None):
    if not user or not user.is_active:
        return False, None
    preference = preference_for(user)
    if preference:
        if not preference.master_enabled or not getattr(preference, CHANNEL_FIELDS[channel]):
            return False, None
        field = CATEGORY_FIELDS.get(category)
        if field and not getattr(preference, field):
            return False, None
        if category == NotificationCategory.FELLOWSHIP and not preference.announcements_enabled:
            return False, None
        return True, quiet_until(preference, now) if channel != NotificationChannel.IN_APP else None
    # Public prayer broadcasts are opt-in; personal prayer updates are on by default.
    return (category not in {NotificationCategory.DEVOTIONAL, NotificationCategory.PUBLIC_PRAYER}), None


def create_notification(*, recipient, category, channel, title, body, href="", idempotency_key=None, **kwargs):
    if channel == NotificationChannel.PUSH:
        return None  # There is no registered device-token lifecycle in this application yet.
    allowed, scheduled_for = delivery_eligibility(recipient, category, channel)
    if not allowed:
        return None
    target = href or DEFAULT_HREFS.get(category, "/app/notifications")
    if not (target == "/app" or target.startswith("/app/") or target == "/livestream") or target.startswith("//"):
        raise ValueError("Notification links must stay inside the application.")
    values = dict(
        recipient=recipient, category=category, channel=channel, title=title,
        body=body, href=target, scheduled_for=scheduled_for, **kwargs,
    )
    if idempotency_key:
        notification, _ = Notification.objects.get_or_create(
            idempotency_key=idempotency_key, defaults=values,
        )
        return notification
    return Notification.objects.create(**values)


def queue_notification(**kwargs):
    """Create an eligible notification and enqueue delivery after its DB commit."""
    from .models import NotificationStatus
    from .tasks import deliver_notification

    notification = create_notification(**kwargs)
    if notification and notification.status in {NotificationStatus.PENDING, NotificationStatus.FAILED}:
        transaction.on_commit(lambda notification_id=str(notification.id): deliver_notification.delay(notification_id))
    return notification
