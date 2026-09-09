from rest_framework import viewsets
from django.utils import timezone
from common.viewsets import StandardModelViewSet

from common.constants.roles import Roles
from common.permissions.rbac import IsSuperAdmin
from common.permissions.scoping import BranchScopedQuerysetMixin
from common.utils.responses import success_response
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.views import APIView
from .models import Branch, Organization
from .serializers import BranchSerializer, OrganizationSerializer


class PublicContentView(APIView):
    """Public chapel pages served without exposing private organization data."""
    permission_classes = [AllowAny]

    content = {
        "home": {
            "eyebrow": "Faith. Fellowship. Formation.",
            "title": "A chapel community for every part of university life.",
            "description": "Join us as we worship, grow, and serve together at Chrisland University Chapel, Abeokuta.",
            "sections": [
                {"id": "welcome", "heading": "Welcome home", "body": "A place to belong, believe, and become through worship, fellowship, and service.", "action": {"label": "See upcoming events", "href": "/events"}},
                {"id": "service", "heading": "Sunday worship", "body": "Gather with the chapel community each Sunday at 9:00 AM."},
            ],
        },
        "about": {
            "eyebrow": "About the chapel", "title": "A community rooted in faith and service.",
            "description": "Chrisland University Chapel serves students and staff through worship, care, and formation.",
            "sections": [{"id": "about", "heading": "Our community", "body": "We create space for students and staff to grow in faith and serve one another."}],
        },
        "events": {
            "eyebrow": "Chapel life", "title": "Events and gatherings", "description": "Find worship services, fellowships, and campus gatherings.",
            "sections": [{"id": "events", "heading": "Plan your visit", "body": "View upcoming events and register through ChapelFlow.", "action": {"label": "View events", "href": "/app/events"}}],
        },
    }

    def get(self, request, slug):
        content = self.content.get(slug) or {
            "eyebrow": "Chrisland University Chapel",
            "title": slug.replace("-", " ").title(),
            "description": "Chapel content and updates for the university community.",
            "sections": [{"id": slug, "body": "This page is being prepared by the chapel team."}],
        }
        return success_response({"slug": slug, **content, "updatedAt": timezone.now().isoformat()})


class OrganizationViewSet(StandardModelViewSet):
    """Only super admins manage organizations (top of the hierarchy)."""
    queryset = Organization.objects.all().order_by("name")
    serializer_class = OrganizationSerializer

    def get_permissions(self):
        if self.action in ("list", "retrieve"):
            return [IsAuthenticated()]
        return [IsSuperAdmin()]


class BranchViewSet(BranchScopedQuerysetMixin, StandardModelViewSet):
    """
    Phase 1 fix: previously this hand-rolled branch scoping and, in doing
    so, missed the ORG_WIDE_SCOPE_ROLES (Chaplain) case entirely — a
    Chaplain fell through to the branch-only check and could list only
    their own single branch, not every branch in their Organization as
    intended everywhere else. Moved onto the shared mixin (extended with
    an "id" self-lookup, since this model IS the branch, not something
    pointing at one) so this gets the same three-tier scoping as every
    other branch-scoped endpoint and can't drift from it again.
    """
    serializer_class = BranchSerializer
    filterset_fields = ["organization", "branch_type", "parent", "is_active"]
    search_fields = ["name", "city"]
    branch_field_lookup = "id"

    def get_base_queryset(self):
        return Branch.objects.select_related("organization", "parent").order_by("name")

    def get_permissions(self):
        if self.action == "list":
            # Registration needs a branch identifier before a user has an
            # account. The list exposes only ordinary location metadata;
            # create/update/delete remain super-admin-only.
            return [AllowAny()]
        if self.action == "retrieve":
            return [IsAuthenticated()]
        return [IsSuperAdmin()]
