"""
Phase 16: Dashboard response serializers.

Provides consistent, documented response structures for all dashboard endpoints.
"""
from rest_framework import serializers


class PeriodSerializer(serializers.Serializer):
    """Date range period."""
    start = serializers.DateField()
    end = serializers.DateField()


class ScopeSerializer(serializers.Serializer):
    """Dashboard scope information."""
    organization = serializers.CharField(required=False, allow_null=True)
    branch = serializers.CharField(required=False, allow_null=True)
    user_role = serializers.CharField()


class ComparisonSerializer(serializers.Serializer):
    """Period comparison data."""
    current = serializers.FloatField()
    previous = serializers.FloatField()
    change = serializers.FloatField()
    percentage_change = serializers.FloatField(allow_null=True)


class TimeSeriesDataPointSerializer(serializers.Serializer):
    """Single data point in time series."""
    period = serializers.CharField()
    count = serializers.IntegerField()


class CategoryBreakdownSerializer(serializers.Serializer):
    """Generic category breakdown."""
    category = serializers.CharField(source='*')
    count = serializers.IntegerField()


# =============================================================================
# MEMBER ANALYTICS SERIALIZERS
# =============================================================================

class MemberCountsSerializer(serializers.Serializer):
    """Member counts response."""
    total_members = serializers.IntegerField()
    active_members = serializers.IntegerField()
    inactive_members = serializers.IntegerField()
    pending_members = serializers.IntegerField()
    transferred_members = serializers.IntegerField()
    deceased_members = serializers.IntegerField()


class MemberDemographicsSerializer(serializers.Serializer):
    """Member demographics response."""
    by_gender = CategoryBreakdownSerializer(many=True)
    by_fellowship = CategoryBreakdownSerializer(many=True)
    by_college = CategoryBreakdownSerializer(many=True)
    by_department = CategoryBreakdownSerializer(many=True)
    by_community = CategoryBreakdownSerializer(many=True)


class MemberFollowUpStatsSerializer(serializers.Serializer):
    """Member follow-up statistics."""
    total_follow_ups = serializers.IntegerField()
    pending_follow_ups = serializers.IntegerField()
    completed_follow_ups = serializers.IntegerField()
    overdue_follow_ups = serializers.IntegerField()


# =============================================================================
# ATTENDANCE ANALYTICS SERIALIZERS
# =============================================================================

class AttendanceCountsSerializer(serializers.Serializer):
    """Attendance counts response."""
    total_attendance = serializers.IntegerField()
    unique_attendees = serializers.IntegerField()
    average_attendance = serializers.FloatField()
    member_attendance = serializers.IntegerField()
    visitor_attendance = serializers.IntegerField()


# =============================================================================
# VISITOR ANALYTICS SERIALIZERS
# =============================================================================

class VisitorCountsSerializer(serializers.Serializer):
    """Visitor counts response."""
    total_visitors = serializers.IntegerField()
    new_visitors = serializers.IntegerField()
    returning_visitors = serializers.IntegerField()
    converted_visitors = serializers.IntegerField()


class VisitorFollowUpStatsSerializer(serializers.Serializer):
    """Visitor follow-up statistics."""
    total_follow_ups = serializers.IntegerField()
    pending_follow_ups = serializers.IntegerField()
    completed_follow_ups = serializers.IntegerField()
    overdue_follow_ups = serializers.IntegerField()


# =============================================================================
# EVENT ANALYTICS SERIALIZERS
# =============================================================================

class EventCountsSerializer(serializers.Serializer):
    """Event counts response."""
    total_events = serializers.IntegerField()
    upcoming_events = serializers.IntegerField()
    completed_events = serializers.IntegerField()
    cancelled_events = serializers.IntegerField()


class EventAttendanceStatsSerializer(serializers.Serializer):
    """Event attendance statistics."""
    total_registrations = serializers.IntegerField()
    average_attendance_per_event = serializers.FloatField()


# =============================================================================
# GROUP/MINISTRY ANALYTICS SERIALIZERS
# =============================================================================

