from decimal import Decimal, InvalidOperation
from django.db import models
from rest_framework import serializers

from common.serializers.validators import ScopedFKValidationMixin
from .models import (
    FinancialStatement, Giving, GivingCategory, Payment, Pledge, Reconciliation, Refund,
    FinancialPeriod, ReconciliationResult, FinancialAdjustment
)


class GivingCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = GivingCategory
        fields = ["id", "name", "description", "is_active"]


class GivingSerializer(ScopedFKValidationMixin, serializers.ModelSerializer):
    """
    Phase 8 hardened: Critical mass assignment vulnerabilities fixed.
    
    Security model:
    - branch: Server-controlled (derived from user or explicit validation)
    - member: Server-controlled for self-service, validated for staff
    - recorded_by: Always server-controlled
    - given_at: Server-controlled
    - payment: Read-only (webhook-controlled)
    - status: Read-only (service-controlled)
    """
    class Meta:
        model = Giving
        fields = [
            "id", "branch", "member", "category", "amount", "currency",
            "source", "status", "payment", "event", "group",
            "given_at", "recorded_by", "note", "created_at",
        ]
        read_only_fields = [
            "id", "recorded_by", "created_at", "status", "payment", "given_at"
        ]
    
    def validate_amount(self, value):
        """Phase 8: Validate amount > 0."""
        try:
            amount = Decimal(str(value))
            if amount <= 0:
                raise serializers.ValidationError("Amount must be greater than zero.")
            return amount
        except (InvalidOperation, ValueError):
            raise serializers.ValidationError("Invalid amount format.")
    
    def validate_currency(self, value):
        """Phase 8: Validate currency code."""
        if value not in ["NGN", "USD", "GBP", "EUR"]:  # Add supported currencies
            raise serializers.ValidationError(f"Unsupported currency: {value}")
        return value
    
    def validate_branch(self, branch):
        """Phase 3: Validate user can access this branch."""
        return self.validate_branch_fk(branch)
    
    def validate_member(self, member):
        """
        Phase 3: Validate member belongs to accessible branch.
        Phase 8: Member can be null for anonymous giving.
        """
        if member:
            return self.validate_member_fk(member)
        return member
    
    def validate_event(self, event):
        """Phase 8: Validate event belongs to accessible branch."""
        if event:
            return self.validate_related_branch_fk(event, 'event')
        return event
    
    def validate_group(self, group):
        """Phase 8: Validate group belongs to accessible branch."""
        if group:
            return self.validate_related_branch_fk(group, 'group')
        return group
    
    def validate(self, attrs):
        """
        Phase 8: Cross-field validation.
        
        Security checks:
        1. member.branch == giving.branch (if member provided)
        2. event.branch == giving.branch (if event provided)
        3. group.branch == giving.branch (if group provided)
        """
        branch = attrs.get('branch')
        member = attrs.get('member')
        event = attrs.get('event')
        group = attrs.get('group')
        
        # Validate member belongs to same branch
        if member and branch and member.branch_id != branch.id:
            raise serializers.ValidationError({
                "member": "Member must belong to the same branch as the giving record."
            })
        
        # Validate event belongs to same branch
        if event and branch and event.branch_id != branch.id:
            raise serializers.ValidationError({
                "event": "Event must belong to the same branch as the giving record."
            })
        
        # Validate group belongs to same branch
        if group and branch and group.branch_id != branch.id:
            raise serializers.ValidationError({
                "group": "Group must belong to the same branch as the giving record."
            })
        
        return attrs


class MemberGivingHistorySerializer(serializers.ModelSerializer):
    """
    Phase 8: Read-only serializer for member self-service giving history.
    
    Security: Members can only view their own giving history. No writable fields.
    """
    category_name = serializers.CharField(source='category.name', read_only=True)
    
    class Meta:
        model = Giving
        fields = [
            "id", "category", "category_name", "amount", "currency",
            "source", "status", "given_at", "note", "created_at",
        ]
        read_only_fields = fields


class PledgeSerializer(ScopedFKValidationMixin, serializers.ModelSerializer):
    """
    Phase 8 hardened: Similar security model as GivingSerializer.
    """
    balance = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)

    class Meta:
        model = Pledge
        fields = [
            "id", "branch", "member", "category", "amount_pledged",
            "amount_fulfilled", "balance", "start_date", "end_date",
            "is_active", "created_at",
        ]
        read_only_fields = ["id", "amount_fulfilled", "balance", "created_at"]
    
    def validate_amount_pledged(self, value):
        """Phase 8: Validate amount_pledged > 0."""
        if value <= 0:
            raise serializers.ValidationError("Pledge amount must be greater than zero.")
        return value
    
    def validate_branch(self, branch):
        """Phase 3: Validate user can access this branch."""
        return self.validate_branch_fk(branch)
    
    def validate_member(self, member):
        """Phase 3: Validate member belongs to accessible branch."""
        return self.validate_member_fk(member)
    
    def validate(self, attrs):
        """Phase 8: Validate member.branch == pledge.branch."""
        branch = attrs.get('branch')
        member = attrs.get('member')
        
        if member and branch and member.branch_id != branch.id:
            raise serializers.ValidationError({
                "member": "Member must belong to the same branch as the pledge."
            })
        
        # Validate date range
        start_date = attrs.get('start_date')
        end_date = attrs.get('end_date')
        if start_date and end_date and end_date < start_date:
            raise serializers.ValidationError({
                "end_date": "End date must be after start date."
            })
        
        return attrs


