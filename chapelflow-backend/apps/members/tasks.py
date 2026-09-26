import io
import logging

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task
def bulk_import_members_task(file_url, requesting_user_id):
    """
    Background path for large CSV imports. `file_url` points at shared/
    object storage (StorageService), NOT a local path on the web
    container's filesystem — the web process and this worker do not share
    a disk, so a local temp-file path would 404/FileNotFoundError here in
    any multi-container deployment (spec section 20).
    
    Phase 3 Security: Re-validates that requesting_user still has
    members.create permission at task execution time (could be hours/days
    after task was queued if Redis/Celery were down or backlogged).
    """
    import urllib.request

    from django.contrib.auth import get_user_model

    from common.constants.roles import PermissionCodes
    from .services import parse_and_import_members

    User = get_user_model()
    
    try:
        user = User.objects.get(pk=requesting_user_id)
    except User.DoesNotExist:
        logger.error(f"bulk_import_members_task: User {requesting_user_id} not found")
        return {"error": "User not found", "imported": 0, "failed": 0}
    
    # Phase 3: Re-validate permission at execution time
    if not user.has_perm_code(PermissionCodes.MEMBERS_CREATE):
        logger.warning(
            f"bulk_import_members_task: User {user.id} ({user.email}) no longer has "
            f"members.create permission - task aborted"
        )
        summary = {
            "error": "Permission denied - you no longer have members.create permission",
            "imported": 0,
            "failed": 0
        }
        _notify_member_import_result(user, summary, succeeded=False)
        return summary

    try:
        with urllib.request.urlopen(file_url) as response:
            content = response.read()

        summary = parse_and_import_members(io.BytesIO(content), user)
    except Exception:
        logger.exception(
            "bulk_import_members_task: Import failed for requesting user %s",
            user.id,
        )
        _notify_member_import_result(
            user,
            {"created": 0, "updated": 0, "failed": 0},
            succeeded=False,
        )
        raise

    _notify_member_import_result(user, summary, succeeded=True)
    return summary


def _notify_member_import_result(user, summary, *, succeeded):
    from apps.notifications.models import Notification, NotificationChannel
    from apps.notifications.tasks import deliver_notification

    if succeeded:
        created = summary.get("created", 0)
        updated = summary.get("updated", 0)
        failed = summary.get("failed", 0)
        title = "Member import completed"
        body = (
            f"Your member import completed. Created: {created}. "
            f"Updated: {updated}. Failed: {failed}."
        )
    else:
        title = "Member import failed"
        body = (
            "Your member import could not be completed. No additional rows were "
            "processed. Please review your access and file, then try again."
        )

    notification = Notification.objects.create(
        recipient=user,
        title=title,
        body=body,
        channel=NotificationChannel.EMAIL,
    )
    deliver_notification.delay(str(notification.id))



@shared_task
def send_member_follow_up_reminders():
    """
    Phase 11: Send reminders for due member follow-ups.
    
    Periodic task (daily via CELERY_BEAT_SCHEDULE):
    - Finds follow-ups that are due (scheduled_for <= now)
    - Not yet completed (completed_at is NULL)
    - Not yet reminded (reminder_sent_at is NULL)
    - Has assigned staff (assigned_to is not NULL)
    
    Creates notification for each due follow-up.
    
    Idempotency:
    - reminder_sent_at stamped immediately (same transaction as query)
    - select_for_update with skip_locked prevents concurrent processing
    - Mirrors visitor follow-up task for consistency
    
    Returns:
    {
        "reminders_sent": int,
        "timestamp": str
    }
    """
    from django.db import transaction
    from django.utils import timezone
    
    from apps.members.models import MemberFollowUp
    from apps.notifications.models import Notification
    from apps.notifications.tasks import deliver_notification
    
    now = timezone.now()
    
    # Find due follow-ups (with locking for concurrency safety)
    due = MemberFollowUp.objects.select_for_update(skip_locked=True).filter(
        completed_at__isnull=True,
        reminder_sent_at__isnull=True,
        scheduled_for__lte=now,
        assigned_to__isnull=False,
    ).select_related("assigned_to", "member")
    
    sent = 0
    with transaction.atomic():
        for follow_up in due:
            # Mark as reminded (idempotency)
            follow_up.reminder_sent_at = now
            follow_up.save(update_fields=["reminder_sent_at"])
            
            # Create notification
            notification = Notification.objects.create(
                recipient=follow_up.assigned_to,
                title=f"{follow_up.get_milestone_display()} Reminder",
                body=(
                    f"Follow-up with {follow_up.member.full_name} is due. "
                    f"This is their {follow_up.get_milestone_display().lower()}."
                ),
                channel="EMAIL",
            )
            
            # Queue delivery
            deliver_notification.delay(str(notification.id))
            sent += 1
    
    logger.info(f"send_member_follow_up_reminders: sent {sent} reminders")
    return {"reminders_sent": sent, "timestamp": now.isoformat()}


