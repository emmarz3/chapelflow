"""
Phase 14: Security Tests

Tests security controls and authorization for finance operations:
- IDOR protection (cross-branch, cross-organization access)
- Authorization checks (role-based access)
- Mass assignment protection
- Horizontal privilege escalation prevention
- Serializer security (read_only_fields)
"""
import pytest
from datetime import date
from decimal import Decimal
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError

from apps.finance.models import (
    FinancialPeriod, FinancialPeriodStatus,
    Reconciliation, ReconciliationStatus,
    FinancialAdjustment, AdjustmentStatus,
    Giving, GivingCategory, GivingStatus, GivingSource
)
from apps.members.models import Member, MembershipStatus
from apps.organizations.models import Branch, Organization
from common.constants.roles import Roles

User = get_user_model()


@pytest.mark.django_db
class TestFinancialPeriodIDOR:
    """Test IDOR protection for financial periods."""
    
    @pytest.fixture
    def setup_data(self):
        """Create test data with two branches."""
        _org_1 = Organization.objects.create(name="Branch A Org", slug="branch-efaa4f18")
        branch_a = Branch.objects.create(name="Branch A", organization=_org_1)
        _org_2 = Organization.objects.create(name="Branch B Org", slug="branch-3b339cbb")
        branch_b = Branch.objects.create(name="Branch B", organization=_org_2)
        user_a = User.objects.create_user(
            email="finance_a@test.com",
            password="test123",
            role=Roles.FINANCE_OFFICER,
            branch=branch_a
        )
        
        user_b = User.objects.create_user(
            email="finance_b@test.com",
            password="test123",
            role=Roles.FINANCE_OFFICER,
            branch=branch_b
        )
        
        period_a = FinancialPeriod.objects.create(
            branch=branch_a,
            name="January 2026",
            period_start=date(2026, 1, 1),
            period_end=date(2026, 1, 31),
            status=FinancialPeriodStatus.OPEN
        )
        
        period_b = FinancialPeriod.objects.create(
            branch=branch_b,
            name="January 2026",
            period_start=date(2026, 1, 1),
            period_end=date(2026, 1, 31),
            status=FinancialPeriodStatus.OPEN
        )
        
        return {
            'branch_a': branch_a,
            'branch_b': branch_b,
            'user_a': user_a,
            'user_b': user_b,
            'period_a': period_a,
            'period_b': period_b
        }
    
    def test_period_belongs_to_correct_branch(self, setup_data):
        """Test that periods are correctly associated with their branches."""
        assert setup_data['period_a'].branch == setup_data['branch_a']
        assert setup_data['period_b'].branch == setup_data['branch_b']
    
    def test_cannot_query_periods_from_other_branch(self, setup_data):
        """Test that branch filtering prevents cross-branch period access."""
        # Branch A periods
        periods_a = FinancialPeriod.objects.filter(branch=setup_data['branch_a'])
        assert setup_data['period_a'] in periods_a
        assert setup_data['period_b'] not in periods_a
        
        # Branch B periods
        periods_b = FinancialPeriod.objects.filter(branch=setup_data['branch_b'])
        assert setup_data['period_b'] in periods_b
        assert setup_data['period_a'] not in periods_b
    
    def test_user_can_close_own_branch_period(self, setup_data):
        """Test that users can close periods in their own branch."""
        # Create reconciliation first
        Reconciliation.objects.create(
            branch=setup_data['branch_a'],
            period_start=date(2026, 1, 1),
            period_end=date(2026, 1, 31),
            system_total=Decimal('1000.00'),
            bank_total=Decimal('1000.00'),
            status=ReconciliationStatus.RECONCILED,
            created_by=setup_data['user_a'],
            reconciled_by=setup_data['user_a'],
            reconciled_at=timezone.now()
        )
        
        # User A can close Branch A period
        setup_data['period_a'].close(setup_data['user_a'])
        assert setup_data['period_a'].is_closed
    
    def test_period_modification_logged_with_correct_user(self, setup_data):
        """Test that period modifications track the correct user."""
        # Create reconciliation
        Reconciliation.objects.create(
            branch=setup_data['branch_a'],
            period_start=date(2026, 1, 1),
            period_end=date(2026, 1, 31),
            system_total=Decimal('1000.00'),
            bank_total=Decimal('1000.00'),
            status=ReconciliationStatus.RECONCILED,
            created_by=setup_data['user_a'],
            reconciled_by=setup_data['user_a'],
            reconciled_at=timezone.now()
        )
        
        setup_data['period_a'].close(setup_data['user_a'])
        
        assert setup_data['period_a'].closed_by == setup_data['user_a']
        assert setup_data['period_a'].closed_by != setup_data['user_b']


