from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import BranchViewSet, OrganizationViewSet, PublicContentView

router = DefaultRouter()
router.register("organizations", OrganizationViewSet, basename="organization")
router.register("branches", BranchViewSet, basename="branch")

urlpatterns = [
    path("public/content/<slug:slug>/", PublicContentView.as_view(), name="public-content"),
] + router.urls
