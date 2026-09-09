from common.constants.roles import PermissionCodes
from common.permissions.rbac import HasRolePermission
from common.permissions.scoping import BranchScopedQuerysetMixin
from common.viewsets import StandardModelViewSet
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from common.utils.responses import error_response, success_response

from django.db import transaction
from django.utils import timezone
from rest_framework.decorators import action
from rest_framework.response import Response

from .models import GroupJoinRequest, GroupMeeting, GroupMeetingAttendance, GroupMembership, GroupRole, GroupTask, JoinRequestStatus
from .serializers import GroupJoinRequestSerializer, GroupMeetingAttendanceSerializer, GroupMeetingSerializer, GroupMembershipSerializer, GroupTaskSerializer


def _community_type(group_type):
    return {"UNIT": "unit", "FELLOWSHIP": "campus_fellowship"}.get(group_type, "other")


def _community_summary(membership):
    group = membership.group
    return {
        "id": str(group.id), "slug": str(group.id), "name": group.name,
        "type": _community_type(group.group_type), "description": group.description,
        "status": "active" if group.is_active else "inactive", "requires_approval": False,
        "members_can_post": False, "chat_enabled": False,
        "membership_status": "active" if membership.is_active else "suspended",
        "is_leader": membership.role in {GroupRole.LEADER, GroupRole.ASSISTANT_LEADER},
        "unreadCount": 0, "member_count": group.memberships.filter(is_active=True).count(), "pending_count": 0,
    }


class MyCommunityListView(APIView):
    """Expose the caller's own group memberships without broad member access."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        memberships = GroupMembership.objects.filter(
            member__user=request.user, is_active=True, group__is_active=True
        ).select_related("group").order_by("group__name")
        return success_response([_community_summary(membership) for membership in memberships])


class MyCommunityDetailView(APIView):
    """Display a member's own group workspace overview, scoped to membership."""
    permission_classes = [IsAuthenticated]

    def get(self, request, group_id):
        membership = GroupMembership.objects.filter(
            member__user=request.user, group_id=group_id, is_active=True, group__is_active=True
        ).select_related("group").first()
        if not membership:
            return error_response("Community not found.", status=404)
        summary = _community_summary(membership)
        leaders = GroupMembership.objects.filter(
            group=membership.group, is_active=True, role=GroupRole.LEADER
        ).select_related("member").order_by("joined_at")
        return success_response({
            **summary, "membershipStatus": summary["membership_status"],
            "memberCount": summary["member_count"],
            "access": {"isLeader": summary["is_leader"], "canPost": False, "canManage": summary["is_leader"]},
            "leaders": [{"position": "Group leader", "name": leader.member.full_name} for leader in leaders],
            "pinnedAnnouncement": None, "nextEvent": None,
        })


def _audit_leadership_change(instance, user, verb):
    """
    Spec Phase 6: "leadership history". GroupMembership itself only holds
    current state (is_active/role) -- this is the append-only trail of
    who became/stopped being a LEADER of what, and when, without
    introducing a second parallel history model for what the existing
    apps.audit.AuditLog already exists to record.
    """
    if instance.role != GroupRole.LEADER:
        return
    from apps.audit.services import write_audit_log
    from apps.audit.models import AuditAction
    write_audit_log(
        AuditAction.GROUP_LEADERSHIP_CHANGE, "group_membership", str(instance.id), user=user,
        metadata={
            "verb": verb, "group_id": str(instance.group_id), "member_id": str(instance.member_id),
            "is_active": instance.is_active,
        },
    )


class GroupMembershipViewSet(BranchScopedQuerysetMixin, StandardModelViewSet):
    """
    NOTE (Phase 0): this ViewSet previously implemented its own
    get_queryset() with branch-only scoping and no leadership restriction
    at all — every assignment-scoped leader (Fellowship/Unit/Ministry)
    could see every membership row in their branch, not just their own
    group(s). Refactored onto BranchScopedQuerysetMixin so it gets both
    branch scoping AND leader scoping (via group_field_lookup) from one
    shared, tested implementation instead of a second hand-rolled copy.
    """
    serializer_class = GroupMembershipSerializer
    permission_classes = [HasRolePermission]
    filterset_fields = ["group", "member", "role", "is_active"]
    branch_field_lookup = "group__branch"
    group_field_lookup = "group"

    permission_action_map = {
        "list": PermissionCodes.GROUPS_VIEW,
        "retrieve": PermissionCodes.GROUPS_VIEW,
        "create": PermissionCodes.GROUPS_MANAGE_MEMBERS,
        "update": PermissionCodes.GROUPS_MANAGE_MEMBERS,
        "partial_update": PermissionCodes.GROUPS_MANAGE_MEMBERS,
        "destroy": PermissionCodes.GROUPS_MANAGE_MEMBERS,
    }

    def get_base_queryset(self):
        return GroupMembership.objects.select_related("member", "group", "group__branch")

    def perform_create(self, serializer):
        instance = serializer.save()
        _audit_leadership_change(instance, self.request.user, "assigned")

    def perform_update(self, serializer):
        instance = serializer.save()
        _audit_leadership_change(instance, self.request.user, "updated")

    def perform_destroy(self, instance):
        _audit_leadership_change(instance, self.request.user, "removed")
        instance.delete()


