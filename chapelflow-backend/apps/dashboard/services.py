"""
Phase 16: Dashboard analytics services.

Architecture:
    View → Service → Analytics Query → Database

This service layer provides reusable analytics functions that can be used by:
- Dashboard views
- Report generators
- API endpoints
- Export functions

All analytics respect organization/branch scoping and RBAC.
"""
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Optional, Tuple

from django.db.models import (
    Avg,
    Count,
    F,
    Max,
    Min,
    Q,
    Sum,
)
from django.db.models.functions import TruncDate, TruncMonth, TruncWeek
from django.utils import timezone


def get_scoped_queryset(model, user, branch_field="branch"):
    """
    Get branch-scoped or org-wide queryset based on user role.
    
    Rules:
    - SUPER_ADMIN: sees all data across all organizations
    - CHAPLAIN: sees all data in their organization (all branches)
    - Branch-level users: see only their branch data
    - Users without branch: see nothing
    
    Args:
        model: Django model class
        user: User instance
        branch_field: Name of the branch FK field (default: "branch")
    
    Returns:
        Scoped queryset
    """
    from common.constants.roles import Roles
    
    if user.role in Roles.GLOBAL_SCOPE_ROLES:
        # Super admin sees everything
        return model.objects.all()
    
    if user.role in Roles.ORG_WIDE_SCOPE_ROLES:
        # Chaplain sees all branches in their organization
        if user.branch_id:
            # Get organization from user's branch
            org_id = user.branch.organization_id
            return model.objects.filter(**{f"{branch_field}__organization_id": org_id})
        return model.objects.none()
    
    # Branch-level users see only their branch
    if not user.branch_id:
        return model.objects.none()
    
    return model.objects.filter(**{f"{branch_field}_id": user.branch_id})


def get_date_range_filter(
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    default_days: int = 30,
    max_days: int = 365,
) -> Tuple[date, date]:
    """
    Validate and normalize date range for analytics queries.
    
    Args:
        start_date: Start date (optional)
        end_date: End date (optional)
        default_days: Default range if no dates provided
        max_days: Maximum allowed range
    
    Returns:
        (start_date, end_date) tuple
    
    Raises:
        ValueError: If date range is invalid
    """
    today = timezone.now().date()
    
    # Set defaults
    if not end_date:
        end_date = today
    if not start_date:
        start_date = end_date - timedelta(days=default_days)
    
    # Validate
    if start_date > end_date:
        raise ValueError("start_date must be <= end_date")
    
    if (end_date - start_date).days > max_days:
        raise ValueError(f"Date range cannot exceed {max_days} days")
    
    return start_date, end_date


def calculate_percentage_change(current: float, previous: float) -> Optional[float]:
    """
    Calculate percentage change with zero-denominator handling.
    
    Args:
        current: Current period value
        previous: Previous period value
    
    Returns:
        Percentage change or None if previous is zero
    
    Examples:
        calculate_percentage_change(150, 120) -> 25.0
        calculate_percentage_change(100, 200) -> -50.0
        calculate_percentage_change(50, 0) -> None
    """
    if previous == 0:
        return None
    
    return ((current - previous) / previous) * 100


def get_period_comparison(
    current_value: float,
    previous_value: float,
) -> Dict:
    """
    Generate comparison analytics between two periods.
    
    Args:
        current_value: Current period value
        previous_value: Previous period value
    
    Returns:
        Dict with current, previous, change, percentage_change
    """
    change = current_value - previous_value
    percentage_change = calculate_percentage_change(current_value, previous_value)
    
    return {
        "current": current_value,
        "previous": previous_value,
        "change": change,
        "percentage_change": percentage_change,
    }


def aggregate_by_time_period(
    queryset,
    date_field: str,
    start_date: date,
    end_date: date,
    period: str = "day",
    count_field: str = "id",
) -> List[Dict]:
    """
    Aggregate queryset by time period (day/week/month).
    
    Args:
        queryset: Django queryset to aggregate
        date_field: Name of the date/datetime field to group by
        start_date: Start date for filtering
        end_date: End date for filtering
        period: "day", "week", or "month"
        count_field: Field to count (default: "id")
    
    Returns:
        List of dicts with period and count
    
    Example:
        [
            {"period": "2026-09-01", "count": 150},
            {"period": "2026-09-02", "count": 142},
            ...
        ]
    """
    # Filter by date range
    filter_kwargs = {
        f"{date_field}__gte": start_date,
        f"{date_field}__lte": end_date,
    }
    qs = queryset.filter(**filter_kwargs)
    
    # Choose truncation function
    if period == "day":
        trunc_func = TruncDate
        period_label = "period"
    elif period == "week":
        trunc_func = TruncWeek
        period_label = "period"
    elif period == "month":
        trunc_func = TruncMonth
        period_label = "period"
    else:
        raise ValueError(f"Invalid period: {period}. Must be 'day', 'week', or 'month'")
    
    # Aggregate
    results = (
        qs.annotate(period=trunc_func(date_field))
        .values("period")
        .annotate(count=Count(count_field))
        .order_by("period")
    )
    
    # Convert to list and format dates
    return [
        {
            "period": result["period"].isoformat() if result["period"] else None,
            "count": result["count"],
        }
        for result in results
    ]


