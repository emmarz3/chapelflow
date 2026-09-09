"""
Phase 14: Reconciliation Lifecycle Tests

Tests reconciliation status lifecycle, idempotency, and business logic:
- Status transitions (PENDING → IN_PROGRESS → RECONCILED/DISCREPANCY → APPROVED)
- Automatic discrepancy detection
- Difference calculation
- Idempotency (unique constraint on period)
- Branch scoping
- Audit trail tracking
"""
import pytest
from datetime import date, timedelta
from decimal import Decimal
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db.utils import IntegrityError

from apps.finance.models import (
    Reconciliation, ReconciliationStatus,
    Giving, GivingCategory, GivingStatus, GivingSource,
    Payment, PaymentStatus
)
from apps.members.models import Member, MembershipStatus
from apps.organizations.models import Branch, Organization
from common.constants.roles import Roles

User = get_user_model()


@pytest.mark.django_db
class TestReconciliationLifecycle:
    """Test reconciliation status lifecycle transitions."""
    
    @pytest.fixture
    def setup_data(self):
        """Create test data."""
        _org_1 = Organization.objects.create(name="Test Branch Org", slug="test-47327583")
        branch = Branch.objects.create(name="Test Branch", organization=_org_1)
        user = User.objects.create_user(
            email="finance@test.com",
            password="test123",
            role=Roles.FINANCE_OFFICER,
            branch=branch
        )
        
        return {'branch': branch, 'user': user}
    
    def test_reconciliation_created_as_pending(self, setup_data):
        """Test that new reconciliations start in PENDING status."""
        recon = Reconciliation.objects.create(
            branch=setup_data['branch'],
            period_start=date(2026, 1, 1),
            period_end=date(2026, 1, 31),
            system_total=Decimal('1000.00'),
            bank_total=Decimal('1000.00'),
            created_by=setup_data['user']
        )
        
        assert recon.status == ReconciliationStatus.PENDING
        assert recon.is_pending
        assert not recon.is_in_progress
        assert not recon.is_reconciled
        assert not recon.is_discrepancy
        assert recon.created_by == setup_data['user']
        assert recon.created_at is not None
    
    def test_start_pending_reconciliation(self, setup_data):
        """Test starting a pending reconciliation."""
        recon = Reconciliation.objects.create(
            branch=setup_data['branch'],
            period_start=date(2026, 1, 1),
            period_end=date(2026, 1, 31),
            system_total=Decimal('1000.00'),
            bank_total=Decimal('1000.00'),
            created_by=setup_data['user']
        )
        
        recon.start(setup_data['user'])
        
        assert recon.status == ReconciliationStatus.IN_PROGRESS
        assert recon.is_in_progress
        assert not recon.is_pending
    
    def test_cannot_start_non_pending_reconciliation(self, setup_data):
        """Test that only PENDING reconciliations can be started."""
        recon = Reconciliation.objects.create(
            branch=setup_data['branch'],
            period_start=date(2026, 1, 1),
            period_end=date(2026, 1, 31),
            system_total=Decimal('1000.00'),
            bank_total=Decimal('1000.00'),
            created_by=setup_data['user']
        )
        
        recon.start(setup_data['user'])
        
        # Try to start again
        with pytest.raises(ValidationError, match="Cannot start reconciliation"):
            recon.start(setup_data['user'])
    
    def test_complete_reconciliation_perfect_match(self, setup_data):
        """Test completing reconciliation with matching totals (RECONCILED)."""
        recon = Reconciliation.objects.create(
            branch=setup_data['branch'],
            period_start=date(2026, 1, 1),
            period_end=date(2026, 1, 31),
            system_total=Decimal('1000.00'),
            bank_total=Decimal('1000.00'),
            created_by=setup_data['user']
        )
        
        recon.start(setup_data['user'])
        recon.complete(setup_data['user'])
        
        assert recon.status == ReconciliationStatus.RECONCILED
        assert recon.is_reconciled
        assert recon.difference == Decimal('0.00')
        assert not recon.has_discrepancy
        assert recon.reconciled_by == setup_data['user']
        assert recon.reconciled_at is not None
    
    def test_complete_reconciliation_with_discrepancy(self, setup_data):
        """Test completing reconciliation with mismatched totals (DISCREPANCY)."""
        recon = Reconciliation.objects.create(
            branch=setup_data['branch'],
            period_start=date(2026, 1, 1),
            period_end=date(2026, 1, 31),
            system_total=Decimal('1000.00'),
            bank_total=Decimal('950.00'),  # $50 short
            created_by=setup_data['user']
        )
        
        recon.start(setup_data['user'])
        recon.complete(setup_data['user'])
        
        assert recon.status == ReconciliationStatus.DISCREPANCY
        assert recon.is_discrepancy
        assert recon.difference == Decimal('50.00')  # system - bank
        assert recon.has_discrepancy
        assert recon.reconciled_by == setup_data['user']
        assert recon.reconciled_at is not None
    
    def test_difference_calculated_on_save(self, setup_data):
        """Test that difference is automatically calculated on save."""
        recon = Reconciliation.objects.create(
            branch=setup_data['branch'],
            period_start=date(2026, 1, 1),
            period_end=date(2026, 1, 31),
            system_total=Decimal('1000.00'),
            bank_total=Decimal('975.50'),
            created_by=setup_data['user']
        )
        
        assert recon.difference == Decimal('24.50')
    
    def test_negative_difference_when_bank_exceeds_system(self, setup_data):
        """Test difference is negative when bank total exceeds system."""
        recon = Reconciliation.objects.create(
            branch=setup_data['branch'],
            period_start=date(2026, 1, 1),
            period_end=date(2026, 1, 31),
            system_total=Decimal('1000.00'),
            bank_total=Decimal('1050.00'),  # Bank has more
            created_by=setup_data['user']
        )
        
        assert recon.difference == Decimal('-50.00')
        assert recon.has_discrepancy
    
    def test_cannot_complete_non_in_progress_reconciliation(self, setup_data):
        """Test that only IN_PROGRESS reconciliations can be completed."""
        recon = Reconciliation.objects.create(
            branch=setup_data['branch'],
            period_start=date(2026, 1, 1),
            period_end=date(2026, 1, 31),
            system_total=Decimal('1000.00'),
            bank_total=Decimal('1000.00'),
            created_by=setup_data['user']
        )
        
        # Try to complete without starting
        with pytest.raises(ValidationError, match="Cannot complete reconciliation"):
            recon.complete(setup_data['user'])
    
    def test_approve_discrepancy(self, setup_data):
        """Test approving a reconciliation with discrepancy."""
        recon = Reconciliation.objects.create(
            branch=setup_data['branch'],
            period_start=date(2026, 1, 1),
            period_end=date(2026, 1, 31),
            system_total=Decimal('1000.00'),
            bank_total=Decimal('980.00'),
            created_by=setup_data['user']
        )
        
        recon.start(setup_data['user'])
        recon.complete(setup_data['user'])
        
        assert recon.is_discrepancy
        
        # Approve with note
        recon.approve(setup_data['user'], note="Bank fees accounted for")
        
        assert recon.status == ReconciliationStatus.APPROVED
        assert recon.is_approved
        assert recon.approved_by == setup_data['user']
        assert recon.approved_at is not None
        assert recon.discrepancy_note == "Bank fees accounted for"
    
    def test_cannot_approve_non_discrepancy_reconciliation(self, setup_data):
        """Test that only DISCREPANCY reconciliations can be approved."""
        recon = Reconciliation.objects.create(
            branch=setup_data['branch'],
            period_start=date(2026, 1, 1),
            period_end=date(2026, 1, 31),
            system_total=Decimal('1000.00'),
            bank_total=Decimal('1000.00'),  # Perfect match
            created_by=setup_data['user']
        )
        
        recon.start(setup_data['user'])
        recon.complete(setup_data['user'])
        
        assert recon.is_reconciled
        
        # Try to approve (should fail - no discrepancy)
        with pytest.raises(ValidationError, match="Cannot approve reconciliation"):
            recon.approve(setup_data['user'])
    
    def test_has_discrepancy_with_small_difference(self, setup_data):
        """Test that discrepancy detection has 1 cent tolerance."""
        # Exactly 1 cent - should NOT have discrepancy
        recon1 = Reconciliation.objects.create(
            branch=setup_data['branch'],
            period_start=date(2026, 1, 1),
            period_end=date(2026, 1, 31),
            system_total=Decimal('1000.00'),
            bank_total=Decimal('1000.01'),
            created_by=setup_data['user']
        )
        assert not recon1.has_discrepancy
        
        # More than 1 cent - should have discrepancy
        recon2 = Reconciliation.objects.create(
            branch=setup_data['branch'],
            period_start=date(2026, 2, 1),
            period_end=date(2026, 2, 28),
            system_total=Decimal('1000.00'),
            bank_total=Decimal('1000.02'),
            created_by=setup_data['user']
        )
        assert recon2.has_discrepancy


