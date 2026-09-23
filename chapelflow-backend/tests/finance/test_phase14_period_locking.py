"""
Phase 14: Financial Period Locking Security Tests

Tests security controls for:
- Period status transitions (OPEN -> CLOSED -> LOCKED)
- Immutability enforcement
- Authorization for close/lock/reopen operations
- Giving record protection in closed/locked periods
"""
import pytest
from datetime import date, timedelta
from decimal import Decimal
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError

from apps.finance.models import (
    FinancialPeriod, FinancialPeriodStatus,
    Giving, GivingCategory, GivingStatus, GivingSource,
    Payment, PaymentStatus,
    Reconciliation, ReconciliationStatus
)
from apps.members.models import Member, MembershipStatus
from apps.organizations.models import Branch, Organization
from common.constants.roles import Roles

User = get_user_model()


@pytest.mark.django_db
class TestFinancialPeriodLifecycle:
    """Test financial period status transitions and security."""
    
    @pytest.fixture
    def branch(self):
        """Create test branch."""
        return Branch.objects.create(name="Test Branch")
    
    @pytest.fixture
    def users(self, branch):
        """Create users with different roles."""
        finance_admin = User.objects.create_user(
            email="finance@test.com",
            password="test123",
            role=Roles.FINANCE_OFFICER,
            branch=branch
        )
        
        regular_staff = User.objects.create_user(
            email="staff@test.com",
            password="test123",
            role=Roles.CHAPEL_ADMIN,
            branch=branch
        )
        
        return {'finance_admin': finance_admin, 'regular_staff': regular_staff}
    
    @pytest.fixture
    def period(self, branch):
        """Create open financial period."""
        return FinancialPeriod.objects.create(
            branch=branch,
            name="January 2026",
            period_start=date(2026, 1, 1),
            period_end=date(2026, 1, 31),
            status=FinancialPeriodStatus.OPEN
        )
    
    def test_close_open_period(self, period, users):
        """Test closing an open period."""
        assert period.is_open
        assert not period.is_closed
        assert not period.is_locked
        
        # Close the period
        period.close(users['finance_admin'])
        
        assert not period.is_open
        assert period.is_closed
        assert period.status == FinancialPeriodStatus.CLOSED
        assert period.closed_by == users['finance_admin']
        assert period.closed_at is not None
    
    def test_cannot_close_already_closed_period(self, period, users):
        """Test that closing a closed period raises error."""
        period.close(users['finance_admin'])
        
        # Try to close again
        with pytest.raises(ValidationError, match="Cannot close period"):
            period.close(users['finance_admin'])
    
    def test_lock_closed_period(self, period, users):
        """Test locking a closed period."""
        # Close first
        period.close(users['finance_admin'])
        
        # Then lock
        period.lock(users['finance_admin'])
        
        assert not period.is_open
        assert not period.is_closed
        assert period.is_locked
        assert period.status == FinancialPeriodStatus.LOCKED
        assert period.locked_by == users['finance_admin']
        assert period.locked_at is not None
    
    def test_cannot_lock_open_period(self, period, users):
        """Test that locking an open period raises error (must close first)."""
        with pytest.raises(ValidationError, match="Must be CLOSED first"):
            period.lock(users['finance_admin'])
    
    def test_cannot_lock_already_locked_period(self, period, users):
        """Test that locking a locked period raises error."""
        period.close(users['finance_admin'])
        period.lock(users['finance_admin'])
        
        # Try to lock again
        with pytest.raises(ValidationError, match="Cannot lock period"):
            period.lock(users['finance_admin'])
    
    def test_reopen_closed_period(self, period, users):
        """Test reopening a closed period (emergency fix)."""
        period.close(users['finance_admin'])
        assert period.is_closed
        
        # Reopen
        period.reopen(users['finance_admin'])
        
        assert period.is_open
        assert period.status == FinancialPeriodStatus.OPEN
        assert period.closed_by is None
        assert period.closed_at is None
    
    def test_cannot_reopen_locked_period(self, period, users):
        """Test that locked periods cannot be reopened (immutable)."""
        period.close(users['finance_admin'])
        period.lock(users['finance_admin'])
        
        # Try to reopen
        with pytest.raises(ValidationError, match="Cannot reopen LOCKED period"):
            period.reopen(users['finance_admin'])
    
    def test_cannot_reopen_already_open_period(self, period, users):
        """Test that reopening an open period raises error."""
        with pytest.raises(ValidationError, match="Can only reopen CLOSED periods"):
            period.reopen(users['finance_admin'])


