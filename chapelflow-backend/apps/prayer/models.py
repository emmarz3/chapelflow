import uuid

from django.conf import settings
from django.db import models
from django.core.exceptions import ValidationError


class PrayerCategory(models.TextChoices):
    HEALING = "HEALING", "Healing"
    FAMILY = "FAMILY", "Family"
    FINANCIAL = "FINANCIAL", "Financial"
    SPIRITUAL = "SPIRITUAL", "Spiritual Growth"
    THANKSGIVING = "THANKSGIVING", "Thanksgiving"
    OTHER = "OTHER", "Other"


class PrayerRequestStatus(models.TextChoices):
    """
    Phase 13: Prayer request lifecycle states.
    
    Workflow:
    NEW → ASSIGNED → IN_PROGRESS → FOLLOW_UP → ANSWERED → CLOSED
    
    Exception states:
    - CANCELLED: Request withdrawn by requester
    """
    NEW = "NEW", "New"
    ASSIGNED = "ASSIGNED", "Assigned"
    IN_PROGRESS = "IN_PROGRESS", "In Progress"
    FOLLOW_UP = "FOLLOW_UP", "Follow-Up Needed"
    ANSWERED = "ANSWERED", "Answered"
    CLOSED = "CLOSED", "Closed"
    CANCELLED = "CANCELLED", "Cancelled"


class PrayerPrivacyLevel(models.TextChoices):
    """
    Phase 13: Multi-level privacy for prayer requests.
    
    - PRIVATE: Only requester and assigned pastoral staff
    - PASTORAL: All authorized pastoral/chaplain staff in branch
    - FELLOWSHIP: Fellowship leaders + pastoral staff
    - PUBLIC: Visible to all authenticated users in branch
    """
    PRIVATE = "PRIVATE", "Private (Requester + Assigned Staff Only)"
    PASTORAL = "PASTORAL", "Pastoral Staff Only"
    FELLOWSHIP = "FELLOWSHIP", "Fellowship Leaders + Pastoral"
    PUBLIC = "PUBLIC", "Public (All Branch Members)"


class TestimonyStatus(models.TextChoices):
    PENDING = "PENDING", "Pending pastoral review"
    APPROVED = "APPROVED", "Approved for sharing"
    REJECTED = "REJECTED", "Not approved"


