from rest_framework.routers import DefaultRouter

from .views import PastoralCaseViewSet, PastoralNoteViewSet

router = DefaultRouter()
router.register("cases", PastoralCaseViewSet, basename="pastoral-case")
router.register("notes", PastoralNoteViewSet, basename="pastoral-note")

urlpatterns = router.urls
