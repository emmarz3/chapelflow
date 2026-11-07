from rest_framework.permissions import AllowAny

from common.viewsets import StandardModelViewSet
from common.permissions.rbac import ReadOnlyOrHasPermission
from common.constants.roles import PermissionCodes

from .models import College, Department, University
from .serializers import CollegeSerializer, DepartmentSerializer, UniversitySerializer


class _UniversityStructureViewSet(StandardModelViewSet):
    """
    Shared base: University/College/Department are academic reference data,
    not branch-scoped Chapel data (spec section 2 — kept separate from
    apps.organizations Branch scoping on purpose). Writes require the same
    system-configuration permission as role/permission management, since
    this is structural org data, not day-to-day Chapel operations. Reads
    are AllowAny — the public self-registration form (spec section 3) needs
    to populate College/Department dropdowns before the visitor has any
    account at all — this table holds no PII, only academic structure.
    """
    permission_classes = [ReadOnlyOrHasPermission]
    view_permission_code = None  # reads are open regardless of role, see above
    permission_action_map = {
        "create": PermissionCodes.ROLE_MANAGE,
        "update": PermissionCodes.ROLE_MANAGE,
        "partial_update": PermissionCodes.ROLE_MANAGE,
        "destroy": PermissionCodes.ROLE_MANAGE,
    }

    def get_permissions(self):
        if self.request.method in ("GET", "HEAD", "OPTIONS"):
            return [AllowAny()]
        return super().get_permissions()


class UniversityViewSet(_UniversityStructureViewSet):
    queryset = University.objects.all()
    serializer_class = UniversitySerializer
    filterset_fields = ["organization", "is_active"]


class CollegeViewSet(_UniversityStructureViewSet):
    queryset = College.objects.select_related("university").all()
    serializer_class = CollegeSerializer
    filterset_fields = ["university", "is_active"]


class DepartmentViewSet(_UniversityStructureViewSet):
    queryset = Department.objects.select_related("college").all()
    serializer_class = DepartmentSerializer
    filterset_fields = ["college", "is_active"]
