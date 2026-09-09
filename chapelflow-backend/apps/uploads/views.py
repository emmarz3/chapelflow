from django.core.exceptions import ValidationError
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from common.permissions.scoping import BranchScopedQuerysetMixin
from common.utils.responses import error_response, success_response
from common.viewsets import StandardReadOnlyModelViewSet

from .models import Upload, UploadCategory
from .serializers import UploadSerializer
from .storage import generate_storage_filename, get_storage_service
from .validators import validate_upload


class UploadView(APIView):
    """POST /api/v1/uploads/upload/ — multipart 'file' + 'category' fields."""
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        file_obj = request.FILES.get("file")
        if not file_obj:
            return error_response("A 'file' is required.", status=400)

        try:
            validate_upload(file_obj)
        except ValidationError as exc:
            return error_response(str(exc), status=400)

        category = request.data.get("category", UploadCategory.OTHER)
        storage = get_storage_service()
        filename = generate_storage_filename(file_obj.name, prefix=category.lower())
        file_url = storage.upload_bytes(file_obj.read(), filename, content_type=file_obj.content_type)

        upload = Upload.objects.create(
            branch=request.user.branch,
            uploaded_by=request.user,
            category=category,
            original_filename=file_obj.name,
            file_url=file_url,
            content_type=file_obj.content_type or "",
            size_bytes=file_obj.size,
        )
        return success_response(UploadSerializer(upload).data, message="File uploaded.", status=201)


class UploadListView(BranchScopedQuerysetMixin, StandardReadOnlyModelViewSet):
    """
    GET /api/v1/uploads/  and  GET /api/v1/uploads/{id}/

    NOTE (Phase 0 audit sweep): this used to be a plain APIView with its
    own hand-rolled `Upload.objects.filter(branch=request.user.branch)` —
    no RBAC permission-code check at all, no ORG_WIDE_SCOPE_ROLES handling
    for Chaplain, no GLOBAL_SCOPE_ROLES handling for Super Admin (both
    would have been silently limited to whatever `request.user.branch`
    happens to be, which can even be None), and no detail/retrieve route
    at all (list-only). Rebuilt on the shared BranchScopedQuerysetMixin so
    it gets the same tested branch/org-wide/global scoping as every other
    ViewSet, and now exposes a proper retrieve() that goes through DRF's
    normal get_object() -> get_queryset() path, so a direct-ID request for
    another branch's upload 404s instead of ever reaching the object.
    """
    serializer_class = UploadSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ["branch", "category"]

    def get_base_queryset(self):
        return Upload.objects.select_related("branch", "uploaded_by").order_by("-created_at")