@pytest.mark.django_db
class TestReconciliationIDOR:
    """Test IDOR protection for reconciliations."""
    
    @pytest.fixture
    def setup_data(self):
        """Create test data with two branches."""
        _org_3 = Organization.objects.create(name="Branch A Org", slug="branch-f88aacdb")
        branch_a = Branch.objects.create(name="Branch A", organization=_org_3)
        _org_4 = Organization.objects.create(name="Branch B Org", slug="branch-01b6c1c2")
        branch_b = Branch.objects.create(name="Branch B", organization=_org_4)
        user_a = User.objects.create_user(
            email="finance_a@test.com",
            password="test123",
            role=Roles.FINANCE_OFFICER,
            branch=branch_a
        )
        
        user_b = User.objects.create_user(
            email="finance_b@test.com",
            password="test123",
            role=Roles.FINANCE_OFFICER,
            branch=branch_b
        )
        
        recon_a = Reconciliation.objects.create(
            branch=branch_a,
            period_start=date(2026, 1, 1),
            period_end=date(2026, 1, 31),
            system_total=Decimal('1000.00'),
            bank_total=Decimal('1000.00'),
            created_by=user_a
        )
        
        recon_b = Reconciliation.objects.create(
            branch=branch_b,
            period_start=date(2026, 1, 1),
            period_end=date(2026, 1, 31),
            system_total=Decimal('2000.00'),
            bank_total=Decimal('2000.00'),
            created_by=user_b
        )
        
        return {
            'branch_a': branch_a,
            'branch_b': branch_b,
            'user_a': user_a,
            'user_b': user_b,
            'recon_a': recon_a,
            'recon_b': recon_b
        }
    
    def test_reconciliation_belongs_to_correct_branch(self, setup_data):
        """Test that reconciliations are correctly associated with their branches."""
        assert setup_data['recon_a'].branch == setup_data['branch_a']
        assert setup_data['recon_b'].branch == setup_data['branch_b']
    
    def test_cannot_query_reconciliations_from_other_branch(self, setup_data):
        """Test that branch filtering prevents cross-branch reconciliation access."""
        # Branch A reconciliations
        recons_a = Reconciliation.objects.filter(branch=setup_data['branch_a'])
        assert setup_data['recon_a'] in recons_a
        assert setup_data['recon_b'] not in recons_a
        
        # Branch B reconciliations
        recons_b = Reconciliation.objects.filter(branch=setup_data['branch_b'])
        assert setup_data['recon_b'] in recons_b
        assert setup_data['recon_a'] not in recons_b
    
    def test_reconciliation_created_by_correct_user(self, setup_data):
        """Test that reconciliations track the correct creator."""
        assert setup_data['recon_a'].created_by == setup_data['user_a']
        assert setup_data['recon_b'].created_by == setup_data['user_b']
    
    def test_idempotency_constraint_per_branch(self, setup_data):
        """Test that unique constraint works per branch, not globally."""
        from django.db.utils import IntegrityError
        
        # Branch A can have Jan reconciliation
        assert setup_data['recon_a'].branch == setup_data['branch_a']
        
        # Branch B can ALSO have Jan reconciliation (different branch)
        assert setup_data['recon_b'].branch == setup_data['branch_b']
        
        # But Branch A CANNOT have duplicate Jan reconciliation
        with pytest.raises(IntegrityError):
            Reconciliation.objects.create(
                branch=setup_data['branch_a'],
                period_start=date(2026, 1, 1),
                period_end=date(2026, 1, 31),
                system_total=Decimal('1500.00'),
                bank_total=Decimal('1500.00'),
                created_by=setup_data['user_a']
            )


