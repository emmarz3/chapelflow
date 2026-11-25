from django.urls import path
from rest_framework.routers import DefaultRouter

from .leadership import CommunityOversightView, LeadershipNoticeDetailView, LeadershipNoticeListView, LeadershipReplyView
from .views import AnnouncementViewSet, CommunicationPreferenceViewSet, MyCommunicationPreferenceView, StudentAnnouncementFeedView

router = DefaultRouter()
router.register("announcements", AnnouncementViewSet, basename="announcement")
router.register("preferences", CommunicationPreferenceViewSet, basename="communication-preference")

urlpatterns = [
    path("community-oversight/", CommunityOversightView.as_view(), name="community-oversight"),
    path("community-oversight/<uuid:group_id>/", CommunityOversightView.as_view(), name="community-oversight-detail"),
    path("leadership/notices/", LeadershipNoticeListView.as_view(), name="leadership-notice-list"),
    path("leadership/notices/<uuid:notice_id>/", LeadershipNoticeDetailView.as_view(), name="leadership-notice-detail"),
    path("leadership/notices/<uuid:notice_id>/replies/", LeadershipReplyView.as_view(), name="leadership-notice-replies"),
    path("preferences/me/", MyCommunicationPreferenceView.as_view(), name="my-communication-preferences"),
    path("announcements/me/", StudentAnnouncementFeedView.as_view(), name="student-announcement-feed"),
] + router.urls