# =============================================================================
# MEMBER ANALYTICS
# =============================================================================

def get_member_counts(user) -> Dict:
    """
    Get basic member counts with branch scoping.
    
    Returns:
        {
            "total_members": int,
            "active_members": int,
            "inactive_members": int,
            "pending_members": int,
            "transferred_members": int,
            "deceased_members": int,
        }
    """
    from apps.members.models import Member, MembershipStatus
    
    qs = get_scoped_queryset(Member, user)
    
    total = qs.count()
    active = qs.filter(membership_status=MembershipStatus.ACTIVE).count()
    inactive = qs.filter(membership_status=MembershipStatus.INACTIVE).count()
    pending = qs.filter(membership_status=MembershipStatus.PENDING).count()
    transferred = qs.filter(membership_status=MembershipStatus.TRANSFERRED).count()
    deceased = qs.filter(membership_status=MembershipStatus.DECEASED).count()
    
    return {
        "total_members": total,
        "active_members": active,
        "inactive_members": inactive,
        "pending_members": pending,
        "transferred_members": transferred,
        "deceased_members": deceased,
    }


def get_member_status_breakdown(user) -> List[Dict]:
    """
    Get member count by membership status.
    
    Returns:
        [
            {"membership_status": "ACTIVE", "count": 150},
            {"membership_status": "INACTIVE", "count": 20},
            ...
        ]
    """
    from apps.members.models import Member
    
    qs = get_scoped_queryset(Member, user)
    
    return list(
        qs.values("membership_status")
        .annotate(count=Count("id"))
        .order_by("-count")
    )


def get_member_growth(
    user,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    period: str = "month",
) -> List[Dict]:
    """
    Get member growth over time (time-series).
    
    Args:
        user: User instance for scoping
        start_date: Start date (default: 1 year ago)
        end_date: End date (default: today)
        period: "day", "week", or "month"
    
    Returns:
        [
            {"period": "2026-01-01", "count": 1200},
            {"period": "2026-02-01", "count": 1235},
            ...
        ]
    """
    from apps.members.models import Member
    
    # Default to last year for growth trends
    start_date, end_date = get_date_range_filter(
        start_date, end_date, default_days=365, max_days=730
    )
    
    qs = get_scoped_queryset(Member, user)
    
    return aggregate_by_time_period(
        qs, "created_at", start_date, end_date, period=period
    )


def get_new_members_count(
    user,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
) -> int:
    """
    Get count of new members within date range.
    
    Args:
        user: User instance for scoping
        start_date: Start date (default: 30 days ago)
        end_date: End date (default: today)
    
    Returns:
        Count of new members
    """
    from apps.members.models import Member
    
    start_date, end_date = get_date_range_filter(start_date, end_date)
    
    qs = get_scoped_queryset(Member, user)
    
    return qs.filter(
        created_at__date__gte=start_date,
        created_at__date__lte=end_date,
    ).count()


def get_member_demographics(user) -> Dict:
    """
    Get member demographic breakdowns.
    
    Returns:
        {
            "by_gender": [{"gender": "MALE", "count": 100}, ...],
            "by_fellowship": [{"fellowship__name": "Fellowship A", "count": 50}, ...],
            "by_college": [{"college__name": "Engineering", "count": 30}, ...],
            "by_department": [{"department__name": "Computer Science", "count": 20}, ...],
            "by_community": [{"community": "STUDENT", "count": 150}, ...],
        }
    """
    from apps.members.models import Member
    
    qs = get_scoped_queryset(Member, user)
    
    # Gender distribution
    by_gender = list(
        qs.exclude(gender="")
        .values("gender")
        .annotate(count=Count("id"))
        .order_by("-count")
    )
    
    # Fellowship distribution
    by_fellowship = list(
        qs.filter(fellowship__isnull=False)
        .values("fellowship__name")
        .annotate(count=Count("id"))
        .order_by("-count")
    )
    
    # College distribution (University Edition)
    by_college = list(
        qs.filter(college__isnull=False)
        .values("college__name")
        .annotate(count=Count("id"))
        .order_by("-count")
    )
    
    # Department distribution (University Edition)
    by_department = list(
        qs.filter(department__isnull=False)
        .values("department__name")
        .annotate(count=Count("id"))
        .order_by("-count")
    )
    
    # Community classification
    by_community = list(
        qs.exclude(community="")
        .values("community")
        .annotate(count=Count("id"))
        .order_by("-count")
    )
    
    return {
        "by_gender": by_gender,
        "by_fellowship": by_fellowship,
        "by_college": by_college,
        "by_department": by_department,
        "by_community": by_community,
    }