class PrayerRequest(models.Model):
    """
    Phase 13: Prayer request with enhanced privacy and lifecycle management.
    
    Privacy model:
    - PRIVATE: Only requester and assigned staff
    - PASTORAL: All pastoral staff in branch
    - FELLOWSHIP: Fellowship leaders + pastoral
    - PUBLIC: All branch members
    
    Enhancements:
    - Multi-level privacy instead of boolean
    - created_by for audit trail
    - answered_at for answered prayers
    - closure_reason for tracking
    - Enhanced status states
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    branch = models.ForeignKey("organizations.Branch", on_delete=models.CASCADE, related_name="prayer_requests")
    
    # Requester information
    member = models.ForeignKey(
        "members.Member", 
        null=True, 
        blank=True, 
        on_delete=models.SET_NULL, 
        related_name="prayer_requests",
        help_text="Member submitting the request (null for anonymous)"
    )
    submitted_by_name = models.CharField(
        max_length=255, 
        blank=True, 
        help_text="For anonymous/visitor submissions"
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="created_prayer_requests",
        help_text="User who created the request (for staff-entered requests)"
    )

    # Request details
    category = models.CharField(
        max_length=20, 
        choices=PrayerCategory.choices, 
        default=PrayerCategory.OTHER
    )
    details = models.TextField(help_text="Prayer request details")
    
    # Privacy and status
    privacy_level = models.CharField(
        max_length=15,
        choices=PrayerPrivacyLevel.choices,
        default=PrayerPrivacyLevel.PRIVATE,
        help_text="Who can view this prayer request"
    )
    # Legacy field for backward compatibility
    is_private = models.BooleanField(
        default=True, 
        help_text="Legacy field: If true, only pastoral staff and assignee can view (deprecated, use privacy_level)"
    )
    status = models.CharField(
        max_length=15, 
        choices=PrayerRequestStatus.choices, 
        default=PrayerRequestStatus.NEW
    )
    
    # Assignment
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        null=True, 
        blank=True, 
        on_delete=models.SET_NULL, 
        related_name="assigned_prayer_requests",
        help_text="Staff member assigned to pray/follow-up"
    )
    
    # Outcome tracking
    answered_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When prayer was answered"
    )
    closure_reason = models.TextField(
        blank=True,
        help_text="Reason for closing (e.g., 'Answered', 'Request withdrawn', 'No longer applicable')"
    )

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "prayer_request"
        indexes = [
            models.Index(fields=["branch", "status"]),
            models.Index(fields=["assigned_to", "status"]),
            models.Index(fields=["member", "status"]),
            models.Index(fields=["privacy_level", "branch"]),
        ]
    
    def clean(self):
        """
        Phase 13: Validate status transitions and field consistency.
        """
        super().clean()
        
        # Validate answered requests have answered_at
        if self.status == PrayerRequestStatus.ANSWERED and not self.answered_at:
            raise ValidationError("Status ANSWERED requires answered_at timestamp.")
        
        # Validate closed requests have closure_reason
        if self.status == PrayerRequestStatus.CLOSED and not self.closure_reason:
            raise ValidationError("Status CLOSED requires closure_reason.")
        
        # Validate assigned requests have assignee
        if self.status == PrayerRequestStatus.ASSIGNED and not self.assigned_to:
            raise ValidationError("Status ASSIGNED requires assigned_to user.")
    
    def save(self, *args, **kwargs):
        """
        Phase 13: Sync legacy is_private with privacy_level for backward compatibility.
        """
        # Sync privacy_level to is_private for backward compatibility
        self.is_private = (self.privacy_level == PrayerPrivacyLevel.PRIVATE)
        
        self.full_clean()
        super().save(*args, **kwargs)


class PrayerNote(models.Model):
    """
    Phase 13: Follow-up notes on a prayer request, staff-only.
    
    Security:
    - Only accessible to pastoral staff
    - Append-only for audit trail
    - Author auto-set, cannot be changed
    """
    prayer_request = models.ForeignKey(PrayerRequest, on_delete=models.CASCADE, related_name="notes")
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        null=True, 
        on_delete=models.SET_NULL, 
        related_name="+",
        help_text="Staff member who wrote this note"
    )
    note = models.TextField(help_text="Follow-up note content")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "prayer_note"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["prayer_request", "-created_at"]),
        ]
    
    def save(self, *args, **kwargs):
        """
        Phase 13: Append-only enforcement.
        Notes cannot be modified once created for audit trail integrity.
        """
        if self.pk:
            raise ValidationError("Prayer notes cannot be modified once created (append-only).")
        super().save(*args, **kwargs)


class Testimony(models.Model):
    """A member-submitted testimony that never becomes public without review."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    branch = models.ForeignKey("organizations.Branch", on_delete=models.CASCADE, related_name="testimonies")
    member = models.ForeignKey("members.Member", on_delete=models.CASCADE, related_name="testimonies")
    title = models.CharField(max_length=180)
    details = models.TextField()
    consent_to_publish = models.BooleanField(default=False)
    status = models.CharField(max_length=12, choices=TestimonyStatus.choices, default=TestimonyStatus.PENDING)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="reviewed_testimonies"
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "prayer_testimony"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["branch", "status"], name="prayer_tes_branch_status_idx"),
            models.Index(fields=["member", "status"], name="prayer_tes_member_status_idx"),
        ]

    def clean(self):
        super().clean()
        if self.status == TestimonyStatus.APPROVED and not self.consent_to_publish:
            raise ValidationError("Explicit consent is required before a testimony can be approved for sharing.")
        if self.status == TestimonyStatus.REJECTED and not self.rejection_reason:
            raise ValidationError("A rejection reason is required.")
