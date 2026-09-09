from rest_framework import viewsets
from common.viewsets import StandardModelViewSet

from common.constants.roles import PermissionCodes
from common.permissions.rbac import HasRolePermission
from common.permissions.scoping import BranchScopedQuerysetMixin
from .models import Household
from .serializers import HouseholdSerializer


class HouseholdViewSet(BranchScopedQuerysetMixin, StandardModelViewSet):
    serializer_class = HouseholdSerializer
    permission_classes = [HasRolePermission]
    filterset_fields = ["branch"]
    search_fields = ["name"]

    permission_action_map = {
        "list": PermissionCodes.MEMBERS_VIEW,
        "retrieve": PermissionCodes.MEMBERS_VIEW,
        "create": PermissionCodes.MEMBERS_CREATE,
        "update": PermissionCodes.MEMBERS_UPDATE,
        "partial_update": PermissionCodes.MEMBERS_UPDATE,
        "destroy": PermissionCodes.MEMBERS_DELETE,
    }

    def get_base_queryset(self):
        return Household.objects.select_related("branch", "head").prefetch_related("members")