class GroupJoinRequestViewSet(BranchScopedQuerysetMixin, StandardModelViewSet):
    serializer_class = GroupJoinRequestSerializer
    permission_classes = [HasRolePermission]
    branch_field_lookup = "group__branch"
    group_field_lookup = "group"
    filterset_fields = ["group", "status"]
    http_method_names = ["get", "post", "head", "options"]
    permission_action_map = {"list": PermissionCodes.GROUPS_VIEW, "retrieve": PermissionCodes.GROUPS_VIEW, "create": PermissionCodes.GROUPS_MANAGE_MEMBERS, "approve": PermissionCodes.GROUPS_MANAGE_MEMBERS, "reject": PermissionCodes.GROUPS_MANAGE_MEMBERS}

    def get_base_queryset(self):
        return GroupJoinRequest.objects.select_related("group", "member")

    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        item = self.get_object()
        if item.status != JoinRequestStatus.PENDING:
            return Response({"detail": "Only pending requests can be approved."}, status=400)
        with transaction.atomic():
            GroupMembership.objects.update_or_create(group=item.group, member=item.member, defaults={"is_active": True, "role": GroupRole.MEMBER})
            item.status, item.resolved_at, item.resolved_by = JoinRequestStatus.APPROVED, timezone.now(), request.user
            item.save(update_fields=["status", "resolved_at", "resolved_by"])
        return Response(self.get_serializer(item).data)

    @action(detail=True, methods=["post"])
    def reject(self, request, pk=None):
        item = self.get_object()
        if item.status != JoinRequestStatus.PENDING:
            return Response({"detail": "Only pending requests can be rejected."}, status=400)
        item.status, item.resolved_at, item.resolved_by = JoinRequestStatus.REJECTED, timezone.now(), request.user
        item.save(update_fields=["status", "resolved_at", "resolved_by"])
        return Response(self.get_serializer(item).data)


class MyGroupJoinRequestView(APIView):
    """Student self-service group discovery and join requests.

    Students can only see active groups at their own branch and can only
    create a request for their own Member profile. Leaders still approve via
    the separately scoped review endpoint above.
    """
    permission_classes = [IsAuthenticated]

    def _member(self, request):
        if request.user.get_role_code() != "MEMBER":
            return None
        return getattr(request.user, "member_profile", None)

    def get(self, request):
        member = self._member(request)
        if member is None:
            return error_response("This feature is available to student accounts only.", status=403)
        from apps.ministries.models import Group
        groups = Group.objects.filter(branch=member.branch, is_active=True).exclude(
            memberships__member=member, memberships__is_active=True,
        ).order_by("group_type", "name")
        requests = GroupJoinRequest.objects.filter(member=member).select_related("group").order_by("-requested_at")
        return success_response({
            "groups": [{"id": str(group.id), "name": group.name, "type": group.group_type, "description": group.description} for group in groups],
            "requests": [{"id": str(item.id), "group": item.group.name, "status": item.status, "message": item.message, "requested_at": item.requested_at} for item in requests],
        })

    def post(self, request):
        member = self._member(request)
        if member is None:
            return error_response("This feature is available to student accounts only.", status=403)
        from apps.ministries.models import Group
        group_id = request.data.get("group")
        try:
            group = Group.objects.get(id=group_id, branch=member.branch, is_active=True)
        except Group.DoesNotExist:
            return error_response("The selected community is unavailable.", status=404)
        if GroupMembership.objects.filter(group=group, member=member, is_active=True).exists():
            return error_response("You are already an active member of this community.", status=409)
        request_row, _ = GroupJoinRequest.objects.update_or_create(
            group=group, member=member,
            defaults={"message": str(request.data.get("message", ""))[:500], "status": JoinRequestStatus.PENDING, "resolved_at": None, "resolved_by": None},
        )
        return success_response({"id": str(request_row.id), "status": request_row.status}, status=201)

class GroupTaskViewSet(BranchScopedQuerysetMixin, StandardModelViewSet):
    serializer_class = GroupTaskSerializer
    permission_classes = [HasRolePermission]
    branch_field_lookup = "group__branch"
    group_field_lookup = "group"
    filterset_fields = ["group", "status", "assignee"]
    permission_action_map = {action: PermissionCodes.GROUPS_MANAGE_MEMBERS for action in ("list", "retrieve", "create", "update", "partial_update", "destroy")}

    def get_base_queryset(self):
        return GroupTask.objects.select_related("group", "assignee")

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)


class GroupMeetingViewSet(BranchScopedQuerysetMixin, StandardModelViewSet):
    serializer_class = GroupMeetingSerializer
    permission_classes = [HasRolePermission]
    branch_field_lookup = "group__branch"
    group_field_lookup = "group"
    filterset_fields = ["group"]
    permission_action_map = {action: PermissionCodes.GROUPS_MANAGE_MEMBERS for action in ("list", "retrieve", "create", "update", "partial_update", "destroy", "attendance")}

    def get_base_queryset(self):
        return GroupMeeting.objects.select_related("group").prefetch_related("attendance")

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    @action(detail=True, methods=["get", "post"])
    def attendance(self, request, pk=None):
        meeting = self.get_object()
        if request.method == "GET":
            return Response(GroupMeetingAttendanceSerializer(meeting.attendance.select_related("member"), many=True).data)
        serializer = GroupMeetingAttendanceSerializer(data={**request.data, "meeting": str(meeting.id)})
        serializer.is_valid(raise_exception=True)
        if serializer.validated_data["member"].branch_id != meeting.group.branch_id:
            return Response({"detail": "Member is outside the meeting branch."}, status=400)
        attendance, _ = GroupMeetingAttendance.objects.update_or_create(meeting=meeting, member=serializer.validated_data["member"], defaults={"present": serializer.validated_data.get("present", True), "recorded_by": request.user})
        return Response(GroupMeetingAttendanceSerializer(attendance).data)