class GroupCountsSerializer(serializers.Serializer):
    """Group/ministry counts response."""
    total_groups = serializers.IntegerField()
    active_groups = serializers.IntegerField()
    inactive_groups = serializers.IntegerField()
    fellowship_count = serializers.IntegerField()
    ministry_count = serializers.IntegerField()
    unit_count = serializers.IntegerField()


class GroupParticipationStatsSerializer(serializers.Serializer):
    """Group participation statistics."""
    total_memberships = serializers.IntegerField()
    active_memberships = serializers.IntegerField()
    average_group_size = serializers.FloatField()


# =============================================================================
# VOLUNTEER ANALYTICS SERIALIZERS
# =============================================================================

class VolunteerCountsSerializer(serializers.Serializer):
    """Volunteer counts response."""
    total_volunteers = serializers.IntegerField()
    active_volunteers = serializers.IntegerField()
    total_assignments = serializers.IntegerField()
    confirmed_assignments = serializers.IntegerField()
    completed_assignments = serializers.IntegerField()


# =============================================================================
# COMMUNICATION ANALYTICS SERIALIZERS
# =============================================================================

class CommunicationCountsSerializer(serializers.Serializer):
    """Communication counts response."""
    total_announcements = serializers.IntegerField()
    total_notifications = serializers.IntegerField()
    sent_count = serializers.IntegerField()
    failed_count = serializers.IntegerField()


# =============================================================================
# FINANCE ANALYTICS SERIALIZERS
# =============================================================================

class GivingTotalsSerializer(serializers.Serializer):
    """Giving totals response."""
    total_giving = serializers.DecimalField(max_digits=12, decimal_places=2)
    total_transactions = serializers.IntegerField()
    average_giving = serializers.DecimalField(max_digits=12, decimal_places=2)


class GivingCategorySerializer(serializers.Serializer):
    """Giving by category."""
    category__name = serializers.CharField()
    total = serializers.DecimalField(max_digits=12, decimal_places=2)
    count = serializers.IntegerField()


class GivingTrendDataPointSerializer(serializers.Serializer):
    """Giving trend data point."""
    period = serializers.CharField()
    total = serializers.DecimalField(max_digits=12, decimal_places=2)
    count = serializers.IntegerField()


class PledgeStatsSerializer(serializers.Serializer):
    """Pledge statistics."""
    total_pledges = serializers.IntegerField()
    active_pledges = serializers.IntegerField()
    fulfilled_pledges = serializers.IntegerField()
    total_pledged_amount = serializers.DecimalField(max_digits=12, decimal_places=2)
    total_fulfilled_amount = serializers.DecimalField(max_digits=12, decimal_places=2)


class ReconciliationStatusSerializer(serializers.Serializer):
    """Reconciliation status (Phase 14 integration)."""
    open_reconciliations = serializers.IntegerField()
    pending_reconciliations = serializers.IntegerField()
    completed_reconciliations = serializers.IntegerField()
    approved_reconciliations = serializers.IntegerField()
    total_discrepancies = serializers.IntegerField()


class CurrentPeriodSerializer(serializers.Serializer):
    """Current financial period."""
    id = serializers.CharField()
    name = serializers.CharField()
    start_date = serializers.DateField()
    end_date = serializers.DateField()
    status = serializers.CharField()


class FinancialPeriodStatusSerializer(serializers.Serializer):
    """Financial period status (Phase 14 integration)."""
    open_periods = serializers.IntegerField()
    closed_periods = serializers.IntegerField()
    locked_periods = serializers.IntegerField()
    current_period = CurrentPeriodSerializer(allow_null=True)


# =============================================================================
# PASTORAL ANALYTICS SERIALIZERS
# =============================================================================

class PastoralCaseCountsSerializer(serializers.Serializer):
    """Pastoral case counts (aggregate only)."""
    total_cases = serializers.IntegerField()
    open_cases = serializers.IntegerField()
    in_progress_cases = serializers.IntegerField()
    resolved_cases = serializers.IntegerField()
    my_assigned_cases = serializers.IntegerField()
    overdue_cases = serializers.IntegerField()