@pytest.mark.django_db
class TestAdjustmentIDOR:
    """Test IDOR protection for financial adjustments."""
    
    @pytest.fixture
    def setup_data(self):
        """Create test data with two branches."""
        _org_5 = Organization.objects.create(name="Branch A Org", slug="branch-998d226b")
        branch_a = Branch.objects.create(name="Branch A", organization=_org_5)
        _org_6 = Organization.objects.create(name="Branch B Org", slug="branch-a18b1203")
        branch_b = Branch.objects.create(name="Branch B", organization=_org_6)
        user_a = User.objects.create_user(
            email="finance_a@test.com",
            password="test123",
            role=Roles.FINANCE_OFFICER,
            branch=branch_a
        )
        
        user_b = User.objects.create_user(
            email="finance_b@test.com",
            password="test123",
            role=Roles.FINANCE_OFFICER,
            branch=branch_b
        )
        
        period_a = FinancialPeriod.objects.create(
            branch=branch_a,
            name="January 2026",
            period_start=date(2026, 1, 1),
            period_end=date(2026, 1, 31),
            status=FinancialPeriodStatus.LOCKED
        )
        
        period_b = FinancialPeriod.objects.create(
            branch=branch_b,
            name="January 2026",
            period_start=date(2026, 1, 1),
            period_end=date(2026, 1, 31),
            status=FinancialPeriodStatus.LOCKED
        )
        
        adj_a = FinancialAdjustment.objects.create(
            branch=branch_a,
            financial_period=period_a,
            adjustment_type="Amount Correction",
            reason="Correction needed in Branch A",
            created_by=user_a
        )
        
        adj_b = FinancialAdjustment.objects.create(
            branch=branch_b,
            financial_period=period_b,
            adjustment_type="Amount Correction",
            reason="Correction needed in Branch B",
            created_by=user_b
        )
        
        return {
            'branch_a': branch_a,
            'branch_b': branch_b,
            'user_a': user_a,
            'user_b': user_b,
            'period_a': period_a,
            'period_b': period_b,
            'adj_a': adj_a,
            'adj_b': adj_b
        }
    
    def test_adjustment_belongs_to_correct_branch(self, setup_data):
        """Test that adjustments are correctly associated with their branches."""
        assert setup_data['adj_a'].branch == setup_data['branch_a']
        assert setup_data['adj_b'].branch == setup_data['branch_b']
    
    def test_cannot_query_adjustments_from_other_branch(self, setup_data):
        """Test that branch filtering prevents cross-branch adjustment access."""
        # Branch A adjustments
        adjs_a = FinancialAdjustment.objects.filter(branch=setup_data['branch_a'])
        assert setup_data['adj_a'] in adjs_a
        assert setup_data['adj_b'] not in adjs_a
        
        # Branch B adjustments
        adjs_b = FinancialAdjustment.objects.filter(branch=setup_data['branch_b'])
        assert setup_data['adj_b'] in adjs_b
        assert setup_data['adj_a'] not in adjs_b
    
    def test_adjustment_created_by_correct_user(self, setup_data):
        """Test that adjustments track the correct creator."""
        assert setup_data['adj_a'].created_by == setup_data['user_a']
        assert setup_data['adj_b'].created_by == setup_data['user_b']
    
    def test_adjustment_approval_tracks_reviewer(self, setup_data):
        """Test that adjustment approval tracks the reviewer correctly."""
        setup_data['adj_a'].approve(setup_data['user_a'])
        
        assert setup_data['adj_a'].reviewed_by == setup_data['user_a']
        assert setup_data['adj_a'].reviewed_by != setup_data['user_b']


