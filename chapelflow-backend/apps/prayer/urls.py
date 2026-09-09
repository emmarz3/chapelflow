from rest_framework.routers import DefaultRouter

from .views import PrayerNoteViewSet, PrayerRequestViewSet

router = DefaultRouter()
router.register("requests", PrayerRequestViewSet, basename="prayer-request")
router.register("notes", PrayerNoteViewSet, basename="prayer-note")

urlpatterns = router.urls
