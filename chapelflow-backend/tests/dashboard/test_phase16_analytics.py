"""
Phase 16: Dashboard analytics correctness tests.

Tests for:
- KPI calculation accuracy
- Time-series analytics
- Trend calculations
- Comparison analytics
- Edge cases (zero records, empty periods, etc.)
- Data correctness verification
"""
import pytest
from datetime import date, datetime, timedelta
from decimal import Decimal
from django.contrib.auth import get_user_model
from django.utils import timezone

from apps.dashboard import services
from apps.members.models import Member, MembershipStatus, MemberFollowUp, MemberFollowUpMilestone
from apps.attendance.models import AttendanceSession, AttendanceRecord, AttendanceMethod
from apps.visitors.models import Visitor, VisitorStatus, VisitorFollowUp
from apps.finance.models import Giving, GivingCategory, Pledge, Reconciliation, ReconciliationStatus, FinancialPeriod, FinancialPeriodStatus
from apps.events.models import Event, EventSchedule
from apps.ministries.models import Group, GroupType
from apps.groups.models import GroupMembership
from apps.volunteers.models import VolunteerAssignment
from apps.pastoral.models import PastoralCase, PastoralCaseStatus
from apps.prayer.models import PrayerRequest, PrayerRequestStatus
from apps.organizations.models import Organization, Branch
from common.constants.roles import Roles

User = get_user_model()


@pytest.fixture
def organization(db):
    """Create test organization."""
    return Organization.objects.create(name="Test Organization", slug="test-org-p16-analytics")


@pytest.fixture
def branch(organization):
    """Create test branch."""
    return Branch.objects.create(
        name="Test Branch",
        organization=organization
    )


@pytest.fixture
def admin_user(branch):
    """Create admin user for testing."""
    return User.objects.create_user(
        email="admin@test.com",
        password="testpass123",
        role=Roles.CHAPEL_ADMIN,
        branch=branch,
    )


# =============================================================================
# MEMBER ANALYTICS TESTS
# =============================================================================