@pytest.mark.django_db
class TestFinancialPeriodClosureValidation:
    """Test period closure validation checks."""
    
    @pytest.fixture
    def setup_data(self):
        """Create test data."""
        _org_1 = Organization.objects.create(name="Test Branch Org", slug="test-4570be34")
        branch = Branch.objects.create(name="Test Branch", organization=_org_1)
        user = User.objects.create_user(
            email="finance@test.com",
            password="test123",
            role=Roles.FINANCE_OFFICER,
            branch=branch
        )
        
        member = Member.objects.create(
            branch=branch,
            first_name="Test",
            last_name="Member",
            email="test@test.com",
            membership_status=MembershipStatus.ACTIVE
        )
        
        category = GivingCategory.objects.create(
            name="Tithe",
            description="Regular tithe"
        )
        
        return {
            'branch': branch,
            'user': user,
            'member': member,
            'category': category
        }
    
    def test_cannot_close_period_with_pending_payments(self, setup_data):
        """Test that periods with pending payments cannot be closed."""
        period = FinancialPeriod.objects.create(
            branch=setup_data['branch'],
            name="January 2026",
            period_start=date(2026, 1, 1),
            period_end=date(2026, 1, 31),
            status=FinancialPeriodStatus.OPEN
        )
        
        # Create pending payment within period
        Payment.objects.create(
            branch=setup_data['branch'],
            member=setup_data['member'],
            amount=Decimal('100.00'),
            currency='NGN',
            provider='paystack',
            provider_reference='ref_pending',
            status=PaymentStatus.PENDING,
            created_at=timezone.make_aware(
                timezone.datetime(2026, 1, 15, 10, 0, 0)
            )
        )
        
        # Try to close period
        with pytest.raises(ValidationError, match="pending payment"):
            period.close(setup_data['user'])
        
        # Period should still be open
        period.refresh_from_db()
        assert period.is_open
    
    def test_cannot_close_period_without_reconciliation(self, setup_data):
        """Test that periods without reconciliation cannot be closed."""
        period = FinancialPeriod.objects.create(
            branch=setup_data['branch'],
            name="January 2026",
            period_start=date(2026, 1, 1),
            period_end=date(2026, 1, 31),
            status=FinancialPeriodStatus.OPEN
        )
        
        # No reconciliation created for this period
        
        # Try to close period
        with pytest.raises(ValidationError, match="No completed reconciliation"):
            period.close(setup_data['user'])
        
        # Period should still be open
        period.refresh_from_db()
        assert period.is_open
    
    def test_can_close_period_with_reconciled_status(self, setup_data):
        """Test that period can be closed if reconciliation is RECONCILED."""
        period = FinancialPeriod.objects.create(
            branch=setup_data['branch'],
            name="January 2026",
            period_start=date(2026, 1, 1),
            period_end=date(2026, 1, 31),
            status=FinancialPeriodStatus.OPEN
        )
        
        # Create completed reconciliation
        reconciliation = Reconciliation.objects.create(
            branch=setup_data['branch'],
            period_start=date(2026, 1, 1),
            period_end=date(2026, 1, 31),
            system_total=Decimal('1000.00'),
            bank_total=Decimal('1000.00'),
            status=ReconciliationStatus.RECONCILED,
            created_by=setup_data['user'],
            reconciled_by=setup_data['user'],
            reconciled_at=timezone.now()
        )
        
        # Close period should succeed
        period.close(setup_data['user'])
        
        assert period.is_closed
        assert period.closed_by == setup_data['user']
    
    def test_can_close_period_with_approved_reconciliation(self, setup_data):
        """Test that period can be closed if reconciliation discrepancy is APPROVED."""
        period = FinancialPeriod.objects.create(
            branch=setup_data['branch'],
            name="January 2026",
            period_start=date(2026, 1, 1),
            period_end=date(2026, 1, 31),
            status=FinancialPeriodStatus.OPEN
        )
        
        # Create approved reconciliation (had discrepancy but was approved)
        reconciliation = Reconciliation.objects.create(
            branch=setup_data['branch'],
            period_start=date(2026, 1, 1),
            period_end=date(2026, 1, 31),
            system_total=Decimal('1000.00'),
            bank_total=Decimal('980.00'),
            status=ReconciliationStatus.APPROVED,
            created_by=setup_data['user'],
            reconciled_by=setup_data['user'],
            reconciled_at=timezone.now(),
            approved_by=setup_data['user'],
            approved_at=timezone.now()
        )
        
        # Close period should succeed
        period.close(setup_data['user'])
        
        assert period.is_closed
    
    def test_cannot_close_period_with_pending_reconciliation(self, setup_data):
        """Test that period cannot be closed if reconciliation is still PENDING."""
        period = FinancialPeriod.objects.create(
            branch=setup_data['branch'],
            name="January 2026",
            period_start=date(2026, 1, 1),
            period_end=date(2026, 1, 31),
            status=FinancialPeriodStatus.OPEN
        )
        
        # Create pending reconciliation (not completed)
        reconciliation = Reconciliation.objects.create(
            branch=setup_data['branch'],
            period_start=date(2026, 1, 1),
            period_end=date(2026, 1, 31),
            system_total=Decimal('1000.00'),
            bank_total=Decimal('1000.00'),
            status=ReconciliationStatus.PENDING,  # Not completed
            created_by=setup_data['user']
        )
        
        # Try to close period
        with pytest.raises(ValidationError, match="No completed reconciliation"):
            period.close(setup_data['user'])
    
    def test_cannot_close_period_with_unapproved_discrepancy(self, setup_data):
        """Test that period cannot be closed if reconciliation has unapproved discrepancy."""
        period = FinancialPeriod.objects.create(
            branch=setup_data['branch'],
            name="January 2026",
            period_start=date(2026, 1, 1),
            period_end=date(2026, 1, 31),
            status=FinancialPeriodStatus.OPEN
        )
        
        # Create reconciliation with discrepancy (not approved)
        reconciliation = Reconciliation.objects.create(
            branch=setup_data['branch'],
            period_start=date(2026, 1, 1),
            period_end=date(2026, 1, 31),
            system_total=Decimal('1000.00'),
            bank_total=Decimal('950.00'),
            status=ReconciliationStatus.DISCREPANCY,  # Has discrepancy
            created_by=setup_data['user'],
            reconciled_by=setup_data['user'],
            reconciled_at=timezone.now()
        )
        
        # Try to close period
        with pytest.raises(ValidationError, match="No completed reconciliation"):
            period.close(setup_data['user'])
    
    def test_skip_checks_allows_emergency_closure(self, setup_data):
        """Test that skip_checks=True allows closing without validation."""
        period = FinancialPeriod.objects.create(
            branch=setup_data['branch'],
            name="January 2026",
            period_start=date(2026, 1, 1),
            period_end=date(2026, 1, 31),
            status=FinancialPeriodStatus.OPEN
        )
        
        # Create pending payment (would normally block closure)
        Payment.objects.create(
            branch=setup_data['branch'],
            member=setup_data['member'],
            amount=Decimal('100.00'),
            currency='NGN',
            provider='paystack',
            provider_reference='ref_pending',
            status=PaymentStatus.PENDING,
            created_at=timezone.make_aware(
                timezone.datetime(2026, 1, 15, 10, 0, 0)
            )
        )
        
        # No reconciliation either
        
        # Close with skip_checks (emergency override)
        period.close(setup_data['user'], skip_checks=True)
        
        # Should succeed despite validation failures
        assert period.is_closed
        assert period.closed_by == setup_data['user']
    
    def test_voided_giving_generates_warning(self, setup_data):
        """Test that voided giving records generate warning in validation."""
        period = FinancialPeriod.objects.create(
            branch=setup_data['branch'],
            name="January 2026",
            period_start=date(2026, 1, 1),
            period_end=date(2026, 1, 31),
            status=FinancialPeriodStatus.OPEN
        )
        
        # Create voided giving
        Giving.objects.create(
            branch=setup_data['branch'],
            member=setup_data['member'],
            category=setup_data['category'],
            amount=Decimal('100.00'),
            currency='NGN',
            source=GivingSource.OFFLINE,
            status=GivingStatus.VOIDED,
            given_at=timezone.make_aware(
                timezone.datetime(2026, 1, 15, 10, 0, 0)
            )
        )
        
        # Try to close period
        with pytest.raises(ValidationError, match="voided giving"):
            period.close(setup_data['user'])
    
    def test_successful_payments_do_not_block_closure(self, setup_data):
        """Test that successful payments do not prevent closure."""
        period = FinancialPeriod.objects.create(
            branch=setup_data['branch'],
            name="January 2026",
            period_start=date(2026, 1, 1),
            period_end=date(2026, 1, 31),
            status=FinancialPeriodStatus.OPEN
        )
        
        # Create successful payment
        Payment.objects.create(
            branch=setup_data['branch'],
            member=setup_data['member'],
            amount=Decimal('100.00'),
            currency='NGN',
            provider='paystack',
            provider_reference='ref_success',
            status=PaymentStatus.SUCCESSFUL,
            created_at=timezone.make_aware(
                timezone.datetime(2026, 1, 15, 10, 0, 0)
            ),
            confirmed_at=timezone.now()
        )
        
        # Create reconciliation
        Reconciliation.objects.create(
            branch=setup_data['branch'],
            period_start=date(2026, 1, 1),
            period_end=date(2026, 1, 31),
            system_total=Decimal('100.00'),
            bank_total=Decimal('100.00'),
            status=ReconciliationStatus.RECONCILED,
            created_by=setup_data['user'],
            reconciled_by=setup_data['user'],
            reconciled_at=timezone.now()
        )
        
        # Close should succeed (successful payment OK)
        period.close(setup_data['user'])
        
        assert period.is_closed
    
    def test_payments_outside_period_do_not_affect_closure(self, setup_data):
        """Test that payments outside period dates don't block closure."""
        period = FinancialPeriod.objects.create(
            branch=setup_data['branch'],
            name="January 2026",
            period_start=date(2026, 1, 1),
            period_end=date(2026, 1, 31),
            status=FinancialPeriodStatus.OPEN
        )
        
        # Create pending payment OUTSIDE period (February)
        Payment.objects.create(
            branch=setup_data['branch'],
            member=setup_data['member'],
            amount=Decimal('100.00'),
            currency='NGN',
            provider='paystack',
            provider_reference='ref_feb',
            status=PaymentStatus.PENDING,
            created_at=timezone.make_aware(
                timezone.datetime(2026, 2, 5, 10, 0, 0)  # February
            )
        )
        
        # Create reconciliation for January
        Reconciliation.objects.create(
            branch=setup_data['branch'],
            period_start=date(2026, 1, 1),
            period_end=date(2026, 1, 31),
            system_total=Decimal('0.00'),
            bank_total=Decimal('0.00'),
            status=ReconciliationStatus.RECONCILED,
            created_by=setup_data['user'],
            reconciled_by=setup_data['user'],
            reconciled_at=timezone.now()
        )
        
        # Close should succeed (payment is in February, not January)
        period.close(setup_data['user'])
        
        assert period.is_closed


