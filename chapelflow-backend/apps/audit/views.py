from django.http import HttpResponse
from django.db.models import Q
from rest_framework import viewsets
from rest_framework.decorators import action
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
        "export_pdf": PermissionCodes.AUDIT_VIEW,
    }
    branch_field_lookup = "user__branch"

    def get_base_queryset(self):
        return AuditLog.objects.select_related("user")

    @action(detail=False, methods=["get"], url_path="export-pdf")
    def export_pdf(self, request):
        """Export every audit entry visible through this viewset's branch scope."""
        search = request.query_params.get("search", "").strip()
        queryset = self.filter_queryset(self.get_queryset())
        if search:
            queryset = queryset.filter(
                Q(action__icontains=search)
                | Q(resource_type__icontains=search)
                | Q(resource_id__icontains=search)
                | Q(user__email__icontains=search)
            )

        from apps.audit.models import AuditAction
        from apps.audit.services import write_audit_log
        from apps.reports.services import export_rows_pdf

        # Log the export before reading the report so the generated file
        # includes its own audit event.
        write_audit_log(
            AuditAction.REPORT_EXPORT,
            "audit.AuditLog",
            metadata={"format": "PDF", "scope": "authorized_queryset"},
            user=request.user,
        )

        rows = []
        for entry in queryset.order_by("-created_at").iterator(chunk_size=500):
            rows.append({
                "timestamp": entry.created_at,
                "actor": entry.user.email if entry.user_id else "System",
                "action": entry.get_action_display() if hasattr(entry, "get_action_display") else entry.action,
                "resource_type": entry.resource_type,
                "resource_id": entry.resource_id,
                "metadata": entry.metadata,
                "ip_address": entry.ip_address or "",
                "user_agent": entry.user_agent,
            })

        content = export_rows_pdf(rows, title="ChapelFlow Audit Trail")
        response = HttpResponse(content, content_type="application/pdf")
        response["Content-Disposition"] = 'attachment; filename="chapelflow-audit.pdf"'
        response["Cache-Control"] = "private, no-store"
        return response
