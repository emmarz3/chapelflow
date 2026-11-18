from rest_framework.routers import DefaultRouter

from .views import EventRegistrationViewSet, EventTypeViewSet, EventViewSet, LocationViewSet

router = DefaultRouter()
router.register("events", EventViewSet, basename="event")
router.register("event-types", EventTypeViewSet, basename="event-type")
router.register("locations", LocationViewSet, basename="location")
router.register("event-registrations", EventRegistrationViewSet, basename="event-registration")

urlpatterns = router.urls
