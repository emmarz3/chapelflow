from rest_framework.routers import DefaultRouter

from .views import VolunteerAssignmentViewSet, VolunteerAvailabilityViewSet, VolunteerProfileViewSet

router = DefaultRouter()
router.register("profiles", VolunteerProfileViewSet, basename="volunteer-profile")
router.register("availability", VolunteerAvailabilityViewSet, basename="volunteer-availability")
router.register("assignments", VolunteerAssignmentViewSet, basename="volunteer-assignment")

urlpatterns = router.urls