def get_member_age_distribution(user) -> List[Dict]:
    """
    Get member age group distribution.
    
    Returns:
        [
            {"age_group": "0-17", "count": 20},
            {"age_group": "18-25", "count": 150},
            {"age_group": "26-35", "count": 100},
            {"age_group": "36-50", "count": 80},
            {"age_group": "51+", "count": 50},
        ]
    """
    from apps.members.models import Member
    
    qs = get_scoped_queryset(Member, user).filter(date_of_birth__isnull=False)
    
    today = timezone.now().date()
    age_groups = {
        "0-17": 0,
        "18-25": 0,
        "26-35": 0,
        "36-50": 0,
        "51+": 0,
    }
    
    # Calculate ages - this is acceptable for small datasets
    # For very large datasets, consider database-level calculation
    for member in qs.only("date_of_birth"):
        age = (today - member.date_of_birth).days // 365
        
        if age < 18:
            age_groups["0-17"] += 1
        elif age < 26:
            age_groups["18-25"] += 1
        elif age < 36:
            age_groups["26-35"] += 1
        elif age < 51:
            age_groups["36-50"] += 1
        else:
            age_groups["51+"] += 1
    
    return [
        {"age_group": group, "count": count}
        for group, count in age_groups.items()
    ]


def get_member_follow_up_stats(user) -> Dict:
    """
    Get member follow-up statistics (Phase 11 integration).
    
    Returns:
        {
            "total_follow_ups": int,
            "pending_follow_ups": int,
            "completed_follow_ups": int,
            "overdue_follow_ups": int,
        }
    """
    from apps.members.models import MemberFollowUp
    
    # Member follow-ups are scoped via member.branch
    qs = get_scoped_queryset(MemberFollowUp, user, branch_field="member__branch")
    
    now = timezone.now()
    
    total = qs.count()
    completed = qs.filter(completed_at__isnull=False).count()
    pending = qs.filter(completed_at__isnull=True).count()
    overdue = qs.filter(
        completed_at__isnull=True,
        scheduled_for__lt=now,
    ).count()
    
    return {
        "total_follow_ups": total,
        "pending_follow_ups": pending,
        "completed_follow_ups": completed,
        "overdue_follow_ups": overdue,
    }


# =============================================================================
# ATTENDANCE ANALYTICS
# =============================================================================

def get_attendance_counts(
    user,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
) -> Dict:
    """
    Get attendance counts for date range.
    
    Returns:
        {
            "total_attendance": int,
            "unique_attendees": int,
            "average_attendance": float,
            "member_attendance": int,
            "visitor_attendance": int,
        }
    """
    from apps.attendance.models import AttendanceRecord, AttendanceSession
    
    start_date, end_date = get_date_range_filter(start_date, end_date)
    
    # Scope by session.branch
    session_qs = get_scoped_queryset(AttendanceSession, user)
    session_ids = session_qs.values_list("id", flat=True)
    
    # Get attendance records for scoped sessions
    qs = AttendanceRecord.objects.filter(
        session_id__in=session_ids,
        checked_in_at__date__gte=start_date,
        checked_in_at__date__lte=end_date,
    )
    
    total = qs.count()
    unique = qs.filter(member__isnull=False).values("member").distinct().count()
    member_count = qs.filter(member__isnull=False).count()
    visitor_count = qs.filter(member__isnull=True, visitor__isnull=False).count()
    
    # Calculate average per session
    sessions_count = session_qs.filter(
        opened_at__date__gte=start_date,
        opened_at__date__lte=end_date,
    ).count()
    
    average = total / sessions_count if sessions_count > 0 else 0
    
    return {
        "total_attendance": total,
        "unique_attendees": unique,
        "average_attendance": round(average, 2),
        "member_attendance": member_count,
        "visitor_attendance": visitor_count,
    }


def get_attendance_rate(user) -> Optional[float]:
    """
    Calculate attendance rate (unique attendees / active members).
    
    Returns:
        Attendance rate percentage or None if no active members
    """
    from apps.members.models import Member, MembershipStatus
    
    member_qs = get_scoped_queryset(Member, user)
    active_members = member_qs.filter(membership_status=MembershipStatus.ACTIVE).count()
    
    if active_members == 0:
        return None
    
    # Get attendance for last 30 days
    thirty_days_ago = timezone.now().date() - timedelta(days=30)
    attendance_data = get_attendance_counts(user, start_date=thirty_days_ago)
    
    unique_attendees = attendance_data["unique_attendees"]
    
    return round((unique_attendees / active_members) * 100, 2)


def get_attendance_trend(
    user,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    period: str = "week",
) -> List[Dict]:
    """
    Get attendance trend over time.
    
    Returns:
        [
            {"period": "2026-09-01", "count": 250},
            {"period": "2026-09-08", "count": 275},
            ...
        ]
    """
    from apps.attendance.models import AttendanceRecord, AttendanceSession
    
    start_date, end_date = get_date_range_filter(
        start_date, end_date, default_days=90
    )
    
    # Scope by session.branch
    session_qs = get_scoped_queryset(AttendanceSession, user)
    session_ids = session_qs.values_list("id", flat=True)
    
    # Get attendance records for scoped sessions
    qs = AttendanceRecord.objects.filter(session_id__in=session_ids)
    
    return aggregate_by_time_period(
        qs, "checked_in_at", start_date, end_date, period=period
    )


