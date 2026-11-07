from django.utils import timezone
from rest_framework import viewsets
from common.viewsets import StandardReadOnlyModelViewSet
from rest_framework.decorators import action
<<<<<<< HEAD
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from common.utils.responses import success_response
from .models import Notification, NotificationStatus
from .serializers import NotificationSerializer
from .services import WebhookVerificationError, process_delivery_webhook
=======

from common.utils.responses import success_response
from .models import Notification
from .serializers import NotificationSerializer
>>>>>>> origin/main


class NotificationViewSet(StandardReadOnlyModelViewSet):
    """Users only ever see their own notifications."""
    serializer_class = NotificationSerializer
<<<<<<< HEAD
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Notification.objects.filter(recipient=self.request.user).exclude(status=NotificationStatus.SKIPPED).order_by("-created_at")

    @action(detail=False, methods=["get"], url_path="unread-count")
    def unread_count(self, request):
        return success_response({"count": self.get_queryset().filter(read_at__isnull=True).count()})
=======

    def get_queryset(self):
        return Notification.objects.filter(recipient=self.request.user).order_by("-created_at")
>>>>>>> origin/main

    @action(detail=True, methods=["post"], url_path="mark-read")
    def mark_read(self, request, pk=None):
        notification = self.get_object()
<<<<<<< HEAD
        if notification.read_at is None:
            notification.read_at = timezone.now()
            notification.save(update_fields=["read_at"])
        return success_response(message="Marked as read.")
class DeliveryWebhookView(APIView):
    """Accept signed delivery updates from the configured notification provider."""

    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_scope = "public"

    def post(self, request):
        try:
            result = process_delivery_webhook(request)
        except WebhookVerificationError as exc:
            return Response({"detail": str(exc)}, status=400)
        return Response(result)

=======
        notification.read_at = timezone.now()
        notification.save(update_fields=["read_at"])
        return success_response(message="Marked as read.")
>>>>>>> origin/main