@pytest.mark.django_db
class TestReconciliationIdempotency:
    """Test reconciliation idempotency and uniqueness constraints."""
    
    @pytest.fixture
    def setup_data(self):
        """Create test data."""
        _org_2 = Organization.objects.create(name="Test Branch Org", slug="test-993e7b40")
        branch = Branch.objects.create(name="Test Branch", organization=_org_2)
        user = User.objects.create_user(
            email="finance@test.com",
            password="test123",
            role=Roles.FINANCE_OFFICER,
            branch=branch
        )
        
        return {'branch': branch, 'user': user}
    
    def test_cannot_create_duplicate_reconciliation_same_period(self, setup_data):
        """Test that duplicate reconciliations for same period are prevented."""
        # Create first reconciliation
        Reconciliation.objects.create(
            branch=setup_data['branch'],
            period_start=date(2026, 1, 1),
            period_end=date(2026, 1, 31),
            system_total=Decimal('1000.00'),
            bank_total=Decimal('1000.00'),
            created_by=setup_data['user']
        )
        
        # Try to create duplicate
        with pytest.raises(IntegrityError):
            Reconciliation.objects.create(
                branch=setup_data['branch'],
                period_start=date(2026, 1, 1),
                period_end=date(2026, 1, 31),
                system_total=Decimal('1100.00'),
                bank_total=Decimal('1100.00'),
                created_by=setup_data['user']
            )
    
    def test_can_create_reconciliation_different_periods(self, setup_data):
        """Test that reconciliations for different periods are allowed."""
        # January
        recon1 = Reconciliation.objects.create(
            branch=setup_data['branch'],
            period_start=date(2026, 1, 1),
            period_end=date(2026, 1, 31),
            system_total=Decimal('1000.00'),
            bank_total=Decimal('1000.00'),
            created_by=setup_data['user']
        )
        
        # February
        recon2 = Reconciliation.objects.create(
            branch=setup_data['branch'],
            period_start=date(2026, 2, 1),
            period_end=date(2026, 2, 28),
            system_total=Decimal('1100.00'),
            bank_total=Decimal('1100.00'),
            created_by=setup_data['user']
        )
        
        assert recon1.id != recon2.id
    
    def test_can_create_reconciliation_same_period_different_branches(self, setup_data):
        """Test that same period reconciliations allowed in different branches."""
        _org_3 = Organization.objects.create(name="Branch B Org", slug="branch-ea6344d2")
        branch_b = Branch.objects.create(name="Branch B", organization=_org_3)
        # Branch A reconciliation
        recon_a = Reconciliation.objects.create(
            branch=setup_data['branch'],
            period_start=date(2026, 1, 1),
            period_end=date(2026, 1, 31),
            system_total=Decimal('1000.00'),
            bank_total=Decimal('1000.00'),
            created_by=setup_data['user']
        )
        
        # Branch B reconciliation (same period)
        recon_b = Reconciliation.objects.create(
            branch=branch_b,
            period_start=date(2026, 1, 1),
            period_end=date(2026, 1, 31),
            system_total=Decimal('2000.00'),
            bank_total=Decimal('2000.00'),
            created_by=setup_data['user']
        )
        
        assert recon_a.id != recon_b.id
        assert recon_a.branch != recon_b.branch


