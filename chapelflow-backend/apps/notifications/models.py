import uuid

from django.conf import settings
from django.db import models


class NotificationChannel(models.TextChoices):
    EMAIL = "EMAIL", "Email"
    SMS = "SMS", "SMS"
    PUSH = "PUSH", "Push"
    IN_APP = "IN_APP", "In-App"


class NotificationStatus(models.TextChoices):
    PENDING = "PENDING", "Pending"
    SENT = "SENT", "Sent"
    DELIVERED = "DELIVERED", "Delivered"
    FAILED = "FAILED", "Failed"
    STUBBED = "STUBBED", "Stubbed (provider not configured)"


class BirthdayAnnouncement(models.Model):
    """One branch-safe, idempotent birthday celebration per member per day."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    member = models.ForeignKey("members.Member", on_delete=models.CASCADE, related_name="birthday_announcements")
    celebrated_on = models.DateField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "notifications_birthday_announcement"
        constraints = [
            models.UniqueConstraint(fields=["member", "celebrated_on"], name="unique_member_birthday_announcement"),
        ]
        indexes = [models.Index(fields=["celebrated_on"], name="notificatio_celebra_e72f02_idx")]


class Notification(models.Model):
    """
    A single notification delivery attempt to a user, on a specific
    channel. Delivery is always executed by a Celery task via the
    provider abstraction in services.py, never synchronously in a view.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    recipient = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="notifications")
    recipient_member = models.ForeignKey(
        "members.Member", null=True, blank=True, on_delete=models.SET_NULL, related_name="notifications"
    )
    source_announcement = models.ForeignKey(
        "communications.Announcement", null=True, blank=True, on_delete=models.SET_NULL, related_name="notifications",
        help_text="Set when this notification was fanned out from a communications.Announcement, "
                  "so delivery state can be tracked/aggregated per-campaign.",
    )
    birthday_announcement = models.ForeignKey(
        BirthdayAnnouncement, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="notifications",
    )
    channel = models.CharField(max_length=10, choices=NotificationChannel.choices)
    title = models.CharField(max_length=255)
    body = models.TextField()
    status = models.CharField(max_length=10, choices=NotificationStatus.choices, default=NotificationStatus.PENDING)
    provider_response = models.JSONField(null=True, blank=True)
    read_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    sent_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "notifications_notification"
        indexes = [models.Index(fields=["recipient", "status"])]

    def __str__(self):
        return f"{self.channel}:{self.title} -> {self.recipient_id}"
