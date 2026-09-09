"""
Phase 9: volunteer assignment reminders. Mirrors the pattern in
apps.events.tasks/apps.notifications.tasks -- a real Notification row is
created and handed to apps.notifications.tasks.deliver_notification, so
delivery state (SENT/STUBBED/FAILED/DELIVERED) is tracked the same way as
every other notification in the system. Never fakes delivery.

Security & Idempotency:
- Checks reminder_sent_at to prevent duplicate reminders
- Uses select_for_update() to prevent race conditions
- Only sends reminders for CONFIRMED assignments
- Respects user existence (no notification if no user account)
- Integrates with Phase 10 CommunicationPreferences

Phase 10 Integration:
- Checks member.communication_preference before sending
- Respects email_enabled flag
- Respects announcements_enabled flag (volunteer reminders are system announcements)
- Members without preferences are treated as opted-in (default=True model)
"""
from datetime import timedelta

from celery import shared_task
from django.db import transaction
from django.utils import timezone

from .models import AssignmentStatus, VolunteerAssignment


@shared_task
def send_assignment_reminder(assignment_id):
    """
    Send a single assignment reminder via the Phase 10 notification system.
    
    Idempotency: Uses select_for_update() and reminder_sent_at check to prevent
    duplicate reminders even under concurrent task execution.
    
    Security:
    - Only sends for CONFIRMED assignments
    - Checks reminder_sent_at atomically to prevent duplicates
    - Validates user exists before creating notification
    
    Phase 10 Integration: Checks communication preferences before sending.
    """
    from apps.notifications.models import Notification, NotificationChannel
    from apps.notifications.tasks import deliver_notification

    # Atomic idempotency check using select_for_update
    with transaction.atomic():
        assignment = (
            VolunteerAssignment.objects
            .select_for_update()
            .select_related("volunteer__member__user", "event_schedule__event")
            .filter(
                id=assignment_id, 
                status=AssignmentStatus.CONFIRMED,
                reminder_sent_at__isnull=True,  # Only if not already reminded
            )
            .first()
        )
        
        # Early exit if assignment doesn't meet criteria or already reminded
        if assignment is None:
            return
        
        user = assignment.volunteer.member.user
        if not user:
            # No user account = cannot send notification
            # Still mark reminder_sent_at to prevent retry loops
            assignment.reminder_sent_at = timezone.now()
            assignment.save(update_fields=["reminder_sent_at"])
            return
        
        # Phase 10 Integration: Check communication preferences
        member = assignment.volunteer.member
        if hasattr(member, 'communication_preference'):
            prefs = member.communication_preference
            # Check if member has disabled email OR disabled announcements
            if not prefs.email_enabled or not prefs.announcements_enabled:
                # User opted out, mark as sent to prevent retry
                assignment.reminder_sent_at = timezone.now()
                assignment.save(update_fields=["reminder_sent_at"])
                return
        # No preference record = default opted-in (model default=True)
        
        # Build notification content
        schedule = assignment.event_schedule
        title = "Volunteer reminder"
        
        if schedule:
            when = schedule.occurrence_start.strftime("%a %b %d, %I:%M %p")
            event_name = schedule.event.title if schedule.event else "your assignment"
            body = f"Reminder: you're serving as {assignment.get_role_display()} at {event_name} on {when}."
        else:
            body = f"Reminder: you're serving as {assignment.get_role_display()} for your scheduled assignment."
        
        # Create notification (Phase 10 system handles delivery)
        notification = Notification.objects.create(
            recipient=user, 
            recipient_member=assignment.volunteer.member,
            channel=NotificationChannel.EMAIL,
            title=title, 
            body=body,
        )
        
        # Queue delivery via Phase 10 task
        deliver_notification.delay(str(notification.id))
        
        # Mark reminder as sent (atomically within transaction)
        assignment.reminder_sent_at = timezone.now()
        assignment.save(update_fields=["reminder_sent_at"])


@shared_task
def remind_upcoming_volunteer_assignments(hours_ahead=24):
    """
    Periodic sweep (wire into CELERY_BEAT_SCHEDULE): finds CONFIRMED
    assignments whose occurrence starts within the next `hours_ahead`
    hours and haven't been reminded yet, and fans out one
    send_assignment_reminder per assignment.
    
    Idempotency: 
    - reminder_sent_at is checked both here and inside send_assignment_reminder
    - If a reminder task runs twice, the inner select_for_update() prevents duplicates
    
    Security:
    - Only processes CONFIRMED assignments (not PENDING/DECLINED/CANCELLED/COMPLETED)
    - Only processes assignments with upcoming occurrences
    - Respects organizational scope implicitly (all assignments already scoped)
    
    Returns: Count of reminder tasks queued
    """
    now = timezone.now()
    window_end = now + timedelta(hours=hours_ahead)
    
    due = VolunteerAssignment.objects.filter(
        status=AssignmentStatus.CONFIRMED,
        reminder_sent_at__isnull=True,
        event_schedule__occurrence_start__gte=now,
        event_schedule__occurrence_start__lte=window_end,
    ).values_list("id", flat=True)
    
    count = 0
    for assignment_id in due:
        send_assignment_reminder.delay(str(assignment_id))
        count += 1
    
    return count
