from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import CommunityAnnouncementView, CommunityLeadershipDirectoryView, CommunityMeetingView, CommunityMemberDirectoryView, CommunityMessageView, CommunityResourceView, GroupJoinRequestViewSet, GroupMeetingViewSet, GroupMembershipViewSet, GroupTaskViewSet, MyCommunityDetailView, MyCommunityListView, MyGroupJoinRequestView

router = DefaultRouter()
router.register("group-memberships", GroupMembershipViewSet, basename="group-membership")
router.register("group-join-requests", GroupJoinRequestViewSet, basename="group-join-request")
router.register("group-tasks", GroupTaskViewSet, basename="group-task")
router.register("group-meetings", GroupMeetingViewSet, basename="group-meeting")

urlpatterns = [
    path("community-memberships/", MyCommunityListView.as_view(), name="my-communities"),
    path("community-memberships/leadership-directory/", CommunityLeadershipDirectoryView.as_view(), name="community-leadership-directory"),
    path("community-memberships/<uuid:group_id>/", MyCommunityDetailView.as_view(), name="my-community-detail"),
    path("community-memberships/<uuid:group_id>/messages/", CommunityMessageView.as_view(), name="community-messages"),
    path("community-memberships/<uuid:group_id>/resources/", CommunityResourceView.as_view(), name="community-resources"),
    path("community-memberships/<uuid:group_id>/announcements/", CommunityAnnouncementView.as_view(), name="community-announcements"),
    path("community-memberships/<uuid:group_id>/meetings/", CommunityMeetingView.as_view(), name="community-meetings"),
    path("community-memberships/<uuid:group_id>/members/", CommunityMemberDirectoryView.as_view(), name="community-members"),
    path("community-memberships/<uuid:group_id>/members/<uuid:record_id>/", CommunityMemberDirectoryView.as_view(), name="community-member-update"),
    path("group-join-requests/me/", MyGroupJoinRequestView.as_view(), name="my-group-join-requests"),
] + router.urls
