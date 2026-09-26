from common.constants.roles import PermissionCodes
from common.permissions.rbac import HasRolePermission
from common.permissions.scoping import BranchScopedQuerysetMixin
from common.viewsets import StandardModelViewSet
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from common.utils.responses import error_response, success_response
from apps.members.models import Member, is_student_community_member

from django.db import transaction
from django.utils import timezone
from rest_framework.decorators import action
from rest_framework.response import Response

from .models import GroupJoinRequest, GroupMeeting, GroupMeetingAttendance, GroupMembership, GroupMessage, GroupResource, GroupRole, GroupTask, JoinRequestStatus
from .serializers import GroupJoinRequestSerializer, GroupMeetingAttendanceSerializer, GroupMeetingSerializer, GroupMembershipSerializer, GroupTaskSerializer


def _community_type(group_type):
    return {"UNIT": "unit", "FELLOWSHIP": "campus_fellowship"}.get(group_type, "other")


def _fellowship_conflict(member, group):
    """Return a message when a member already has or requested another Fellowship."""
    if group.group_type != "FELLOWSHIP":
        return None
    if member.fellowship_id and member.fellowship_id != group.id:
        return "You already have a Fellowship. You can still join Chapel Units separately."
    if GroupMembership.objects.filter(
        member=member, group__group_type="FELLOWSHIP", is_active=True,
    ).exclude(group=group).exists():
        return "You already belong to another Fellowship. You can still join Chapel Units separately."
    if GroupJoinRequest.objects.filter(
        member=member, group__group_type="FELLOWSHIP", status=JoinRequestStatus.PENDING,
    ).exclude(group=group).exists():
        return "You already have a pending Fellowship request. You can still request a Chapel Unit."
    return None


def _has_student_community_access(request):
    member = Member.objects.filter(user=request.user).only("id", "community").first()
    return is_student_community_member(member)


def _community_summary(membership):
    group = membership.group
    return {
        "id": str(group.id), "slug": str(group.id), "name": group.name,
        "type": _community_type(group.group_type), "description": group.description,
        "status": "active" if group.is_active else "inactive", "requires_approval": False,
        "members_can_post": True, "chat_enabled": True,
        "membership_status": "active" if membership.is_active else "suspended",
        "is_leader": membership.role in {GroupRole.LEADER, GroupRole.ASSISTANT_LEADER},
        "unreadCount": 0, "member_count": group.memberships.filter(is_active=True).count(), "pending_count": 0,
    }


class MyCommunityListView(APIView):
    """Expose the caller's own group memberships without broad member access."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not _has_student_community_access(request):
            return error_response("Communities are available only to student accounts.", status=403)
        memberships = GroupMembership.objects.filter(
            member__user=request.user, is_active=True, group__is_active=True
        ).select_related("group").order_by("group__name")
        return success_response([_community_summary(membership) for membership in memberships])


class MyCommunityDetailView(APIView):
    """Display a member's own group workspace overview, scoped to membership."""
    permission_classes = [IsAuthenticated]

    def get(self, request, group_id):
        if not _has_student_community_access(request):
            return error_response("Communities are available only to student accounts.", status=403)
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
            "access": {"isLeader": summary["is_leader"], "canPost": True, "canManage": summary["is_leader"]},
            "leaders": [{"position": "Group leader", "name": leader.member.full_name} for leader in leaders],
            "pinnedAnnouncement": None, "nextEvent": None,
        })


