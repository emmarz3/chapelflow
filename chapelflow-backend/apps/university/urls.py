from rest_framework.routers import DefaultRouter

from .views import CollegeViewSet, DepartmentViewSet, UniversityViewSet

router = DefaultRouter()
router.register("universities", UniversityViewSet, basename="university")
router.register("colleges", CollegeViewSet, basename="college")
router.register("departments", DepartmentViewSet, basename="department")

urlpatterns = router.urls
