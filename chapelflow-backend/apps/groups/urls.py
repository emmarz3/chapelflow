from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import GroupJoinRequestViewSet, GroupMeetingViewSet, GroupMembershipViewSet, GroupTaskViewSet, MyCommunityDetailView, MyCommunityListView, MyGroupJoinRequestView

router = DefaultRouter()
router.register("group-memberships", GroupMembershipViewSet, basename="group-membership")
router.register("group-join-requests", GroupJoinRequestViewSet, basename="group-join-request")
router.register("group-tasks", GroupTaskViewSet, basename="group-task")
router.register("group-meetings", GroupMeetingViewSet, basename="group-meeting")

urlpatterns = [
    path("community-memberships/", MyCommunityListView.as_view(), name="my-communities"),
    path("community-memberships/<uuid:group_id>/", MyCommunityDetailView.as_view(), name="my-community-detail"),
    path("group-join-requests/me/", MyGroupJoinRequestView.as_view(), name="my-group-join-requests"),
] + router.urls
