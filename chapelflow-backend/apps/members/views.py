from rest_framework import viewsets
from common.viewsets import StandardModelViewSet
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.throttling import ScopedRateThrottle

from common.constants.roles import PermissionCodes
from common.permissions.rbac import HasRolePermission
from common.permissions.scoping import BranchScopedQuerysetMixin
from common.utils.responses import error_response, success_response
from .models import Member, MemberQRCode, MembershipHistory, MembershipStatus
from .serializers import MemberImportSummarySerializer, MemberSerializer
from .services import find_duplicate_members, merge_members, parse_and_import_members, transfer_member


class MemberViewSet(BranchScopedQuerysetMixin, StandardModelViewSet):
    serializer_class = MemberSerializer
    permission_classes = [HasRolePermission]
    # Phase 4: Expanded filter fields to include academic and chapel relationships
    filterset_fields = [
        "branch", "household", "membership_status", "gender",
        "college", "department", "community", "fellowship"
    ]
    search_fields = ["first_name", "last_name", "email", "phone_number"]
    ordering_fields = ["last_name", "created_at", "membership_date"]

    # Deliberately NOT wired through the generic group_field_lookup
    # mechanism: BranchScopedQuerysetMixin._apply_leader_scope only knows
    # how to do a single `{lookup}_id__in=...` filter, which is correct
    # for a Fellowship Leader (Member.fellowship is a direct FK) but
    # wrong for a Unit Head / Ministry Leader, whose members are related
    # via the groups.GroupMembership M2M table instead — there is no
    # Member.unit_id / Member.ministry_id to filter on directly. See the
    # _apply_leader_scope override below, which is the real Phase 6 fix.

    # NOTE (spec section 3, mandatory): normal administrators must NOT
    # create members manually. There is deliberately no permission code
    # mapped to "create" here — HasRolePermission fails closed on any
    # action with no map entry, so POST /members/ is blocked for every
    # role including Super Admin's own "just POST it" habit. The only
    # ways a Member row is created are:
    #   1. public self-registration -> apps.accounts.views.RegisterView
    #      (creates User + Member together, see apps/accounts/services.py)
    #   2. the explicitly-separate historical data migration import below
    #      (import_csv / MEMBERS_IMPORT), never the normal admin flow.
    permission_action_map = {
        "list": PermissionCodes.MEMBERS_VIEW,
        "retrieve": PermissionCodes.MEMBERS_VIEW,
        "update": PermissionCodes.MEMBERS_UPDATE,
        "partial_update": PermissionCodes.MEMBERS_UPDATE,
        "destroy": PermissionCodes.MEMBERS_DELETE,
        "regenerate_qr": PermissionCodes.MEMBERS_UPDATE,
        "import_csv": PermissionCodes.MEMBERS_IMPORT,
        "deactivate": PermissionCodes.MEMBERS_UPDATE,
        "reactivate": PermissionCodes.MEMBERS_UPDATE,
        "merge": PermissionCodes.MEMBERS_DELETE,
        "duplicates": PermissionCodes.MEMBERS_VIEW,
        "transfer": PermissionCodes.MEMBERS_UPDATE,
    }

    def create(self, request, *args, **kwargs):
        from common.utils.responses import error_response
        return error_response(
            "Members cannot be created manually. Members are created via public "
            "self-registration (POST /api/v1/auth/register/) or, for historical "
            "records only, the separate data-migration import "
            "(POST /api/v1/members/import/).",
            status=405,
        )

    def get_base_queryset(self):
        # Phase 4: Optimized with select_related for academic and chapel FKs
        return Member.objects.select_related(
            "branch", "household", "college", "department", "fellowship"
        ).prefetch_related("tags", "qr_code")

    def _apply_leader_scope(self, qs, user):
        """
        CRITICAL Phase 6 fix: previously this override didn't exist at
        all, so a Fellowship/Unit/Ministry Leader with members.view could
        see EVERY member in their branch, not just members of the
        group(s) they actually lead -- confirmed via a proof-of-concept
        request before this fix (a Fellowship Leader saw a member of a
        completely different Fellowship in the same branch). Branch
        scoping alone was never enough for assignment-scoped roles (spec
        Phase 6: "Fellowship Leaders: Only Fellowship scope... applies
        consistently to members").
        """
        from common.permissions.scoping import ROLE_TO_GROUP_TYPE, led_group_ids
        from apps.ministries.models import GroupType

        if user.role not in ROLE_TO_GROUP_TYPE:
            return qs
        allowed_ids = led_group_ids(user)
        if ROLE_TO_GROUP_TYPE[user.role] == GroupType.FELLOWSHIP:
            # Member.fellowship is a direct FK -- simple filter.
            return qs.filter(fellowship_id__in=allowed_ids)
        # UNIT_HEAD / MINISTRY_GROUP_LEADER: membership is many-to-many
        # via groups.GroupMembership, so it has to be joined, not a plain
        # `_id__in` filter, and must be de-duplicated (a member with more
        # than one active membership in the led group would otherwise
        # appear more than once).
        return qs.filter(
            group_memberships__group_id__in=allowed_ids, group_memberships__is_active=True,
        ).distinct()

    def perform_create(self, serializer):
        member = serializer.save()
        MemberQRCode.objects.get_or_create(member=member)

    @action(detail=True, methods=["post"])
    def deactivate(self, request, pk=None):
        member = self.get_object()
        previous = member.membership_status
        member.membership_status = MembershipStatus.INACTIVE
        member.save(update_fields=["membership_status"])
        MembershipHistory.objects.create(
            member=member, previous_status=previous, new_status=MembershipStatus.INACTIVE,
            previous_branch=member.branch, new_branch=member.branch,
            note=request.data.get("note", ""), changed_by=request.user,
        )
        from apps.audit.services import write_audit_log
        from apps.audit.models import AuditAction
        write_audit_log(AuditAction.MEMBER_DEACTIVATE, "member", str(member.id), user=request.user)
        return success_response(MemberSerializer(member).data, message="Member deactivated.")

    @action(detail=True, methods=["post"])
    def reactivate(self, request, pk=None):
        member = self.get_object()
        previous = member.membership_status
        member.membership_status = MembershipStatus.ACTIVE
        member.save(update_fields=["membership_status"])
        MembershipHistory.objects.create(
            member=member, previous_status=previous, new_status=MembershipStatus.ACTIVE,
            previous_branch=member.branch, new_branch=member.branch,
            note=request.data.get("note", ""), changed_by=request.user,
        )
        from apps.audit.services import write_audit_log
        from apps.audit.models import AuditAction
        write_audit_log(AuditAction.MEMBER_REACTIVATE, "member", str(member.id), user=request.user)
        return success_response(MemberSerializer(member).data, message="Member reactivated.")

    @action(detail=True, methods=["post"])
    def transfer(self, request, pk=None):
        """
        POST /api/v1/members/{id}/transfer/
        {"branch_id": "...", "fellowship_id": "...", "note": "..."}

        The only supported way to move a member across branch/fellowship
        boundaries (spec Phase 4). Both fields are optional but at least
        one is required; omit fellowship_id (or send it as null) with no
        change; send "fellowship_id": null explicitly to CLEAR the
        member's fellowship without setting a new one.
        """
        from apps.organizations.models import Branch
        from apps.ministries.models import Group, GroupType
        from common.permissions.scoping import user_can_access_branch, user_can_access_group
        from django.shortcuts import get_object_or_404

        # Deliberately NOT self.get_object(): that now goes through the
        # leader-scoped queryset (see _apply_leader_scope above), which
        # would make it impossible for a Fellowship Leader to ever pull a
        # *new* member into their Fellowship from elsewhere in the branch
        # -- transfer is exactly the operation that's supposed to cross
        # that boundary. Branch scope still applies (a leader can only
        # transfer members already within their own branch); it's only
        # the *group* restriction that's intentionally not applied to the
        # member being looked up here -- it's applied to the destination
        # group instead, via user_can_access_group below.
        member = get_object_or_404(self.get_base_queryset(), pk=pk)
        if not user_can_access_branch(request.user, member.branch_id):
            from django.http import Http404
            raise Http404

        branch_id = request.data.get("branch_id")
        new_branch = None
        if branch_id:
            new_branch = Branch.objects.filter(id=branch_id).first()
            if not new_branch:
                return error_response("Target branch not found.", status=404)
            if not user_can_access_branch(request.user, new_branch.id):
                return error_response("You are not authorized to transfer members into this branch.", status=403)

        fellowship_provided = "fellowship_id" in request.data
        fellowship_id = request.data.get("fellowship_id")
        new_fellowship = None
        if fellowship_provided and fellowship_id:
            new_fellowship = Group.objects.filter(id=fellowship_id, group_type=GroupType.FELLOWSHIP).first()
            if not new_fellowship:
                return error_response("Target fellowship not found.", status=404)
            if not user_can_access_group(request.user, new_fellowship):
                return error_response("You are not authorized to transfer members into this fellowship.", status=403)
        elif fellowship_provided and not fellowship_id:
            new_fellowship = False  # explicit "clear it" sentinel understood by transfer_member()

        if new_branch is None and new_fellowship is None:
            return error_response("Provide branch_id and/or fellowship_id to transfer.", status=400)

        try:
            transfer_member(
                member, request.user,
                new_branch=new_branch, new_fellowship=new_fellowship,
                note=request.data.get("note", ""),
            )
        except ValueError as exc:
            return error_response(str(exc), status=400)

        from apps.audit.services import write_audit_log
        from apps.audit.models import AuditAction
        write_audit_log(
            AuditAction.MEMBER_TRANSFER, "member", str(member.id), user=request.user,
            metadata={"branch_id": branch_id, "fellowship_id": fellowship_id},
        )
        return success_response(MemberSerializer(member).data, message="Member transferred.")

    @action(detail=False, methods=["get"])
    def duplicates(self, request):
        """GET /api/v1/members/duplicates/ — candidate duplicate pairs within the caller's scope."""
        pairs = find_duplicate_members(self.filter_queryset(self.get_queryset()))
        return success_response(pairs, message=f"{len(pairs)} candidate duplicate pair(s) found.")

    @action(detail=False, methods=["post"])
    def merge(self, request):
        """
        POST /api/v1/members/merge/ {"keep_id": "...", "merge_id": "..."}
        `merge_id`'s attendance/giving/group-membership/pastoral history is
        reassigned to `keep_id`, then `merge_id` is deactivated (never hard
        deleted — spec section 8 requires an audit trail of the merge).
        """
        keep_id = request.data.get("keep_id")
        merge_id = request.data.get("merge_id")
        if not keep_id or not merge_id:
            return error_response("Both keep_id and merge_id are required.", status=400)
        if keep_id == merge_id:
            return error_response("keep_id and merge_id must be different members.", status=400)

        queryset = self.get_queryset()
        keep = queryset.filter(id=keep_id).first()
        merged = queryset.filter(id=merge_id).first()
        if not keep or not merged:
            return error_response("One or both members were not found in your scope.", status=404)

        result = merge_members(keep=keep, merged=merged, changed_by=request.user)
        from apps.audit.services import write_audit_log
        from apps.audit.models import AuditAction
        write_audit_log(
            AuditAction.MEMBER_MERGE, "member", str(keep.id), user=request.user,
            metadata={"merged_member_id": str(merged.id), **result},
        )
        return success_response(MemberSerializer(keep).data, message="Members merged.")

    @action(detail=True, methods=["post"], url_path="regenerate-qr")
    def regenerate_qr(self, request, pk=None):
        member = self.get_object()
        qr, _ = MemberQRCode.objects.get_or_create(member=member)
        qr.regenerate()
        return success_response({"token": qr.token}, message="QR code regenerated.")

    @action(
        detail=False, methods=["post"], url_path="import",
        parser_classes=[MultiPartParser, FormParser],
    )
    def import_csv(self, request):
        """POST /api/v1/members/import/ — multipart file upload, field name 'file'."""
        file_obj = request.FILES.get("file")
        if not file_obj:
            return error_response("A 'file' is required.", status=400)

        MAX_SYNC_BYTES = 2 * 1024 * 1024  # 2MB: larger files go to Celery instead
        if file_obj.size > MAX_SYNC_BYTES:
            # Spec section 20: the web container and the Celery worker have
            # separate filesystems, so a path written to local /tmp here is
            # invisible to the worker. Route through the same shared/object
            # StorageService used everywhere else (uploads/finance) instead
            # of a local temp file — this was the bug on the previous path.
            import uuid as _uuid
            from apps.uploads.storage import get_storage_service
            from .tasks import bulk_import_members_task

            storage = get_storage_service()
            key = f"member-imports/{_uuid.uuid4()}.csv"
            file_url = storage.upload_bytes(file_obj.read(), key, content_type="text/csv")
            bulk_import_members_task.delay(file_url, str(request.user.id))
            return success_response(
                message="Large file queued for background import. You'll be notified when it completes.",
                status=202,
            )

        try:
            summary = parse_and_import_members(file_obj, request.user)
        except ValueError as exc:
            return error_response(str(exc), status=400)

        return success_response(MemberImportSummarySerializer(summary).data, message="Import completed.")