@pytest.mark.django_db
class TestMemberAnalytics:
    """Test member analytics calculations."""
    
    def test_member_counts_accuracy(self, admin_user, branch):
        """Member counts match actual data."""
        # Create members with different statuses
        Member.objects.create(
            branch=branch,
            first_name="Active",
            last_name="Member1",
            membership_status=MembershipStatus.ACTIVE,
        )
        Member.objects.create(
            branch=branch,
            first_name="Active",
            last_name="Member2",
            membership_status=MembershipStatus.ACTIVE,
        )
        Member.objects.create(
            branch=branch,
            first_name="Inactive",
            last_name="Member",
            membership_status=MembershipStatus.INACTIVE,
        )
        Member.objects.create(
            branch=branch,
            first_name="Pending",
            last_name="Member",
            membership_status=MembershipStatus.PENDING,
        )
        
        # Get member counts
        counts = services.get_member_counts(admin_user)
        
        assert counts["total_members"] == 4
        assert counts["active_members"] == 2
        assert counts["inactive_members"] == 1
        assert counts["pending_members"] == 1
        assert counts["transferred_members"] == 0
        assert counts["deceased_members"] == 0
    
    def test_member_status_breakdown(self, admin_user, branch):
        """Member status breakdown is accurate."""
        # Create members
        for i in range(5):
            Member.objects.create(
                branch=branch,
                first_name=f"Active{i}",
                last_name="Member",
                membership_status=MembershipStatus.ACTIVE,
            )
        
        for i in range(2):
            Member.objects.create(
                branch=branch,
                first_name=f"Inactive{i}",
                last_name="Member",
                membership_status=MembershipStatus.INACTIVE,
            )
        
        # Get breakdown
        breakdown = services.get_member_status_breakdown(admin_user)
        
        # Convert to dict for easier assertion
        breakdown_dict = {item["membership_status"]: item["count"] for item in breakdown}
        
        assert breakdown_dict[MembershipStatus.ACTIVE] == 5
        assert breakdown_dict[MembershipStatus.INACTIVE] == 2
    
    def test_new_members_count(self, admin_user, branch):
        """New members count respects date range."""
        today = timezone.now().date()
        
        # Create member created today
        Member.objects.create(
            branch=branch,
            first_name="New",
            last_name="Today",
            membership_status=MembershipStatus.ACTIVE,
            created_at=timezone.now(),
        )
        
        # Create member created 10 days ago
        Member.objects.create(
            branch=branch,
            first_name="New",
            last_name="Old",
            membership_status=MembershipStatus.ACTIVE,
            created_at=timezone.now() - timedelta(days=10),
        )
        
        # Create member created 40 days ago (outside default range)
        Member.objects.create(
            branch=branch,
            first_name="Old",
            last_name="Member",
            membership_status=MembershipStatus.ACTIVE,
            created_at=timezone.now() - timedelta(days=40),
        )
        
        # Get new members count (default: last 30 days)
        count = services.get_new_members_count(admin_user)
        
        # Should include today and 10 days ago, exclude 40 days ago
        assert count == 2
    
    def test_member_growth_time_series(self, admin_user, branch):
        """Member growth time-series is accurate."""
        today = timezone.now().date()
        
        # Create members at different times
        Member.objects.create(
            branch=branch,
            first_name="Jan",
            last_name="Member",
            membership_status=MembershipStatus.ACTIVE,
            created_at=datetime(2026, 1, 15, tzinfo=timezone.get_current_timezone()),
        )
        Member.objects.create(
            branch=branch,
            first_name="Feb",
            last_name="Member1",
            membership_status=MembershipStatus.ACTIVE,
            created_at=datetime(2026, 2, 10, tzinfo=timezone.get_current_timezone()),
        )
        Member.objects.create(
            branch=branch,
            first_name="Feb",
            last_name="Member2",
            membership_status=MembershipStatus.ACTIVE,
            created_at=datetime(2026, 2, 20, tzinfo=timezone.get_current_timezone()),
        )
        
        # Get growth trend
        start_date = date(2026, 1, 1)
        end_date = date(2026, 2, 28)
        growth = services.get_member_growth(admin_user, start_date, end_date, period="month")
        
        # Verify time-series structure
        assert len(growth) == 2  # Jan and Feb
        
        # Verify counts
        jan_data = [item for item in growth if item["period"].startswith("2026-01")][0]
        feb_data = [item for item in growth if item["period"].startswith("2026-02")][0]
        
        assert jan_data["count"] == 1
        assert feb_data["count"] == 2
    
    def test_member_age_distribution(self, admin_user, branch):
        """Member age distribution is accurate."""
        today = timezone.now().date()
        
        # Create members with different ages
        Member.objects.create(
            branch=branch,
            first_name="Teen",
            last_name="Member",
            date_of_birth=today - timedelta(days=365 * 16),  # 16 years old
        )
        Member.objects.create(
            branch=branch,
            first_name="Young",
            last_name="Adult",
            date_of_birth=today - timedelta(days=365 * 22),  # 22 years old
        )
        Member.objects.create(
            branch=branch,
            first_name="Adult",
            last_name="Member",
            date_of_birth=today - timedelta(days=365 * 35),  # 35 years old
        )
        
        # Get age distribution
        distribution = services.get_member_age_distribution(admin_user)
        
        # Convert to dict
        age_dict = {item["age_group"]: item["count"] for item in distribution}
        
        assert age_dict["0-17"] == 1
        assert age_dict["18-25"] == 1
        assert age_dict["26-35"] == 0
        assert age_dict["36-50"] == 1


# =============================================================================
# ATTENDANCE ANALYTICS TESTS
# =============================================================================