class CommunityMessageView(APIView):
    """Group chat constrained to an active membership at every request."""

    permission_classes = [IsAuthenticated]

    def _membership(self, request, group_id):
        return GroupMembership.objects.filter(
            member__user=request.user, group_id=group_id, is_active=True, group__is_active=True
        ).select_related("group").first()

    @staticmethod
    def _data(item):
        return {
            "id": str(item.id), "body": item.body, "reply_to_id": None, "pinned": False,
            "created_at": item.created_at, "edited_at": None,
            "sender_id": str(item.author_id), "sender_name": item.author.get_full_name() or item.author.email,
        }

    def get(self, request, group_id):
        if not _has_student_community_access(request):
            return error_response("Communities are available only to student accounts.", status=403)
        membership = self._membership(request, group_id)
        if not membership:
            return error_response("Community not found.", status=404)
        messages = GroupMessage.objects.filter(group=membership.group).select_related("author")
        search = str(request.query_params.get("search", "")).strip()
        if search:
            messages = messages.filter(body__icontains=search)
        return success_response([self._data(item) for item in messages[:200]])

    def post(self, request, group_id):
        if not _has_student_community_access(request):
            return error_response("Communities are available only to student accounts.", status=403)
        membership = self._membership(request, group_id)
        if not membership:
            return error_response("Community not found.", status=404)
        body = str(request.data.get("body", "")).strip()
        if not body:
            return error_response("Write a message before sending it.", status=400)
        if len(body) > 4000:
            return error_response("Messages cannot exceed 4,000 characters.", status=400)
        message = GroupMessage.objects.create(group=membership.group, author=request.user, body=body)
        return success_response(self._data(message), status=201)


class CommunityResourceView(APIView):
    """A member-readable and leader-managed resource library for a group."""

    permission_classes = [IsAuthenticated]

    def _membership(self, request, group_id):
        return GroupMembership.objects.filter(
            member__user=request.user, group_id=group_id, is_active=True, group__is_active=True
        ).select_related("group").first()

    @staticmethod
    def _data(item):
        return {
            "id": str(item.id), "title": item.title, "url": item.url, "description": item.description,
            "created_at": item.created_at, "created_by_name": item.created_by.get_full_name() if item.created_by else "",
        }

    def get(self, request, group_id):
        if not _has_student_community_access(request):
            return error_response("Communities are available only to student accounts.", status=403)
        membership = self._membership(request, group_id)
        if not membership:
            return error_response("Community not found.", status=404)
        resources = GroupResource.objects.filter(group=membership.group).select_related("created_by")
        return success_response([self._data(item) for item in resources])

    def post(self, request, group_id):
        if not _has_student_community_access(request):
            return error_response("Communities are available only to student accounts.", status=403)
        membership = self._membership(request, group_id)
        if not membership:
            return error_response("Community not found.", status=404)
        if membership.role not in {GroupRole.LEADER, GroupRole.ASSISTANT_LEADER}:
            return error_response("Only community leaders can add resources.", status=403)
        title = str(request.data.get("title", "")).strip()
        url = str(request.data.get("url", "")).strip()
        description = str(request.data.get("description", "")).strip()
        if not title or not url:
            return error_response("A resource title and valid link are required.", status=400)
        from django.core.validators import URLValidator
        from django.core.exceptions import ValidationError as DjangoValidationError
        try:
            URLValidator(schemes=["http", "https"])(url)
        except DjangoValidationError:
            return error_response("Use a valid http or https resource link.", status=400)
        resource = GroupResource.objects.create(
            group=membership.group, title=title[:180], url=url, description=description, created_by=request.user
        )
        return success_response(self._data(resource), status=201)


class _CommunityMemberView(APIView):
    """Shared membership lookup for community-only endpoints."""

    permission_classes = [IsAuthenticated]

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        if not _has_student_community_access(request):
            self.permission_denied(request, message="Communities are available only to student accounts.")

    def membership(self, request, group_id):
        return GroupMembership.objects.filter(
            member__user=request.user, group_id=group_id, is_active=True, group__is_active=True
        ).select_related("group").first()

    def leader_membership(self, request, group_id):
        membership = self.membership(request, group_id)
        if membership is None:
            return None, error_response("Community not found.", status=404)
        if membership.role not in {GroupRole.LEADER, GroupRole.ASSISTANT_LEADER}:
            return None, error_response("Only community leaders can manage this workspace.", status=403)
        return membership, None