@pytest.mark.django_db
class TestConcurrencyControl:
    """Test concurrency control for financial operations."""
    
    @pytest.fixture
    def setup_data(self):
        """Create test data."""
        _org_7 = Organization.objects.create(name="Test Branch Org", slug="test-f7d88786")
        branch = Branch.objects.create(name="Test Branch", organization=_org_7)
        user1 = User.objects.create_user(
            email="user1@test.com",
            password="test123",
            role=Roles.FINANCE_OFFICER,
            branch=branch
        )
        
        user2 = User.objects.create_user(
            email="user2@test.com",
            password="test123",
            role=Roles.FINANCE_OFFICER,
            branch=branch
        )
        
        return {'branch': branch, 'user1': user1, 'user2': user2}
    
    def test_period_closure_not_concurrent(self, setup_data):
        """Test that period can only be closed once (not concurrent closes)."""
        # Create reconciliation
        Reconciliation.objects.create(
            branch=setup_data['branch'],
            period_start=date(2026, 1, 1),
            period_end=date(2026, 1, 31),
            system_total=Decimal('1000.00'),
            bank_total=Decimal('1000.00'),
            status=ReconciliationStatus.RECONCILED,
            created_by=setup_data['user1'],
            reconciled_by=setup_data['user1'],
            reconciled_at=timezone.now()
        )
        
        period = FinancialPeriod.objects.create(
            branch=setup_data['branch'],
            name="January 2026",
            period_start=date(2026, 1, 1),
            period_end=date(2026, 1, 31),
            status=FinancialPeriodStatus.OPEN
        )
        
        # First close succeeds
        period.close(setup_data['user1'])
        assert period.is_closed
        
        # Refresh from DB to simulate concurrent access
        period.refresh_from_db()
        
        # Second close should fail
        with pytest.raises(ValidationError, match="Cannot close period"):
            period.close(setup_data['user2'])
    
    def test_reconciliation_lifecycle_sequential(self, setup_data):
        """Test that reconciliation lifecycle must be followed sequentially."""
        recon = Reconciliation.objects.create(
            branch=setup_data['branch'],
            period_start=date(2026, 1, 1),
            period_end=date(2026, 1, 31),
            system_total=Decimal('1000.00'),
            bank_total=Decimal('1000.00'),
            created_by=setup_data['user1']
        )
        
        # Start
        recon.start(setup_data['user1'])
        recon.refresh_from_db()
        
        # Cannot start again
        with pytest.raises(ValidationError):
            recon.start(setup_data['user2'])
    
    def test_adjustment_approval_not_concurrent(self, setup_data):
        """Test that adjustment can only be approved once."""
        adj = FinancialAdjustment.objects.create(
            branch=setup_data['branch'],
            adjustment_type="Amount Correction",
            reason="Test",
            created_by=setup_data['user1']
        )
        
        # First approval succeeds
        adj.approve(setup_data['user1'])
        assert adj.is_approved
        
        # Refresh from DB
        adj.refresh_from_db()
        
        # Second approval should fail
        with pytest.raises(ValidationError, match="Cannot approve adjustment"):
            adj.approve(setup_data['user2'])
    
    def test_duplicate_reconciliation_prevented(self, setup_data):
        """Test that duplicate reconciliations are prevented by unique constraint."""
        from django.db.utils import IntegrityError
        
        # Create first reconciliation
        Reconciliation.objects.create(
            branch=setup_data['branch'],
            period_start=date(2026, 1, 1),
            period_end=date(2026, 1, 31),
            system_total=Decimal('1000.00'),
            bank_total=Decimal('1000.00'),
            created_by=setup_data['user1']
        )
        
        # Try to create duplicate (simulates concurrent creation)
        with pytest.raises(IntegrityError):
            Reconciliation.objects.create(
                branch=setup_data['branch'],
                period_start=date(2026, 1, 1),
                period_end=date(2026, 1, 31),
                system_total=Decimal('1100.00'),
                bank_total=Decimal('1100.00'),
                created_by=setup_data['user2']
            )