@pytest.mark.django_db
class TestFinancialPeriodValidation:
    """Test financial period validation constraints."""
    
    @pytest.fixture
    def branch(self):
        """Create test branch."""
        return Branch.objects.create(name="Test Branch")
    
    def test_period_start_must_be_before_end(self, branch):
        """Test that period start date must be before end date."""
        with pytest.raises(ValidationError, match="must be after start date"):
            FinancialPeriod.objects.create(
                branch=branch,
                name="Invalid Period",
                period_start=date(2026, 1, 31),
                period_end=date(2026, 1, 1)  # End before start
            )
    
    def test_period_start_cannot_equal_end(self, branch):
        """Test that period start and end cannot be the same day."""
        with pytest.raises(ValidationError, match="must be after start date"):
            FinancialPeriod.objects.create(
                branch=branch,
                name="Single Day Period",
                period_start=date(2026, 1, 15),
                period_end=date(2026, 1, 15)  # Same day
            )
    
    def test_cannot_create_overlapping_period_exact_duplicate(self, branch):
        """Test that exact duplicate periods are prevented."""
        # Create first period
        FinancialPeriod.objects.create(
            branch=branch,
            name="January 2026",
            period_start=date(2026, 1, 1),
            period_end=date(2026, 1, 31)
        )
        
        # Try to create exact duplicate
        with pytest.raises(ValidationError, match="overlaps with existing period"):
            FinancialPeriod.objects.create(
                branch=branch,
                name="January 2026 Duplicate",
                period_start=date(2026, 1, 1),
                period_end=date(2026, 1, 31)
            )
    
    def test_cannot_create_overlapping_period_partial_overlap(self, branch):
        """Test that partially overlapping periods are prevented."""
        # Create first period (Jan 1-31)
        FinancialPeriod.objects.create(
            branch=branch,
            name="January 2026",
            period_start=date(2026, 1, 1),
            period_end=date(2026, 1, 31)
        )
        
        # Try to create overlapping period (Jan 15 - Feb 15)
        with pytest.raises(ValidationError, match="overlaps with existing period"):
            FinancialPeriod.objects.create(
                branch=branch,
                name="Jan-Feb 2026",
                period_start=date(2026, 1, 15),
                period_end=date(2026, 2, 15)
            )
    
    def test_cannot_create_period_contained_within_existing(self, branch):
        """Test that periods fully contained within existing periods are prevented."""
        # Create first period (Jan 1-31)
        FinancialPeriod.objects.create(
            branch=branch,
            name="January 2026",
            period_start=date(2026, 1, 1),
            period_end=date(2026, 1, 31)
        )
        
        # Try to create period inside existing (Jan 10-20)
        with pytest.raises(ValidationError, match="overlaps with existing period"):
            FinancialPeriod.objects.create(
                branch=branch,
                name="Mid-January 2026",
                period_start=date(2026, 1, 10),
                period_end=date(2026, 1, 20)
            )
    
    def test_cannot_create_period_containing_existing(self, branch):
        """Test that periods containing existing periods are prevented."""
        # Create first period (Jan 10-20)
        FinancialPeriod.objects.create(
            branch=branch,
            name="Mid-January 2026",
            period_start=date(2026, 1, 10),
            period_end=date(2026, 1, 20)
        )
        
        # Try to create period containing existing (Jan 1-31)
        with pytest.raises(ValidationError, match="overlaps with existing period"):
            FinancialPeriod.objects.create(
                branch=branch,
                name="January 2026",
                period_start=date(2026, 1, 1),
                period_end=date(2026, 1, 31)
            )
    
    def test_can_create_adjacent_periods(self, branch):
        """Test that adjacent (non-overlapping) periods are allowed."""
        # Create January period
        jan_period = FinancialPeriod.objects.create(
            branch=branch,
            name="January 2026",
            period_start=date(2026, 1, 1),
            period_end=date(2026, 1, 31)
        )
        
        # Create February period (adjacent, no overlap)
        feb_period = FinancialPeriod.objects.create(
            branch=branch,
            name="February 2026",
            period_start=date(2026, 2, 1),
            period_end=date(2026, 2, 28)
        )
        
        assert jan_period.id is not None
        assert feb_period.id is not None
    
    def test_overlapping_periods_allowed_in_different_branches(self, branch):
        """Test that overlapping periods are allowed if in different branches."""
        _org_2 = Organization.objects.create(name="Branch B Org", slug="branch-df05a1f5")
        branch_b = Branch.objects.create(name="Branch B", organization=_org_2)
        # Create January period in Branch A
        period_a = FinancialPeriod.objects.create(
            branch=branch,
            name="January 2026",
            period_start=date(2026, 1, 1),
            period_end=date(2026, 1, 31)
        )
        
        # Create overlapping period in Branch B (should succeed)
        period_b = FinancialPeriod.objects.create(
            branch=branch_b,
            name="January 2026",
            period_start=date(2026, 1, 1),
            period_end=date(2026, 1, 31)
        )
        
        assert period_a.id is not None
        assert period_b.id is not None
        assert period_a.branch != period_b.branch
    
    def test_can_update_period_without_creating_overlap(self, branch):
        """Test that existing periods can be updated if no overlap created."""
        # Create two adjacent periods
        jan_period = FinancialPeriod.objects.create(
            branch=branch,
            name="January 2026",
            period_start=date(2026, 1, 1),
            period_end=date(2026, 1, 31)
        )
        
        feb_period = FinancialPeriod.objects.create(
            branch=branch,
            name="February 2026",
            period_start=date(2026, 2, 1),
            period_end=date(2026, 2, 28)
        )
        
        # Update January name (no date change)
        jan_period.name = "January 2026 Updated"
        jan_period.save()  # Should succeed
        
        assert jan_period.name == "January 2026 Updated"
    
    def test_cannot_update_period_to_create_overlap(self, branch):
        """Test that updating a period to overlap with another is prevented."""
        # Create two adjacent periods
        jan_period = FinancialPeriod.objects.create(
            branch=branch,
            name="January 2026",
            period_start=date(2026, 1, 1),
            period_end=date(2026, 1, 31)
        )
        
        feb_period = FinancialPeriod.objects.create(
            branch=branch,
            name="February 2026",
            period_start=date(2026, 2, 1),
            period_end=date(2026, 2, 28)
        )
        
        # Try to extend January into February
        jan_period.period_end = date(2026, 2, 15)
        
        with pytest.raises(ValidationError, match="overlaps with existing period"):
            jan_period.save()


