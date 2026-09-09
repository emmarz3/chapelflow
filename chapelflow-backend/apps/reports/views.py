from rest_framework.decorators import action

from common.constants.roles import PermissionCodes
from common.permissions.rbac import HasRolePermission
from common.permissions.scoping import BranchScopedQuerysetMixin
from common.utils.responses import success_response
from common.viewsets import StandardModelViewSet

from .models import ReportJob
from .serializers import ReportJobSerializer
from .services import REPORT_EXPORTERS
from .tasks import run_report_job


class ReportJobViewSet(BranchScopedQuerysetMixin, StandardModelViewSet):
    """
    Creating a report job always returns immediately (202) and dispatches
    a Celery task — reports are never generated inline in the request.
    """
    serializer_class = ReportJobSerializer
    permission_classes = [HasRolePermission]
    filterset_fields = ["branch", "report_type", "status"]
    http_method_names = ["get", "post", "head", "options"]

    permission_action_map = {
        "list": PermissionCodes.REPORTS_VIEW,
        "retrieve": PermissionCodes.REPORTS_VIEW,
        "create": PermissionCodes.REPORTS_EXPORT,
        "formats": PermissionCodes.REPORTS_VIEW,
    }

    def get_base_queryset(self):
        return ReportJob.objects.select_related("branch", "requested_by")

    def perform_create(self, serializer):
        job = serializer.save(requested_by=self.request.user)
        run_report_job.delay(str(job.id))

    @action(detail=False, methods=["get"])
    def formats(self, request):
        """
        GET /api/v1/reports/jobs/formats/ — which export_format values are
        genuinely implemented right now (spec section 16: don't claim a
        format the export engine doesn't actually support). Sourced
        directly from apps.reports.services.REPORT_EXPORTERS, so this can
        never drift out of sync with what run_report_job actually does.
        """
        return success_response(
            {fmt: {"content_type": cfg["content_type"], "extension": cfg["extension"]}
             for fmt, cfg in REPORT_EXPORTERS.items()}
        )