@shared_task
def recalculate_engagement_metrics():
    """
    Phase 11: Recalculate engagement metrics for all active members.
    
    Periodic task (daily via CELERY_BEAT_SCHEDULE):
    - Updates or creates EngagementMetrics for each ACTIVE member
    - Calculates attendance, events, volunteering, giving
    - Computes engagement score (0-100)
    - Updates days_since_last_activity
    
    Performance:
    - Materialized approach (not calculated on-demand)
    - Runs during off-peak hours (configured in beat schedule)
    - Can be optimized with batching if needed
    
    Returns:
    {
        "metrics_updated": int,
        "duration_seconds": float
    }
    """
    import time
    from datetime import timedelta
    
    from django.utils import timezone
    
    from apps.members.models import Member, MembershipStatus, EngagementMetrics
    
    start_time = time.time()
    now = timezone.now()
    cutoff_30d = now - timedelta(days=30)
    cutoff_90d = now - timedelta(days=90)
    
    # Process all active members
    active_members = Member.objects.filter(
        membership_status=MembershipStatus.ACTIVE
    ).select_related('branch')
    
    updated = 0
    for member in active_members:
        # Get or create metrics record
        metrics, created = EngagementMetrics.objects.get_or_create(member=member)
        
        # Calculate attendance metrics
        from apps.attendance.models import AttendanceRecord
        
        services_30d = AttendanceRecord.objects.filter(
            member=member,
            checked_in_at__gte=cutoff_30d
        ).count()
        
        services_90d = AttendanceRecord.objects.filter(
            member=member,
            checked_in_at__gte=cutoff_90d
        ).count()
        
        last_attendance = AttendanceRecord.objects.filter(
            member=member
        ).order_by('-checked_in_at').values_list('checked_in_at', flat=True).first()
        
        # Calculate event participation
        from apps.events.models import EventRegistration
        
        events_30d = EventRegistration.objects.filter(
            member=member,
            created_at__gte=cutoff_30d
        ).count()
        
        events_90d = EventRegistration.objects.filter(
            member=member,
            created_at__gte=cutoff_90d
        ).count()
        
        last_event = EventRegistration.objects.filter(
            member=member
        ).order_by('-created_at').values_list('created_at', flat=True).first()
        
        # Calculate volunteering
        from apps.volunteers.models import VolunteerAssignment, AssignmentStatus
        
        active_assignments = VolunteerAssignment.objects.filter(
            volunteer__member=member,
            status=AssignmentStatus.CONFIRMED
        ).count()
        
        completed_assignments = VolunteerAssignment.objects.filter(
            volunteer__member=member,
            status=AssignmentStatus.COMPLETED
        ).count()
        
        last_volunteer = VolunteerAssignment.objects.filter(
            volunteer__member=member
        ).order_by('-created_at').values_list('created_at', flat=True).first()
        
        # Calculate giving (optional - privacy consideration)
        from apps.finance.models import Giving, GivingStatus
        
        giving_30d = Giving.objects.filter(
            member=member,
            status=GivingStatus.CONFIRMED,
            given_at__gte=cutoff_30d
        ).count()
        
        giving_90d = Giving.objects.filter(
            member=member,
            status=GivingStatus.CONFIRMED,
            given_at__gte=cutoff_90d
        ).count()
        
        last_giving = Giving.objects.filter(
            member=member,
            status=GivingStatus.CONFIRMED
        ).order_by('-given_at').values_list('given_at', flat=True).first()
        
        # Calculate engagement score (weighted)
        score = 0
        score += min(services_30d * 10, 40)      # Max 40 points for attendance
        score += min(events_30d * 5, 20)         # Max 20 points for events
        score += min(active_assignments * 15, 30) # Max 30 points for volunteering
        score += min(giving_30d * 2, 10)         # Max 10 points for giving
        
        # Update metrics
        metrics.services_attended_30d = services_30d
        metrics.services_attended_90d = services_90d
        metrics.last_service_date = last_attendance.date() if last_attendance else None
        metrics.events_attended_30d = events_30d
        metrics.events_attended_90d = events_90d
        metrics.last_event_date = last_event.date() if last_event else None
        metrics.volunteer_assignments_active = active_assignments
        metrics.volunteer_assignments_completed = completed_assignments
        metrics.last_volunteer_date = last_volunteer.date() if last_volunteer else None
        metrics.giving_count_30d = giving_30d
        metrics.giving_count_90d = giving_90d
        metrics.last_giving_date = last_giving.date() if last_giving else None
        metrics.engagement_score = min(score, 100)
        
        # Calculate days since last activity
        last_dates = [
            metrics.last_service_date,
            metrics.last_event_date,
            metrics.last_volunteer_date,
            metrics.last_giving_date,
        ]
        last_dates = [d for d in last_dates if d is not None]
        
        if last_dates:
            most_recent = max(last_dates)
            metrics.days_since_last_activity = (now.date() - most_recent).days
        else:
            metrics.days_since_last_activity = 999  # No recorded activity
        
        metrics.save()
        updated += 1
    
    duration = time.time() - start_time
    logger.info(
        f"recalculate_engagement_metrics: updated {updated} members in {duration:.2f}s"
    )
    
    return {
        "metrics_updated": updated,
        "duration_seconds": round(duration, 2)
    }
