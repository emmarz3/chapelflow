from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import DeliveryWebhookView, NotificationViewSet

router = DefaultRouter()
router.register("", NotificationViewSet, basename="notification")

urlpatterns = [path("webhook/", DeliveryWebhookView.as_view(), name="notification-delivery-webhook")] + router.urls