@pytest.mark.django_db
class TestGivingPeriodEnforcement:
    """Test that giving records respect financial period constraints."""
    
    @pytest.fixture
    def setup_data(self):
        """Create test data for giving period tests."""
        _org_3 = Organization.objects.create(name="Test Branch Org", slug="test-42d2c8ad")
        branch = Branch.objects.create(name="Test Branch", organization=_org_3)
        member = Member.objects.create(
            branch=branch,
            first_name="Test",
            last_name="Member",
            email="test@test.com",
            membership_status=MembershipStatus.ACTIVE
        )
        
        category = GivingCategory.objects.create(
            name="Tithe",
            description="Regular tithe"
        )
        
        # Create closed period for January
        closed_period = FinancialPeriod.objects.create(
            branch=branch,
            name="January 2026",
            period_start=date(2026, 1, 1),
            period_end=date(2026, 1, 31),
            status=FinancialPeriodStatus.CLOSED
        )
        
        # Create locked period for December
        locked_period = FinancialPeriod.objects.create(
            branch=branch,
            name="December 2025",
            period_start=date(2025, 12, 1),
            period_end=date(2025, 12, 31),
            status=FinancialPeriodStatus.LOCKED
        )
        
        # Create open period for February
        open_period = FinancialPeriod.objects.create(
            branch=branch,
            name="February 2026",
            period_start=date(2026, 2, 1),
            period_end=date(2026, 2, 28),
            status=FinancialPeriodStatus.OPEN
        )
        
        return {
            'branch': branch,
            'member': member,
            'category': category,
            'closed_period': closed_period,
            'locked_period': locked_period,
            'open_period': open_period
        }
    
    def test_cannot_modify_giving_in_closed_period(self, setup_data):
        """Test that giving records in closed periods cannot be modified."""
        # Create giving in closed period (January)
        giving = Giving.objects.create(
            branch=setup_data['branch'],
            member=setup_data['member'],
            category=setup_data['category'],
            amount=Decimal('100.00'),
            currency='NGN',
            source=GivingSource.OFFLINE,
            status=GivingStatus.CONFIRMED,
            given_at=timezone.make_aware(
                timezone.datetime(2026, 1, 15, 10, 0, 0)
            )
        )
        
        # Try to modify amount
        giving.amount = Decimal('150.00')
        
        # Should raise ValidationError when validate_giving_period is called
        from apps.finance.models import validate_giving_period
        with pytest.raises(ValidationError, match="CLOSED"):
            validate_giving_period(giving)
    
    def test_cannot_modify_giving_in_locked_period(self, setup_data):
        """Test that giving records in locked periods cannot be modified."""
        # Create giving in locked period (December)
        giving = Giving.objects.create(
            branch=setup_data['branch'],
            member=setup_data['member'],
            category=setup_data['category'],
            amount=Decimal('200.00'),
            currency='NGN',
            source=GivingSource.OFFLINE,
            status=GivingStatus.CONFIRMED,
            given_at=timezone.make_aware(
                timezone.datetime(2025, 12, 20, 10, 0, 0)
            )
        )
        
        # Try to modify
        giving.amount = Decimal('250.00')
        
        from apps.finance.models import validate_giving_period
        with pytest.raises(ValidationError, match="LOCKED"):
            validate_giving_period(giving)
    
    def test_can_modify_giving_in_open_period(self, setup_data):
        """Test that giving records in open periods can be modified."""
        # Create giving in open period (February)
        giving = Giving.objects.create(
            branch=setup_data['branch'],
            member=setup_data['member'],
            category=setup_data['category'],
            amount=Decimal('300.00'),
            currency='NGN',
            source=GivingSource.OFFLINE,
            status=GivingStatus.CONFIRMED,
            given_at=timezone.make_aware(
                timezone.datetime(2026, 2, 10, 10, 0, 0)
            )
        )
        
        # Modify amount
        giving.amount = Decimal('350.00')
        
        # Should not raise error
        from apps.finance.models import validate_giving_period
        validate_giving_period(giving)  # No exception = success
    
    def test_can_create_giving_outside_any_period(self, setup_data):
        """Test that giving can be created for dates not covered by any period."""
        # Create giving in March (no period defined)
        giving = Giving.objects.create(
            branch=setup_data['branch'],
            member=setup_data['member'],
            category=setup_data['category'],
            amount=Decimal('400.00'),
            currency='NGN',
            source=GivingSource.OFFLINE,
            status=GivingStatus.CONFIRMED,
            given_at=timezone.make_aware(
                timezone.datetime(2026, 3, 15, 10, 0, 0)
            )
        )
        
        # Should succeed (no period = no restrictions)
        assert giving.id is not None


