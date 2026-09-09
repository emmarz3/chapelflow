from rest_framework import viewsets
from common.viewsets import StandardModelViewSet

from common.constants.roles import PermissionCodes
from common.permissions.rbac import HasRolePermission
from common.permissions.scoping import BranchScopedQuerysetMixin
from .models import Group
from .serializers import GroupSerializer


class GroupViewSet(BranchScopedQuerysetMixin, StandardModelViewSet):
    serializer_class = GroupSerializer
    permission_classes = [HasRolePermission]
    filterset_fields = ["branch", "group_type", "is_active", "parent"]
    search_fields = ["name"]

    # The model IS Group, so leadership scoping (spec section 6/7) filters
    # on its own `id` — a FELLOWSHIP_LEADER only sees the Fellowship(s)
    # they actively lead per GroupMembership, never every Group in branch.
    group_field_lookup = "id"

    permission_action_map = {
        "list": PermissionCodes.MEMBERS_VIEW,
        "retrieve": PermissionCodes.MEMBERS_VIEW,
        "create": PermissionCodes.MEMBERS_CREATE,
        "update": PermissionCodes.MEMBERS_UPDATE,
        "partial_update": PermissionCodes.MEMBERS_UPDATE,
        "destroy": PermissionCodes.MEMBERS_DELETE,
    }

    def get_base_queryset(self):
        return Group.objects.select_related("branch", "parent", "leader")
