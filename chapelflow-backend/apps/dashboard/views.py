"""
Phase 16: Dashboard views.

Architecture:
    View → Service → Analytics Query → Database

All dashboards:
- Respect RBAC (role-based access control)
- Enforce organization/branch isolation
- Use services layer for business logic
- Return consistent serialized responses
"""
from datetime import timedelta

from django.db.models import Count, Q
from django.utils import timezone
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from common.constants.roles import Roles
from common.utils.responses import error_response, success_response

from . import services
from .serializers import (
    AdminDashboardSerializer,
    ExecutiveDashboardSerializer,
    FinanceDashboardSerializer,
    MemberPersonalDashboardSerializer,
    MinistryLeaderDashboardSerializer,
    PastorDashboardSerializer,
)


def _get_period_scope_context(user, days=30):
    """
    Generate period and scope context for dashboard responses.
    
    Returns:
        {
            "period": {"start": date, "end": date},
            "scope": {"organization": str, "branch": str, "user_role": str},
        }
    """
    end_date = timezone.now().date()
    start_date = end_date - timedelta(days=days)
    
    period = {
        "start": start_date,
        "end": end_date,
    }
    
    scope = {
        "organization": user.branch.organization.name if user.branch_id else None,
        "branch": user.branch.name if user.branch_id else None,
        "user_role": user.role,
    }
    
    return {"period": period, "scope": scope}


class AdminDashboardView(APIView):
    """
    GET /api/v1/dashboard/admin/
    
    Admin dashboard with comprehensive analytics.
    
    Authorization:
    - SUPER_ADMIN (global scope)
    - CHAPEL_ADMIN (branch scope)
    
    Returns:
    - Member counts and status breakdown
    - Attendance summary
    - Event counts
    - Group/ministry overview
    - Volunteer statistics
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        
        # Authorization check
        if user.role not in (Roles.GLOBAL_SCOPE_ROLES | {Roles.CHAPEL_ADMIN}):
            return error_response("Not authorized for the admin dashboard.", status=403)
        
        # Get date range from query params (default: last 30 days)
        try:
            days = int(request.query_params.get('days', 30))
            days = min(days, 365)  # Cap at 1 year
        except ValueError:
            days = 30
        
        # Build response
        context = _get_period_scope_context(user, days=days)
        end_date = context["period"]["end"]
        start_date = context["period"]["start"]
        
        data = {
            **context,
            "members": services.get_member_counts(user),
            "attendance": services.get_attendance_counts(user, start_date, end_date),
            "events": services.get_event_counts(user, start_date, end_date),
            "groups": services.get_group_counts(user),
            "volunteers": services.get_volunteer_counts(user),
        }
        
        # Validate with serializer for consistent structure
        serializer = AdminDashboardSerializer(data)
        return success_response(serializer.data)



class PastorDashboardView(APIView):
    """
    GET /api/v1/dashboard/pastor/
    
    Pastor/chaplain dashboard with pastoral care analytics.
    
    Authorization:
    - SUPER_ADMIN (global scope)
    - CHAPLAIN (organization scope)
    - CHAPEL_ADMIN (branch scope)
    - PASTOR (legacy, branch scope)
    
    Returns:
    - Pastoral case counts (aggregate only, no sensitive details)
    - Prayer request counts (aggregate only)
    - Member follow-up statistics
    - Visitor follow-up statistics
    
    Privacy:
    - No pastoral notes or prayer content exposed
    - Only aggregate counts and assigned case info
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        
        # Authorization check
        if user.role not in (Roles.GLOBAL_SCOPE_ROLES | Roles.PASTORAL_ACCESS_ROLES):
            return error_response("Not authorized for the pastor dashboard.", status=403)
        
        # Get date range
        try:
            days = int(request.query_params.get('days', 30))
            days = min(days, 365)
        except ValueError:
            days = 30
        
        # Build response
        context = _get_period_scope_context(user, days=days)
        
        data = {
            **context,
            "pastoral_cases": services.get_pastoral_case_counts(user),
            "prayer_requests": services.get_prayer_request_counts(user),
            "member_follow_ups": services.get_member_follow_up_stats(user),
            "visitor_follow_ups": services.get_visitor_follow_up_stats(user),
        }
        
        # Validate with serializer
        serializer = PastorDashboardSerializer(data)
        return success_response(serializer.data)


