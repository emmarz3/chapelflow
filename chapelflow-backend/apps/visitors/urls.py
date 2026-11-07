from rest_framework.routers import DefaultRouter

from .views import VisitorViewSet

router = DefaultRouter()
router.register("", VisitorViewSet, basename="visitor")

urlpatterns = router.urls
