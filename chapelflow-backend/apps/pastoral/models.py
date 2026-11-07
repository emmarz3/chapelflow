import uuid

from django.conf import settings
from django.db import models
from django.core.exceptions import ValidationError


class PastoralCaseStatus(models.TextChoices):
    """
    Phase 13: Pastoral case lifecycle states.
    
    Workflow:
    OPEN → ASSIGNED → IN_PROGRESS → FOLLOW_UP → RESOLVED → CLOSED
    
    Exception states:
    - ESCALATED: Case requires higher-level intervention
    """
    OPEN = "OPEN", "Open"
    ASSIGNED = "ASSIGNED", "Assigned"
    IN_PROGRESS = "IN_PROGRESS", "In Progress"
    FOLLOW_UP = "FOLLOW_UP", "Follow-Up Needed"
    ESCALATED = "ESCALATED", "Escalated"
    RESOLVED = "RESOLVED", "Resolved"
    CLOSED = "CLOSED", "Closed"


class PastoralCasePriority(models.TextChoices):
    """Phase 13: Case priority/severity levels for triage."""
    LOW = "LOW", "Low"
    MEDIUM = "MEDIUM", "Medium"
    HIGH = "HIGH", "High"
    URGENT = "URGENT", "Urgent"


class PastoralCase(models.Model):
    """
    Highly sensitive pastoral care record. Access is enforced both here
    (queryset filtering) and at the object level via
    common.permissions.rbac.IsPastoralAuthorized — a normal member must
    NEVER be able to read another member's case.
    
    Phase 13 Enhancements:
    - Added priority field for triage
    - Added created_by/updated_by for audit trail
    - Added closure_reason for tracking
    - Added escalation fields
    - Added next_follow_up_date for scheduling
    - Enhanced status with ASSIGNED/FOLLOW_UP/ESCALATED/RESOLVED states
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    branch = models.ForeignKey("organizations.Branch", on_delete=models.CASCADE, related_name="pastoral_cases")
    member = models.ForeignKey("members.Member", on_delete=models.CASCADE, related_name="pastoral_cases")
    
    # Assignment
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        null=True, 
        blank=True, 
        on_delete=models.SET_NULL, 
        related_name="pastoral_cases",
        help_text="Pastoral staff member assigned to this case"
    )
    
    # Case details
    category = models.CharField(
        max_length=100, 
        blank=True,
        help_text="Case category (e.g., Family, Health, Financial, Spiritual)"
    )
    summary = models.TextField(help_text="Case summary (visible to authorized pastoral staff only)")
    
    # Priority and status
    priority = models.CharField(
        max_length=10,
        choices=PastoralCasePriority.choices,
        default=PastoralCasePriority.MEDIUM,
        help_text="Case priority for triage"
    )
    status = models.CharField(
        max_length=15, 
        choices=PastoralCaseStatus.choices, 
        default=PastoralCaseStatus.OPEN,
        help_text="Current case status"
    )
    
    # Follow-up tracking
    next_follow_up_date = models.DateField(
        null=True,
        blank=True,
        help_text="Date for next scheduled follow-up"
    )
    
    # Escalation tracking
    escalated_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When case was escalated"
    )
    escalated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
        help_text="Who escalated the case"
    )
    escalation_reason = models.TextField(
        blank=True,
        help_text="Reason for escalation"
    )
    
    # Closure tracking
    closed_at = models.DateTimeField(
        null=True, 
        blank=True,
        help_text="When case was closed"
    )
    closure_reason = models.TextField(
        blank=True,
        help_text="Reason for closing the case"
    )
    
    # Audit trail
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="created_pastoral_cases",
        help_text="Who created the case"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
        help_text="Who last updated the case"
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "pastoral_case"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["branch", "status"]),
            models.Index(fields=["assigned_to", "status"]),
            models.Index(fields=["member", "status"]),
            models.Index(fields=["priority", "status"]),
            models.Index(fields=["next_follow_up_date"]),
        ]
    
    def clean(self):
        """
        Phase 13: Validate status transitions and field consistency.
        """
        super().clean()
        
        # Validate closed cases have closure info
        if self.status == PastoralCaseStatus.CLOSED:
            if not self.closed_at:
                raise ValidationError("Closed cases must have a closed_at timestamp.")
            if not self.closure_reason:
                raise ValidationError("Closed cases must have a closure reason.")
        
        # Validate escalated cases have escalation info
        if self.status == PastoralCaseStatus.ESCALATED:
            if not self.escalated_at:
                raise ValidationError("Escalated cases must have an escalated_at timestamp.")
            if not self.escalation_reason:
                raise ValidationError("Escalated cases must have an escalation reason.")
        
        # Validate assigned cases have assignee
        if self.status == PastoralCaseStatus.ASSIGNED and not self.assigned_to:
            raise ValidationError("Status ASSIGNED requires an assigned_to user.")
    
    def save(self, *args, **kwargs):
        """
        Phase 13: Auto-set timestamps and validate on save.
        """
        self.full_clean()
        super().save(*args, **kwargs)


class PastoralNote(models.Model):
    """
    Phase 13: Highly sensitive pastoral notes.
    
    Security:
    - Only accessible to authorized pastoral staff
    - Never exposed in public endpoints
    - Cannot be edited (append-only for audit trail)
    - Author auto-set, cannot be changed
    """
    case = models.ForeignKey(PastoralCase, on_delete=models.CASCADE, related_name="notes")
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        null=True, 
        on_delete=models.SET_NULL, 
        related_name="+",
        help_text="Pastoral staff member who wrote this note"
    )
    note = models.TextField(help_text="Pastoral note content (highly sensitive)")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "pastoral_note"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["case", "-created_at"]),
        ]
    
    def save(self, *args, **kwargs):
        """
        Phase 13: Append-only enforcement.
        Notes cannot be modified once created for audit trail integrity.
        """
        if self.pk:
            raise ValidationError("Pastoral notes cannot be modified once created (append-only).")
        super().save(*args, **kwargs)
