from rest_framework import serializers

from .models import Notification


class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = [
            "id", "recipient", "recipient_member", "channel", "title",
<<<<<<< HEAD
            "body", "category", "href", "status", "read_at", "created_at", "sent_at",
=======
            "body", "status", "read_at", "created_at", "sent_at",
>>>>>>> origin/main
        ]
        read_only_fields = fields