class CommunityAnnouncementView(_CommunityMemberView):
    """Official group announcements, delivered through the existing communications workflow."""

    @staticmethod
    def _data(item):
        return {
            "id": str(item.id), "title": item.title, "content": item.body, "pinned": False,
            "priority": "normal", "published_at": item.completed_at or item.publish_at,
            "expires_at": item.expires_at, "author_name": item.created_by.get_full_name() if item.created_by else "",
        }

    def get(self, request, group_id):
        membership = self.membership(request, group_id)
        if not membership:
            return error_response("Community not found.", status=404)
        from apps.communications.models import Announcement, AnnouncementStatus
        rows = Announcement.objects.filter(
            branch=membership.group.branch,
            target_groups=membership.group,
            status__in=[AnnouncementStatus.QUEUED, AnnouncementStatus.SENDING, AnnouncementStatus.COMPLETED],
        ).select_related("created_by").order_by("-publish_at")[:100]
        return success_response([self._data(item) for item in rows])

    def post(self, request, group_id):
        membership, error = self.leader_membership(request, group_id)
        if error:
            return error
        title = str(request.data.get("title", "")).strip()
        body = str(request.data.get("content", "")).strip()
        if not title or not body:
            return error_response("An announcement needs a title and message.", status=400)
        from apps.communications.models import Announcement, AnnouncementStatus, AudienceType
        from apps.communications.services import authorize_audience
        from apps.communications.tasks import dispatch_announcement
        try:
            authorize_audience(request.user, membership.group.branch, AudienceType.CUSTOM, [membership.group], "")
        except Exception as exc:
            return error_response(str(exc), status=403)
        announcement = Announcement.objects.create(
            branch=membership.group.branch, title=title[:255], body=body,
            audience_type=AudienceType.CUSTOM, channels=["PUSH"], publish_at=timezone.now(),
            created_by=request.user, status=AnnouncementStatus.QUEUED,
        )
        announcement.target_groups.add(membership.group)
        dispatch_announcement.delay(str(announcement.id))
        return success_response(self._data(announcement), status=201)


class CommunityMeetingView(_CommunityMemberView):
    """Group meeting calendar visible to active members and edited by its leaders."""

    @staticmethod
    def _data(item):
        return {
            "id": str(item.id), "title": item.title, "description": item.agenda, "venue": item.location,
            "starts_at": item.starts_at, "ends_at": item.ends_at or item.starts_at,
            "status": "completed" if item.ends_at and item.ends_at < timezone.now() else "upcoming",
        }

    def get(self, request, group_id):
        membership = self.membership(request, group_id)
        if not membership:
            return error_response("Community not found.", status=404)
        rows = GroupMeeting.objects.filter(group=membership.group).order_by("starts_at")[:100]
        return success_response([self._data(item) for item in rows])

    def post(self, request, group_id):
        membership, error = self.leader_membership(request, group_id)
        if error:
            return error
        from django.utils.dateparse import parse_datetime
        title = str(request.data.get("title", "")).strip()
        starts_at = parse_datetime(str(request.data.get("starts_at", "")))
        ends_at = parse_datetime(str(request.data.get("ends_at", "")))
        if not title or starts_at is None or ends_at is None:
            return error_response("A title, start time and end time are required.", status=400)
        if timezone.is_naive(starts_at):
            starts_at = timezone.make_aware(starts_at)
        if timezone.is_naive(ends_at):
            ends_at = timezone.make_aware(ends_at)
        if ends_at <= starts_at:
            return error_response("The meeting end time must be after its start time.", status=400)
        meeting = GroupMeeting.objects.create(
            group=membership.group, title=title[:180], starts_at=starts_at, ends_at=ends_at,
            location=str(request.data.get("venue", "")).strip()[:255],
            agenda=str(request.data.get("description", "")).strip(), created_by=request.user,
        )
        return success_response(self._data(meeting), status=201)