class FinanceDashboardView(APIView):
    """
    GET /api/v1/dashboard/finance/
    
    Finance dashboard with giving and reconciliation analytics.
    
    Authorization:
    - SUPER_ADMIN (global scope)
    - CHAPEL_ADMIN (branch scope)
    - FINANCE_OFFICER (legacy, branch scope)
    
    Returns:
    - Giving totals and breakdowns
    - Pledge statistics
    - Reconciliation status (Phase 14 integration)
    - Financial period status (Phase 14 integration)
    
    Security:
    - Finance data restricted to authorized roles only
    - No PII exposure in aggregates
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        
        # Authorization check
        if user.role not in Roles.FINANCE_ACCESS_ROLES and user.role not in Roles.GLOBAL_SCOPE_ROLES:
            return error_response("Not authorized for the finance dashboard.", status=403)
        
        # Get date range
        try:
            days = int(request.query_params.get('days', 30))
            days = min(days, 365)
        except ValueError:
            days = 30
        
        # Build response
        context = _get_period_scope_context(user, days=days)
        end_date = context["period"]["end"]
        start_date = context["period"]["start"]
        
        data = {
            **context,
            "giving": services.get_giving_totals(user, start_date, end_date),
            "giving_by_category": services.get_giving_by_category(user, start_date, end_date),
            "pledges": services.get_pledge_stats(user),
            "reconciliation": services.get_reconciliation_status(user),
            "financial_period": services.get_financial_period_status(user),
        }
        
        # Validate with serializer
        serializer = FinanceDashboardSerializer(data)
        return success_response(serializer.data)


class MemberDashboardView(APIView):
    """
    GET /api/v1/dashboard/member/
    
    Individual member's personal dashboard.
    
    Authorization:
    - Any authenticated user with linked member profile
    
    Returns:
    - Membership status
    - Group memberships
    - Upcoming event registrations
    - Recent attendance count
    
    Privacy:
    - User sees only their own data
    - No access to other members' information
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        member = getattr(request.user, "member_profile", None)
        if not member:
            return error_response("No member profile linked to this account.", status=404)

        data = {
            "membership_status": member.membership_status,
            "groups": list(member.group_memberships.filter(is_active=True).values_list("group__name", flat=True)),
            "upcoming_registrations": member.event_registrations.filter(
                schedule__occurrence_start__gte=timezone.now()
            ).count(),
            "recent_attendance_count": member.attendance_records.count(),
        }
        
        # Validate with serializer
        serializer = MemberPersonalDashboardSerializer(data)
        return success_response(serializer.data)


