from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import CounsellingRequestView, PastoralCaseViewSet, PastoralNoteViewSet

router = DefaultRouter()
router.register("cases", PastoralCaseViewSet, basename="pastoral-case")
router.register("notes", PastoralNoteViewSet, basename="pastoral-note")

urlpatterns = [
    path("counselling-requests/", CounsellingRequestView.as_view(), name="counselling-request"),
] + router.urls
