from rest_framework.decorators import action
from rest_framework.permissions import AllowAny
from rest_framework.throttling import ScopedRateThrottle

from common.constants.roles import PermissionCodes
from common.permissions.rbac import HasRolePermission
from common.permissions.scoping import BranchScopedQuerysetMixin
from common.utils.responses import error_response, success_response
from common.viewsets import StandardModelViewSet

from .models import Visitor, VisitorFollowUp
from .serializers import VisitorFirstTimerFormSerializer, VisitorFollowUpSerializer, VisitorSerializer
from .services import find_duplicate_visitors, visitor_analytics


class VisitorViewSet(BranchScopedQuerysetMixin, StandardModelViewSet):
    """
    Staff-facing visitor management. The public submission entry point is
    the `first-timer-form` action below (AllowAny) — everything else here
    requires the normal RBAC + branch scoping, same as Member.
    """
    serializer_class = VisitorSerializer
    permission_classes = [HasRolePermission]
    filterset_fields = ["branch", "status"]
    search_fields = ["full_name", "phone_number", "email"]
    ordering_fields = ["created_at", "first_visit_date"]

    permission_action_map = {
        "list": PermissionCodes.MEMBERS_VIEW,
        "retrieve": PermissionCodes.MEMBERS_VIEW,
        "create": PermissionCodes.MEMBERS_CREATE,
        "update": PermissionCodes.MEMBERS_UPDATE,
        "partial_update": PermissionCodes.MEMBERS_UPDATE,
        "destroy": PermissionCodes.MEMBERS_DELETE,
        "convert": PermissionCodes.MEMBERS_CREATE,
        "add_follow_up": PermissionCodes.MEMBERS_UPDATE,
        "duplicates": PermissionCodes.MEMBERS_VIEW,
        "analytics": PermissionCodes.MEMBERS_VIEW,
    }

    def get_base_queryset(self):
        return Visitor.objects.select_related("branch", "converted_member").prefetch_related("follow_ups")

    def get_permissions(self):
        if self.action == "first_timer_form":
            return [AllowAny()]
        return super().get_permissions()

    def get_throttles(self):
        if self.action == "first_timer_form":
            # Spec Phase 5: public endpoints must be rate-limited against
            # spam/enumeration/excessive requests. This is the only fully
            # anonymous write endpoint on this ViewSet, so it's the only
            # one that needs its own throttle scope — everything else
            # already requires an authenticated, permissioned user.
            self.throttle_scope = "public"
            return [ScopedRateThrottle()]
        return super().get_throttles()

    def create(self, request, *args, **kwargs):
        # Staff can still directly log a visitor they met in person; this
        # is distinct from public self-submission (first_timer_form) but
        # both funnel into the same Visitor model/status pipeline.
        return super().create(request, *args, **kwargs)

    @action(detail=False, methods=["post"], url_path="first-timer-form")
    def first_timer_form(self, request):
        """
        POST /api/v1/visitors/first-timer-form/ — public, no auth required
        (spec section 4: "Public/guest user... can submit visitor/
        first-timer information"). This is step 2 of the pipeline
        (Visitor -> First-Timer Form -> Visitor Record).
        """
        serializer = VisitorFirstTimerFormSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        visitor = serializer.save()
        return success_response(VisitorSerializer(visitor).data, message="Thanks! We'll be in touch.", status=201)

    @action(detail=True, methods=["post"], url_path="follow-up")
    def add_follow_up(self, request, pk=None):
        visitor = self.get_object()
        # request.data may be a QueryDict (multipart/form submissions) —
        # spreading a QueryDict with ** yields list-wrapped values, so
        # normalize via .dict() first (flattens to last-value-per-key,
        # matching DRF's own multipart handling elsewhere in this codebase).
        raw = request.data.dict() if hasattr(request.data, "dict") else dict(request.data)
        data = {**raw, "visitor": str(visitor.id)}
        serializer = VisitorFollowUpSerializer(data=data)
        serializer.is_valid(raise_exception=True)
        follow_up = serializer.save()

        if visitor.status == "NEW":
            visitor.status = "CONTACTED"
            visitor.save(update_fields=["status"])

        from apps.audit.services import write_audit_log
        from apps.audit.models import AuditAction
        write_audit_log(AuditAction.VISITOR_FOLLOW_UP, "visitor", str(visitor.id), user=request.user)

        return success_response(VisitorFollowUpSerializer(follow_up).data, message="Follow-up logged.", status=201)

    @action(detail=True, methods=["post"])
    def convert(self, request, pk=None):
        """
        POST /api/v1/visitors/{id}/convert/ — Optional Full Registration
        step (spec section 4), staff-assisted. See services.convert_visitor_to_member
        for how this differs from public self-registration.
        """
        visitor = self.get_object()
        from .services import convert_visitor_to_member
        try:
            member = convert_visitor_to_member(visitor, request.data, changed_by=request.user)
        except ValueError as exc:
            return error_response(str(exc), status=400)

        from apps.members.serializers import MemberSerializer
        return success_response(MemberSerializer(member).data, message="Visitor converted to member.")

    @action(detail=False, methods=["get"])
    def duplicates(self, request):
        """
        GET /api/v1/visitors/duplicates/ — candidate duplicate pairs
        within the caller's scope (spec Phase 5). Detection only; nothing
        here merges records automatically — that requires human review.
        """
        pairs = find_duplicate_visitors(self.filter_queryset(self.get_queryset()))
        return success_response(pairs, message=f"{len(pairs)} candidate duplicate pair(s) found.")

    @action(detail=False, methods=["get"])
    def analytics(self, request):
        """GET /api/v1/visitors/analytics/ — spec Phase 5 visitor analytics, scoped to the caller."""
        stats = visitor_analytics(self.filter_queryset(self.get_queryset()))
        return success_response(stats)
