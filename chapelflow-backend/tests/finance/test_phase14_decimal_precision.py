"""
Phase 14: Decimal Precision Tests

Tests that all financial calculations use Decimal arithmetic, not float:
- Payment webhook processing (kobo to naira conversion)
- Reconciliation amount comparisons
- Difference calculations
- No float rounding errors
"""
import pytest
from decimal import Decimal
from django.utils import timezone
from django.contrib.auth import get_user_model

from apps.finance.models import (
    Payment, PaymentStatus,
    Giving, GivingCategory, GivingStatus, GivingSource,
    Reconciliation, ReconciliationStatus,
    ReconciliationResult, ReconciliationResultType
)
from apps.finance.services import PaystackService, reconcile_gateway_transactions
from apps.members.models import Member, MembershipStatus
from apps.organizations.models import Branch, Organization
from common.constants.roles import Roles

User = get_user_model()


@pytest.mark.django_db
class TestWebhookDecimalPrecision:
    """Test that webhook processing uses Decimal, not float."""
    
    def test_paystack_kobo_to_naira_conversion_uses_decimal(self):
        """Test that Paystack kobo->naira conversion returns Decimal, not float."""
        service = PaystackService()
        
        payload = {
            "event": "charge.success",
            "data": {
                "reference": "test_ref_123",
                "amount": 50000  # 50000 kobo = 500.00 naira
            }
        }
        
        result = service.parse_webhook_event(payload)
        
        # Must be Decimal, not float
        assert isinstance(result["amount"], Decimal)
        assert result["amount"] == Decimal("500.00")
    
    def test_paystack_handles_fractional_kobo(self):
        """Test that fractional kobo amounts are handled correctly."""
        service = PaystackService()
        
        # 12345 kobo = 123.45 naira
        payload = {
            "event": "charge.success",
            "data": {
                "reference": "test_ref_456",
                "amount": 12345
            }
        }
        
        result = service.parse_webhook_event(payload)
        
        assert isinstance(result["amount"], Decimal)
        assert result["amount"] == Decimal("123.45")
    
    def test_paystack_handles_small_amounts(self):
        """Test that small amounts (under 1 naira) are handled correctly."""
        service = PaystackService()
        
        # 50 kobo = 0.50 naira
        payload = {
            "event": "charge.success",
            "data": {
                "reference": "test_ref_small",
                "amount": 50
            }
        }
        
        result = service.parse_webhook_event(payload)
        
        assert isinstance(result["amount"], Decimal)
        assert result["amount"] == Decimal("0.50")
    
    def test_paystack_handles_zero_amount(self):
        """Test that zero amounts are handled correctly."""
        service = PaystackService()
        
        payload = {
            "event": "charge.success",
            "data": {
                "reference": "test_ref_zero",
                "amount": 0
            }
        }
        
        result = service.parse_webhook_event(payload)
        
        assert isinstance(result["amount"], Decimal)
        assert result["amount"] == Decimal("0.00")
    
    def test_paystack_handles_missing_amount(self):
        """Test that missing amount defaults to zero."""
        service = PaystackService()
        
        payload = {
            "event": "charge.success",
            "data": {
                "reference": "test_ref_missing"
                # No amount field
            }
        }
        
        result = service.parse_webhook_event(payload)
        
        assert isinstance(result["amount"], Decimal)
        assert result["amount"] == Decimal("0.00")
    
    def test_no_float_rounding_errors_in_conversion(self):
        """Test that conversion avoids float rounding errors."""
        service = PaystackService()
        
        # Amount that would cause rounding errors with float
        # 33333 kobo = 333.33 naira (repeating decimal)
        payload = {
            "event": "charge.success",
            "data": {
                "reference": "test_ref_rounding",
                "amount": 33333
            }
        }
        
        result = service.parse_webhook_event(payload)
        
        # With float: might get 333.32999999... or 333.33000001
        # With Decimal: exact 333.33
        assert isinstance(result["amount"], Decimal)
        assert result["amount"] == Decimal("333.33")
        
        # Verify no float contamination by checking string representation
        assert str(result["amount"]) == "333.33"


