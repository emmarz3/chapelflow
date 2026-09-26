from django.db import transaction
from rest_framework import viewsets
from rest_framework.decorators import action
from common.viewsets import StandardModelViewSet

from common.constants.roles import PermissionCodes
from common.permissions.rbac import HasRolePermission
from common.permissions.scoping import BranchScopedQuerysetMixin
from common.permissions.rbac import IsSuperAdmin
from common.utils.responses import error_response, success_response
from apps.organizations.models import Branch
from .models import Group
from .catalog import ensure_standard_chapel_groups
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

    @action(
        detail=False,
        methods=["post"],
        url_path="bootstrap-chapel-groups",
        permission_classes=[IsSuperAdmin],
    )
    def bootstrap_chapel_groups(self, request):
        """Create the standard CUC unit and fellowship groups for account assignment and student join requests."""
        branch = Branch.objects.filter(
            name__iexact="Chrisland University Chapel", is_active=True
        ).first()
        if branch is None:
            return error_response("The active Chrisland University Chapel branch was not found.", status=404)

        with transaction.atomic():
            created = ensure_standard_chapel_groups(branch)

        return success_response(
            {"created": [{"id": str(group.id), "name": group.name} for group in created], "count": len(created)},
            message=f"{len(created)} chapel group(s) added. Existing groups were left unchanged.",
        )