class PaymentSerializer(ScopedFKValidationMixin, serializers.ModelSerializer):
    """
    Phase 8: Payments are created/updated by webhooks only.
    This serializer is for read-only display purposes.
    """
    class Meta:
        model = Payment
        fields = [
            "id", "branch", "member", "provider", "provider_reference",
            "amount", "currency", "status", "idempotency_key",
            "created_at", "confirmed_at",
        ]
        read_only_fields = ["id", "status", "created_at", "confirmed_at"]
    
    def validate_branch(self, branch):
        """Phase 3: Validate user can access this branch."""
        return self.validate_branch_fk(branch)
    
    def validate_member(self, member):
        """Phase 3: Validate member belongs to accessible branch."""
        if member:
            return self.validate_member_fk(member)
        return member


class RefundSerializer(ScopedFKValidationMixin, serializers.ModelSerializer):
    """
    Phase 8: Refund creation serializer.
    
    Security: Refunds require explicit authorization. The original giving
    record is never mutated.
    """
    original_giving_amount = serializers.DecimalField(
        source='original_giving.amount',
        max_digits=14, decimal_places=2,
        read_only=True
    )
    total_refunded = serializers.SerializerMethodField()
    
    class Meta:
        model = Refund
        fields = [
            "id", "original_giving", "original_giving_amount",
            "amount", "total_refunded", "reason",
            "refunded_by", "refunded_at", "payment_refund_reference",
        ]
        read_only_fields = ["id", "refunded_by", "refunded_at"]
    
    def get_total_refunded(self, obj):
        """Calculate total amount already refunded for the original giving."""
        return obj.original_giving.refunds.aggregate(
            total=models.Sum('amount')
        )['total'] or Decimal('0')
    
    def validate_amount(self, value):
        """Phase 8: Validate refund amount > 0."""
        if value <= 0:
            raise serializers.ValidationError("Refund amount must be greater than zero.")
        return value
    
    def validate(self, attrs):
        """
        Phase 8: Validate refund does not exceed original amount.
        """
        original_giving = attrs.get('original_giving')
        refund_amount = attrs.get('amount')
        
        if not original_giving:
            return attrs
        
        # Check if giving is voided
        if original_giving.is_voided:
            raise serializers.ValidationError({
                "original_giving": "Cannot refund a voided transaction."
            })
        
        # Calculate total already refunded
        from django.db.models import Sum
        total_refunded = original_giving.refunds.aggregate(
            total=Sum('amount')
        )['total'] or Decimal('0')
        
        # Validate refund amount
        remaining = original_giving.amount - total_refunded
        if refund_amount > remaining:
            raise serializers.ValidationError({
                "amount": f"Refund amount ({refund_amount}) exceeds remaining refundable amount ({remaining})."
            })
        
        return attrs


class FinancialStatementSerializer(ScopedFKValidationMixin, serializers.ModelSerializer):
    class Meta:
        model = FinancialStatement
        fields = ["id", "branch", "period_start", "period_end", "total_income", "file_url", "generated_at"]
        read_only_fields = fields
    
    def validate_branch(self, branch):
        """Phase 3: Validate user can access this branch."""
        return self.validate_branch_fk(branch)


class ReconciliationSerializer(ScopedFKValidationMixin, serializers.ModelSerializer):
    """
    Phase 14: Reconciliation serializer with security hardening.
    
    Security model:
    - branch: Server-controlled (user's branch)
    - system_total/bank_total: Read-only (calculated by system)
    - difference: Read-only (auto-calculated)
    - status: Read-only (lifecycle-controlled)
    - created_by/reconciled_by/approved_by: Server-controlled
    - All timestamps: Read-only
    """
    class Meta:
        model = Reconciliation
        fields = [
            "id", "branch", "period_start", "period_end",
            "status", "system_total", "bank_total", "difference",
            "discrepancy_note",
            "created_by", "created_at",
            "reconciled_by", "reconciled_at",
            "approved_by", "approved_at",
        ]
        read_only_fields = [
            "id", "branch", "system_total", "bank_total", "difference",
            "status", "created_by", "created_at",
            "reconciled_by", "reconciled_at",
            "approved_by", "approved_at",
        ]
    
    def validate_branch(self, branch):
        """Phase 3: Validate user can access this branch."""
        return self.validate_branch_fk(branch)