class PrayerRequestCountsSerializer(serializers.Serializer):
    """Prayer request counts (aggregate only)."""
    total_requests = serializers.IntegerField()
    new_requests = serializers.IntegerField()
    praying_requests = serializers.IntegerField()
    answered_requests = serializers.IntegerField()


# =============================================================================
# DASHBOARD RESPONSE SERIALIZERS
# =============================================================================

class AdminDashboardSerializer(serializers.Serializer):
    """Admin dashboard response."""
    period = PeriodSerializer()
    scope = ScopeSerializer()
    members = MemberCountsSerializer()
    attendance = AttendanceCountsSerializer()
    events = EventCountsSerializer()
    groups = GroupCountsSerializer()
    volunteers = VolunteerCountsSerializer()


class PastorDashboardSerializer(serializers.Serializer):
    """Pastor/chaplain dashboard response."""
    period = PeriodSerializer()
    scope = ScopeSerializer()
    pastoral_cases = PastoralCaseCountsSerializer()
    prayer_requests = PrayerRequestCountsSerializer()
    member_follow_ups = MemberFollowUpStatsSerializer()
    visitor_follow_ups = VisitorFollowUpStatsSerializer()


class FinanceDashboardSerializer(serializers.Serializer):
    """Finance dashboard response."""
    period = PeriodSerializer()
    scope = ScopeSerializer()
    giving = GivingTotalsSerializer()
    giving_by_category = GivingCategorySerializer(many=True)
    pledges = PledgeStatsSerializer()
    reconciliation = ReconciliationStatusSerializer()
    financial_period = FinancialPeriodStatusSerializer()


class MemberPersonalDashboardSerializer(serializers.Serializer):
    """Member personal dashboard response."""
    membership_status = serializers.CharField()
    groups = serializers.ListField(child=serializers.CharField())
    upcoming_registrations = serializers.IntegerField()
    recent_attendance_count = serializers.IntegerField()


class ExecutiveDashboardSerializer(serializers.Serializer):
    """Executive/leadership dashboard response."""
    period = PeriodSerializer()
    scope = ScopeSerializer()
    members = MemberCountsSerializer()
    member_growth = TimeSeriesDataPointSerializer(many=True)
    attendance = AttendanceCountsSerializer()
    attendance_rate = serializers.FloatField(allow_null=True)
    visitors = VisitorCountsSerializer()
    visitor_conversion_rate = serializers.FloatField(allow_null=True)
    giving = GivingTotalsSerializer()
    events = EventCountsSerializer()
    volunteers = VolunteerCountsSerializer()
    volunteer_participation_rate = serializers.FloatField(allow_null=True)


class MinistryLeaderDashboardSerializer(serializers.Serializer):
    """Ministry/unit leader dashboard response."""
    period = PeriodSerializer()
    scope = ScopeSerializer()
    ministry_info = serializers.DictField()
    members = serializers.IntegerField()
    active_members = serializers.IntegerField()
    events = serializers.IntegerField()
    upcoming_events = serializers.IntegerField()
    volunteers = serializers.IntegerField()


# =============================================================================
# ANALYTICS REQUEST SERIALIZERS
# =============================================================================

class DateRangeFilterSerializer(serializers.Serializer):
    """Date range filter for analytics requests."""
    start_date = serializers.DateField(required=False, allow_null=True)
    end_date = serializers.DateField(required=False, allow_null=True)
    
    def validate(self, data):
        """Validate start_date <= end_date."""
        start = data.get('start_date')
        end = data.get('end_date')
        
        if start and end and start > end:
            raise serializers.ValidationError(
                {"start_date": "start_date must be <= end_date"}
            )
        
        return data


class TimeSeriesFilterSerializer(DateRangeFilterSerializer):
    """Time series filter with period selection."""
    period = serializers.ChoiceField(
        choices=['day', 'week', 'month', 'quarter', 'year'],
        default='month',
    )