def get_attendance_by_method(
    user,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
) -> List[Dict]:
    """
    Get attendance breakdown by check-in method.
    
    Returns:
        [
            {"method": "QR_CODE", "count": 200},
            {"method": "MANUAL", "count": 50},
            ...
        ]
    """
    from apps.attendance.models import AttendanceRecord, AttendanceSession
    
    start_date, end_date = get_date_range_filter(start_date, end_date)
    
    # Scope by session.branch
    session_qs = get_scoped_queryset(AttendanceSession, user)
    session_ids = session_qs.values_list("id", flat=True)
    
    # Get attendance records for scoped sessions
    qs = AttendanceRecord.objects.filter(
        session_id__in=session_ids,
        checked_in_at__date__gte=start_date,
        checked_in_at__date__lte=end_date,
    )
    
    return list(
        qs.values("method")
        .annotate(count=Count("id"))
        .order_by("-count")
    )


def get_attendance_by_status(
    user,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
) -> List[Dict]:
    """
    Get attendance breakdown by status (PRESENT, LATE, ABSENT, EXCUSED).
    
    Returns:
        [
            {"status": "PRESENT", "count": 200},
            {"status": "LATE", "count": 30},
            ...
        ]
    """
    from apps.attendance.models import AttendanceRecord, AttendanceSession
    
    start_date, end_date = get_date_range_filter(start_date, end_date)
    
    # Scope by session.branch
    session_qs = get_scoped_queryset(AttendanceSession, user)
    session_ids = session_qs.values_list("id", flat=True)
    
    # Get attendance records for scoped sessions
    qs = AttendanceRecord.objects.filter(
        session_id__in=session_ids,
        checked_in_at__date__gte=start_date,
        checked_in_at__date__lte=end_date,
    )
    
    return list(
        qs.values("status")
        .annotate(count=Count("id"))
        .order_by("-count")
    )


# =============================================================================
# VISITOR ANALYTICS
# =============================================================================

def get_visitor_counts(
    user,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
) -> Dict:
    """
    Get visitor counts for date range.
    
    Returns:
        {
            "total_visitors": int,
            "new_visitors": int,
            "returning_visitors": int,
            "converted_visitors": int,
        }
    """
    from apps.visitors.models import Visitor, VisitorStatus
    
    start_date, end_date = get_date_range_filter(start_date, end_date)
    
    qs = get_scoped_queryset(Visitor, user)
    
    total = qs.count()
    new = qs.filter(
        created_at__date__gte=start_date,
        created_at__date__lte=end_date,
    ).count()
    
    # Returning visitors: have attendance records beyond first visit
    from apps.attendance.models import VisitorAttendance
    returning = qs.filter(
        attendance_records__checked_in_at__date__gte=start_date,
        attendance_records__checked_in_at__date__lte=end_date,
    ).annotate(
        visit_count=Count("attendance_records")
    ).filter(visit_count__gt=1).count()
    
    converted = qs.filter(
        status=VisitorStatus.REGISTERED,
        converted_at__date__gte=start_date,
        converted_at__date__lte=end_date,
    ).count()
    
    return {
        "total_visitors": total,
        "new_visitors": new,
        "returning_visitors": returning,
        "converted_visitors": converted,
    }


def get_visitor_conversion_rate(user) -> Optional[float]:
    """
    Calculate visitor-to-member conversion rate.
    
    Returns:
        Conversion rate percentage or None if no visitors
    """
    from apps.visitors.models import Visitor, VisitorStatus
    
    qs = get_scoped_queryset(Visitor, user)
    
    total = qs.count()
    if total == 0:
        return None
    
    converted = qs.filter(status=VisitorStatus.REGISTERED).count()
    
    return round((converted / total) * 100, 2)


def get_visitor_follow_up_stats(user) -> Dict:
    """
    Get visitor follow-up statistics.
    
    Returns:
        {
            "total_follow_ups": int,
            "pending_follow_ups": int,
            "completed_follow_ups": int,
            "overdue_follow_ups": int,
        }
    """
    from apps.visitors.models import VisitorFollowUp
    
    # Visitor follow-ups are scoped via visitor.branch
    qs = get_scoped_queryset(VisitorFollowUp, user, branch_field="visitor__branch")
    
    now = timezone.now()
    
    total = qs.count()
    completed = qs.filter(completed_at__isnull=False).count()
    pending = qs.filter(completed_at__isnull=True).count()
    overdue = qs.filter(
        completed_at__isnull=True,
        scheduled_for__isnull=False,
        scheduled_for__lt=now,
    ).count()
    
    return {
        "total_follow_ups": total,
        "pending_follow_ups": pending,
        "completed_follow_ups": completed,
        "overdue_follow_ups": overdue,
    }


def get_visitor_status_breakdown(user) -> List[Dict]:
    """
    Get visitor count by status.
    
    Returns:
        [
            {"status": "NEW", "count": 20},
            {"status": "CONTACTED", "count": 15},
            ...
        ]
    """
    from apps.visitors.models import Visitor
    
    qs = get_scoped_queryset(Visitor, user)
    
    return list(
        qs.values("status")
        .annotate(count=Count("id"))
        .order_by("-count")
    )