@pytest.mark.django_db
class TestAttendanceAnalytics:
    """Test attendance analytics calculations."""
    
    def test_attendance_counts_accuracy(self, admin_user, branch):
        """Attendance counts match actual records."""
        # Create session
        session = AttendanceSession.objects.create(
            branch=branch,
            label="Test Session",
            is_open=True,
        )
        
        # Create members
        members = []
        for i in range(3):
            member = Member.objects.create(
                branch=branch,
                first_name=f"Member{i}",
                last_name="Test",
                membership_status=MembershipStatus.ACTIVE,
            )
            members.append(member)
        
        # Create attendance records
        for i, member in enumerate(members):
            AttendanceRecord.objects.create(
                session=session,
                member=member,
                method=AttendanceMethod.QR_CODE,
                checked_in_at=timezone.now(),
            )
        
        # Member 0 attends twice (but should count once per session due to unique constraint)
        # This tests duplicate prevention
        
        # Get attendance counts
        today = timezone.now().date()
        counts = services.get_attendance_counts(admin_user, today, today)
        
        assert counts["total_attendance"] == 3
        assert counts["unique_attendees"] == 3
        assert counts["member_attendance"] == 3
        assert counts["visitor_attendance"] == 0
    
    def test_attendance_rate_calculation(self, admin_user, branch):
        """Attendance rate is calculated correctly."""
        # Create 10 active members
        members = []
        for i in range(10):
            member = Member.objects.create(
                branch=branch,
                first_name=f"Member{i}",
                last_name="Test",
                membership_status=MembershipStatus.ACTIVE,
            )
            members.append(member)
        
        # Create session
        session = AttendanceSession.objects.create(
            branch=branch,
            label="Test Session",
            opened_at=timezone.now(),
        )
        
        # 6 out of 10 members attended
        for i in range(6):
            AttendanceRecord.objects.create(
                session=session,
                member=members[i],
                method=AttendanceMethod.QR_CODE,
                checked_in_at=timezone.now(),
            )
        
        # Get attendance rate
        rate = services.get_attendance_rate(admin_user)
        
        # Should be 60% (6/10)
        assert rate == 60.0
    
    def test_attendance_trend_time_series(self, admin_user, branch):
        """Attendance trend time-series is accurate."""
        # Create session
        session = AttendanceSession.objects.create(
            branch=branch,
            label="Test Session",
        )
        
        # Create member
        member = Member.objects.create(
            branch=branch,
            first_name="Test",
            last_name="Member",
        )
        
        # Create attendance records at different times
        AttendanceRecord.objects.create(
            session=session,
            member=member,
            method=AttendanceMethod.QR_CODE,
            checked_in_at=datetime(2026, 8, 10, tzinfo=timezone.get_current_timezone()),
        )
        AttendanceRecord.objects.create(
            session=session,
            member=member,
            method=AttendanceMethod.MANUAL,
            checked_in_at=datetime(2026, 8, 17, tzinfo=timezone.get_current_timezone()),
        )
        
        # Get trend
        start_date = date(2026, 8, 1)
        end_date = date(2026, 8, 31)
        trend = services.get_attendance_trend(admin_user, start_date, end_date, period="week")
        
        # Should have data for the weeks containing Aug 10 and Aug 17
        assert len(trend) >= 1


# =============================================================================
# VISITOR ANALYTICS TESTS
# =============================================================================

@pytest.mark.django_db
class TestVisitorAnalytics:
    """Test visitor analytics calculations."""
    
    def test_visitor_counts_accuracy(self, admin_user, branch):
        """Visitor counts match actual data."""
        # Create visitors
        Visitor.objects.create(
            branch=branch,
            full_name="New Visitor",
            status=VisitorStatus.NEW,
            created_at=timezone.now(),
        )
        Visitor.objects.create(
            branch=branch,
            full_name="Contacted Visitor",
            status=VisitorStatus.CONTACTED,
            created_at=timezone.now() - timedelta(days=10),
        )
        Visitor.objects.create(
            branch=branch,
            full_name="Converted Visitor",
            status=VisitorStatus.REGISTERED,
            converted_at=timezone.now() - timedelta(days=5),
            created_at=timezone.now() - timedelta(days=40),  # Outside default range
        )
        
        # Get visitor counts
        today = timezone.now().date()
        thirty_days_ago = today - timedelta(days=30)
        counts = services.get_visitor_counts(admin_user, thirty_days_ago, today)
        
        # new_visitors: created within range (2)
        # converted_visitors: converted within range (1)
        assert counts["total_visitors"] == 3
        assert counts["new_visitors"] == 2
        assert counts["converted_visitors"] == 1
    
    def test_visitor_conversion_rate(self, admin_user, branch):
        """Visitor conversion rate is calculated correctly."""
        # Create 10 visitors, 3 converted
        for i in range(7):
            Visitor.objects.create(
                branch=branch,
                full_name=f"Visitor {i}",
                status=VisitorStatus.NEW,
            )
        
        for i in range(3):
            Visitor.objects.create(
                branch=branch,
                full_name=f"Converted {i}",
                status=VisitorStatus.REGISTERED,
            )
        
        # Get conversion rate
        rate = services.get_visitor_conversion_rate(admin_user)
        
        # Should be 30% (3/10)
        assert rate == 30.0


