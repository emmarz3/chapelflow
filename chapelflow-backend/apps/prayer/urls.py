from rest_framework.routers import DefaultRouter

from .views import PrayerNoteViewSet, PrayerRequestViewSet, TestimonyViewSet

router = DefaultRouter()
router.register("requests", PrayerRequestViewSet, basename="prayer-request")
router.register("notes", PrayerNoteViewSet, basename="prayer-note")
router.register("testimonies", TestimonyViewSet, basename="testimony")

urlpatterns = router.urls
