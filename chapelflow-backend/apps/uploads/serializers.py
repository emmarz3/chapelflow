from rest_framework import serializers
from django.conf import settings
from django.urls import reverse

from .models import Upload, UploadCategory
from .storage import S3StorageService


def public_media_url(upload):
    return f"{settings.PUBLIC_BACKEND_URL.rstrip('/')}{reverse('uploads-public-media', kwargs={'pk': upload.pk})}"


class UploadSerializer(serializers.ModelSerializer):
    file_url = serializers.SerializerMethodField()

    def get_file_url(self, upload):
        if upload.category == UploadCategory.MEDIA_CONTENT and S3StorageService().owns_media_url(upload.file_url):
            return public_media_url(upload)
        return upload.file_url

    class Meta:
        model = Upload
        fields = [
            "id", "branch", "uploaded_by", "category", "original_filename",
            "file_url", "content_type", "size_bytes", "created_at",
        ]
        read_only_fields = fields