def get_visitor_source_breakdown(user) -> List[Dict]:
    """
    Get visitor count by source (how_heard).
    
    Returns:
        [
            {"how_heard": "Friend", "count": 50},
            {"how_heard": "Social Media", "count": 30},
            ...
        ]
    """
    from apps.visitors.models import Visitor
    
    qs = get_scoped_queryset(Visitor, user)
    
    return list(
        qs.exclude(how_heard="")
        .values("how_heard")
        .annotate(count=Count("id"))
        .order_by("-count")
    )


def get_visitor_trend(
    user,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    period: str = "month",
) -> List[Dict]:
    """
    Get visitor growth trend over time.
    
    Returns:
        [
            {"period": "2026-01-01", "count": 15},
            {"period": "2026-02-01", "count": 20},
            ...
        ]
    """
    from apps.visitors.models import Visitor
    
    start_date, end_date = get_date_range_filter(
        start_date, end_date, default_days=180
    )
    
    qs = get_scoped_queryset(Visitor, user)
    
    return aggregate_by_time_period(
        qs, "created_at", start_date, end_date, period=period
    )



# =============================================================================
# EVENT ANALYTICS
# =============================================================================

def get_event_counts(
    user,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
) -> Dict:
    """
    Get event counts for date range.
    
    Returns:
        {
            "total_events": int,
            "upcoming_events": int,
            "completed_events": int,
            "cancelled_events": int,
        }
    """
    from apps.events.models import Event
    
    qs = get_scoped_queryset(Event, user)
    
    now = timezone.now()
    
    total = qs.count()
    
    # Upcoming events (have schedules in the future)
    upcoming = qs.filter(schedules__start_time__gte=now).distinct().count()
    
    # Completed events (all schedules in the past)
    completed = qs.filter(
        schedules__end_time__lt=now
    ).exclude(
        schedules__start_time__gte=now
    ).distinct().count()
    
    # Cancelled events (if status field exists)
    cancelled = qs.filter(is_cancelled=True).count() if hasattr(Event, 'is_cancelled') else 0
    
    return {
        "total_events": total,
        "upcoming_events": upcoming,
        "completed_events": completed,
        "cancelled_events": cancelled,
    }


def get_event_type_breakdown(user) -> List[Dict]:
    """
    Get event count by type.
    
    Returns:
        [
            {"event_type": "SERVICE", "count": 50},
            {"event_type": "FELLOWSHIP", "count": 20},
            ...
        ]
    """
    from apps.events.models import Event
    
    qs = get_scoped_queryset(Event, user)
    
    return list(
        qs.values("event_type")
        .annotate(count=Count("id"))
        .order_by("-count")
    )


def get_event_category_breakdown(user) -> List[Dict]:
    """
    Get event count by category.
    
    Returns:
        [
            {"category__name": "Worship", "count": 40},
            {"category__name": "Outreach", "count": 15},
            ...
        ]
    """
    from apps.events.models import Event
    
    qs = get_scoped_queryset(Event, user)
    
    return list(
        qs.filter(category__isnull=False)
        .values("category__name")
        .annotate(count=Count("id"))
        .order_by("-count")
    )


def get_event_attendance_stats(user) -> Dict:
    """
    Get event attendance statistics.
    
    Returns:
        {
            "total_registrations": int,
            "average_attendance_per_event": float,
        }
    """
    from apps.events.models import EventRegistration
    from apps.attendance.models import AttendanceSession
    
    # Event registrations scoped by registration.schedule.event.branch
    reg_qs = get_scoped_queryset(
        EventRegistration, user, branch_field="schedule__event__branch"
    )
    total_registrations = reg_qs.count()
    
    # Attendance per event via sessions
    session_qs = get_scoped_queryset(AttendanceSession, user)
    sessions_with_attendance = session_qs.filter(
        event_schedule__isnull=False,
        records__isnull=False
    ).annotate(
        attendance_count=Count("records")
    )
    
    if sessions_with_attendance.exists():
        avg_attendance = sessions_with_attendance.aggregate(
            avg=Avg("attendance_count")
        )["avg"] or 0
    else:
        avg_attendance = 0
    
    return {
        "total_registrations": total_registrations,
        "average_attendance_per_event": round(avg_attendance, 2),
    }


# =============================================================================
# GROUP/MINISTRY ANALYTICS
# =============================================================================

def get_group_counts(user) -> Dict:
    """
    Get group/ministry/fellowship counts.
    
    Returns:
        {
            "total_groups": int,
            "active_groups": int,
            "inactive_groups": int,
            "fellowship_count": int,
            "ministry_count": int,
            "unit_count": int,
        }
    """
    from apps.groups.models import Group, GroupType
    
    qs = get_scoped_queryset(Group, user)
    
    total = qs.count()
    active = qs.filter(is_active=True).count()
    inactive = qs.filter(is_active=False).count()
    
    fellowship_count = qs.filter(group_type=GroupType.FELLOWSHIP).count()
    ministry_count = qs.filter(group_type=GroupType.MINISTRY).count()
    unit_count = qs.filter(group_type=GroupType.UNIT).count()
    
    return {
        "total_groups": total,
        "active_groups": active,
        "inactive_groups": inactive,
        "fellowship_count": fellowship_count,
        "ministry_count": ministry_count,
        "unit_count": unit_count,
    }


