import uuid

from django.conf import settings
from django.db import models


class SocialPostStatus(models.TextChoices):
    PUBLISHED = "PUBLISHED", "Published"
    REMOVED = "REMOVED", "Removed"


class SocialMediaType(models.TextChoices):
    IMAGE = "IMAGE", "Image"
    VIDEO = "VIDEO", "Video"


class SocialPost(models.Model):
    """A branch-safe community post in The Upper Room."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    branch = models.ForeignKey("organizations.Branch", on_delete=models.PROTECT, related_name="upper_room_posts")
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="upper_room_posts")
    caption = models.CharField(max_length=1_000, blank=True)
    status = models.CharField(max_length=12, choices=SocialPostStatus.choices, default=SocialPostStatus.PUBLISHED)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "social_post"
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["branch", "status", "created_at"])]


class SocialPostMedia(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    post = models.ForeignKey(SocialPost, on_delete=models.CASCADE, related_name="media")
    upload = models.ForeignKey("uploads.Upload", on_delete=models.PROTECT, related_name="upper_room_media")
    media_type = models.CharField(max_length=8, choices=SocialMediaType.choices)
    position = models.PositiveSmallIntegerField(default=0)

    class Meta:
        db_table = "social_post_media"
        ordering = ["position", "id"]
        constraints = [models.UniqueConstraint(fields=["post", "position"], name="social_post_media_position_unique")]


class SocialReaction(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    post = models.ForeignKey(SocialPost, on_delete=models.CASCADE, related_name="likes")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="upper_room_likes")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "social_reaction"
        constraints = [models.UniqueConstraint(fields=["post", "user"], name="social_one_like_per_user")]


class SocialCommentStatus(models.TextChoices):
    PUBLISHED = "PUBLISHED", "Published"
    REMOVED = "REMOVED", "Removed"


class SocialComment(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    post = models.ForeignKey(SocialPost, on_delete=models.CASCADE, related_name="comments")
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="upper_room_comments")
    body = models.CharField(max_length=750)
    status = models.CharField(max_length=12, choices=SocialCommentStatus.choices, default=SocialCommentStatus.PUBLISHED)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "social_comment"
        ordering = ["created_at"]
        indexes = [models.Index(fields=["post", "status", "created_at"])]