@pytest.mark.django_db
class TestReconciliationSecurity:
    """Test reconciliation service security."""
    
    def test_reconciliation_respects_branch_boundaries(self, setup_data):
        """Test that reconciliation only matches within same branch."""
        from apps.finance.services import reconcile_gateway_transactions
        from apps.finance.models import Payment, PaymentStatus
        
        branch_a = setup_data['branch']
        _org_4 = Organization.objects.create(name="Branch B Org", slug="branch-620ed9a4")
        branch_b = Branch.objects.create(name="Branch B", organization=_org_4)
        # Create payment in Branch A
        payment_a = Payment.objects.create(
            branch=branch_a,
            member=setup_data['member'],
            amount=Decimal('100.00'),
            currency='NGN',
            provider='paystack',
            provider_reference='ref_a',
            status=PaymentStatus.SUCCESSFUL,
            confirmed_at=timezone.now()
        )
        
        # Create giving in Branch B (different branch)
        member_b = Member.objects.create(
            branch=branch_b,
            first_name="Bob",
            last_name="Brown",
            email="bob@test.com",
            membership_status=MembershipStatus.ACTIVE
        )
        
        giving_b = Giving.objects.create(
            branch=branch_b,
            member=member_b,
            category=setup_data['category'],
            amount=Decimal('100.00'),
            currency='NGN',
            source=GivingSource.ONLINE,
            status=GivingStatus.CONFIRMED,
            given_at=timezone.now()
        )
        
        # Reconcile Branch A
        period_start = timezone.now() - timedelta(days=1)
        period_end = timezone.now() + timedelta(days=1)
        
        result = reconcile_gateway_transactions(branch_a, period_start, period_end)
        
        # Branch B giving should not appear in results
        assert giving_b not in result['matched']
        assert giving_b not in result['unmatched_giving']
        
        # Payment A should appear as unmatched (no Branch A giving)
        assert payment_a in result['unmatched_payments']
