"""
Phase 11: Attendance-related Celery tasks.
"""
import logging

from celery import shared_task
from django.conf import settings

logger = logging.getLogger(__name__)


@shared_task
def flag_absent_members():
    """
    Phase 11: Weekly task to detect members with repeated absence.
    
    Runs weekly (configured in CELERY_BEAT_SCHEDULE):
    - Finds ACTIVE members who haven't attended in threshold weeks
    - Creates pastoral follow-up case for each
    - Respects branch boundaries
    
    Configuration:
    - ABSENCE_THRESHOLD_WEEKS (default: 3)
    
    Returns:
    {
        "absent_members_flagged": int,
        "cases_created": int,
        "cases_skipped": int (already have open case)
    }
    """
    from apps.members.models import Member, MembershipStatus
    from .services import detect_repeated_absence, create_attendance_follow_up
    
    # Get configuration
    threshold_weeks = getattr(settings, 'ABSENCE_THRESHOLD_WEEKS', 3)
    
    # Find all active members
    active_members = Member.objects.filter(
        membership_status=MembershipStatus.ACTIVE
    ).select_related('branch', 'fellowship')
    
    absent_count = 0
    cases_created = 0
    cases_skipped = 0
    
    for member in active_members:
        # Check if member has repeated absence
        if detect_repeated_absence(member, threshold_weeks=threshold_weeks):
            absent_count += 1
            
            # Create follow-up case
            case = create_attendance_follow_up(member)
            
            if case:
                cases_created += 1
            else:
                cases_skipped += 1
    
    logger.info(
        f"flag_absent_members: flagged {absent_count} absent members, "
        f"created {cases_created} cases, skipped {cases_skipped} (already have open case)"
    )
    
    return {
        "absent_members_flagged": absent_count,
        "cases_created": cases_created,
        "cases_skipped": cases_skipped
    }