@pytest.mark.django_db
class TestReconciliationAuditTrail:
    """Test reconciliation audit trail tracking."""
    
    @pytest.fixture
    def setup_data(self):
        """Create test data with multiple users."""
        _org_4 = Organization.objects.create(name="Test Branch Org", slug="test-0085a72e")
        branch = Branch.objects.create(name="Test Branch", organization=_org_4)
        creator = User.objects.create_user(
            email="creator@test.com",
            password="test123",
            role=Roles.FINANCE_OFFICER,
            branch=branch
        )
        
        reconciler = User.objects.create_user(
            email="reconciler@test.com",
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
        
        return {
            'branch': branch,
            'creator': creator,
            'reconciler': reconciler,
            'approver': approver
        }
    
    def test_audit_trail_tracks_all_users(self, setup_data):
        """Test that audit trail captures creator, reconciler, and approver."""
        # Create
        recon = Reconciliation.objects.create(
            branch=setup_data['branch'],
            period_start=date(2026, 1, 1),
            period_end=date(2026, 1, 31),
            system_total=Decimal('1000.00'),
            bank_total=Decimal('950.00'),
            created_by=setup_data['creator']
        )
        
        assert recon.created_by == setup_data['creator']
        assert recon.created_at is not None
        assert recon.reconciled_by is None
        assert recon.approved_by is None
        
        # Start and complete
        recon.start(setup_data['reconciler'])
        recon.complete(setup_data['reconciler'])
        
        assert recon.reconciled_by == setup_data['reconciler']
        assert recon.reconciled_at is not None
        assert recon.approved_by is None
        
        # Approve
        recon.approve(setup_data['approver'], note="Approved")
        
        assert recon.approved_by == setup_data['approver']
        assert recon.approved_at is not None
        
        # All three users tracked
        assert recon.created_by == setup_data['creator']
        assert recon.reconciled_by == setup_data['reconciler']
        assert recon.approved_by == setup_data['approver']
    
    def test_timestamps_are_sequential(self, setup_data):
        """Test that timestamps progress correctly through lifecycle."""
        recon = Reconciliation.objects.create(
            branch=setup_data['branch'],
            period_start=date(2026, 1, 1),
            period_end=date(2026, 1, 31),
            system_total=Decimal('1000.00'),
            bank_total=Decimal('950.00'),
            created_by=setup_data['creator']
        )
        
        created_at = recon.created_at
        
        recon.start(setup_data['reconciler'])
        recon.complete(setup_data['reconciler'])
        
        reconciled_at = recon.reconciled_at
        assert reconciled_at >= created_at
        
        recon.approve(setup_data['approver'])
        
        approved_at = recon.approved_at
        assert approved_at >= reconciled_at



@pytest.mark.django_db
class TestReconciliationResult:
    """Test reconciliation result tracking for detailed discrepancy analysis."""
    
    @pytest.fixture
    def setup_data(self):
        """Create test data."""
        from apps.finance.models import ReconciliationResult, ReconciliationResultType
        
        _org_5 = Organization.objects.create(name="Test Branch Org", slug="test-67b6c256")
        
        branch = Branch.objects.create(name="Test Branch", organization=_org_5)
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
        
        reconciliation = Reconciliation.objects.create(
            branch=branch,
            period_start=date(2026, 1, 1),
            period_end=date(2026, 1, 31),
            system_total=Decimal('1000.00'),
            bank_total=Decimal('950.00'),
            created_by=user
        )
        
        return {
            'branch': branch,
            'user': user,
            'member': member,
            'category': category,
            'reconciliation': reconciliation,
            'ReconciliationResult': ReconciliationResult,
            'ReconciliationResultType': ReconciliationResultType
        }
    
    def test_create_matched_result(self, setup_data):
        """Test creating a matched result (payment + giving)."""
        ReconciliationResult = setup_data['ReconciliationResult']
        ReconciliationResultType = setup_data['ReconciliationResultType']
        
        # Create payment
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
        
        # Create giving
        giving = Giving.objects.create(
            branch=setup_data['branch'],
            member=setup_data['member'],
            category=setup_data['category'],
            amount=Decimal('100.00'),
            currency='NGN',
            source=GivingSource.ONLINE,
            status=GivingStatus.CONFIRMED,
            given_at=timezone.now()
        )
        
        # Create matched result
        result = ReconciliationResult.objects.create(
            reconciliation=setup_data['reconciliation'],
            result_type=ReconciliationResultType.MATCHED,
            payment=payment,
            giving=giving,
            expected_amount=Decimal('100.00'),
            actual_amount=Decimal('100.00')
        )
        
        assert result.result_type == ReconciliationResultType.MATCHED
        assert result.payment == payment
        assert result.giving == giving
        assert result.difference == Decimal('0.00')
        assert result.expected_amount == result.actual_amount
    
    def test_create_unmatched_payment_result(self, setup_data):
        """Test creating unmatched payment result (payment without giving)."""
        ReconciliationResult = setup_data['ReconciliationResult']
        ReconciliationResultType = setup_data['ReconciliationResultType']
        
        # Create payment (no corresponding giving)
        payment = Payment.objects.create(
            branch=setup_data['branch'],
            member=setup_data['member'],
            amount=Decimal('50.00'),
            currency='NGN',
            provider='paystack',
            provider_reference='ref_orphan',
            status=PaymentStatus.SUCCESSFUL,
            confirmed_at=timezone.now()
        )
        
        # Create unmatched payment result
        result = ReconciliationResult.objects.create(
            reconciliation=setup_data['reconciliation'],
            result_type=ReconciliationResultType.UNMATCHED_PAYMENT,
            payment=payment,
            giving=None,  # No giving
            expected_amount=None,
            actual_amount=Decimal('50.00')
        )
        
        assert result.result_type == ReconciliationResultType.UNMATCHED_PAYMENT
        assert result.payment == payment
        assert result.giving is None
        assert result.actual_amount == Decimal('50.00')
        assert result.expected_amount is None
    
    def test_create_unmatched_giving_result(self, setup_data):
        """Test creating unmatched giving result (giving without payment)."""
        ReconciliationResult = setup_data['ReconciliationResult']
        ReconciliationResultType = setup_data['ReconciliationResultType']
        
        # Create giving (no corresponding payment)
        giving = Giving.objects.create(
            branch=setup_data['branch'],
            member=setup_data['member'],
            category=setup_data['category'],
            amount=Decimal('75.00'),
            currency='NGN',
            source=GivingSource.OFFLINE,  # Cash giving, no payment
            status=GivingStatus.CONFIRMED,
            given_at=timezone.now()
        )
        
        # Create unmatched giving result
        result = ReconciliationResult.objects.create(
            reconciliation=setup_data['reconciliation'],
            result_type=ReconciliationResultType.UNMATCHED_GIVING,
            payment=None,  # No payment
            giving=giving,
            expected_amount=Decimal('75.00'),
            actual_amount=None
        )
        
        assert result.result_type == ReconciliationResultType.UNMATCHED_GIVING
        assert result.payment is None
        assert result.giving == giving
        assert result.expected_amount == Decimal('75.00')
        assert result.actual_amount is None
    
    def test_create_amount_mismatch_result(self, setup_data):
        """Test creating amount mismatch result (amounts don't match)."""
        ReconciliationResult = setup_data['ReconciliationResult']
        ReconciliationResultType = setup_data['ReconciliationResultType']
        
        # Create payment
        payment = Payment.objects.create(
            branch=setup_data['branch'],
            member=setup_data['member'],
            amount=Decimal('95.00'),  # Payment amount
            currency='NGN',
            provider='paystack',
            provider_reference='ref_mismatch',
            status=PaymentStatus.SUCCESSFUL,
            confirmed_at=timezone.now()
        )
        
        # Create giving with different amount
        giving = Giving.objects.create(
            branch=setup_data['branch'],
            member=setup_data['member'],
            category=setup_data['category'],
            amount=Decimal('100.00'),  # Different amount
            currency='NGN',
            source=GivingSource.ONLINE,
            status=GivingStatus.CONFIRMED,
            given_at=timezone.now()
        )
        
        # Create mismatch result
        result = ReconciliationResult.objects.create(
            reconciliation=setup_data['reconciliation'],
            result_type=ReconciliationResultType.AMOUNT_MISMATCH,
            payment=payment,
            giving=giving,
            expected_amount=Decimal('100.00'),
            actual_amount=Decimal('95.00'),
            notes="Possible gateway fee deduction"
        )
        
        assert result.result_type == ReconciliationResultType.AMOUNT_MISMATCH
        assert result.payment == payment
        assert result.giving == giving
        assert result.difference == Decimal('5.00')  # expected - actual
        assert result.notes == "Possible gateway fee deduction"
    
    def test_difference_calculated_automatically(self, setup_data):
        """Test that difference is calculated automatically on save."""
        ReconciliationResult = setup_data['ReconciliationResult']
        ReconciliationResultType = setup_data['ReconciliationResultType']
        
        result = ReconciliationResult.objects.create(
            reconciliation=setup_data['reconciliation'],
            result_type=ReconciliationResultType.AMOUNT_MISMATCH,
            expected_amount=Decimal('100.00'),
            actual_amount=Decimal('97.50')
        )
        
        assert result.difference == Decimal('2.50')
    
    def test_negative_difference_when_actual_exceeds_expected(self, setup_data):
        """Test difference is negative when actual exceeds expected."""
        ReconciliationResult = setup_data['ReconciliationResult']
        ReconciliationResultType = setup_data['ReconciliationResultType']
        
        result = ReconciliationResult.objects.create(
            reconciliation=setup_data['reconciliation'],
            result_type=ReconciliationResultType.AMOUNT_MISMATCH,
            expected_amount=Decimal('100.00'),
            actual_amount=Decimal('105.00')  # More than expected
        )
        
        assert result.difference == Decimal('-5.00')
    
    def test_results_cascade_deleted_with_reconciliation(self, setup_data):
        """Test that results are deleted when reconciliation is deleted."""
        ReconciliationResult = setup_data['ReconciliationResult']
        ReconciliationResultType = setup_data['ReconciliationResultType']
        
        # Create multiple results
        for i in range(3):
            ReconciliationResult.objects.create(
                reconciliation=setup_data['reconciliation'],
                result_type=ReconciliationResultType.MATCHED,
                expected_amount=Decimal('100.00'),
                actual_amount=Decimal('100.00')
            )
        
        recon_id = setup_data['reconciliation'].id
        assert ReconciliationResult.objects.filter(reconciliation_id=recon_id).count() == 3
        
        # Delete reconciliation
        setup_data['reconciliation'].delete()
        
        # Results should be cascade deleted
        assert ReconciliationResult.objects.filter(reconciliation_id=recon_id).count() == 0
    
    def test_multiple_results_per_reconciliation(self, setup_data):
        """Test that one reconciliation can have many results."""
        ReconciliationResult = setup_data['ReconciliationResult']
        ReconciliationResultType = setup_data['ReconciliationResultType']
        
        # Create matched result
        result1 = ReconciliationResult.objects.create(
            reconciliation=setup_data['reconciliation'],
            result_type=ReconciliationResultType.MATCHED,
            expected_amount=Decimal('100.00'),
            actual_amount=Decimal('100.00')
        )
        
        # Create unmatched payment
        result2 = ReconciliationResult.objects.create(
            reconciliation=setup_data['reconciliation'],
            result_type=ReconciliationResultType.UNMATCHED_PAYMENT,
            actual_amount=Decimal('50.00')
        )
        
        # Create amount mismatch
        result3 = ReconciliationResult.objects.create(
            reconciliation=setup_data['reconciliation'],
            result_type=ReconciliationResultType.AMOUNT_MISMATCH,
            expected_amount=Decimal('200.00'),
            actual_amount=Decimal('195.00')
        )
        
        # Check all results linked to same reconciliation
        results = setup_data['reconciliation'].results.all()
        assert results.count() == 3
        assert result1 in results
        assert result2 in results
        assert result3 in results
    
    def test_result_ordering_by_created_at(self, setup_data):
        """Test that results are ordered by creation time."""
        ReconciliationResult = setup_data['ReconciliationResult']
        ReconciliationResultType = setup_data['ReconciliationResultType']
        
        # Create results in sequence
        result1 = ReconciliationResult.objects.create(
            reconciliation=setup_data['reconciliation'],
            result_type=ReconciliationResultType.MATCHED,
            expected_amount=Decimal('100.00'),
            actual_amount=Decimal('100.00')
        )
        
        result2 = ReconciliationResult.objects.create(
            reconciliation=setup_data['reconciliation'],
            result_type=ReconciliationResultType.UNMATCHED_PAYMENT,
            actual_amount=Decimal('50.00')
        )
        
        # Query results
        results = list(setup_data['reconciliation'].results.all())
        
        # Should be in creation order
        assert results[0].id == result1.id
        assert results[1].id == result2.id
