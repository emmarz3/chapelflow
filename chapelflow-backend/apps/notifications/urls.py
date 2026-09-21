from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import NotificationViewSet, NotificationWebhookView

router = DefaultRouter()
router.register("", NotificationViewSet, basename="notification")

# The explicit webhook route must come BEFORE the router: otherwise
# "webhook/" is captured by the router's <pk>/ detail route and requires auth.
urlpatterns = [
    path("webhook/", NotificationWebhookView.as_view(), name="notification-webhook"),
] + router.urls
