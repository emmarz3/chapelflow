from celery import shared_task

from apps.accounts.models import User
from apps.operations.models import ContentEntry, ContentStatus, ContentType

from .models import NotificationCategory, NotificationChannel
from .models import Notification
from .preferences import queue_notification


@shared_task
def notify_live_service_published(entry_id):
    entry = ContentEntry.objects.filter(pk=entry_id, content_type=ContentType.LIVESTREAM, status=ContentStatus.PUBLISHED).first()
    if not entry:
        return {"created": 0}
    created = 0
    for user in User.objects.filter(branch_id=entry.branch_id, is_active=True).iterator(chunk_size=500):
        key = f"live-service:{entry.id}:{user.id}"
        if Notification.objects.filter(idempotency_key=key).exists():
            continue
        notification = queue_notification(
            recipient=user, category=NotificationCategory.LIVE_SERVICE,
            channel=NotificationChannel.IN_APP,
            title="A chapel service is live", body=f"{entry.title} is now live.",
            href="/livestream", idempotency_key=key,
        )
        if notification:
            created += 1
    return {"created": created}
