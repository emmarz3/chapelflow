from django.utils import timezone
from rest_framework import viewsets
from common.viewsets import StandardReadOnlyModelViewSet
from rest_framework.decorators import action

from common.utils.responses import success_response
from .models import Notification
from .serializers import NotificationSerializer


class NotificationViewSet(StandardReadOnlyModelViewSet):
    """Users only ever see their own notifications."""
    serializer_class = NotificationSerializer

    def get_queryset(self):
        return Notification.objects.filter(recipient=self.request.user).order_by("-created_at")

    @action(detail=True, methods=["post"], url_path="mark-read")
    def mark_read(self, request, pk=None):
        notification = self.get_object()
        notification.read_at = timezone.now()
        notification.save(update_fields=["read_at"])
        return success_response(message="Marked as read.")
