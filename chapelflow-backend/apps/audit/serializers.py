from rest_framework import serializers

from .models import AuditLog


class AuditLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = AuditLog
        fields = [
            "id", "user", "action", "resource_type", "resource_id",
            "metadata", "ip_address", "user_agent", "created_at",
        ]
        read_only_fields = fields