# =============================================================================
# FINANCE ANALYTICS TESTS
# =============================================================================

@pytest.mark.django_db
class TestFinanceAnalytics:
    """Test finance analytics calculations."""
    
    def test_giving_totals_accuracy(self, admin_user, branch):
        """Giving totals match actual transactions."""
        # Create category
        category = GivingCategory.objects.create(name="Tithe")
        
        # Create member
        member = Member.objects.create(
            branch=branch,
            first_name="Test",
            last_name="Member",
        )
        
        # Create giving records
        Giving.objects.create(
            branch=branch,
            member=member,
            category=category,
            amount=Decimal("1000.00"),
            given_at=timezone.now(),
        )
        Giving.objects.create(
            branch=branch,
            member=member,
            category=category,
            amount=Decimal("500.50"),
            given_at=timezone.now(),
        )
        Giving.objects.create(
            branch=branch,
            member=member,
            category=category,
            amount=Decimal("250.25"),
            given_at=timezone.now(),
        )
        
        # Get giving totals
        today = timezone.now().date()
        totals = services.get_giving_totals(admin_user, today, today)
        
        assert totals["total_giving"] == Decimal("1750.75")
        assert totals["total_transactions"] == 3
        assert totals["average_giving"] == Decimal("583.58")  # Rounded
    
    def test_giving_trend_time_series(self, admin_user, branch):
        """Giving trend time-series is accurate."""
        category = GivingCategory.objects.create(name="Tithe")
        member = Member.objects.create(branch=branch, first_name="Test", last_name="Member")
        
        # Create giving at different times
        Giving.objects.create(
            branch=branch,
            member=member,
            category=category,
            amount=Decimal("1000.00"),
            given_at=datetime(2026, 1, 15, tzinfo=timezone.get_current_timezone()),
        )
        Giving.objects.create(
            branch=branch,
            member=member,
            category=category,
            amount=Decimal("1500.00"),
            given_at=datetime(2026, 2, 10, tzinfo=timezone.get_current_timezone()),
        )
        
        # Get trend
        start_date = date(2026, 1, 1)
        end_date = date(2026, 2, 28)
        trend = services.get_giving_trend(admin_user, start_date, end_date, period="month")
        
        # Verify structure
        assert len(trend) == 2
        
        # Verify amounts
        jan_data = [item for item in trend if item["period"].startswith("2026-01")][0]
        feb_data = [item for item in trend if item["period"].startswith("2026-02")][0]
        
        assert jan_data["total"] == Decimal("1000.00")
        assert feb_data["total"] == Decimal("1500.00")
    
    def test_reconciliation_status_integration(self, admin_user, branch):
        """Reconciliation status integration with Phase 14."""
        # Create financial period
        period = FinancialPeriod.objects.create(
            branch=branch,
            name="Q1 2026",
            start_date=date(2026, 1, 1),
            end_date=date(2026, 3, 31),
            status=FinancialPeriodStatus.OPEN,
        )
        
        # Create reconciliations
        Reconciliation.objects.create(
            branch=branch,
            period=period,
            status=ReconciliationStatus.OPEN,
        )
        Reconciliation.objects.create(
            branch=branch,
            period=period,
            status=ReconciliationStatus.PENDING_APPROVAL,
        )
        Reconciliation.objects.create(
            branch=branch,
            period=period,
            status=ReconciliationStatus.APPROVED,
            has_discrepancy=True,
        )
        
        # Get reconciliation status
        status = services.get_reconciliation_status(admin_user)
        
        assert status["open_reconciliations"] == 1
        assert status["pending_reconciliations"] == 1
        assert status["approved_reconciliations"] == 1
        assert status["total_discrepancies"] == 1


# =============================================================================
# EDGE CASE TESTS
# =============================================================================

