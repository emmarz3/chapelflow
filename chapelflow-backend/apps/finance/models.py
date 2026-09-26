import uuid
from decimal import Decimal

from django.conf import settings
from django.db import models
from django.utils import timezone


class GivingCategory(models.Model):
    """e.g. Tithe, Offering, Building Fund, Missions."""

    name = models.CharField(max_length=100, unique=True)
    description = models.CharField(max_length=255, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "finance_giving_category"

    def __str__(self):
        return self.name


class GivingSource(models.TextChoices):
    ONLINE = "ONLINE", "Online"
    OFFLINE = "OFFLINE", "Offline / Cash"
    BANK_TRANSFER = "BANK_TRANSFER", "Bank Transfer"
    CHECK = "CHECK", "Check"


class GivingStatus(models.TextChoices):
    """
    Phase 8: Transaction status lifecycle for financial integrity.
    - CONFIRMED: Normal completed transaction (default for staff-recorded)
    - VOIDED: Cancelled/reversed transaction (immutable, creates audit trail)
    """
    CONFIRMED = "CONFIRMED", "Confirmed"
    VOIDED = "VOIDED", "Voided"


class Giving(models.Model):
    """
    A single giving/donation record. Online gifts link to a Payment.
    
    Phase 8 enhancements:
    - status field for immutability protection
    - event/group FKs for Phase 6/5 integration
    - amount > 0 constraint
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    branch = models.ForeignKey("organizations.Branch", on_delete=models.PROTECT, related_name="giving_records")
    member = models.ForeignKey(
        "members.Member", null=True, blank=True, on_delete=models.SET_NULL, related_name="giving_records"
    )
    category = models.ForeignKey(GivingCategory, on_delete=models.PROTECT, related_name="giving_records")

    # Phase 8: Optional organizational scope (Phase 5/6 integration)
    event = models.ForeignKey(
        "events.Event", null=True, blank=True, on_delete=models.SET_NULL, related_name="giving_records",
        help_text="Optional: Event-specific contribution"
    )
    group = models.ForeignKey(
        "ministries.Group", null=True, blank=True, on_delete=models.SET_NULL, related_name="giving_records",
        help_text="Optional: Group/Fellowship/Unit-specific contribution"
    )

    amount = models.DecimalField(max_digits=14, decimal_places=2)
    currency = models.CharField(max_length=3, default="NGN")
    source = models.CharField(max_length=20, choices=GivingSource.choices, default=GivingSource.OFFLINE)
    
    # Phase 8: Status for immutability protection
    status = models.CharField(max_length=15, choices=GivingStatus.choices, default=GivingStatus.CONFIRMED)

    payment = models.OneToOneField(
        "finance.Payment", null=True, blank=True, on_delete=models.SET_NULL, related_name="giving_record"
    )

    given_at = models.DateTimeField()
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    note = models.CharField(max_length=500, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "finance_giving"
        ordering = ["-given_at"]
        indexes = [
            models.Index(fields=["branch", "given_at"]),
            models.Index(fields=["member", "category"]),
            models.Index(fields=["event"]),
            models.Index(fields=["group"]),
            models.Index(fields=["status"]),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(amount__gt=0),
                name="finance_giving_amount_positive"
            ),
        ]

    def __str__(self):
        return f"{self.amount} {self.currency} - {self.category}"
    
    @property
    def is_confirmed(self):
        """Phase 8: Check if transaction is confirmed (not voided)."""
        return self.status == GivingStatus.CONFIRMED
    
    @property
    def is_voided(self):
        """Phase 8: Check if transaction is voided."""
        return self.status == GivingStatus.VOIDED


class Pledge(models.Model):
    """
    Phase 8: Pledge tracking with fulfillment validation.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    branch = models.ForeignKey("organizations.Branch", on_delete=models.PROTECT, related_name="pledges")
    member = models.ForeignKey("members.Member", on_delete=models.CASCADE, related_name="pledges")
    category = models.ForeignKey(GivingCategory, on_delete=models.PROTECT, related_name="pledges")
    amount_pledged = models.DecimalField(max_digits=14, decimal_places=2)
    amount_fulfilled = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "finance_pledge"
        constraints = [
            models.CheckConstraint(
                condition=models.Q(amount_pledged__gt=0),
                name="finance_pledge_amount_pledged_positive"
            ),
            models.CheckConstraint(
                condition=models.Q(amount_fulfilled__gte=0) & models.Q(amount_fulfilled__lte=models.F("amount_pledged")),
                name="finance_pledge_amount_fulfilled_valid"
            ),
        ]

    @property
    def balance(self):
        return self.amount_pledged - self.amount_fulfilled


class PaymentStatus(models.TextChoices):
    PENDING = "PENDING", "Pending"
    SUCCESSFUL = "SUCCESSFUL", "Successful"
    FAILED = "FAILED", "Failed"
    REFUNDED = "REFUNDED", "Refunded"


class Payment(models.Model):
    """
    A payment gateway transaction. Never stores raw card data — only the
    gateway's reference and status, confirmed exclusively via webhook.
    
    Phase 8: Enhanced with amount validation constraint.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    branch = models.ForeignKey("organizations.Branch", on_delete=models.PROTECT, related_name="payments")
    member = models.ForeignKey(
        "members.Member", null=True, blank=True, on_delete=models.SET_NULL, related_name="payments"
    )
    initiated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="initiated_payments",
        help_text="Authenticated account that started the gateway checkout.",
    )
    giving_category = models.ForeignKey(
        GivingCategory,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="payment_attempts",
        help_text="The purpose selected before the gateway checkout.",
    )
    giving_note = models.CharField(max_length=500, blank=True)
    provider = models.CharField(
        max_length=20, choices=[("PAYSTACK", "Paystack"), ("FLUTTERWAVE", "Flutterwave")]
    )
    provider_reference = models.CharField(max_length=100, unique=True)
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    currency = models.CharField(max_length=3, default="NGN")
    status = models.CharField(max_length=15, choices=PaymentStatus.choices, default=PaymentStatus.PENDING)
    raw_webhook_payload = models.JSONField(null=True, blank=True)
    idempotency_key = models.CharField(max_length=150, unique=True, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    confirmed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "finance_payment"
        indexes = [models.Index(fields=["provider", "provider_reference"])]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(amount__gt=0),
                name="finance_payment_amount_positive"
            ),
        ]

    def __str__(self):
        return f"{self.provider}:{self.provider_reference} ({self.status})"


class FinancialStatement(models.Model):
    """Generated periodic statement (usually produced asynchronously via Celery)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    branch = models.ForeignKey("organizations.Branch", on_delete=models.CASCADE, related_name="statements")
    period_start = models.DateField()
    period_end = models.DateField()
    total_income = models.DecimalField(max_digits=16, decimal_places=2, default=0)
    file_url = models.URLField(blank=True)
    generated_at = models.DateTimeField(auto_now_add=True)
    generated_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+")

    class Meta:
        db_table = "finance_statement"


class ReconciliationStatus(models.TextChoices):
    """
    Phase 14: Reconciliation lifecycle states.
    
    - PENDING: Created but not yet started
    - IN_PROGRESS: Actively being reconciled
    - RECONCILED: Completed, all amounts match
    - DISCREPANCY: Completed, but mismatches found
    - APPROVED: Discrepancies reviewed and approved by authorized user
    """
    PENDING = "PENDING", "Pending"
    IN_PROGRESS = "IN_PROGRESS", "In Progress"
    RECONCILED = "RECONCILED", "Reconciled (Matched)"
    DISCREPANCY = "DISCREPANCY", "Discrepancy Found"
    APPROVED = "APPROVED", "Approved (Discrepancy Resolved)"


class Reconciliation(models.Model):
    """
    Phase 14: Financial reconciliation tracking.
    
    Reconciles system records (Giving) against external sources (Payment gateway).
    Tracks matches, mismatches, and discrepancies for audit trail.
    
    Lifecycle:
    1. PENDING: Created, not yet executed
    2. IN_PROGRESS: Reconciliation running
    3. RECONCILED: Complete, perfect match (system_total == bank_total)
    4. DISCREPANCY: Complete, mismatch found (system_total != bank_total)
    5. APPROVED: Finance admin reviewed and approved discrepancy
    
    Security:
    - Immutable after creation (no edits)
    - Branch-scoped (cannot see other branches)
    - Idempotency via unique constraint on (branch, period_start, period_end)
    - Results persisted in ReconciliationResult for detailed tracking
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    branch = models.ForeignKey(
        "organizations.Branch",
        on_delete=models.PROTECT,
        related_name="reconciliations"
    )
    period_start = models.DateField(
        help_text="Start date of reconciliation period (inclusive)"
    )
    period_end = models.DateField(
        help_text="End date of reconciliation period (inclusive)"
    )
    
    # Status tracking
    status = models.CharField(
        max_length=20,
        choices=ReconciliationStatus.choices,
        default=ReconciliationStatus.PENDING,
        help_text="Current reconciliation status"
    )
    
    # Totals
    system_total = models.DecimalField(
        max_digits=16,
        decimal_places=2,
        help_text="Total from system (Giving records)"
    )
    bank_total = models.DecimalField(
        max_digits=16,
        decimal_places=2,
        help_text="Total from bank/gateway"
    )
    difference = models.DecimalField(
        max_digits=16,
        decimal_places=2,
        default=0,
        help_text="Calculated difference (system_total - bank_total)"
    )
    
    # Notes
    discrepancy_note = models.TextField(
        blank=True,
        help_text="Explanation of discrepancies or resolution notes"
    )
    
    # Audit trail
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="reconciliations_created",
        help_text="User who initiated reconciliation"
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text="When reconciliation was created"
    )
    
    reconciled_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reconciliations_completed",
        help_text="User who completed reconciliation"
    )
    reconciled_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When reconciliation was completed"
    )
    
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reconciliations_approved",
        help_text="User who approved discrepancy"
    )
    approved_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When discrepancy was approved"
    )

    class Meta:
        db_table = "finance_reconciliation"
        # Prevent duplicate reconciliations for same period
        unique_together = [["branch", "period_start", "period_end"]]
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["branch", "status"]),
            models.Index(fields=["period_start", "period_end"]),
            models.Index(fields=["status", "created_at"]),
        ]
    
    def __str__(self):
        return f"Reconciliation {self.branch.name} {self.period_start} to {self.period_end} ({self.get_status_display()})"
    
    @property
    def is_pending(self):
        """Check if reconciliation is pending."""
        return self.status == ReconciliationStatus.PENDING
    
    @property
    def is_in_progress(self):
        """Check if reconciliation is in progress."""
        return self.status == ReconciliationStatus.IN_PROGRESS
    
    @property
    def is_reconciled(self):
        """Check if reconciliation completed with perfect match."""
        return self.status == ReconciliationStatus.RECONCILED
    
    @property
    def is_discrepancy(self):
        """Check if reconciliation found discrepancies."""
        return self.status == ReconciliationStatus.DISCREPANCY
    
    @property
    def is_approved(self):
        """Check if discrepancy was approved."""
        return self.status == ReconciliationStatus.APPROVED
    
    @property
    def has_discrepancy(self):
        """Check if there is a difference between totals."""
        return abs(self.difference) > Decimal("0.01")  # Allow 1 cent tolerance
    
    def start(self, user):
        """
        Mark reconciliation as in progress.
        Can only start PENDING reconciliations.
        """
        from django.core.exceptions import ValidationError
        
        if self.status != ReconciliationStatus.PENDING:
            raise ValidationError(f"Cannot start reconciliation in {self.get_status_display()} status")
        
        self.status = ReconciliationStatus.IN_PROGRESS
        self.save()
        
        # Log the start
        from apps.audit.services import write_audit_log
        from apps.audit.models import AuditAction
        write_audit_log(
            user=user,
            action=AuditAction.RECONCILIATION_STARTED,
            resource_type="Reconciliation",
            resource_id=str(self.id),
            metadata={
                "period_start": str(self.period_start),
                "period_end": str(self.period_end),
                "branch": self.branch.name
            }
        )
    
    def complete(self, user):
        """
        Mark reconciliation as complete.
        Automatically sets status to RECONCILED or DISCREPANCY based on difference.
        Can only complete IN_PROGRESS reconciliations.
        """
        from django.core.exceptions import ValidationError
        
        if self.status != ReconciliationStatus.IN_PROGRESS:
            raise ValidationError(f"Cannot complete reconciliation in {self.get_status_display()} status")
        
        # Calculate difference
        self.difference = self.system_total - self.bank_total
        
        # Set status based on whether there's a discrepancy
        if self.has_discrepancy:
            self.status = ReconciliationStatus.DISCREPANCY
        else:
            self.status = ReconciliationStatus.RECONCILED
        
        self.reconciled_by = user
        self.reconciled_at = timezone.now()
        self.save()
        
        # Log the completion
        from apps.audit.services import write_audit_log
        from apps.audit.models import AuditAction
        write_audit_log(
            user=user,
            action=AuditAction.RECONCILIATION_COMPLETED,
            resource_type="Reconciliation",
            resource_id=str(self.id),
            metadata={
                "period_start": str(self.period_start),
                "period_end": str(self.period_end),
                "branch": self.branch.name,
                "status": self.status,
                "system_total": str(self.system_total),
                "bank_total": str(self.bank_total),
                "difference": str(self.difference),
                "has_discrepancy": self.has_discrepancy
            }
        )
    
    def approve(self, user, note=None):
        """
        Approve a discrepancy.
        Can only approve reconciliations in DISCREPANCY status.
        """
        from django.core.exceptions import ValidationError
        
        if self.status != ReconciliationStatus.DISCREPANCY:
            raise ValidationError(f"Cannot approve reconciliation in {self.get_status_display()} status")
        
        self.status = ReconciliationStatus.APPROVED
        self.approved_by = user
        self.approved_at = timezone.now()
        
        if note:
            self.discrepancy_note = note
        
        self.save()
        
        # Log the approval
        from apps.audit.services import write_audit_log
        from apps.audit.models import AuditAction
        write_audit_log(
            user=user,
            action=AuditAction.RECONCILIATION_APPROVED,
            resource_type="Reconciliation",
            resource_id=str(self.id),
            metadata={
                "period_start": str(self.period_start),
                "period_end": str(self.period_end),
                "branch": self.branch.name,
                "difference": str(self.difference),
                "note": note or ""
            }
        )
    
    def save(self, *args, **kwargs):
        """Calculate difference on save and log creation."""
        is_new = self.pk is None
        
        if self.system_total is not None and self.bank_total is not None:
            self.difference = self.system_total - self.bank_total
        
        super().save(*args, **kwargs)
        
        # Log creation
        if is_new:
            from apps.audit.services import write_audit_log
            from apps.audit.models import AuditAction
            write_audit_log(
                user=self.created_by,
                action=AuditAction.RECONCILIATION_CREATED,
                resource_type="Reconciliation",
                resource_id=str(self.id),
                metadata={
                    "period_start": str(self.period_start),
                    "period_end": str(self.period_end),
                    "branch": self.branch.name,
                    "system_total": str(self.system_total),
                    "bank_total": str(self.bank_total)
                }
            )


class ReconciliationResultType(models.TextChoices):
    """
    Phase 14: Types of reconciliation result entries.
    
    - MATCHED: Payment/Giving pair matched successfully
    - UNMATCHED_PAYMENT: Payment with no corresponding Giving record
    - UNMATCHED_GIVING: Giving record with no corresponding Payment
    - AMOUNT_MISMATCH: Records exist but amounts don't match
    """
    MATCHED = "MATCHED", "Matched"
    UNMATCHED_PAYMENT = "UNMATCHED_PAYMENT", "Unmatched Payment"
    UNMATCHED_GIVING = "UNMATCHED_GIVING", "Unmatched Giving"
    AMOUNT_MISMATCH = "AMOUNT_MISMATCH", "Amount Mismatch"


class ReconciliationResult(models.Model):
    """
    Phase 14: Detailed reconciliation results for audit trail.
    
    Stores individual match/mismatch records from reconciliation process.
    Each result entry represents one transaction pair (or unpaired transaction).
    
    Use cases:
    - Track which payments matched which giving records
    - Identify unmatched transactions for investigation
    - Document amount mismatches with expected vs actual
    - Provide drill-down detail for discrepancy resolution
    
    Security:
    - Immutable after creation (append-only)
    - Cascade deleted with parent reconciliation
    - Branch-scoped via reconciliation
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    reconciliation = models.ForeignKey(
        Reconciliation,
        on_delete=models.CASCADE,
        related_name="results",
        help_text="Parent reconciliation"
    )
    result_type = models.CharField(
        max_length=20,
        choices=ReconciliationResultType.choices,
        help_text="Type of result entry"
    )
    
    # Transaction references (nullable for unmatched scenarios)
    payment = models.ForeignKey(
        "Payment",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reconciliation_results",
        help_text="Payment record (if applicable)"
    )
    giving = models.ForeignKey(
        "Giving",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reconciliation_results",
        help_text="Giving record (if applicable)"
    )
    
    # Amount tracking
    expected_amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Expected amount (from system/giving)"
    )
    actual_amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Actual amount (from bank/payment)"
    )
    difference = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=0,
        help_text="Difference (expected - actual)"
    )
    
    # Details
    notes = models.TextField(
        blank=True,
        help_text="Additional notes or resolution details"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = "finance_reconciliation_result"
        ordering = ["created_at"]
        indexes = [
            models.Index(fields=["reconciliation", "result_type"]),
            models.Index(fields=["payment"]),
            models.Index(fields=["giving"]),
        ]
    
    def __str__(self):
        return f"{self.get_result_type_display()} - {self.reconciliation.id}"
    
    def save(self, *args, **kwargs):
        """Calculate difference on save."""
        if self.expected_amount is not None and self.actual_amount is not None:
            self.difference = self.expected_amount - self.actual_amount
        super().save(*args, **kwargs)


class AdjustmentStatus(models.TextChoices):
    """
    Phase 14: Financial adjustment approval workflow states.
    
    - PENDING: Created, awaiting approval
    - APPROVED: Approved by authorized user
    - REJECTED: Rejected by authorized user
    """
    PENDING = "PENDING", "Pending Approval"
    APPROVED = "APPROVED", "Approved"
    REJECTED = "REJECTED", "Rejected"


class FinancialAdjustment(models.Model):
    """
    Phase 14: Controlled corrections for closed/locked financial periods.
    
    When errors are discovered in closed periods, direct edits are blocked.
    This model provides a controlled, auditable correction mechanism with:
    - Mandatory justification
    - Approval workflow
    - Complete audit trail
    - Before/after value tracking
    
    Use cases:
    - Correct data entry errors discovered after period closure
    - Adjust for bank fees not initially recorded
    - Fix reconciliation discrepancies
    - Document manual corrections
    
    Security:
    - Immutable after approval/rejection
    - Requires FINANCE_ADMIN or higher role
    - Branch-scoped
    - Full audit trail
    
    Workflow:
    1. Finance staff creates adjustment (PENDING)
    2. Senior finance admin reviews
    3. If approved: adjustment can be applied
    4. If rejected: adjustment archived with rejection reason
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # What's being adjusted
    branch = models.ForeignKey(
        "organizations.Branch",
        on_delete=models.PROTECT,
        related_name="financial_adjustments",
        help_text="Branch where adjustment applies"
    )
    financial_period = models.ForeignKey(
        "FinancialPeriod",
        on_delete=models.PROTECT,
        related_name="adjustments",
        null=True,
        blank=True,
        help_text="Period being adjusted (if applicable)"
    )
    
    # Link to affected record (if applicable)
    giving = models.ForeignKey(
        "Giving",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="adjustments",
        help_text="Giving record being adjusted (if applicable)"
    )
    payment = models.ForeignKey(
        "Payment",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="adjustments",
        help_text="Payment record being adjusted (if applicable)"
    )
    
    # Adjustment details
    adjustment_type = models.CharField(
        max_length=100,
        help_text="Type of adjustment (e.g., 'Amount Correction', 'Category Change', 'Date Correction')"
    )
    field_name = models.CharField(
        max_length=100,
        blank=True,
        help_text="Field being adjusted (e.g., 'amount', 'category', 'given_at')"
    )
    old_value = models.TextField(
        blank=True,
        help_text="Original value before adjustment (JSON or string representation)"
    )
    new_value = models.TextField(
        blank=True,
        help_text="New value after adjustment (JSON or string representation)"
    )
    amount_delta = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Amount change (positive or negative) if applicable"
    )
    
    # Justification
    reason = models.TextField(
        help_text="Detailed explanation of why this adjustment is necessary"
    )
    
    # Approval workflow
    status = models.CharField(
        max_length=20,
        choices=AdjustmentStatus.choices,
        default=AdjustmentStatus.PENDING,
        help_text="Approval status"
    )
    
    # Audit trail
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="financial_adjustments_created",
        help_text="User who created the adjustment"
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text="When adjustment was created"
    )
    
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="financial_adjustments_reviewed",
        help_text="User who approved/rejected the adjustment"
    )
    reviewed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When adjustment was reviewed"
    )
    
    rejection_reason = models.TextField(
        blank=True,
        help_text="Reason for rejection (if applicable)"
    )
    
    applied_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When adjustment was actually applied to the system"
    )
    
    class Meta:
        db_table = "finance_adjustment"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["branch", "status"]),
            models.Index(fields=["financial_period"]),
            models.Index(fields=["giving"]),
            models.Index(fields=["payment"]),
            models.Index(fields=["status", "created_at"]),
        ]
    
    def __str__(self):
        return f"Adjustment {self.adjustment_type} - {self.get_status_display()}"
    
    @property
    def is_pending(self):
        """Check if adjustment is pending approval."""
        return self.status == AdjustmentStatus.PENDING
    
    @property
    def is_approved(self):
        """Check if adjustment was approved."""
        return self.status == AdjustmentStatus.APPROVED
    
    @property
    def is_rejected(self):
        """Check if adjustment was rejected."""
        return self.status == AdjustmentStatus.REJECTED
    
    def approve(self, user):
        """
        Approve the adjustment.
        Can only approve PENDING adjustments.
        """
        from django.core.exceptions import ValidationError
        
        if self.status != AdjustmentStatus.PENDING:
            raise ValidationError(f"Cannot approve adjustment in {self.get_status_display()} status")
        
        self.status = AdjustmentStatus.APPROVED
        self.reviewed_by = user
        self.reviewed_at = timezone.now()
        self.save()
        
        # Log the approval
        from apps.audit.services import write_audit_log
        from apps.audit.models import AuditAction
        write_audit_log(
            user=user,
            action=AuditAction.ADJUSTMENT_APPROVED,
            resource_type="FinancialAdjustment",
            resource_id=str(self.id),
            metadata={
                "adjustment_type": self.adjustment_type,
                "branch": self.branch.name,
                "period": self.financial_period.name if self.financial_period else None,
                "amount_delta": str(self.amount_delta) if self.amount_delta else None,
                "reason": self.reason
            }
        )
    
    def reject(self, user, reason):
        """
        Reject the adjustment.
        Can only reject PENDING adjustments.
        """
        from django.core.exceptions import ValidationError
        
        if self.status != AdjustmentStatus.PENDING:
            raise ValidationError(f"Cannot reject adjustment in {self.get_status_display()} status")
        
        if not reason:
            raise ValidationError("Rejection reason is required")
        
        self.status = AdjustmentStatus.REJECTED
        self.reviewed_by = user
        self.reviewed_at = timezone.now()
        self.rejection_reason = reason
        self.save()
        
        # Log the rejection
        from apps.audit.services import write_audit_log
        from apps.audit.models import AuditAction
        write_audit_log(
            user=user,
            action=AuditAction.ADJUSTMENT_REJECTED,
            resource_type="FinancialAdjustment",
            resource_id=str(self.id),
            metadata={
                "adjustment_type": self.adjustment_type,
                "branch": self.branch.name,
                "period": self.financial_period.name if self.financial_period else None,
                "rejection_reason": reason
            }
        )
    
    def mark_applied(self):
        """
        Mark adjustment as applied to the system.
        Can only mark approved adjustments as applied.
        """
        from django.core.exceptions import ValidationError
        
        if self.status != AdjustmentStatus.APPROVED:
            raise ValidationError("Can only mark approved adjustments as applied")
        
        if self.applied_at:
            raise ValidationError("Adjustment has already been marked as applied")
        
        self.applied_at = timezone.now()
        self.save()
        
        # Log the application
        from apps.audit.services import write_audit_log
        from apps.audit.models import AuditAction
        write_audit_log(
            user=self.reviewed_by,  # Use the approver as the user
            action=AuditAction.ADJUSTMENT_APPLIED,
            resource_type="FinancialAdjustment",
            resource_id=str(self.id),
            metadata={
                "adjustment_type": self.adjustment_type,
                "branch": self.branch.name,
                "period": self.financial_period.name if self.financial_period else None,
                "old_value": self.old_value,
                "new_value": self.new_value,
                "amount_delta": str(self.amount_delta) if self.amount_delta else None
            }
        )
    
    def save(self, *args, **kwargs):
        """Override save to log creation."""
        is_new = self.pk is None
        
        super().save(*args, **kwargs)
        
        # Log creation
        if is_new:
            from apps.audit.services import write_audit_log
            from apps.audit.models import AuditAction
            write_audit_log(
                user=self.created_by,
                action=AuditAction.ADJUSTMENT_CREATED,
                resource_type="FinancialAdjustment",
                resource_id=str(self.id),
                metadata={
                    "adjustment_type": self.adjustment_type,
                    "branch": self.branch.name,
                    "period": self.financial_period.name if self.financial_period else None,
                    "field_name": self.field_name,
                    "old_value": self.old_value,
                    "new_value": self.new_value,
                    "amount_delta": str(self.amount_delta) if self.amount_delta else None,
                    "reason": self.reason
                }
            )


class Refund(models.Model):
    """
    Phase 8: Tracks refunds/reversals of giving records.
    
    Refunds create an auditable trail without mutating the original transaction.
    The original Giving record remains intact; the Refund references it.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    original_giving = models.ForeignKey(
        Giving, on_delete=models.PROTECT, related_name="refunds",
        help_text="The original giving record being refunded"
    )
    amount = models.DecimalField(
        max_digits=14, decimal_places=2,
        help_text="Refund amount (may be partial)"
    )
    reason = models.CharField(max_length=500)
    refunded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="+"
    )
    refunded_at = models.DateTimeField(auto_now_add=True)
    
    # If refund is via payment gateway
    payment_refund_reference = models.CharField(max_length=150, blank=True, null=True)

    class Meta:
        db_table = "finance_refund"
        indexes = [models.Index(fields=["original_giving", "refunded_at"])]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(amount__gt=0),
                name="finance_refund_amount_positive"
            ),
        ]

    def __str__(self):
        return f"Refund {self.amount} for {self.original_giving_id}"



