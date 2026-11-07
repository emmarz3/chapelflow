from rest_framework.routers import DefaultRouter

from .views import MemberViewSet, MemberFollowUpViewSet, EngagementMetricsViewSet

router = DefaultRouter()
router.register("members", MemberViewSet, basename="member")
router.register("follow-ups", MemberFollowUpViewSet, basename="member-followup")
router.register("engagement", EngagementMetricsViewSet, basename="engagement-metrics")

urlpatterns = router.urls