def get_group_type_breakdown(user) -> List[Dict]:
    """
    Get group count by type.
    
    Returns:
        [
            {"group_type": "FELLOWSHIP", "count": 20},
            {"group_type": "MINISTRY", "count": 15},
            ...
        ]
    """
    from apps.groups.models import Group
    
    qs = get_scoped_queryset(Group, user)
    
    return list(
        qs.values("group_type")
        .annotate(count=Count("id"))
        .order_by("-count")
    )


def get_group_participation_stats(user) -> Dict:
    """
    Get group participation statistics.
    
    Returns:
        {
            "total_memberships": int,
            "active_memberships": int,
            "average_group_size": float,
        }
    """
    from apps.groups.models import Group, GroupMembership
    
    group_qs = get_scoped_queryset(Group, user)
    membership_qs = get_scoped_queryset(GroupMembership, user, branch_field="group__branch")
    
    total_memberships = membership_qs.count()
    active_memberships = membership_qs.filter(is_active=True).count()
    
    # Calculate average group size
    groups_with_members = group_qs.filter(is_active=True).annotate(
        member_count=Count("memberships", filter=Q(memberships__is_active=True))
    )
    
    if groups_with_members.exists():
        avg_size = groups_with_members.aggregate(avg=Avg("member_count"))["avg"] or 0
    else:
        avg_size = 0
    
    return {
        "total_memberships": total_memberships,
        "active_memberships": active_memberships,
        "average_group_size": round(avg_size, 2),
    }


# =============================================================================
# VOLUNTEER ANALYTICS
# =============================================================================

def get_volunteer_counts(user) -> Dict:
    """
    Get volunteer counts.
    
    Returns:
        {
            "total_volunteers": int,
            "active_volunteers": int,
            "total_assignments": int,
            "confirmed_assignments": int,
            "completed_assignments": int,
        }
    """
    from apps.volunteers.models import Volunteer, VolunteerAssignment
    
    volunteer_qs = get_scoped_queryset(Volunteer, user)
    assignment_qs = get_scoped_queryset(VolunteerAssignment, user)
    
    total_volunteers = volunteer_qs.count()
    active_volunteers = volunteer_qs.filter(is_active=True).count()
    
    total_assignments = assignment_qs.count()
    confirmed = assignment_qs.filter(status="CONFIRMED").count()
    completed = assignment_qs.filter(status="COMPLETED").count()
    
    return {
        "total_volunteers": total_volunteers,
        "active_volunteers": active_volunteers,
        "total_assignments": total_assignments,
        "confirmed_assignments": confirmed,
        "completed_assignments": completed,
    }


def get_volunteer_participation_rate(user) -> Optional[float]:
    """
    Calculate volunteer participation rate (volunteers / active members).
    
    Returns:
        Participation rate percentage or None if no active members
    """
    from apps.members.models import Member, MembershipStatus
    from apps.volunteers.models import Volunteer
    
    member_qs = get_scoped_queryset(Member, user)
    active_members = member_qs.filter(membership_status=MembershipStatus.ACTIVE).count()
    
    if active_members == 0:
        return None
    
    volunteer_qs = get_scoped_queryset(Volunteer, user)
    active_volunteers = volunteer_qs.filter(is_active=True).count()
    
    return round((active_volunteers / active_members) * 100, 2)


def get_volunteer_trend(
    user,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    period: str = "month",
) -> List[Dict]:
    """
    Get volunteer assignment trend over time.
    
    Returns:
        [
            {"period": "2026-01-01", "count": 50},
            {"period": "2026-02-01", "count": 55},
            ...
        ]
    """
    from apps.volunteers.models import VolunteerAssignment
    
    start_date, end_date = get_date_range_filter(
        start_date, end_date, default_days=180
    )
    
    qs = get_scoped_queryset(VolunteerAssignment, user)
    
    return aggregate_by_time_period(
        qs, "created_at", start_date, end_date, period=period
    )


# =============================================================================
# COMMUNICATION ANALYTICS
# =============================================================================

def get_communication_counts(
    user,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
) -> Dict:
    """
    Get communication/announcement counts.
    
    Returns:
        {
            "total_announcements": int,
            "total_notifications": int,
            "sent_count": int,
            "failed_count": int,
        }
    """
    from apps.communications.models import Announcement
    from apps.notifications.models import Notification
    
    start_date, end_date = get_date_range_filter(start_date, end_date)
    
    announcement_qs = get_scoped_queryset(Announcement, user)
    announcements = announcement_qs.filter(
        created_at__date__gte=start_date,
        created_at__date__lte=end_date,
    ).count()
    
    # Notifications scoped by announcement.branch
    notification_qs = get_scoped_queryset(
        Notification, user, branch_field="announcement__branch"
    )
    notifications = notification_qs.filter(
        created_at__date__gte=start_date,
        created_at__date__lte=end_date,
    ).count()
    
    sent = notification_qs.filter(
        created_at__date__gte=start_date,
        created_at__date__lte=end_date,
        status="SENT",
    ).count()
    
    failed = notification_qs.filter(
        created_at__date__gte=start_date,
        created_at__date__lte=end_date,
        status="FAILED",
    ).count()
    
    return {
        "total_announcements": announcements,
        "total_notifications": notifications,
        "sent_count": sent,
        "failed_count": failed,
    }


