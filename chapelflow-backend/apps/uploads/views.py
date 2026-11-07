from django.conf import settings
from django.core.exceptions import ValidationError
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from common.permissions.scoping import BranchScopedQuerysetMixin
from common.permissions.media import user_has_media_management_access
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

        category = request.data.get("category", UploadCategory.OTHER)
        if category not in UploadCategory.values:
            return error_response("Select a valid upload category.", status=400)
        if category == UploadCategory.MEDIA_CONTENT and not user_has_media_management_access(request.user):
            return error_response("Only the Super Admin, Chaplain, Student Chaplain, Media Leader, or Social Media Leader can upload public media.", status=403)

        max_size_mb = (
            getattr(settings, "MAX_MEDIA_UPLOAD_SIZE_MB", 100)
            if category == UploadCategory.MEDIA_CONTENT
            else None
        )
        try:
            validate_upload(file_obj, max_size_mb=max_size_mb)
        except ValidationError as exc:
            return error_response(str(exc), status=400)
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
