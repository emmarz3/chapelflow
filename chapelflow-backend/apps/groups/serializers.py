from rest_framework import serializers

from .models import GroupJoinRequest, GroupMeeting, GroupMeetingAttendance, GroupMembership, GroupRole, GroupTask


class GroupMembershipSerializer(serializers.ModelSerializer):
    member_name = serializers.CharField(source="member.full_name", read_only=True)
    member_identifier = serializers.CharField(source="member.user.matric_no", read_only=True)
    group_name = serializers.CharField(source="group.name", read_only=True)

    class Meta:
        model = GroupMembership
        fields = ["id", "member", "group", "role", "joined_at", "is_active", "member_name", "member_identifier", "group_name"]
        read_only_fields = ["id", "joined_at"]

    def validate_group(self, group):
        """
        CRITICAL (Phase 4/6): GroupMembership is the canonical leadership
        source (docs/university_structure.md) — an unchecked `group` FK
        here means any caller with members.update permission (e.g. every
        Fellowship Leader) could POST a membership with role=LEADER
        against a Group in a completely different branch/fellowship they
        have no authority over, self-escalating into leadership of it.
        BranchScopedQuerysetMixin only protects the queryset (list/
        retrieve/update/destroy of EXISTING rows); it does nothing for a
        `group` id supplied in a create/update request body, so that has
        to be validated explicitly here.
        """
        request = self.context.get("request")
        if request is None:
            return group
        from common.permissions.scoping import user_can_access_group
        if not user_can_access_group(request.user, group):
            raise serializers.ValidationError("You are not authorized to manage membership for this group.")
        return group

    def validate_member(self, member):
        """
        Mirrors validate_group: without this, a caller could also target
        a Member outside their own branch/scope even when the `group` is
        legitimately theirs (e.g. adding an out-of-branch member into a
        group they lead, or probing which member ids exist elsewhere).
        """
        request = self.context.get("request")
        if request is None:
            return member
        from common.permissions.scoping import user_can_access_branch
        if not user_can_access_branch(request.user, member.branch_id):
            raise serializers.ValidationError("You are not authorized to manage membership for this member.")
        return member

    def validate(self, attrs):
        """
        Cross-field check: even if both `group` and `member` individually
        pass, a Fellowship Leader could still pair a group they lead with
        a member from a *different* branch than that group. Group and
        member must belong to the same branch.
        """
        group = attrs.get("group") or getattr(self.instance, "group", None)
        member = attrs.get("member") or getattr(self.instance, "member", None)
        if group is not None and member is not None and group.branch_id != member.branch_id:
            raise serializers.ValidationError(
                {"member": "Member and group must belong to the same branch."}
            )
        return attrs


class _ScopedGroupSerializer(serializers.ModelSerializer):
    """Validates both supplied group and member IDs against the caller's scope."""
    def validate_group(self, group):
        request = self.context["request"]
        from common.permissions.scoping import user_can_access_group
        if not user_can_access_group(request.user, group):
            raise serializers.ValidationError("You are not authorized for this group.")
        return group


class GroupJoinRequestSerializer(_ScopedGroupSerializer):
    member_name = serializers.CharField(source="member.full_name", read_only=True)
    group_name = serializers.CharField(source="group.name", read_only=True)

    class Meta:
        model = GroupJoinRequest
        fields = ["id", "group", "group_name", "member", "member_name", "message", "status", "requested_at", "resolved_at"]
        read_only_fields = ["id", "status", "requested_at", "resolved_at"]


class GroupTaskSerializer(_ScopedGroupSerializer):
    assignee_name = serializers.CharField(source="assignee.full_name", read_only=True)

    class Meta:
        model = GroupTask
        fields = ["id", "group", "title", "description", "assignee", "assignee_name", "status", "due_at", "created_at", "completed_at"]
        read_only_fields = ["id", "created_at", "completed_at"]

    def validate_assignee(self, member):
        if member and member.branch_id != self.initial_data.get("branch", member.branch_id):
            raise serializers.ValidationError("Assignee must belong to the group branch.")
        return member


class GroupMeetingSerializer(_ScopedGroupSerializer):
    attendance_count = serializers.IntegerField(source="attendance.count", read_only=True)

    class Meta:
        model = GroupMeeting
        fields = ["id", "group", "title", "starts_at", "ends_at", "location", "agenda", "created_at", "attendance_count"]
        read_only_fields = ["id", "created_at", "attendance_count"]

    def validate(self, attrs):
        if attrs.get("ends_at") and attrs["ends_at"] <= attrs.get("starts_at", self.instance.starts_at if self.instance else None):
            raise serializers.ValidationError({"ends_at": "Meeting end time must be after its start time."})
        return attrs


class GroupMeetingAttendanceSerializer(serializers.ModelSerializer):
    member_name = serializers.CharField(source="member.full_name", read_only=True)

    class Meta:
        model = GroupMeetingAttendance
        fields = ["id", "meeting", "member", "member_name", "present", "recorded_at"]
        read_only_fields = ["id", "recorded_at"]


def active_leader_memberships(group):
    """
    Shared helper: active GroupMembership rows with role=LEADER for a
    given Group, ordered by seniority (earliest joined_at first).

    This is the canonical source for "who leads this group" everywhere in
    the codebase (Phase 0 remediation) — apps.ministries.serializers
    .GroupSerializer.get_leaders uses this same shape, and any new code
    that needs a Group's leadership should call this rather than reading
    apps.ministries.models.Group.leader, which is deprecated (see that
    field's help_text and docs/university_structure.md).
    """
    return (
        GroupMembership.objects.filter(group=group, role=GroupRole.LEADER, is_active=True)
        .select_related("member")
        .order_by("joined_at")
    )