class ExecutiveDashboardView(APIView):
    """
    GET /api/v1/dashboard/executive/
    
    Executive/leadership dashboard with high-level analytics.
    
    Authorization:
    - SUPER_ADMIN (global scope)
    - CHAPLAIN (organization scope)
    - CHAPEL_ADMIN (branch scope, if senior leadership flag exists)
    
    Returns:
    - Member counts and growth trends
    - Attendance summary and rates
    - Visitor analytics and conversion rates
    - Giving overview
    - Event summary
    - Volunteer participation
    
    Purpose:
    - Strategic overview for decision-making
    - KPIs and trends
    - Cross-functional metrics
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        
        # Authorization check: senior leadership only
        authorized_roles = Roles.GLOBAL_SCOPE_ROLES | Roles.ORG_WIDE_SCOPE_ROLES | {Roles.CHAPEL_ADMIN}
        if user.role not in authorized_roles:
            return error_response("Not authorized for the executive dashboard.", status=403)
        
        # Get date range (default: last 90 days for executive view)
        try:
            days = int(request.query_params.get('days', 90))
            days = min(days, 730)  # Cap at 2 years
        except ValueError:
            days = 90
        
        # Build response
        context = _get_period_scope_context(user, days=days)
        end_date = context["period"]["end"]
        start_date = context["period"]["start"]
        
        # Get member growth trend (monthly for executive view)
        member_growth = services.get_member_growth(user, start_date, end_date, period="month")
        
        data = {
            **context,
            "members": services.get_member_counts(user),
            "member_growth": member_growth,
            "attendance": services.get_attendance_counts(user, start_date, end_date),
            "attendance_rate": services.get_attendance_rate(user),
            "visitors": services.get_visitor_counts(user, start_date, end_date),
            "visitor_conversion_rate": services.get_visitor_conversion_rate(user),
            "giving": services.get_giving_totals(user, start_date, end_date),
            "events": services.get_event_counts(user, start_date, end_date),
            "volunteers": services.get_volunteer_counts(user),
            "volunteer_participation_rate": services.get_volunteer_participation_rate(user),
        }
        
        # Validate with serializer
        serializer = ExecutiveDashboardSerializer(data)
        return success_response(serializer.data)


class MinistryLeaderDashboardView(APIView):
    """
    GET /api/v1/dashboard/ministry/
    
    Ministry/unit leader dashboard (scoped to assigned ministry).
    
    Authorization:
    - FELLOWSHIP_LEADER (fellowship scope)
    - UNIT_HEAD (unit scope)
    - MINISTRY_GROUP_LEADER (ministry scope)
    - Higher roles can view any ministry
    
    Query Params:
    - ministry_id (optional): View specific ministry (if authorized)
    
    Returns:
    - Ministry information
    - Member counts
    - Event counts
    - Volunteer counts
    
    Security:
    - Leaders see only their assigned ministry/unit/fellowship
    - Admins can view any ministry
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        
        # Check if user has ministry leadership role
        if user.role not in (Roles.ASSIGNMENT_SCOPED_ROLES | Roles.GLOBAL_SCOPE_ROLES | {Roles.CHAPEL_ADMIN}):
            return error_response("Not authorized for the ministry leader dashboard.", status=403)
        
        # Get ministry from query param or user's assignment
        ministry_id = request.query_params.get('ministry_id')
        
        if not ministry_id:
            return error_response("ministry_id parameter required.", status=400)
        
        # Validate ministry access
        from apps.groups.models import Group
        
        try:
            ministry_qs = services.get_scoped_queryset(Group, user)
            ministry = ministry_qs.get(id=ministry_id)
        except Group.DoesNotExist:
            return error_response("Ministry not found or access denied.", status=404)
        
        # Get date range
        try:
            days = int(request.query_params.get('days', 30))
            days = min(days, 365)
        except ValueError:
            days = 30
        
        # Build response
        context = _get_period_scope_context(user, days=days)
        end_date = context["period"]["end"]
        start_date = context["period"]["start"]
        
        # Ministry-specific analytics
        from apps.events.models import Event
        from apps.volunteers.models import Volunteer
        from django.db.models import Q
        
        # Events for this ministry
        event_qs = services.get_scoped_queryset(Event, user)
        ministry_events = event_qs.filter(
            Q(ministry=ministry) | Q(category__ministry=ministry)
        )
        upcoming_events = ministry_events.filter(schedules__start_time__gte=timezone.now()).distinct().count()
        
        # Volunteers in this ministry
        volunteer_qs = services.get_scoped_queryset(Volunteer, user)
        ministry_volunteers = volunteer_qs.filter(
            assignments__schedule__ministry=ministry
        ).distinct().count()
        
        data = {
            **context,
            "ministry_info": {
                "id": str(ministry.id),
                "name": ministry.name,
                "type": ministry.group_type,
                "is_active": ministry.is_active,
                "leader": ministry.leader.full_name if ministry.leader else None,
            },
            "members": ministry.memberships.filter(is_active=True).count(),
            "active_members": ministry.memberships.filter(is_active=True).count(),
            "events": ministry_events.count(),
            "upcoming_events": upcoming_events,
            "volunteers": ministry_volunteers,
        }
        
        # Validate with serializer
        serializer = MinistryLeaderDashboardSerializer(data)
        return success_response(serializer.data)


