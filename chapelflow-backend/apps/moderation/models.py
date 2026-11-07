import uuid

from django.conf import settings
from django.db import models


class TargetKind(models.TextChoices):
    POST = "POST", "Community post"
    COMMENT = "COMMENT", "Comment"
    GROUP_MESSAGE = "GROUP_MESSAGE", "Group message"
    GROUP_RESOURCE = "GROUP_RESOURCE", "Group resource"
    GROUP_ANNOUNCEMENT = "GROUP_ANNOUNCEMENT", "Group announcement"
    PRAYER = "PRAYER", "Prayer request"
    TESTIMONY = "TESTIMONY", "Testimony"


class ReportReason(models.TextChoices):
    HARASSMENT = "HARASSMENT", "Harassment"
    BULLYING = "BULLYING", "Bullying"
    SPAM = "SPAM", "Spam"
    IMPERSONATION = "IMPERSONATION", "Impersonation"
    HATE_SPEECH = "HATE_SPEECH", "Hate speech"
    INAPPROPRIATE = "INAPPROPRIATE", "Inappropriate content"
    PRIVACY = "PRIVACY", "Privacy violation"
    OTHER = "OTHER", "Other"


class ReportStatus(models.TextChoices):
    PENDING = "PENDING", "Pending"
    REVIEWED = "REVIEWED", "Reviewed"
    DISMISSED = "DISMISSED", "Dismissed"
    ESCALATED = "ESCALATED", "Escalated"


class RestrictionState(models.TextChoices):
    HIDDEN = "HIDDEN", "Hidden"
    REMOVED = "REMOVED", "Removed"


class ModerationReport(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    branch = models.ForeignKey("organizations.Branch", on_delete=models.PROTECT)
    reporter = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="moderation_reports")
    target_author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="reports_on_content")
    target_kind = models.CharField(max_length=24, choices=TargetKind.choices)
    target_id = models.UUIDField()
    reason = models.CharField(max_length=20, choices=ReportReason.choices)
    explanation = models.TextField(blank=True)
    content_snapshot = models.TextField()
    status = models.CharField(max_length=12, choices=ReportStatus.choices, default=ReportStatus.PENDING)
    assigned_to = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="assigned_moderation_reports")
    reviewed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "moderation_report"
        indexes = [models.Index(fields=["branch", "status", "created_at"]), models.Index(fields=["target_kind", "target_id"])]


class ModerationEvent(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    report = models.ForeignKey(ModerationReport, on_delete=models.PROTECT, related_name="events")
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    action = models.CharField(max_length=16)
    note = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "moderation_event"
        ordering = ["created_at", "id"]


class ModerationRestriction(models.Model):
    branch = models.ForeignKey("organizations.Branch", on_delete=models.CASCADE)
    target_kind = models.CharField(max_length=24, choices=TargetKind.choices)
    target_id = models.UUIDField()
    state = models.CharField(max_length=8, choices=RestrictionState.choices)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "moderation_restriction"
        constraints = [models.UniqueConstraint(fields=["branch", "target_kind", "target_id"], name="moderation_one_restriction_per_target")]
        indexes = [models.Index(fields=["target_kind", "target_id"])]
