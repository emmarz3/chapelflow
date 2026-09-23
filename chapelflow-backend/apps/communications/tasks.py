from celery import shared_task
from django.db import transaction
from django.utils import timezone


@shared_task
def dispatch_announcement(announcement_id):
    """
    Phase 10: Dispatch announcement to resolved audience with authorization and preference enforcement.
    
    Workflow:
    1. Validate announcement is in QUEUED status (idempotency)
    2. Transition to SENDING status
    3. Resolve audience using services.resolve_audience_members()
    4. Filter by communication preferences per channel
    5. Fan out to notifications for each channel
    6. Transition to COMPLETED or FAILED status
    
    Security:
    - Uses services.py for audience resolution (respects authorization)
    - Enforces communication preferences
    - Idempotent (checks status before dispatching)
    - Atomic status transitions
    - Tracks timestamps and failures
    """
    from .models import Announcement, AnnouncementStatus
    from . import services
    
    # Atomic idempotency check and status transition
    with transaction.atomic():
        announcement = (
            Announcement.objects
            .select_for_update()
            .select_related("branch")
            .prefetch_related("target_groups")
            .filter(id=announcement_id, status=AnnouncementStatus.QUEUED)
            .first()
        )
        
        # Idempotency: already dispatched or not queued
        if announcement is None:
            return {"status": "skipped", "reason": "not in QUEUED status"}
        
        # Transition to SENDING
        announcement.status = AnnouncementStatus.SENDING
        announcement.sending_started_at = timezone.now()
        announcement.save(update_fields=["status", "sending_started_at"])
    
    try:
        # Resolve audience using services.py (respects audience_type, groups, statuses)
        members = services.resolve_audience_members(announcement)
        
        # Get channels (default to EMAIL for backward compatibility)
        channels = announcement.channels if announcement.channels else ["EMAIL"]
        
        # Dispatch to each channel
        from apps.notifications.tasks import send_notification_to_members
        
        for channel in channels:
            # Filter by communication preferences for this channel
            filtered_members = services.filter_by_preference(members, channel)
            
            # Send to filtered members
            member_ids = [str(m.id) for m in filtered_members]
            if member_ids:
                send_notification_to_members.delay(
                    member_ids=member_ids,
                    title=announcement.title,
                    body=announcement.body,
                    channel=channel,
                    announcement_id=str(announcement.id),
                )
        
        # Mark as completed
        announcement.status = AnnouncementStatus.COMPLETED
        announcement.completed_at = timezone.now()
        announcement.save(update_fields=["status", "completed_at"])
        
        return {
            "status": "completed",
            "channels": channels,
            "total_members": members.count(),
        }
    
    except Exception as e:
        # Mark as failed
        announcement.status = AnnouncementStatus.FAILED
        announcement.failure_reason = str(e)
        announcement.save(update_fields=["status", "failure_reason"])
        
        # Re-raise so Celery can log/retry if configured
        raise


@shared_task
def dispatch_scheduled_announcements():
    """Release due campaigns once, even if several beat workers overlap."""
    from .models import Announcement, AnnouncementStatus

    with transaction.atomic():
        due_ids = list(
            Announcement.objects.select_for_update(skip_locked=True)
            .filter(status=AnnouncementStatus.SCHEDULED, publish_at__lte=timezone.now())
            .values_list("id", flat=True)[:100]
        )
        if due_ids:
            Announcement.objects.filter(id__in=due_ids, status=AnnouncementStatus.SCHEDULED).update(
                status=AnnouncementStatus.QUEUED
            )
        for announcement_id in due_ids:
            transaction.on_commit(lambda announcement_id=announcement_id: dispatch_announcement.delay(str(announcement_id)))
    return {"dispatched": len(due_ids)}


def get_announcement_delivery_summary(announcement_id):
    """
    Delivery tracking state handler (spec section 13): rolls up every
    apps.notifications.Notification fanned out from this Announcement
    (via Notification.source_announcement, set in dispatch_announcement
    above) into counts per NotificationStatus. Used by
    apps.communications.views to expose delivery state on an Announcement
    without needing a separate rollup table kept in sync by hand.

    Deliberately a plain function, not a Celery task — it's a read, not
    a background job, and callers (a view, a test, another task) want the
    result synchronously.
    """
    from django.db.models import Count

    from apps.notifications.models import Notification, NotificationStatus

    counts = {status: 0 for status, _ in NotificationStatus.choices}
    for row in (
        Notification.objects.filter(source_announcement_id=announcement_id)
        .values("status")
        .annotate(count=Count("id"))
    ):
        counts[row["status"]] = row["count"]

    total = sum(counts.values())
    return {"total": total, "by_status": counts}
