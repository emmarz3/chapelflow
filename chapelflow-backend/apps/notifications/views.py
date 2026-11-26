from django.utils import timezone
from django.conf import settings
from urllib.parse import urlparse
from rest_framework import viewsets
from common.viewsets import StandardReadOnlyModelViewSet
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from common.utils.responses import success_response
from .models import Notification, NotificationStatus, NotificationChannel, WebPushSubscription
from .serializers import NotificationSerializer
from .services import WebhookVerificationError, process_delivery_webhook


class NotificationViewSet(StandardReadOnlyModelViewSet):
    """Users only ever see their own notifications."""
    serializer_class = NotificationSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Notification.objects.filter(recipient=self.request.user, channel=NotificationChannel.IN_APP).exclude(status=NotificationStatus.SKIPPED).order_by("-created_at")

    @action(detail=False, methods=["get"], url_path="unread-count")
    def unread_count(self, request):
        return success_response({"count": self.get_queryset().filter(read_at__isnull=True).count()})

    @action(detail=True, methods=["post"], url_path="mark-read")
    def mark_read(self, request, pk=None):
        notification = self.get_object()
        if notification.read_at is None:
            notification.read_at = timezone.now()
            notification.save(update_fields=["read_at"])
        return success_response(message="Marked as read.")


class WebPushSubscriptionView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return success_response({"enabled": bool(settings.WEB_PUSH_PUBLIC_KEY and settings.WEB_PUSH_PRIVATE_KEY), "public_key": settings.WEB_PUSH_PUBLIC_KEY})

    def post(self, request):
        if not (settings.WEB_PUSH_PUBLIC_KEY and settings.WEB_PUSH_PRIVATE_KEY):
            return Response({"message": "Browser push is not configured."}, status=503)
        endpoint = str(request.data.get("endpoint") or "")
        keys = request.data.get("keys") or {}
        host = urlparse(endpoint).hostname or ""
        allowed = host in {"fcm.googleapis.com", "updates.push.services.mozilla.com", "web.push.apple.com"} or host.endswith(".notify.windows.com")
        if urlparse(endpoint).scheme != "https" or not allowed or len(endpoint) > 2048 or not isinstance(keys, dict) or any(not isinstance(keys.get(name), str) or not 10 <= len(keys[name]) <= 256 for name in ("p256dh", "auth")):
            return Response({"message": "Invalid browser push subscription."}, status=400)
        existing = WebPushSubscription.objects.filter(endpoint=endpoint).first()
        if existing and existing.user_id != request.user.id:
            return Response({"message": "This device is already linked to another account."}, status=409)
        WebPushSubscription.objects.update_or_create(endpoint=endpoint, defaults={"user": request.user, "p256dh": keys["p256dh"], "auth": keys["auth"]})
        return success_response(message="Browser push enabled.")

    def delete(self, request):
        endpoint = str(request.query_params.get("endpoint") or "")
        WebPushSubscription.objects.filter(user=request.user, endpoint=endpoint).delete()
        return success_response(message="Browser push disabled on this device.")
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