def get_communication_delivery_rate(user) -> Optional[float]:
    """
    Calculate notification delivery success rate.
    
    Returns:
        Delivery rate percentage or None if no notifications
    """
    from apps.notifications.models import Notification
    
    notification_qs = get_scoped_queryset(
        Notification, user, branch_field="announcement__branch"
    )
    
    total = notification_qs.count()
    if total == 0:
        return None
    
    sent = notification_qs.filter(status="SENT").count()
    
    return round((sent / total) * 100, 2)


# =============================================================================
# FINANCE ANALYTICS
# =============================================================================

def get_giving_totals(
    user,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
) -> Dict:
    """
    Get giving totals for date range.
    
    Returns:
        {
            "total_giving": Decimal,
            "total_transactions": int,
            "average_giving": Decimal,
        }
    """
    from apps.finance.models import Giving
    
    start_date, end_date = get_date_range_filter(start_date, end_date)
    
    qs = get_scoped_queryset(Giving, user)
    qs = qs.filter(
        given_at__date__gte=start_date,
        given_at__date__lte=end_date,
    )
    
    aggregates = qs.aggregate(
        total=Sum("amount"),
        count=Count("id"),
        average=Avg("amount"),
    )
    
    return {
        "total_giving": aggregates["total"] or Decimal("0.00"),
        "total_transactions": aggregates["count"],
        "average_giving": aggregates["average"] or Decimal("0.00"),
    }


def get_giving_by_category(
    user,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
) -> List[Dict]:
    """
    Get giving breakdown by category.
    
    Returns:
        [
            {"category__name": "Tithe", "total": Decimal("5000.00"), "count": 50},
            {"category__name": "Offering", "total": Decimal("2000.00"), "count": 30},
            ...
        ]
    """
    from apps.finance.models import Giving
    
    start_date, end_date = get_date_range_filter(start_date, end_date)
    
    qs = get_scoped_queryset(Giving, user)
    qs = qs.filter(
        given_at__date__gte=start_date,
        given_at__date__lte=end_date,
    )
    
    return list(
        qs.filter(category__isnull=False)
        .values("category__name")
        .annotate(
            total=Sum("amount"),
            count=Count("id"),
        )
        .order_by("-total")
    )


def get_giving_by_payment_method(
    user,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
) -> List[Dict]:
    """
    Get giving breakdown by payment method.
    
    Returns:
        [
            {"payment_method": "BANK_TRANSFER", "total": Decimal("4000.00"), "count": 40},
            {"payment_method": "CASH", "total": Decimal("2000.00"), "count": 30},
            ...
        ]
    """
    from apps.finance.models import Giving
    
    start_date, end_date = get_date_range_filter(start_date, end_date)
    
    qs = get_scoped_queryset(Giving, user)
    qs = qs.filter(
        given_at__date__gte=start_date,
        given_at__date__lte=end_date,
    )
    
    return list(
        qs.values("payment_method")
        .annotate(
            total=Sum("amount"),
            count=Count("id"),
        )
        .order_by("-total")
    )


def get_giving_trend(
    user,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    period: str = "month",
) -> List[Dict]:
    """
    Get giving trend over time.
    
    Returns:
        [
            {"period": "2026-01-01", "total": Decimal("10000.00"), "count": 100},
            {"period": "2026-02-01", "total": Decimal("12000.00"), "count": 110},
            ...
        ]
    """
    from apps.finance.models import Giving
    
    start_date, end_date = get_date_range_filter(
        start_date, end_date, default_days=365, max_days=730
    )
    
    qs = get_scoped_queryset(Giving, user)
    
    # Filter by date range
    qs = qs.filter(
        given_at__date__gte=start_date,
        given_at__date__lte=end_date,
    )
    
    # Choose truncation function
    if period == "day":
        trunc_func = TruncDate
    elif period == "week":
        trunc_func = TruncWeek
    elif period == "month":
        trunc_func = TruncMonth
    else:
        raise ValueError(f"Invalid period: {period}")
    
    # Aggregate
    results = (
        qs.annotate(period=trunc_func("given_at"))
        .values("period")
        .annotate(
            total=Sum("amount"),
            count=Count("id"),
        )
        .order_by("period")
    )
    
    return [
        {
            "period": result["period"].isoformat() if result["period"] else None,
            "total": result["total"],
            "count": result["count"],
        }
        for result in results
    ]


def get_pledge_stats(user) -> Dict:
    """
    Get pledge statistics.
    
    Returns:
        {
            "total_pledges": int,
            "active_pledges": int,
            "fulfilled_pledges": int,
            "total_pledged_amount": Decimal,
            "total_fulfilled_amount": Decimal,
        }
    """
    from apps.finance.models import Pledge
    
    qs = get_scoped_queryset(Pledge, user)
    
    total = qs.count()
    active = qs.filter(is_active=True).count()
    fulfilled = qs.filter(is_fulfilled=True).count() if hasattr(Pledge, 'is_fulfilled') else 0
    
    pledged_amount = qs.aggregate(total=Sum("pledged_amount"))["total"] or Decimal("0.00")
    fulfilled_amount = qs.aggregate(total=Sum("fulfilled_amount"))["total"] or Decimal("0.00")
    
    return {
        "total_pledges": total,
        "active_pledges": active,
        "fulfilled_pledges": fulfilled,
        "total_pledged_amount": pledged_amount,
        "total_fulfilled_amount": fulfilled_amount,
    }


