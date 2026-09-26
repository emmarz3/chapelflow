"""
Phase 14: Financial Adjustment Tests

Tests controlled correction mechanism for closed/locked periods:
- Adjustment creation with audit trail
- Approval workflow (PENDING → APPROVED/REJECTED)
- Immutability after approval/rejection
- Branch scoping
- Before/after value tracking
"""
import pytest
from datetime import date
from decimal import Decimal
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError

from apps.finance.models import (
    FinancialAdjustment, AdjustmentStatus,
    FinancialPeriod, FinancialPeriodStatus,
    Giving, GivingCategory, GivingStatus, GivingSource,
    Payment, PaymentStatus
)
from apps.members.models import Member, MembershipStatus
from apps.organizations.models import Branch, Organization
from common.constants.roles import Roles

User = get_user_model()


@pytest.mark.django_db
class TestFinancialAdjustmentLifecycle:
    """Test financial adjustment creation and approval workflow."""
    
    @pytest.fixture
    def setup_data(self):
        """Create test data."""
        _org_1 = Organization.objects.create(name="Test Branch Org", slug="test-feb9bd64")
        branch = Branch.objects.create(name="Test Branch", organization=_org_1)
        creator = User.objects.create_user(
            email="staff@test.com",
            password="test123",
            role=Roles.FINANCE_OFFICER,
            branch=branch
        )
        
        approver = User.objects.create_user(
            email="director@test.com",
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
        
        period = FinancialPeriod.objects.create(
            branch=branch,
            name="January 2026",
            period_start=date(2026, 1, 1),
            period_end=date(2026, 1, 31),
            status=FinancialPeriodStatus.CLOSED
        )
        
        giving = Giving.objects.create(
            branch=branch,
            member=member,
            category=category,
            amount=Decimal('100.00'),
            currency='NGN',
            source=GivingSource.OFFLINE,
            status=GivingStatus.CONFIRMED,
            given_at=timezone.make_aware(
                timezone.datetime(2026, 1, 15, 10, 0, 0)
            )
        )
        
        return {
            'branch': branch,
            'creator': creator,
            'approver': approver,
            'member': member,
            'category': category,
            'period': period,
            'giving': giving
        }
    
    def test_create_adjustment_starts_as_pending(self, setup_data):
        """Test that new adjustments start in PENDING status."""
        adjustment = FinancialAdjustment.objects.create(
            branch=setup_data['branch'],
            financial_period=setup_data['period'],
            giving=setup_data['giving'],
            adjustment_type="Amount Correction",
            field_name="amount",
            old_value="100.00",
            new_value="150.00",
            amount_delta=Decimal('50.00'),
            reason="Original amount was incorrectly entered",
            created_by=setup_data['creator']
        )
        
        assert adjustment.status == AdjustmentStatus.PENDING
        assert adjustment.is_pending
        assert not adjustment.is_approved
        assert not adjustment.is_rejected
        assert adjustment.created_by == setup_data['creator']
        assert adjustment.created_at is not None
    
    def test_approve_pending_adjustment(self, setup_data):
        """Test approving a pending adjustment."""
        adjustment = FinancialAdjustment.objects.create(
            branch=setup_data['branch'],
            financial_period=setup_data['period'],
            adjustment_type="Amount Correction",
            reason="Correction needed",
            created_by=setup_data['creator']
        )
        
        adjustment.approve(setup_data['approver'])
        
        assert adjustment.status == AdjustmentStatus.APPROVED
        assert adjustment.is_approved
        assert adjustment.reviewed_by == setup_data['approver']
        assert adjustment.reviewed_at is not None
    
    def test_reject_pending_adjustment(self, setup_data):
        """Test rejecting a pending adjustment."""
        adjustment = FinancialAdjustment.objects.create(
            branch=setup_data['branch'],
            financial_period=setup_data['period'],
            adjustment_type="Amount Correction",
            reason="Correction needed",
            created_by=setup_data['creator']
        )
        
        adjustment.reject(setup_data['approver'], reason="Insufficient justification")
        
        assert adjustment.status == AdjustmentStatus.REJECTED
        assert adjustment.is_rejected
        assert adjustment.reviewed_by == setup_data['approver']
        assert adjustment.reviewed_at is not None
        assert adjustment.rejection_reason == "Insufficient justification"
    
    def test_cannot_approve_already_approved_adjustment(self, setup_data):
        """Test that approved adjustments cannot be approved again."""
        adjustment = FinancialAdjustment.objects.create(
            branch=setup_data['branch'],
            financial_period=setup_data['period'],
            adjustment_type="Amount Correction",
            reason="Correction needed",
            created_by=setup_data['creator']
        )
        
        adjustment.approve(setup_data['approver'])
        
        # Try to approve again
        with pytest.raises(ValidationError, match="Cannot approve adjustment"):
            adjustment.approve(setup_data['approver'])
    
    def test_cannot_reject_already_rejected_adjustment(self, setup_data):
        """Test that rejected adjustments cannot be rejected again."""
        adjustment = FinancialAdjustment.objects.create(
            branch=setup_data['branch'],
            financial_period=setup_data['period'],
            adjustment_type="Amount Correction",
            reason="Correction needed",
            created_by=setup_data['creator']
        )
        
        adjustment.reject(setup_data['approver'], reason="Not valid")
        
        # Try to reject again
        with pytest.raises(ValidationError, match="Cannot reject adjustment"):
            adjustment.reject(setup_data['approver'], reason="Still not valid")
    
    def test_cannot_approve_rejected_adjustment(self, setup_data):
        """Test that rejected adjustments cannot be approved."""
        adjustment = FinancialAdjustment.objects.create(
            branch=setup_data['branch'],
            financial_period=setup_data['period'],
            adjustment_type="Amount Correction",
            reason="Correction needed",
            created_by=setup_data['creator']
        )
        
        adjustment.reject(setup_data['approver'], reason="Not valid")
        
        # Try to approve after rejection
        with pytest.raises(ValidationError, match="Cannot approve adjustment"):
            adjustment.approve(setup_data['approver'])
    
    def test_rejection_requires_reason(self, setup_data):
        """Test that rejecting an adjustment requires a reason."""
        adjustment = FinancialAdjustment.objects.create(
            branch=setup_data['branch'],
            financial_period=setup_data['period'],
            adjustment_type="Amount Correction",
            reason="Correction needed",
            created_by=setup_data['creator']
        )
        
        # Try to reject without reason
        with pytest.raises(ValidationError, match="Rejection reason is required"):
            adjustment.reject(setup_data['approver'], reason="")
    
    def test_mark_approved_adjustment_as_applied(self, setup_data):
        """Test marking an approved adjustment as applied."""
        adjustment = FinancialAdjustment.objects.create(
            branch=setup_data['branch'],
            financial_period=setup_data['period'],
            adjustment_type="Amount Correction",
            reason="Correction needed",
            created_by=setup_data['creator']
        )
        
        adjustment.approve(setup_data['approver'])
        
        assert adjustment.applied_at is None
        
        adjustment.mark_applied()
        
        assert adjustment.applied_at is not None
    
    def test_cannot_mark_pending_adjustment_as_applied(self, setup_data):
        """Test that pending adjustments cannot be marked as applied."""
        adjustment = FinancialAdjustment.objects.create(
            branch=setup_data['branch'],
            financial_period=setup_data['period'],
            adjustment_type="Amount Correction",
            reason="Correction needed",
            created_by=setup_data['creator']
        )
        
        # Try to mark as applied without approval
        with pytest.raises(ValidationError, match="Can only mark approved"):
            adjustment.mark_applied()
    
    def test_cannot_mark_rejected_adjustment_as_applied(self, setup_data):
        """Test that rejected adjustments cannot be marked as applied."""
        adjustment = FinancialAdjustment.objects.create(
            branch=setup_data['branch'],
            financial_period=setup_data['period'],
            adjustment_type="Amount Correction",
            reason="Correction needed",
            created_by=setup_data['creator']
        )
        
        adjustment.reject(setup_data['approver'], reason="Not valid")
        
        # Try to mark as applied
        with pytest.raises(ValidationError, match="Can only mark approved"):
            adjustment.mark_applied()
    
    def test_cannot_mark_already_applied_adjustment_again(self, setup_data):
        """Test that applied adjustments cannot be marked as applied again."""
        adjustment = FinancialAdjustment.objects.create(
            branch=setup_data['branch'],
            financial_period=setup_data['period'],
            adjustment_type="Amount Correction",
            reason="Correction needed",
            created_by=setup_data['creator']
        )
        
        adjustment.approve(setup_data['approver'])
        adjustment.mark_applied()
        
        # Try to mark as applied again
        with pytest.raises(ValidationError, match="already been marked as applied"):
            adjustment.mark_applied()


@pytest.mark.django_db
class TestFinancialAdjustmentTypes:
    """Test different types of adjustments."""
    
    @pytest.fixture
    def setup_data(self):
        """Create test data."""
        _org_2 = Organization.objects.create(name="Test Branch Org", slug="test-6ed90dd1")
        branch = Branch.objects.create(name="Test Branch", organization=_org_2)
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
        
        period = FinancialPeriod.objects.create(
            branch=branch,
            name="January 2026",
            period_start=date(2026, 1, 1),
            period_end=date(2026, 1, 31),
            status=FinancialPeriodStatus.CLOSED
        )
        
        giving = Giving.objects.create(
            branch=branch,
            member=member,
            category=category,
            amount=Decimal('100.00'),
            currency='NGN',
            source=GivingSource.OFFLINE,
            status=GivingStatus.CONFIRMED,
            given_at=timezone.make_aware(
                timezone.datetime(2026, 1, 15, 10, 0, 0)
            )
        )
        
        return {
            'branch': branch,
            'user': user,
            'member': member,
            'category': category,
            'period': period,
            'giving': giving
        }
    
    def test_amount_correction_adjustment(self, setup_data):
        """Test creating an amount correction adjustment."""
        adjustment = FinancialAdjustment.objects.create(
            branch=setup_data['branch'],
            financial_period=setup_data['period'],
            giving=setup_data['giving'],
            adjustment_type="Amount Correction",
            field_name="amount",
            old_value="100.00",
            new_value="150.00",
            amount_delta=Decimal('50.00'),
            reason="Member informed us they gave $150, not $100",
            created_by=setup_data['user']
        )
        
        assert adjustment.adjustment_type == "Amount Correction"
        assert adjustment.field_name == "amount"
        assert adjustment.old_value == "100.00"
        assert adjustment.new_value == "150.00"
        assert adjustment.amount_delta == Decimal('50.00')
        assert adjustment.giving == setup_data['giving']
    
    def test_category_change_adjustment(self, setup_data):
        """Test creating a category change adjustment."""
        adjustment = FinancialAdjustment.objects.create(
            branch=setup_data['branch'],
            financial_period=setup_data['period'],
            giving=setup_data['giving'],
            adjustment_type="Category Change",
            field_name="category",
            old_value="Tithe",
            new_value="Offering",
            reason="Member specified this was offering, not tithe",
            created_by=setup_data['user']
        )
        
        assert adjustment.adjustment_type == "Category Change"
        assert adjustment.field_name == "category"
        assert adjustment.old_value == "Tithe"
        assert adjustment.new_value == "Offering"
        assert adjustment.amount_delta is None
    
    def test_date_correction_adjustment(self, setup_data):
        """Test creating a date correction adjustment."""
        adjustment = FinancialAdjustment.objects.create(
            branch=setup_data['branch'],
            financial_period=setup_data['period'],
            giving=setup_data['giving'],
            adjustment_type="Date Correction",
            field_name="given_at",
            old_value="2026-01-15",
            new_value="2026-01-20",
            reason="Transaction was actually recorded on wrong date",
            created_by=setup_data['user']
        )
        
        assert adjustment.adjustment_type == "Date Correction"
        assert adjustment.field_name == "given_at"
    
    def test_payment_adjustment(self, setup_data):
        """Test creating an adjustment linked to a payment."""
        payment = Payment.objects.create(
            branch=setup_data['branch'],
            member=setup_data['member'],
            amount=Decimal('100.00'),
            currency='NGN',
            provider='paystack',
            provider_reference='ref_123',
            status=PaymentStatus.SUCCESSFUL,
            confirmed_at=timezone.now()
        )
        
        adjustment = FinancialAdjustment.objects.create(
            branch=setup_data['branch'],
            financial_period=setup_data['period'],
            payment=payment,
            adjustment_type="Gateway Fee Adjustment",
            field_name="amount",
            old_value="100.00",
            new_value="95.00",
            amount_delta=Decimal('-5.00'),
            reason="Gateway deducted $5 fee not initially recorded",
            created_by=setup_data['user']
        )
        
        assert adjustment.payment == payment
        assert adjustment.amount_delta == Decimal('-5.00')
    
    def test_period_level_adjustment_without_specific_record(self, setup_data):
        """Test creating a period-level adjustment not linked to specific record."""
        adjustment = FinancialAdjustment.objects.create(
            branch=setup_data['branch'],
            financial_period=setup_data['period'],
            adjustment_type="Manual Correction",
            reason="Bank reported additional fees for the period totaling $25",
            amount_delta=Decimal('-25.00'),
            created_by=setup_data['user']
        )
        
        assert adjustment.giving is None
        assert adjustment.payment is None
        assert adjustment.financial_period == setup_data['period']
        assert adjustment.amount_delta == Decimal('-25.00')


@pytest.mark.django_db
class TestFinancialAdjustmentAuditTrail:
    """Test adjustment audit trail and immutability."""
    
    @pytest.fixture
    def setup_data(self):
        """Create test data."""
        _org_3 = Organization.objects.create(name="Test Branch Org", slug="test-5c765e05")
        branch = Branch.objects.create(name="Test Branch", organization=_org_3)
        creator = User.objects.create_user(
            email="creator@test.com",
            password="test123",
            role=Roles.FINANCE_OFFICER,
            branch=branch
        )
        
        approver = User.objects.create_user(
            email="approver@test.com",
            password="test123",
            role=Roles.FINANCE_OFFICER,
            branch=branch
        )
        
        period = FinancialPeriod.objects.create(
            branch=branch,
            name="January 2026",
            period_start=date(2026, 1, 1),
            period_end=date(2026, 1, 31),
            status=FinancialPeriodStatus.LOCKED
        )
        
        return {
            'branch': branch,
            'creator': creator,
            'approver': approver,
            'period': period
        }
    
    def test_adjustment_tracks_creator_and_approver(self, setup_data):
        """Test that adjustment tracks both creator and approver."""
        adjustment = FinancialAdjustment.objects.create(
            branch=setup_data['branch'],
            financial_period=setup_data['period'],
            adjustment_type="Amount Correction",
            reason="Correction needed",
            created_by=setup_data['creator']
        )
        
        assert adjustment.created_by == setup_data['creator']
        assert adjustment.created_at is not None
        assert adjustment.reviewed_by is None
        
        adjustment.approve(setup_data['approver'])
        
        assert adjustment.created_by == setup_data['creator']
        assert adjustment.reviewed_by == setup_data['approver']
        assert adjustment.reviewed_at is not None
    
    def test_adjustment_for_locked_period(self, setup_data):
        """Test that adjustments can be created for locked periods."""
        adjustment = FinancialAdjustment.objects.create(
            branch=setup_data['branch'],
            financial_period=setup_data['period'],
            adjustment_type="Amount Correction",
            reason="Error discovered after period was locked",
            created_by=setup_data['creator']
        )
        
        assert adjustment.financial_period.is_locked
        assert adjustment.is_pending
    
    def test_adjustment_ordering_by_created_at(self, setup_data):
        """Test that adjustments are ordered by creation time (newest first)."""
        adj1 = FinancialAdjustment.objects.create(
            branch=setup_data['branch'],
            adjustment_type="Type A",
            reason="First",
            created_by=setup_data['creator']
        )
        
        adj2 = FinancialAdjustment.objects.create(
            branch=setup_data['branch'],
            adjustment_type="Type B",
            reason="Second",
            created_by=setup_data['creator']
        )
        
        adjustments = list(FinancialAdjustment.objects.all())
        
        # Should be ordered newest first
        assert adjustments[0].id == adj2.id
        assert adjustments[1].id == adj1.id