class CommunityMemberDirectoryView(_CommunityMemberView):
    """Leader-only membership directory and controlled approval/suspension actions."""

    @staticmethod
    def _membership_data(item):
        member = item.member
        return {
            "id": str(item.id), "user_id": str(member.user_id), "name": member.full_name,
            "identifier": member.user.matric_no if member.user_id else None,
            "programme": getattr(member.department, "name", None), "level": member.academic_level,
            "status": "active" if item.is_active else "suspended", "is_primary": item.role == GroupRole.LEADER,
            "joined_at": item.joined_at,
        }

    @staticmethod
    def _request_data(item):
        member = item.member
        return {
            "id": str(item.id), "user_id": str(member.user_id), "name": member.full_name,
            "identifier": member.user.matric_no if member.user_id else None,
            "programme": getattr(member.department, "name", None), "level": member.academic_level,
            "status": "pending", "is_primary": False, "joined_at": item.requested_at,
        }

    def get(self, request, group_id):
        membership, error = self.leader_membership(request, group_id)
        if error:
            return error
        requested_status = str(request.query_params.get("status", "pending")).lower()
        if requested_status == "pending":
            rows = GroupJoinRequest.objects.filter(group=membership.group, status=JoinRequestStatus.PENDING).select_related("member", "member__user", "member__department")
            return success_response([self._request_data(item) for item in rows])
        rows = GroupMembership.objects.filter(group=membership.group, is_active=requested_status == "active").select_related("member", "member__user", "member__department")
        return success_response([self._membership_data(item) for item in rows])

    def patch(self, request, group_id, record_id):
        membership, error = self.leader_membership(request, group_id)
        if error:
            return error
        next_status = str(request.data.get("status", "")).lower()
        if next_status in {"active", "rejected"}:
            request_row = GroupJoinRequest.objects.filter(group=membership.group, id=record_id, status=JoinRequestStatus.PENDING).first()
            if not request_row:
                return error_response("Pending membership request not found.", status=404)
            if next_status == "active":
                with transaction.atomic():
                    member = Member.objects.select_for_update().get(pk=request_row.member_id)
                    conflict = _fellowship_conflict(member, membership.group)
                    if conflict:
                        return error_response(conflict, status=409)
                    GroupMembership.objects.update_or_create(group=membership.group, member=member, defaults={"is_active": True, "role": GroupRole.MEMBER})
                    if membership.group.group_type == "FELLOWSHIP":
                        member.fellowship = membership.group
                        member.save(update_fields=["fellowship", "updated_at"])
                    request_row.status = JoinRequestStatus.APPROVED
                    request_row.resolved_by, request_row.resolved_at = request.user, timezone.now()
                    request_row.save(update_fields=["status", "resolved_by", "resolved_at"])
            else:
                request_row.status = JoinRequestStatus.REJECTED
                request_row.resolved_by, request_row.resolved_at = request.user, timezone.now()
                request_row.save(update_fields=["status", "resolved_by", "resolved_at"])
            return success_response({"id": str(request_row.id), "status": next_status})
        if next_status == "suspended":
            record = GroupMembership.objects.filter(group=membership.group, id=record_id).first()
            if not record:
                return error_response("Membership not found.", status=404)
            if record.role == GroupRole.LEADER:
                return error_response("Assign another leader before suspending this leader.", status=400)
            record.is_active = False
            record.save(update_fields=["is_active"])
            return success_response({"id": str(record.id), "status": "suspended"})
        return error_response("Unsupported membership status.", status=400)