class RoleOperationsDashboardView(APIView):
    """A small, role-safe operational summary for chapel staff workspaces.

    This deliberately returns counts and group metadata, never attendance
    tokens, pastoral notes, or student contact details.  Detail screens still
    use their own scoped endpoints, so this endpoint cannot become a shortcut
    around the RBAC rules on those records.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        allowed = {
            Roles.CHAPLAIN,
            Roles.STUDENT_CHAPLAIN,
            Roles.FELLOWSHIP_LEADER,
            Roles.UNIT_HEAD,
            Roles.MINISTRY_GROUP_LEADER,
        }
        if user.get_role_code() not in allowed:
            return error_response("Not authorized for this operations workspace.", status=403)

        from apps.attendance.models import AttendanceRecord, AttendanceSession
        from apps.members.models import Member, MembershipStatus
        from apps.ministries.models import Group
        from apps.reports.models import ReportJob, ReportJobStatus
        from common.permissions.scoping import get_accessible_branch_ids, led_group_ids

        branch_ids = get_accessible_branch_ids(user)
        is_group_leader = user.get_role_code() in Roles.ASSIGNMENT_SCOPED_ROLES
        group_ids = led_group_ids(user) if is_group_leader else []
        groups = Group.objects.filter(
            id__in=group_ids,
            is_active=True,
        ) if is_group_leader else Group.objects.filter(branch_id__in=branch_ids, is_active=True)
        group_rows = list(
            groups.annotate(active_members=Count("memberships", filter=Q(memberships__is_active=True)))
            .values("id", "name", "group_type", "active_members")
        )

        member_qs = Member.objects.filter(branch_id__in=branch_ids)
        if is_group_leader:
            member_qs = member_qs.filter(group_memberships__group_id__in=group_ids, group_memberships__is_active=True).distinct()
        session_qs = AttendanceSession.objects.filter(branch_id__in=branch_ids)
        record_qs = AttendanceRecord.objects.filter(session__branch_id__in=branch_ids)
        if is_group_leader:
            # Attendance stays chapel-controlled. Leaders see only aggregate
            # branch activity, not individual attendance records.
            record_qs = record_qs.none()

        data = {
            "role": user.get_role_code(),
            "branch_id": str(user.branch_id) if user.branch_id else None,
            "groups": [
                {"id": str(item["id"]), "name": item["name"], "type": item["group_type"], "active_members": item["active_members"]}
                for item in group_rows
            ],
            "metrics": {
                "active_students": member_qs.filter(membership_status=MembershipStatus.ACTIVE).count(),
                "groups": len(group_rows),
                "open_sessions": session_qs.filter(is_open=True).count(),
                "attendance_today": record_qs.filter(checked_in_at__date=timezone.localdate()).count(),
                "pending_reports": 0 if is_group_leader else ReportJob.objects.filter(branch_id__in=branch_ids, status__in=[ReportJobStatus.QUEUED, ReportJobStatus.RUNNING]).count(),
            },
            "live_sessions": [
                {
                    "id": str(session.id),
                    "label": session.label or "Chapel attendance session",
                    "state": session.state,
                    "opens_at": session.window_opens_at or session.opened_at,
                    "closes_at": session.window_closes_at,
                    "check_ins": session.check_ins,
                }
                for session in session_qs.filter(is_open=True).annotate(check_ins=Count("records")).order_by("-opened_at")[:8]
            ] if not is_group_leader else [],
        }
        return success_response(data)