@pytest.mark.django_db
class TestReconciliationDecimalPrecision:
    """Test that reconciliation uses Decimal throughout."""
    
    @pytest.fixture
    def setup_data(self):
        """Create test data."""
        _org_1 = Organization.objects.create(name="Test Branch Org", slug="test-15fdf571")
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
    
    def test_reconciliation_difference_is_decimal(self, setup_data):
        """Test that reconciliation difference is Decimal, not float."""
        recon = Reconciliation.objects.create(
            branch=setup_data['branch'],
            period_start=timezone.now().date(),
            period_end=timezone.now().date(),
            system_total=Decimal('1000.00'),
            bank_total=Decimal('999.99'),
            created_by=setup_data['user']
        )
        
        # Difference should be Decimal
        assert isinstance(recon.difference, Decimal)
        assert recon.difference == Decimal('0.01')
    
    def test_reconciliation_result_amounts_are_decimal(self, setup_data):
        """Test that reconciliation result amounts are Decimal."""
        recon = Reconciliation.objects.create(
            branch=setup_data['branch'],
            period_start=timezone.now().date(),
            period_end=timezone.now().date(),
            system_total=Decimal('1000.00'),
            bank_total=Decimal('1000.00'),
            created_by=setup_data['user']
        )
        
        result = ReconciliationResult.objects.create(
            reconciliation=recon,
            result_type=ReconciliationResultType.AMOUNT_MISMATCH,
            expected_amount=Decimal('100.00'),
            actual_amount=Decimal('99.95')
        )
        
        # All amounts should be Decimal
        assert isinstance(result.expected_amount, Decimal)
        assert isinstance(result.actual_amount, Decimal)
        assert isinstance(result.difference, Decimal)
        assert result.difference == Decimal('0.05')
    
    def test_reconciliation_service_preserves_decimal_in_differences(self, setup_data):
        """Test that reconcile_gateway_transactions preserves Decimal precision."""
        # Create payment
        payment = Payment.objects.create(
            branch=setup_data['branch'],
            member=setup_data['member'],
            amount=Decimal('333.33'),  # Potential float rounding issue
            currency='NGN',
            provider='paystack',
            provider_reference='ref_decimal',
            status=PaymentStatus.SUCCESSFUL,
            confirmed_at=timezone.now()
        )
        
        # Create giving with slightly different amount
        giving = Giving.objects.create(
            branch=setup_data['branch'],
            member=setup_data['member'],
            category=setup_data['category'],
            amount=Decimal('333.30'),
            currency='NGN',
            source=GivingSource.ONLINE,
            status=GivingStatus.CONFIRMED,
            payment=payment,
            given_at=timezone.now()
        )
        
        # Run reconciliation
        result = reconcile_gateway_transactions(
            branch=setup_data['branch'],
            period_start=timezone.now() - timezone.timedelta(days=1),
            period_end=timezone.now() + timezone.timedelta(days=1)
        )
        
        # Should detect mismatch
        assert len(result['mismatches']) == 1
        
        payment_matched, giving_matched, differences = result['mismatches'][0]
        amount_diff = next(d for d in differences if d['field'] == 'amount')
        
        # Difference values should be strings (from Decimal), not float
        assert amount_diff['payment'] == '333.33'
        assert amount_diff['giving'] == '333.30'
        assert amount_diff['difference'] == '0.03'
    
    def test_small_difference_tolerance_is_exact(self, setup_data):
        """Test that 1 cent tolerance is exact, not approximate."""
        recon = Reconciliation.objects.create(
            branch=setup_data['branch'],
            period_start=timezone.now().date(),
            period_end=timezone.now().date(),
            system_total=Decimal('1000.00'),
            bank_total=Decimal('1000.01'),  # Exactly 1 cent difference
            created_by=setup_data['user']
        )
        
        # Should NOT have discrepancy (within 1 cent tolerance)
        assert not recon.has_discrepancy
        
        # But 2 cents should have discrepancy
        recon2 = Reconciliation.objects.create(
            branch=setup_data['branch'],
            period_start=timezone.now().date(),
            period_end=timezone.now().date(),
            system_total=Decimal('1000.00'),
            bank_total=Decimal('1000.02'),  # 2 cents difference
            created_by=setup_data['user']
        )
        
        assert recon2.has_discrepancy
    
    def test_large_amount_precision(self, setup_data):
        """Test that large amounts maintain precision."""
        # Test with large amount that could have float rounding issues
        recon = Reconciliation.objects.create(
            branch=setup_data['branch'],
            period_start=timezone.now().date(),
            period_end=timezone.now().date(),
            system_total=Decimal('9999999.99'),
            bank_total=Decimal('9999999.98'),
            created_by=setup_data['user']
        )
        
        assert isinstance(recon.difference, Decimal)
        assert recon.difference == Decimal('0.01')
        # Verify exact string representation
        assert str(recon.difference) == '0.01'
    
    def test_negative_difference_precision(self, setup_data):
        """Test that negative differences maintain precision."""
        recon = Reconciliation.objects.create(
            branch=setup_data['branch'],
            period_start=timezone.now().date(),
            period_end=timezone.now().date(),
            system_total=Decimal('1000.00'),
            bank_total=Decimal('1000.03'),  # Bank has more
            created_by=setup_data['user']
        )
        
        assert isinstance(recon.difference, Decimal)
        assert recon.difference == Decimal('-0.03')
        assert str(recon.difference) == '-0.03'


@pytest.mark.django_db
class TestPaymentModelDecimalStorage:
    """Test that Payment model stores amounts as Decimal."""
    
    @pytest.fixture
    def setup_data(self):
        """Create test data."""
        _org_2 = Organization.objects.create(name="Test Branch Org", slug="test-1a0909e5")
        branch = Branch.objects.create(name="Test Branch", organization=_org_2)
        member = Member.objects.create(
            branch=branch,
            first_name="Test",
            last_name="Member",
            email="test@test.com",
            membership_status=MembershipStatus.ACTIVE
        )
        
        return {'branch': branch, 'member': member}
    
    def test_payment_amount_stored_as_decimal(self, setup_data):
        """Test that payment amounts are stored as Decimal."""
        payment = Payment.objects.create(
            branch=setup_data['branch'],
            member=setup_data['member'],
            amount=Decimal('123.45'),
            currency='NGN',
            provider='paystack',
            provider_reference='ref_storage',
            status=PaymentStatus.PENDING
        )
        
        # Retrieve from database
        payment_from_db = Payment.objects.get(id=payment.id)
        
        assert isinstance(payment_from_db.amount, Decimal)
        assert payment_from_db.amount == Decimal('123.45')
    
    def test_payment_handles_many_decimal_places(self, setup_data):
        """Test that payment handles amounts with many decimal places."""
        # Create with more precision than stored (should round to 2 places)
        payment = Payment.objects.create(
            branch=setup_data['branch'],
            member=setup_data['member'],
            amount=Decimal('123.456789'),
            currency='NGN',
            provider='paystack',
            provider_reference='ref_precision',
            status=PaymentStatus.PENDING
        )
        
        payment_from_db = Payment.objects.get(id=payment.id)
        
        # Should be rounded to 2 decimal places
        assert isinstance(payment_from_db.amount, Decimal)
        assert payment_from_db.amount == Decimal('123.46')  # Rounded
