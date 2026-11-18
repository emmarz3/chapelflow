from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import BranchViewSet, OrganizationViewSet, PublicContentView, PublicDetailView

router = DefaultRouter()
router.register("organizations", OrganizationViewSet, basename="organization")
router.register("branches", BranchViewSet, basename="branch")

urlpatterns = [
    path("public/content/<slug:slug>/", PublicContentView.as_view(), name="public-content"),
    path("public/<str:kind>/<slug:slug>/", PublicDetailView.as_view(), name="public-detail"),
] + router.urls