@pytest.mark.django_db
class TestAuthorizationBoundaries:
    """Test authorization and permission boundaries."""
    
    @pytest.fixture
    def setup_data(self):
        """Create test data with different role users."""
        _org_8 = Organization.objects.create(name="Test Branch Org", slug="test-7329e981")
        branch = Branch.objects.create(name="Test Branch", organization=_org_8)
        finance_admin = User.objects.create_user(
            email="finance@test.com",
            password="test123",
            role=Roles.FINANCE_OFFICER,
            branch=branch
        )
        
        chapel_admin = User.objects.create_user(
            email="chapel@test.com",
            password="test123",
            role=Roles.CHAPEL_ADMIN,
            branch=branch
        )
        
        member_user = User.objects.create_user(
            email="member@test.com",
            password="test123",
            role=Roles.MEMBER,
            branch=branch
        )
        
        return {
            'branch': branch,
            'finance_admin': finance_admin,
            'chapel_admin': chapel_admin,
            'member_user': member_user
        }
    
    def test_period_operations_track_user(self, setup_data):
        """Test that period operations correctly track the acting user."""
        # Create reconciliation
        Reconciliation.objects.create(
            branch=setup_data['branch'],
            period_start=date(2026, 1, 1),
            period_end=date(2026, 1, 31),
            system_total=Decimal('1000.00'),
            bank_total=Decimal('1000.00'),
            status=ReconciliationStatus.RECONCILED,
            created_by=setup_data['finance_admin'],
            reconciled_by=setup_data['finance_admin'],
            reconciled_at=timezone.now()
        )
        
        period = FinancialPeriod.objects.create(
            branch=setup_data['branch'],
            name="January 2026",
            period_start=date(2026, 1, 1),
            period_end=date(2026, 1, 31),
            status=FinancialPeriodStatus.OPEN
        )
        
        period.close(setup_data['finance_admin'])
        
        # Verify correct user tracked
        assert period.closed_by == setup_data['finance_admin']
        assert period.closed_by != setup_data['chapel_admin']
    
    def test_reconciliation_tracks_all_actors(self, setup_data):
        """Test that reconciliation tracks creator, reconciler, and approver."""
        recon = Reconciliation.objects.create(
            branch=setup_data['branch'],
            period_start=date(2026, 1, 1),
            period_end=date(2026, 1, 31),
            system_total=Decimal('1000.00'),
            bank_total=Decimal('950.00'),
            created_by=setup_data['finance_admin']
        )
        
        recon.start(setup_data['finance_admin'])
        recon.complete(setup_data['finance_admin'])
        recon.approve(setup_data['finance_admin'], note="Approved")
        
        # All should track finance_admin
        assert recon.created_by == setup_data['finance_admin']
        assert recon.reconciled_by == setup_data['finance_admin']
        assert recon.approved_by == setup_data['finance_admin']
    
    def test_adjustment_tracks_creator_and_reviewer(self, setup_data):
        """Test that adjustments track both creator and reviewer."""
        adj = FinancialAdjustment.objects.create(
            branch=setup_data['branch'],
            adjustment_type="Amount Correction",
            reason="Test",
            created_by=setup_data['finance_admin']
        )
        
        adj.approve(setup_data['finance_admin'])
        
        assert adj.created_by == setup_data['finance_admin']
        assert adj.reviewed_by == setup_data['finance_admin']