class ReconciliationResultSerializer(serializers.ModelSerializer):
    """
    Phase 14: Reconciliation result detail serializer.
    
    Read-only: Results are created by reconciliation service, not via API.
    """
    class Meta:
        model = ReconciliationResult
        fields = [
            "id", "reconciliation", "result_type",
            "payment", "giving",
            "expected_amount", "actual_amount", "difference",
            "notes", "created_at",
        ]
        read_only_fields = fields


class FinancialPeriodSerializer(ScopedFKValidationMixin, serializers.ModelSerializer):
    """
    Phase 14: Financial period serializer with security hardening.
    
    Security model:
    - branch: Server-controlled (user's branch)
    - status: Read-only (lifecycle-controlled via methods)
    - closed_by/locked_by: Server-controlled
    - All timestamps: Read-only
    """
    class Meta:
        model = FinancialPeriod
        fields = [
            "id", "branch", "name",
            "period_start", "period_end", "status",
            "closed_by", "closed_at",
            "locked_by", "locked_at",
            "created_at", "updated_at",
        ]
        read_only_fields = [
            "id", "branch", "status",
            "closed_by", "closed_at",
            "locked_by", "locked_at",
            "created_at", "updated_at",
        ]
    
    def validate_branch(self, branch):
        """Phase 3: Validate user can access this branch."""
        return self.validate_branch_fk(branch)
    
    def validate(self, attrs):
        """Phase 14: Validate period dates."""
        period_start = attrs.get('period_start')
        period_end = attrs.get('period_end')
        
        if period_start and period_end:
            if period_start >= period_end:
                raise serializers.ValidationError({
                    "period_end": "Period end date must be after start date."
                })
        
        return attrs


class FinancialAdjustmentSerializer(ScopedFKValidationMixin, serializers.ModelSerializer):
    """
    Phase 14: Financial adjustment serializer with security hardening.
    
    Security model:
    - branch: Server-controlled (user's branch)
    - financial_period: Validated to belong to same branch
    - giving/payment: Validated to belong to same branch
    - status: Read-only (lifecycle-controlled)
    - created_by/reviewed_by: Server-controlled
    - All timestamps: Read-only
    - rejection_reason: Read-only (set by reject() method)
    - applied_at: Read-only (set by mark_applied() method)
    """
    class Meta:
        model = FinancialAdjustment
        fields = [
            "id", "branch", "financial_period", "giving", "payment",
            "adjustment_type", "field_name",
            "old_value", "new_value", "amount_delta",
            "reason", "status",
            "created_by", "created_at",
            "reviewed_by", "reviewed_at",
            "rejection_reason", "applied_at",
        ]
        read_only_fields = [
            "id", "branch", "status",
            "created_by", "created_at",
            "reviewed_by", "reviewed_at",
            "rejection_reason", "applied_at",
        ]
    
    def validate_branch(self, branch):
        """Phase 3: Validate user can access this branch."""
        return self.validate_branch_fk(branch)
    
    def validate_financial_period(self, period):
        """Phase 14: Validate period belongs to accessible branch."""
        if period:
            return self.validate_related_branch_fk(period, 'financial_period')
        return period
    
    def validate_giving(self, giving):
        """Phase 14: Validate giving belongs to accessible branch."""
        if giving:
            return self.validate_related_branch_fk(giving, 'giving')
        return giving
    
    def validate_payment(self, payment):
        """Phase 14: Validate payment belongs to accessible branch."""
        if payment:
            return self.validate_related_branch_fk(payment, 'payment')
        return payment
    
    def validate_reason(self, value):
        """Phase 14: Validate reason is not empty."""
        if not value or not value.strip():
            raise serializers.ValidationError("Reason is required and cannot be empty.")
        return value
    
    def validate(self, attrs):
        """
        Phase 14: Cross-field validation.
        
        Security checks:
        1. financial_period.branch == adjustment.branch (if period provided)
        2. giving.branch == adjustment.branch (if giving provided)
        3. payment.branch == adjustment.branch (if payment provided)
        """
        branch = attrs.get('branch')
        financial_period = attrs.get('financial_period')
        giving = attrs.get('giving')
        payment = attrs.get('payment')
        
        # Validate financial_period belongs to same branch
        if financial_period and branch and financial_period.branch_id != branch.id:
            raise serializers.ValidationError({
                "financial_period": "Financial period must belong to the same branch."
            })
        
        # Validate giving belongs to same branch
        if giving and branch and giving.branch_id != branch.id:
            raise serializers.ValidationError({
                "giving": "Giving record must belong to the same branch."
            })
        
        # Validate payment belongs to same branch
        if payment and branch and payment.branch_id != branch.id:
            raise serializers.ValidationError({
                "payment": "Payment record must belong to the same branch."
            })
        
        return attrs
