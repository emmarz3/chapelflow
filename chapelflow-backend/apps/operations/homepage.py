"""Public homepage content: public read, Super Admin write, visitor requests."""
import re

from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.validators import validate_email
from django.db import IntegrityError, transaction
from django.db.models import Count, Q
from rest_framework.permissions import AllowAny
from rest_framework.views import APIView

from apps.audit.models import AuditAction
from apps.audit.services import write_audit_log
from common.permissions.rbac import IsSuperAdmin
from common.utils.responses import error_response, success_response

from .homepage_schema import ID_RE, HomepageValidationError, sanitize_homepage
from .models import (
    HomepageContent, HomepageRequest, HomepageRequestKind, HomepageRequestStatus,
)

KIND_MAP = {"event": HomepageRequestKind.EVENT, "unit": HomepageRequestKind.UNIT}
CONTENT_LIST = {"event": "events", "unit": "units"}


def _document() -> HomepageContent:
    doc, _ = HomepageContent.objects.get_or_create(key="homepage")
    return doc


def _registration_counts():
    rows = (
        HomepageRequest.objects.filter(kind=HomepageRequestKind.EVENT)
        .values("item_id")
        .annotate(total=Count("id"))
    )
    return {row["item_id"]: row["total"] for row in rows}


def _payload(doc: HomepageContent, *, include_counts=True):
    return {
        "content": doc.content or None,
        "version": doc.version,
        "updatedAt": doc.updated_at.isoformat() if doc.version else None,
        "counts": _registration_counts() if include_counts else {},
    }


class PublicHomepageView(APIView):
    """Everything on this response is already public, so drafts do not exist."""

    permission_classes = [AllowAny]
    authentication_classes: list = []

    def get(self, request):
        return success_response(_payload(_document()))


class HomepageAdminView(APIView):
    permission_classes = [IsSuperAdmin]

    def get(self, request):
        return success_response(_payload(_document()))

    def put(self, request):
        body = request.data if isinstance(request.data, dict) else {}
        try:
            cleaned = sanitize_homepage(body.get("content"))
        except HomepageValidationError as exc:
            return error_response(
                "Some homepage fields need attention.", errors=exc.errors, status=400
            )
        expected = body.get("version")
        if isinstance(expected, bool) or not isinstance(expected, int):
            return error_response("The current content version is required.", status=400)

        with transaction.atomic():
            doc = HomepageContent.objects.select_for_update().get_or_create(key="homepage")[0]
            if expected != doc.version:
                return error_response(
                    "The homepage was changed by someone else. Reload to see the latest version.",
                    status=409,
                )
            first_save = doc.version == 0
            doc.content = cleaned
            doc.version += 1
            doc.updated_by = request.user
            doc.save()
            write_audit_log(
                AuditAction.CREATE if first_save else AuditAction.UPDATE,
                "homepage_content",
                doc.pk,
                metadata={
                    "version": doc.version,
                    "counts": {
                        key: len(cleaned[key])
                        for key in ("announcements", "services", "events", "sermons", "units", "gallery")
                    },
                },
                user=request.user,
            )
        return success_response(_payload(doc), message="Homepage saved.")

    def delete(self, request):
        """Restore the built-in defaults (the client renders them when empty)."""
        with transaction.atomic():
            doc = HomepageContent.objects.select_for_update().get_or_create(key="homepage")[0]
            doc.content = {}
            doc.version += 1
            doc.updated_by = request.user
            doc.save()
            write_audit_log(
                AuditAction.UPDATE, "homepage_content", doc.pk,
                metadata={"version": doc.version, "reset": True}, user=request.user,
            )
        return success_response(_payload(doc), message="Homepage restored to defaults.")