def get_reconciliation_status(user) -> Dict:
    """
    Get financial reconciliation status (Phase 14 integration).
    
    Returns:
        {
            "open_reconciliations": int,
            "pending_reconciliations": int,
            "completed_reconciliations": int,
            "approved_reconciliations": int,
            "total_discrepancies": int,
        }
    """
    from apps.finance.models import Reconciliation, ReconciliationStatus
    
    qs = get_scoped_queryset(Reconciliation, user)
    
    open_count = qs.filter(status=ReconciliationStatus.OPEN).count()
    pending = qs.filter(status=ReconciliationStatus.PENDING_APPROVAL).count()
    completed = qs.filter(status=ReconciliationStatus.COMPLETED).count()
    approved = qs.filter(status=ReconciliationStatus.APPROVED).count()
    
    # Count reconciliations with discrepancies
    discrepancies = qs.filter(has_discrepancy=True).count()
    
    return {
        "open_reconciliations": open_count,
        "pending_reconciliations": pending,
        "completed_reconciliations": completed,
        "approved_reconciliations": approved,
        "total_discrepancies": discrepancies,
    }


def get_financial_period_status(user) -> Dict:
    """
    Get financial period status (Phase 14 integration).
    
    Returns:
        {
            "open_periods": int,
            "closed_periods": int,
            "locked_periods": int,
            "current_period": dict or None,
        }
    """
    from apps.finance.models import FinancialPeriod, PeriodStatus
    
    qs = get_scoped_queryset(FinancialPeriod, user)
    
    open_count = qs.filter(status=PeriodStatus.OPEN).count()
    closed = qs.filter(status=PeriodStatus.CLOSED).count()
    locked = qs.filter(status=PeriodStatus.LOCKED).count()
    
    # Get current period (containing today)
    today = timezone.now().date()
    current_period_qs = qs.filter(
        start_date__lte=today,
        end_date__gte=today,
    )
    
    current_period = None
    if current_period_qs.exists():
        period = current_period_qs.first()
        current_period = {
            "id": str(period.id),
            "name": period.name,
            "start_date": period.start_date.isoformat(),
            "end_date": period.end_date.isoformat(),
            "status": period.status,
        }
    
    return {
        "open_periods": open_count,
        "closed_periods": closed,
        "locked_periods": locked,
        "current_period": current_period,
    }


# =============================================================================
# PASTORAL ANALYTICS
# =============================================================================

def get_pastoral_case_counts(user) -> Dict:
    """
    Get pastoral case counts (aggregate only, no sensitive details).
    
    Returns:
        {
            "total_cases": int,
            "open_cases": int,
            "in_progress_cases": int,
            "resolved_cases": int,
            "my_assigned_cases": int,
            "overdue_cases": int,
        }
    """
    from apps.pastoral.models import PastoralCase, PastoralCaseStatus
    
    qs = get_scoped_queryset(PastoralCase, user)
    
    total = qs.count()
    open_count = qs.filter(status=PastoralCaseStatus.OPEN).count()
    in_progress = qs.filter(status=PastoralCaseStatus.IN_PROGRESS).count()
    resolved = qs.filter(status=PastoralCaseStatus.RESOLVED).count()
    
    # Cases assigned to current user
    my_assigned = qs.filter(assigned_to=user).count()
    
    # Overdue cases (open/in-progress with due date in past)
    now = timezone.now()
    overdue = qs.filter(
        status__in=[PastoralCaseStatus.OPEN, PastoralCaseStatus.IN_PROGRESS],
        due_date__isnull=False,
        due_date__lt=now,
    ).count()
    
    return {
        "total_cases": total,
        "open_cases": open_count,
        "in_progress_cases": in_progress,
        "resolved_cases": resolved,
        "my_assigned_cases": my_assigned,
        "overdue_cases": overdue,
    }


def get_prayer_request_counts(user) -> Dict:
    """
    Get prayer request counts (aggregate only, no sensitive content).
    
    Returns:
        {
            "total_requests": int,
            "new_requests": int,
            "praying_requests": int,
            "answered_requests": int,
        }
    """
    from apps.prayer.models import PrayerRequest, PrayerRequestStatus
    
    qs = get_scoped_queryset(PrayerRequest, user)
    
    total = qs.count()
    new = qs.filter(status=PrayerRequestStatus.NEW).count()
    praying = qs.filter(status=PrayerRequestStatus.PRAYING).count()
    answered = qs.filter(status=PrayerRequestStatus.ANSWERED).count()
    
    return {
        "total_requests": total,
        "new_requests": new,
        "praying_requests": praying,
        "answered_requests": answered,
    }
