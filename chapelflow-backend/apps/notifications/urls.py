<<<<<<< HEAD
from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import DeliveryWebhookView, NotificationViewSet
=======
from rest_framework.routers import DefaultRouter

from .views import NotificationViewSet
>>>>>>> origin/main

router = DefaultRouter()
router.register("", NotificationViewSet, basename="notification")

<<<<<<< HEAD
urlpatterns = [path("webhook/", DeliveryWebhookView.as_view(), name="notification-delivery-webhook")] + router.urls
=======
urlpatterns = router.urls
>>>>>>> origin/main