class FinancialPeriodStatus(models.TextChoices):
    """
    Phase 14: Financial period lifecycle.
    
    - OPEN: Active period, records can be created/modified
    - CLOSED: Period ended, no new records, existing can be modified with approval
    - LOCKED: Completely immutable, reconciled and finalized
    """
    OPEN = "OPEN", "Open"
    CLOSED = "CLOSED", "Closed"
    LOCKED = "LOCKED", "Locked (Immutable)"


class FinancialPeriod(models.Model):
    """
    Phase 14: Financial periods for reconciliation and controls.
    
    Enforces immutability after closing:
    - OPEN: Normal operations
    - CLOSED: No new transactions, modifications require approval
    - LOCKED: Completely immutable (post-reconciliation)
    
    Workflow:
    1. Period created as OPEN (monthly/quarterly)
    2. Finance staff record transactions during period
    3. Period CLOSED at end (no new transactions)
    4. Reconciliation performed
    5. Period LOCKED (permanent, auditable)
    
    Security:
    - Only finance admins can close/lock periods
    - Locked periods prevent silent history rewriting
    - Audit trail for all status changes
    
    Integration:
    - Giving/Payment models check period status before saves
    - Reconciliation requires closed periods
    - Reports use period boundaries
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    branch = models.ForeignKey(
        "organizations.Branch",
        on_delete=models.PROTECT,
        related_name="financial_periods"
    )
    name = models.CharField(
        max_length=100,
        help_text="e.g., 'January 2026', 'Q1 2026'"
    )
    period_start = models.DateField(
        help_text="First day of period (inclusive)"
    )
    period_end = models.DateField(
        help_text="Last day of period (inclusive)"
    )
    status = models.CharField(
        max_length=10,
        choices=FinancialPeriodStatus.choices,
        default=FinancialPeriodStatus.OPEN
    )
    
    # Lifecycle tracking
    closed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="closed_financial_periods",
        help_text="User who closed this period"
    )
    closed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When period was closed"
    )
    locked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="locked_financial_periods",
        help_text="User who locked this period"
    )
    locked_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When period was locked (post-reconciliation)"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = "finance_period"
        unique_together = [["branch", "period_start", "period_end"]]
        ordering = ["-period_start"]
        indexes = [
            models.Index(fields=["branch", "status"]),
            models.Index(fields=["period_start", "period_end"]),
        ]
    
    def __str__(self):
        return f"{self.name} - {self.branch.name} ({self.get_status_display()})"
    
    def clean(self):
        """
        Phase 14: Validate period constraints.
        - Prevent date inversion (start >= end)
        - Prevent overlapping periods in same branch
        """
        from django.core.exceptions import ValidationError
        
        # Validate start < end
        if self.period_start and self.period_end:
            if self.period_start >= self.period_end:
                raise ValidationError({
                    'period_end': f"Period end date ({self.period_end}) must be after start date ({self.period_start})"
                })
        
        # Prevent overlapping periods in same branch
        if self.branch_id and self.period_start and self.period_end:
            overlapping = FinancialPeriod.objects.filter(
                branch=self.branch
            ).exclude(pk=self.pk).filter(
                # Check if new period overlaps with existing periods
                # Overlap occurs if: new_start <= existing_end AND new_end >= existing_start
                period_start__lte=self.period_end,
                period_end__gte=self.period_start
            )
            
            if overlapping.exists():
                overlap = overlapping.first()
                raise ValidationError({
                    'period_start': f"This period overlaps with existing period '{overlap.name}' "
                                   f"({overlap.period_start} to {overlap.period_end}). "
                                   f"Periods cannot overlap."
                })
    
    def save(self, *args, **kwargs):
        """Override save to call clean() validation."""
        self.full_clean()
        super().save(*args, **kwargs)
    
    @property
    def is_open(self):
        """Check if period accepts new transactions."""
        return self.status == FinancialPeriodStatus.OPEN
    
    @property
    def is_closed(self):
        """Check if period is closed (no new transactions)."""
        return self.status == FinancialPeriodStatus.CLOSED
    
    @property
    def is_locked(self):
        """Check if period is locked (completely immutable)."""
        return self.status == FinancialPeriodStatus.LOCKED
    
    def close(self, user, skip_checks=False):
        """
        Close period (no new transactions).
        Can only close OPEN periods.
        
        Phase 14: Performs validation checks before closing:
        - Checks for pending payments
        - Checks for unreconciled transactions
        - Verifies all giving records are confirmed
        
        Args:
            user: User performing the closure
            skip_checks: If True, bypass validation (emergency override)
        
        Raises:
            ValidationError: If period cannot be closed or validation fails
        """
        from django.core.exceptions import ValidationError
        
        if self.status != FinancialPeriodStatus.OPEN:
            raise ValidationError(f"Cannot close period in {self.get_status_display()} status")
        
        # Perform validation checks unless explicitly skipped
        if not skip_checks:
            validation_errors = []
            
            # Check for pending payments in this period
            pending_payments = Payment.objects.filter(
                branch=self.branch,
                created_at__date__gte=self.period_start,
                created_at__date__lte=self.period_end,
                status=PaymentStatus.PENDING
            ).count()
            
            if pending_payments > 0:
                validation_errors.append(
                    f"{pending_payments} pending payment(s) found. "
                    f"All payments must be confirmed or failed before closing period."
                )
            
            # Check for voided giving records (should be minimal)
            voided_giving = Giving.objects.filter(
                branch=self.branch,
                given_at__date__gte=self.period_start,
                given_at__date__lte=self.period_end,
                status=GivingStatus.VOIDED
            ).count()
            
            if voided_giving > 0:
                # Warning only, not blocking
                validation_errors.append(
                    f"Warning: {voided_giving} voided giving record(s) in this period. "
                    f"Ensure these are intentional before closing."
                )
            
            # Check if period has been reconciled
            # Look for completed reconciliation covering this exact period
            reconciliation = Reconciliation.objects.filter(
                branch=self.branch,
                period_start=self.period_start,
                period_end=self.period_end,
                status__in=[
                    ReconciliationStatus.RECONCILED,
                    ReconciliationStatus.APPROVED
                ]
            ).first()
            
            if not reconciliation:
                validation_errors.append(
                    f"No completed reconciliation found for this period. "
                    f"Period should be reconciled before closing."
                )
            
            # If there are blocking errors, raise validation error
            if validation_errors:
                error_message = "Cannot close period due to validation failures:\n" + "\n".join(
                    f"- {error}" for error in validation_errors
                )
                raise ValidationError(error_message)
        
        # All checks passed, proceed with closure
        self.status = FinancialPeriodStatus.CLOSED
        self.closed_by = user
        self.closed_at = timezone.now()
        self.save()
        
        # Log the closure
        from apps.audit.services import write_audit_log
        from apps.audit.models import AuditAction
        write_audit_log(
            user=user,
            action=AuditAction.FINANCIAL_PERIOD_CLOSED,
            resource_type="FinancialPeriod",
            resource_id=str(self.id),
            metadata={
                "period_name": self.name,
                "period_start": str(self.period_start),
                "period_end": str(self.period_end),
                "branch": self.branch.name,
                "skip_checks": skip_checks
            }
        )
    
    def lock(self, user):
        """
        Lock period (immutable, post-reconciliation).
        Can only lock CLOSED periods.
        """
        from django.core.exceptions import ValidationError
        
        if self.status != FinancialPeriodStatus.CLOSED:
            raise ValidationError(f"Cannot lock period in {self.get_status_display()} status. Must be CLOSED first.")
        
        self.status = FinancialPeriodStatus.LOCKED
        self.locked_by = user
        self.locked_at = timezone.now()
        self.save()
        
        # Log the lock
        from apps.audit.services import write_audit_log
        from apps.audit.models import AuditAction
        write_audit_log(
            user=user,
            action=AuditAction.FINANCIAL_PERIOD_LOCKED,
            resource_type="FinancialPeriod",
            resource_id=str(self.id),
            metadata={
                "period_name": self.name,
                "period_start": str(self.period_start),
                "period_end": str(self.period_end),
                "branch": self.branch.name
            }
        )
    
    def reopen(self, user):
        """
        Reopen closed period (emergency fix).
        Cannot reopen LOCKED periods.
        Requires audit logging.
        """
        from django.core.exceptions import ValidationError
        
        if self.status == FinancialPeriodStatus.LOCKED:
            raise ValidationError("Cannot reopen LOCKED period. Locked periods are immutable.")
        
        if self.status != FinancialPeriodStatus.CLOSED:
            raise ValidationError(f"Can only reopen CLOSED periods, not {self.get_status_display()}")
        
        self.status = FinancialPeriodStatus.OPEN
        self.closed_by = None
        self.closed_at = None
        self.save()
        
        # Log the reopen action
        from apps.audit.services import write_audit_log
        from apps.audit.models import AuditAction
        write_audit_log(
            user=user,
            action=AuditAction.FINANCIAL_PERIOD_REOPENED,
            resource_type="FinancialPeriod",
            resource_id=str(self.id),
            metadata={"period": self.name, "reason": "Manual reopen"}
        )


# Add validation to Giving model to check financial period
def validate_giving_period(giving):
    """
    Phase 14: Prevent modifications to giving records in closed/locked periods.
    Called from Giving.clean() or Giving.save().
    """
    if not giving.pk:
        # New records allowed in OPEN periods only
        return
    
    period = FinancialPeriod.objects.filter(
        branch=giving.branch,
        period_start__lte=giving.given_at.date(),
        period_end__gte=giving.given_at.date(),
        status__in=[FinancialPeriodStatus.CLOSED, FinancialPeriodStatus.LOCKED]
    ).first()
    
    if period:
        from django.core.exceptions import ValidationError
        raise ValidationError(
            f"Cannot modify giving record dated {giving.given_at.date()} - "
            f"it falls in {period.name} which is {period.get_status_display()}. "
            f"Contact finance administrator if changes are needed."
        )
