from celery import shared_task
from django.utils import timezone

ABSENCE_THRESHOLD_DAYS = 42  # ~6 weeks; configurable via settings.PASTORAL_ABSENCE_THRESHOLD_DAYS
FOLLOW_UP_CATEGORY = "ATTENDANCE_FOLLOW_UP"


@shared_task
def flag_members_with_prolonged_absence():
    """
    Spec Phase 8: "No attendance for configured period -> Pastoral
    follow-up flag. Keep pastoral data restricted." Runs periodically
    (see config/celery.py beat schedule).

    Restriction is inherited for free: this only ever creates
    apps.pastoral.PastoralCase rows, and every read/write path for that
    model already goes through IsPastoralAuthorized (see
    apps/pastoral/views.py) -- there is no separate, less-restricted read
    path introduced here.

    Idempotent per member: never opens a second OPEN
    ATTENDANCE_FOLLOW_UP case for the same member while one is already
    open, so re-running this daily doesn't spam pastoral staff with
    duplicate cases for the same ongoing absence.
    """
    from django.conf import settings
    from django.db.models import Max, Q

    from apps.members.models import Member, MembershipStatus
    from apps.pastoral.models import PastoralCase, PastoralCaseStatus

    threshold_days = getattr(settings, "PASTORAL_ABSENCE_THRESHOLD_DAYS", ABSENCE_THRESHOLD_DAYS)
    cutoff = timezone.now() - timezone.timedelta(days=threshold_days)

    candidates = (
        Member.objects.filter(membership_status=MembershipStatus.ACTIVE)
        .annotate(last_attended=Max("attendance_records__checked_in_at"))
        .filter(Q(last_attended__lt=cutoff) | Q(last_attended__isnull=True))
    )

    already_flagged_member_ids = set(
        PastoralCase.objects.filter(
            category=FOLLOW_UP_CATEGORY, status__in=[PastoralCaseStatus.OPEN, PastoralCaseStatus.IN_PROGRESS],
        ).values_list("member_id", flat=True)
    )

    flagged = 0
    for member in candidates.exclude(id__in=already_flagged_member_ids).select_related("branch"):
        last_seen = member.last_attended.date().isoformat() if member.last_attended else "never recorded"
        PastoralCase.objects.create(
            branch=member.branch,
            member=member,
            category=FOLLOW_UP_CATEGORY,
            summary=f"No attendance recorded since {last_seen} (threshold: {threshold_days} days). "
                    f"Auto-flagged for pastoral follow-up.",
        )
        flagged += 1

    return {"threshold_days": threshold_days, "cases_created": flagged}


@shared_task
def send_pastoral_follow_up_reminders():
    """
    Phase 13: Send reminders for pastoral cases with follow-up dates due.
    
    Checks cases with next_follow_up_date <= today and sends notification
    to assigned chaplain. Runs daily via Celery beat.
    """
    from apps.pastoral.models import PastoralCase, PastoralCaseStatus
    from apps.pastoral.notifications import notify_follow_up_due
    
    today = timezone.now().date()
    
    # Find cases needing follow-up
    cases_needing_follow_up = PastoralCase.objects.filter(
        next_follow_up_date__lte=today,
        status__in=[
            PastoralCaseStatus.ASSIGNED,
            PastoralCaseStatus.IN_PROGRESS,
            PastoralCaseStatus.FOLLOW_UP,
        ],
        assigned_to__isnull=False
    ).select_related('assigned_to', 'member', 'branch')
    
    reminders_sent = 0
    for case in cases_needing_follow_up:
        try:
            notify_follow_up_due(case)
            reminders_sent += 1
        except Exception as e:
            # Log but don't fail entire task
            import logging
            logger = logging.getLogger("chapelflow.pastoral")
            logger.error(f"Failed to send follow-up reminder for case {case.id}: {e}")
    
    return {
        "date_checked": today.isoformat(),
        "cases_found": cases_needing_follow_up.count(),
        "reminders_sent": reminders_sent
    }


@shared_task
def send_prayer_follow_up_reminders():
    """
    Phase 13: Send reminders for prayer requests needing follow-up.
    
    Checks IN_PROGRESS and FOLLOW_UP status prayer requests and sends
    notification to assigned chaplain. Runs daily via Celery beat.
    """
    from apps.prayer.models import PrayerRequest, PrayerRequestStatus
    from apps.prayer.notifications import notify_prayer_follow_up_due
    
    # Find requests needing follow-up (in progress for >7 days)
    seven_days_ago = timezone.now() - timezone.timedelta(days=7)
    
    requests_needing_follow_up = PrayerRequest.objects.filter(
        status__in=[
            PrayerRequestStatus.IN_PROGRESS,
            PrayerRequestStatus.FOLLOW_UP,
        ],
        assigned_to__isnull=False,
        updated_at__lte=seven_days_ago
    ).select_related('assigned_to', 'member', 'branch')
    
    reminders_sent = 0
    for request in requests_needing_follow_up:
        try:
            notify_prayer_follow_up_due(request)
            reminders_sent += 1
        except Exception as e:
            # Log but don't fail entire task
            import logging
            logger = logging.getLogger("chapelflow.prayer")
            logger.error(f"Failed to send follow-up reminder for prayer request {request.id}: {e}")
    
    return {
        "date_checked": timezone.now().date().isoformat(),
        "requests_found": requests_needing_follow_up.count(),
        "reminders_sent": reminders_sent
    }