class MemberFollowUpViewSet(StandardModelViewSet):
    """
    Phase 11: Member follow-up management.
    
    Endpoints:
    - GET /members/follow-ups/ - List follow-ups (filtered by scope)
    - GET /members/follow-ups/{id}/ - Retrieve follow-up
    - PATCH /members/follow-ups/{id}/ - Update (reassign, complete, add notes)
    
    Security:
    - Pastoral staff see all in branch
    - Assigned staff see their own assignments
    - Cannot create via API (created by signal)
    - Cannot change member/milestone/scheduled_for
    - Branch scoping enforced
    
    Authorization:
    - PASTORAL_VIEW: List/retrieve
    - PASTORAL_UPDATE: Update assigned_to, completed_at, notes
    """
    from .serializers import MemberFollowUpSerializer
    serializer_class = MemberFollowUpSerializer
    permission_classes = [HasRolePermission]
    filterset_fields = ['member', 'milestone', 'assigned_to', 'completed_at']
    ordering_fields = ['scheduled_for', 'created_at']
    http_method_names = ['get', 'patch', 'head', 'options']  # No POST/DELETE
    
    permission_action_map = {
        'list': PermissionCodes.PASTORAL_VIEW,
        'retrieve': PermissionCodes.PASTORAL_VIEW,
        'update': PermissionCodes.PASTORAL_UPDATE,
        'partial_update': PermissionCodes.PASTORAL_UPDATE,
    }
    
    def get_queryset(self):
        """
        Filter follow-ups based on user role:
        - Pastoral staff: All in their branch
        - Assigned staff: Only their assignments
        """
        from .models import MemberFollowUp
        from common.constants.roles import Roles
        
        user = self.request.user
        qs = MemberFollowUp.objects.select_related(
            'member', 'member__branch', 'assigned_to'
        )
        
        # Global admins see all
        if user.role in Roles.GLOBAL_SCOPE_ROLES:
            return qs
        
        # Pastoral staff see all in branch
        if user.role in Roles.PASTORAL_ACCESS_ROLES:
            if user.branch_id:
                return qs.filter(member__branch_id=user.branch_id)
            return qs.none()
        
        # Others see only their assignments
        return qs.filter(assigned_to=user)


class EngagementMetricsViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Phase 11: Engagement metrics (read-only).
    
    Endpoints:
    - GET /members/engagement/ - List metrics (filtered by scope)
    - GET /members/engagement/{member_id}/ - Retrieve member's metrics
    
    Security:
    - Read-only (updated by periodic task)
    - Pastoral staff see all in branch
    - Members can view own metrics
    - Branch scoping enforced
    
    Use cases:
    - Pastor dashboard (inactive member detection)
    - Fellowship leader reports
    - Member profile (self-view)
    """
    from .serializers import EngagementMetricsSerializer
    serializer_class = EngagementMetricsSerializer
    permission_classes = [HasRolePermission]
    filterset_fields = ['engagement_score', 'days_since_last_activity']
    
    permission_action_map = {
        'list': PermissionCodes.MEMBERS_VIEW,
        'retrieve': PermissionCodes.MEMBERS_VIEW,
    }
    
    def get_queryset(self):
        """
        Filter engagement metrics based on user role:
        - Pastoral/admin staff: All in branch
        - Members: Only own metrics
        """
        from .models import EngagementMetrics
        from common.constants.roles import Roles
        from common.permissions.scoping import get_accessible_branch_ids
        
        user = self.request.user
        qs = EngagementMetrics.objects.select_related('member', 'member__branch')
        
        # Global admins see all
        if user.role in Roles.GLOBAL_SCOPE_ROLES:
            return qs
        
        # Staff see all in accessible branches
        if user.role in (Roles.BRANCH_SCOPE_ROLES | Roles.PASTORAL_ACCESS_ROLES):
            accessible_branches = get_accessible_branch_ids(user)
            return qs.filter(member__branch_id__in=accessible_branches)
        
        # Members see only own metrics
        if hasattr(user, 'member_profile') and user.member_profile:
            return qs.filter(member=user.member_profile)
        
        return qs.none()