class PublicHomepageRequestView(APIView):
    """Event registrations / RSVPs and unit-join requests from the public site."""

    permission_classes = [AllowAny]
    authentication_classes: list = []
    throttle_scope = "public"

    def post(self, request):
        data = request.data if isinstance(request.data, dict) else {}
        errors = {}

        # Honeypot: humans never see or fill this field.
        if str(data.get("website") or "").strip():
            return success_response({"received": True}, message="Request received.", status=201)

        kind_key = str(data.get("kind") or "")
        kind = KIND_MAP.get(kind_key)
        if kind is None:
            errors["kind"] = ["Choose event or unit."]
        item_id = str(data.get("itemId") or "")
        if not ID_RE.match(item_id):
            errors["itemId"] = ["A valid item is required."]
        name = re.sub(r"\s+", " ", str(data.get("name") or "")).strip()
        if len(name) < 2 or len(name) > 120:
            errors["name"] = ["Enter your full name."]
        email = str(data.get("email") or "").strip().lower()
        try:
            validate_email(email)
        except DjangoValidationError:
            errors["email"] = ["Enter a valid email address."]
        matric = str(data.get("matricNo") or "").strip()
        if len(matric) > 40:
            errors["matricNo"] = ["Matric number is too long."]
        if data.get("consent") is not True:
            errors["consent"] = ["Please agree to the privacy notice."]
        if errors:
            return error_response("Please check the highlighted fields.", errors=errors, status=400)

        doc = _document()
        item_title = str(data.get("itemTitle") or "")[:180]
        if doc.content:
            items = doc.content.get(CONTENT_LIST[kind_key], [])
            item = next((i for i in items if i.get("id") == item_id and i.get("active", True)), None)
            if item is None:
                return error_response("This programme is no longer open.", status=404)
            item_title = item.get("title") or item.get("name") or item_title
            if kind == HomepageRequestKind.EVENT and item.get("capacity"):
                taken = int(item.get("taken") or 0) + HomepageRequest.objects.filter(
                    kind=kind, item_id=item_id
                ).count()
                already = HomepageRequest.objects.filter(
                    kind=kind, item_id=item_id, email=email
                ).exists()
                if taken >= item["capacity"] and not already:
                    return error_response("Sorry, this programme is full.", status=409)

        try:
            with transaction.atomic():
                HomepageRequest.objects.get_or_create(
                    kind=kind, item_id=item_id, email=email,
                    defaults={
                        "item_title": item_title, "name": name,
                        "matric_no": matric, "consent": True,
                    },
                )
        except IntegrityError:
            pass  # A concurrent identical request already stored it.
        # The response never reveals whether this email had already registered.
        return success_response({"received": True}, message="Request received.", status=201)


def _request_row(entry: HomepageRequest):
    return {
        "id": str(entry.id),
        "kind": entry.kind,
        "itemId": entry.item_id,
        "itemTitle": entry.item_title,
        "name": entry.name,
        "email": entry.email,
        "matricNo": entry.matric_no,
        "status": entry.status,
        "createdAt": entry.created_at.isoformat(),
    }


class HomepageRequestListView(APIView):
    permission_classes = [IsSuperAdmin]

    def get(self, request):
        entries = HomepageRequest.objects.all()
        kind = request.query_params.get("kind", "").upper()
        if kind in HomepageRequestKind.values:
            entries = entries.filter(kind=kind)
        status = request.query_params.get("status", "").upper()
        if status in HomepageRequestStatus.values:
            entries = entries.filter(status=status)
        item = request.query_params.get("item", "")
        if item:
            entries = entries.filter(item_id=item)
        search = request.query_params.get("search", "").strip()
        if search:
            entries = entries.filter(
                Q(name__icontains=search) | Q(email__icontains=search)
                | Q(matric_no__icontains=search) | Q(item_title__icontains=search)
            )
        total = entries.count()
        return success_response({"total": total, "results": [_request_row(e) for e in entries[:500]]})


class HomepageRequestDetailView(APIView):
    permission_classes = [IsSuperAdmin]

    def patch(self, request, pk):
        entry = HomepageRequest.objects.filter(pk=pk).first()
        if entry is None:
            return error_response("Request not found.", status=404)
        status = str((request.data or {}).get("status") or "").upper()
        if status not in HomepageRequestStatus.values:
            return error_response("Choose a valid status.", status=400)
        entry.status = status
        entry.save(update_fields=["status", "updated_at"])
        write_audit_log(
            AuditAction.UPDATE, "homepage_request", entry.pk,
            metadata={"status": status}, user=request.user,
        )
        return success_response(_request_row(entry))

    def delete(self, request, pk):
        entry = HomepageRequest.objects.filter(pk=pk).first()
        if entry is None:
            return error_response("Request not found.", status=404)
        write_audit_log(
            AuditAction.DELETE, "homepage_request", entry.pk,
            metadata={"kind": entry.kind, "item_id": entry.item_id}, user=request.user,
        )
        entry.delete()
        return success_response(None, message="Request deleted.")
