from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny
from rest_framework.views import APIView

from common.utils.responses import error_response, success_response
from common.viewsets import StandardReadOnlyModelViewSet
from .models import Notification
from .serializers import NotificationSerializer
from .services import WebhookVerificationError, process_delivery_webhook


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


@method_decorator(csrf_exempt, name="dispatch")
class NotificationWebhookView(APIView):
    """
    POST /api/v1/notifications/webhook/

    Delivery-receipt callback from the SMS/email/push provider. Public (a
    provider cannot authenticate as a ChapelFlow user) but every request's
    HMAC signature is verified before any state change, an unset secret
    fails closed, and processing is idempotent against provider retries.
    Mirrors PaymentWebhookView in apps.finance.
    """
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        try:
            result = process_delivery_webhook(request)
        except WebhookVerificationError as exc:
            return error_response(str(exc), status=400)
        return success_response(result)
