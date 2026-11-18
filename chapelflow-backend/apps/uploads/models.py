import uuid

from django.conf import settings
from django.db import models


class UploadCategory(models.TextChoices):
    MEMBER_PHOTO = "MEMBER_PHOTO", "Member Photo"
    BRANCH_LOGO = "BRANCH_LOGO", "Branch Logo"
    EVENT_IMAGE = "EVENT_IMAGE", "Event Image"
    DOCUMENT = "DOCUMENT", "Document"
    SERMON_AUDIO = "SERMON_AUDIO", "Sermon Audio"
    MEDIA_CONTENT = "MEDIA_CONTENT", "Published media content"
    SOCIAL_POST = "SOCIAL_POST", "Upper Room community post"
    OTHER = "OTHER", "Other"


class Upload(models.Model):
    """
    PostgreSQL stores only metadata; the actual bytes live in
    Cloudinary/S3/local disk depending on settings.STORAGE_PROVIDER.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    branch = models.ForeignKey("organizations.Branch", null=True, blank=True, on_delete=models.SET_NULL, related_name="uploads")
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="uploads")
    category = models.CharField(max_length=20, choices=UploadCategory.choices, default=UploadCategory.OTHER)
    original_filename = models.CharField(max_length=255)
    file_url = models.URLField()
    content_type = models.CharField(max_length=100, blank=True)
    size_bytes = models.PositiveBigIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "uploads_upload"