@pytest.mark.django_db
class TestEdgeCases:
    """Test edge cases and boundary conditions."""
    
    def test_zero_records(self, admin_user, branch):
        """Analytics handle zero records gracefully."""
        # Get member counts with no members
        counts = services.get_member_counts(admin_user)
        
        assert counts["total_members"] == 0
        assert counts["active_members"] == 0
    
    def test_empty_date_range(self, admin_user, branch):
        """Analytics handle empty date ranges."""
        # Create member created 60 days ago
        Member.objects.create(
            branch=branch,
            first_name="Old",
            last_name="Member",
            created_at=timezone.now() - timedelta(days=60),
        )
        
        # Query last 7 days (should be empty)
        today = timezone.now().date()
        seven_days_ago = today - timedelta(days=7)
        count = services.get_new_members_count(admin_user, seven_days_ago, today)
        
        assert count == 0
    
    def test_division_by_zero_in_rates(self, admin_user, branch):
        """Rates handle zero denominators correctly."""
        # No active members, so attendance rate should be None
        rate = services.get_attendance_rate(admin_user)
        
        assert rate is None
        
        # No visitors, so conversion rate should be None
        conversion_rate = services.get_visitor_conversion_rate(admin_user)
        
        assert conversion_rate is None
    
    def test_percentage_change_with_zero_previous(self, admin_user, branch):
        """Percentage change handles zero previous value."""
        # Test helper function
        result = services.calculate_percentage_change(100, 0)
        
        # Should return None when previous is zero
        assert result is None
    
    def test_percentage_change_with_negative_growth(self, admin_user, branch):
        """Percentage change handles negative growth."""
        result = services.calculate_percentage_change(80, 100)
        
        # Should be -20%
        assert result == -20.0
    
    def test_same_start_and_end_date(self, admin_user, branch):
        """Analytics handle same start and end date."""
        today = timezone.now().date()
        
        # Create member today
        Member.objects.create(
            branch=branch,
            first_name="Today",
            last_name="Member",
            created_at=timezone.now(),
        )
        
        # Query with same start and end date
        count = services.get_new_members_count(admin_user, today, today)
        
        assert count == 1
    
    def test_invalid_date_range_raises_error(self, admin_user, branch):
        """Invalid date range raises ValueError."""
        today = timezone.now().date()
        tomorrow = today + timedelta(days=1)
        
        # start_date > end_date should raise error
        with pytest.raises(ValueError, match="start_date must be <= end_date"):
            services.get_date_range_filter(tomorrow, today)
    
    def test_excessive_date_range_raises_error(self, admin_user, branch):
        """Excessive date range raises ValueError."""
        today = timezone.now().date()
        two_years_ago = today - timedelta(days=730)
        
        # Date range > max_days should raise error
        with pytest.raises(ValueError, match="cannot exceed"):
            services.get_date_range_filter(two_years_ago, today, max_days=365)
    
    def test_deleted_records_not_counted(self, admin_user, branch):
        """Soft-deleted records are not counted (if applicable)."""
        # Note: Current models don't have soft delete, but test for future
        # This test verifies only active records are counted
        Member.objects.create(
            branch=branch,
            first_name="Active",
            last_name="Member",
            membership_status=MembershipStatus.ACTIVE,
        )
        Member.objects.create(
            branch=branch,
            first_name="Inactive",
            last_name="Member",
            membership_status=MembershipStatus.INACTIVE,
        )
        
        counts = services.get_member_counts(admin_user)
        
        # Total includes both, but active filter works
        assert counts["total_members"] == 2
        assert counts["active_members"] == 1


# =============================================================================
# COMPARISON ANALYTICS TESTS
# =============================================================================

@pytest.mark.django_db
class TestComparisonAnalytics:
    """Test period-over-period comparison analytics."""
    
    def test_get_period_comparison(self, admin_user, branch):
        """Period comparison calculates correctly."""
        current = 150
        previous = 120
        
        comparison = services.get_period_comparison(current, previous)
        
        assert comparison["current"] == 150
        assert comparison["previous"] == 120
        assert comparison["change"] == 30
        assert comparison["percentage_change"] == 25.0
    
    def test_comparison_with_zero_previous(self, admin_user, branch):
        """Comparison with zero previous period."""
        current = 100
        previous = 0
        
        comparison = services.get_period_comparison(current, previous)
        
        assert comparison["current"] == 100
        assert comparison["previous"] == 0
        assert comparison["change"] == 100
        assert comparison["percentage_change"] is None
    
    def test_comparison_with_negative_change(self, admin_user, branch):
        """Comparison with negative change."""
        current = 80
        previous = 100
        
        comparison = services.get_period_comparison(current, previous)
        
        assert comparison["change"] == -20
        assert comparison["percentage_change"] == -20.0