class CommunityLeadershipDirectoryView(APIView):
    """An authenticated, contact-free directory of active group leaders."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not _has_student_community_access(request):
            return error_response("Communities are available only to student accounts.", status=403)
        rows = GroupMembership.objects.filter(
            group__is_active=True,
            is_active=True,
            role__in=[GroupRole.LEADER, GroupRole.ASSISTANT_LEADER],
        ).select_related("group", "member").order_by("group__name", "role", "joined_at")
        return success_response([
            {
                "position": "Group leader" if row.role == GroupRole.LEADER else "Assistant group leader",
                "leader_name": row.member.full_name,
                "community_name": row.group.name,
                "community_slug": str(row.group_id),
                "community_type": _community_type(row.group.group_type),
                "starts_at": row.joined_at,
                "ends_at": None,
            }
            for row in rows
        ])


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
        return GroupJoinRequest.objects.select_related("group", "member").order_by(
            "-requested_at", "-id"
        )

    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        item = self.get_object()
        if item.status != JoinRequestStatus.PENDING:
            return Response({"detail": "Only pending requests can be approved."}, status=400)
        with transaction.atomic():
            member = Member.objects.select_for_update().get(pk=item.member_id)
            conflict = _fellowship_conflict(member, item.group)
            if conflict:
                return error_response(conflict, status=409)
            GroupMembership.objects.update_or_create(group=item.group, member=member, defaults={"is_active": True, "role": GroupRole.MEMBER})
            if item.group.group_type == "FELLOWSHIP":
                member.fellowship = item.group
                member.save(update_fields=["fellowship", "updated_at"])
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
        member = getattr(request.user, "member_profile", None)
        return member if is_student_community_member(member) else None

    def get(self, request):
        member = self._member(request)
        if member is None:
            return error_response("This feature is available to student accounts only.", status=403)
        from apps.ministries.models import Group
        groups = Group.objects.filter(
            branch=member.branch, is_active=True,
            group_type__in=["FELLOWSHIP", "UNIT"],
        ).order_by("group_type", "name")
        memberships = GroupMembership.objects.filter(
            member=member, is_active=True, group__branch=member.branch,
            group__is_active=True, group__group_type__in=["FELLOWSHIP", "UNIT"],
        ).select_related("group").order_by("group__group_type", "group__name")
        current_fellowship = None
        if member.fellowship_id:
            current_fellowship = Group.objects.filter(
                id=member.fellowship_id, branch=member.branch,
                group_type="FELLOWSHIP", is_active=True,
            ).values("id", "name").first()
        if current_fellowship is None:
            fellowship_membership = next((row for row in memberships if row.group.group_type == "FELLOWSHIP"), None)
            if fellowship_membership:
                current_fellowship = {"id": str(fellowship_membership.group_id), "name": fellowship_membership.group.name}
        requests = GroupJoinRequest.objects.filter(
            member=member, group__group_type__in=["FELLOWSHIP", "UNIT"],
        ).select_related("group").order_by("-requested_at")
        return success_response({
            "groups": [{"id": str(group.id), "name": group.name, "type": group.group_type, "description": group.description} for group in groups],
            "memberships": [{"id": str(row.group_id), "name": row.group.name, "type": row.group.group_type} for row in memberships],
            "current_fellowship": current_fellowship,
            "requests": [{"id": str(item.id), "group_id": str(item.group_id), "group": item.group.name, "type": item.group.group_type, "status": item.status, "message": item.message, "requested_at": item.requested_at} for item in requests],
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
        if group.group_type not in {"FELLOWSHIP", "UNIT"}:
            return error_response("Only Fellowships and Chapel Units accept student join requests.", status=404)
        if GroupMembership.objects.filter(group=group, member=member, is_active=True).exists():
            return error_response("You are already an active member of this community.", status=409)
        with transaction.atomic():
            member = Member.objects.select_for_update().get(pk=member.pk)
            conflict = _fellowship_conflict(member, group)
            if conflict:
                return error_response(conflict, status=409)
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
        return GroupTask.objects.select_related("group", "assignee").order_by(
            "-created_at", "-id"
        )

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
        return (
            GroupMeeting.objects.select_related("group")
            .prefetch_related("attendance")
            .order_by("-starts_at", "-id")
        )

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
