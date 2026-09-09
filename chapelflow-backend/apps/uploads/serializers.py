from rest_framework import serializers

from .models import Upload


class UploadSerializer(serializers.ModelSerializer):
    class Meta:
        model = Upload
        fields = [
            "id", "branch", "uploaded_by", "category", "original_filename",
            "file_url", "content_type", "size_bytes", "created_at",
        ]
        read_only_fields = fields
