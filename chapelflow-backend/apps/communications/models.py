import uuid

from django.conf import settings
from django.db import models


class AudienceType(models.TextChoices):
    """
    Phase 10: Audience targeting types for announcements.
    
    - EVERYONE: All members in the branch
    - FELLOWSHIP: Members of a specific fellowship
    - UNIT: Members of a specific unit
    - MINISTRY: Members of a specific ministry/group
    - STAFF_COMMUNITY: Staff community classification
    - CUSTOM: Custom targeting using explicit groups/statuses
    """
    EVERYONE = "EVERYONE", "Everyone in the branch"
    FELLOWSHIP = "FELLOWSHIP", "Fellowship"
    UNIT = "UNIT", "Unit"
    MINISTRY = "MINISTRY", "Ministry/Group"
    STAFF_COMMUNITY = "STAFF_COMMUNITY", "Staff Community"
    CUSTOM = "CUSTOM", "Custom (explicit groups/statuses)"


class AnnouncementStatus(models.TextChoices):
    """
    Phase 10: Announcement lifecycle status.
    
    - DRAFT: Being composed, not yet ready to send
    - SCHEDULED: Scheduled for future publish_at time
    - QUEUED: Queued for dispatch
    - SENDING: Currently being dispatched to recipients
    - COMPLETED: Successfully sent to all recipients
    - FAILED: Dispatch failed
    """
    DRAFT = "DRAFT", "Draft"
    SCHEDULED = "SCHEDULED", "Scheduled"
    QUEUED = "QUEUED", "Queued"
    SENDING = "SENDING", "Sending"
    COMPLETED = "COMPLETED", "Completed"
    FAILED = "FAILED", "Failed"


class Announcement(models.Model):
    """
    Phase 10: Announcement/campaign for mass communication.
    
    Lifecycle:
    - DRAFT: Created but not ready
    - SCHEDULED: Waiting for publish_at time
    - QUEUED: Dispatching initiated
    - SENDING: Fan-out in progress
    - COMPLETED: All notifications sent
    - FAILED: Dispatch failed
    
    Security:
    - Branch-scoped (cannot target other branches)
    - Audience authorization enforced (assignment-scoped leaders restricted)
    - Communication preferences respected
    - Idempotent dispatch (cannot re-send COMPLETED/SENDING)
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    branch = models.ForeignKey("organizations.Branch", on_delete=models.CASCADE, related_name="announcements")
    title = models.CharField(max_length=255)
    body = models.TextField()
    
    # Lifecycle status
    status = models.CharField(
        max_length=10,
        choices=AnnouncementStatus.choices,
        default=AnnouncementStatus.DRAFT
    )
    
    # Audience targeting
    audience_type = models.CharField(
        max_length=20,
        choices=AudienceType.choices,
        default=AudienceType.CUSTOM,
        help_text="Phase 10 default is CUSTOM so existing rows/callers that only ever set target_groups/target_membership_statuses keep working unchanged.",
    )
    target_groups = models.ManyToManyField("ministries.Group", blank=True, related_name="announcements")
    target_membership_statuses = models.JSONField(default=list, blank=True)
    target_community = models.CharField(
        max_length=10,
        blank=True,
        help_text="members.CommunityClassification value, set when audience_type=STAFF_COMMUNITY.",
    )
    
    # Delivery channels
    channels = models.JSONField(
        default=list,
        blank=True,
        help_text="List of notifications.NotificationChannel values, e.g. ['EMAIL', 'SMS']. Empty is treated as ['EMAIL'] for backward compatibility with rows created before this field existed.",
    )
    
    # Metadata
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+")
    publish_at = models.DateTimeField()
    expires_at = models.DateTimeField(null=True, blank=True)
    
    # Lifecycle timestamps
    sending_started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    failure_reason = models.TextField(blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "communications_announcement"
        indexes = [models.Index(fields=["branch", "publish_at"])]

    def __str__(self):
        return self.title


class CommunicationPreference(models.Model):
    """
    Phase 10: Per-member communication preferences.
    
    Controls which notification channels a member will receive.
    Default is all channels enabled (opt-out model).
    
    Security:
    - Member can manage own preferences
    - Staff cannot override member preferences
    - Preferences enforced server-side during dispatch
    
    Integration:
    - Used by announcement dispatch
    - Used by event reminders (Phase 7)
    - Used by volunteer reminders (Phase 9)
    """
    member = models.OneToOneField(
        "members.Member",
        on_delete=models.CASCADE,
        related_name="communication_preference"
    )
    
    # Channel preferences
    email_enabled = models.BooleanField(default=True)
    sms_enabled = models.BooleanField(default=True)
    push_enabled = models.BooleanField(default=True)
    
    # Feature preferences
    announcements_enabled = models.BooleanField(default=True)
    
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = "communications_preference"
    
    def __str__(self):
        return f"Preferences for {self.member}"
