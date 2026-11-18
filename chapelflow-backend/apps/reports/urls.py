from rest_framework.routers import DefaultRouter

from .views import ReportJobViewSet

router = DefaultRouter()
router.register("jobs", ReportJobViewSet, basename="report-job")

urlpatterns = router.urls
