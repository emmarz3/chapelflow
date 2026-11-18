from rest_framework.routers import DefaultRouter

from .views import GroupViewSet

router = DefaultRouter()
router.register("groups-catalog", GroupViewSet, basename="ministry-group")

urlpatterns = router.urls
