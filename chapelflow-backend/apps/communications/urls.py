from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import AnnouncementViewSet, CommunicationPreferenceViewSet, MyCommunicationPreferenceView, StudentAnnouncementFeedView

router = DefaultRouter()
router.register("announcements", AnnouncementViewSet, basename="announcement")
router.register("preferences", CommunicationPreferenceViewSet, basename="communication-preference")

urlpatterns = [
    path("preferences/me/", MyCommunicationPreferenceView.as_view(), name="my-communication-preferences"),
    path("announcements/me/", StudentAnnouncementFeedView.as_view(), name="student-announcement-feed"),
] + router.urls
