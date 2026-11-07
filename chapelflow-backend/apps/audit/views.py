from rest_framework import viewsets
from common.viewsets import StandardReadOnlyModelViewSet

from common.constants.roles import PermissionCodes
from common.permissions.rbac import HasRolePermission
from common.permissions.scoping import BranchScopedQuerysetMixin
from .models import AuditLog
from .serializers import AuditLogSerializer


class AuditLogViewSet(BranchScopedQuerysetMixin, StandardReadOnlyModelViewSet):
    """
    Read-only by design — audit logs must never be editable via the API.

    Branch-scoped by the ACTING user's branch (Phase 1 fix): previously
    this returned every AuditLog row system-wide to anyone holding
    AUDIT_VIEW, which includes CHAPEL_ADMIN — a branch-scoped role. That
    meant a Chapel Admin at Branch A could read audit entries (MFA
    resets with reasons, financial actions, role changes, member-record
    access) for every other branch. AuditLog has no branch FK of its
    own, so this scopes through the actor: `user__branch`.

    Known limitation, carried forward rather than silently claimed as
    solved: this scopes by who performed the action, not which branch's
    data the action touched. A Super Admin (no fixed branch) acting on
    Branch B's data won't show up for a Branch B Chapel Admin under this
    scheme. Full per-resource branch attribution would need per-
    resource-type join logic and is a larger feature than this phase's
    "de-duplicate onto the shared scoping mixin" scope.
    """
    serializer_class = AuditLogSerializer
    permission_classes = [HasRolePermission]
    filterset_fields = ["user", "action", "resource_type"]
    permission_action_map = {
        "list": PermissionCodes.AUDIT_VIEW,
        "retrieve": PermissionCodes.AUDIT_VIEW,
    }
    branch_field_lookup = "user__branch"

    def get_base_queryset(self):
        return AuditLog.objects.select_related("user")
