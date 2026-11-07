from rest_framework import serializers

from .models import Group


class GroupLeaderSerializer(serializers.Serializer):
    """One active leader, sourced from groups.GroupMembership (role=LEADER)."""
    member_id = serializers.UUIDField()
    full_name = serializers.CharField()
    joined_at = serializers.DateField()


class GroupSerializer(serializers.ModelSerializer):
    member_count = serializers.IntegerField(source="memberships.count", read_only=True)

    # The real, multi-leader-capable leadership listing (Phase 0
    # remediation) — built purely from active GroupMembership rows, never
    # from the deprecated `leader` FK below. See Group.leader's help_text
    # and docs/university_structure.md for why.
    leaders = serializers.SerializerMethodField()

    class Meta:
        model = Group
        fields = [
            "id", "branch", "parent", "name", "group_type", "description",
            "leader", "leaders", "is_active", "member_count", "created_at", "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at", "leaders"]
        extra_kwargs = {
            "leader": {
                "help_text": "DEPRECATED — do not read this for leadership listings, use `leaders` "
                             "instead. Kept writable only for backward compatibility with existing "
                             "integrations; new code should manage leadership via "
                             "POST /api/v1/group-memberships/ with role=LEADER.",
                "required": False,
            },
        }

    def validate_branch(self, branch):
        """
        CRITICAL: without this, any caller holding members.create/update
        (routinely granted to Fellowship/Unit/Ministry leaders) could
        create or re-parent a Group into a completely different branch —
        BranchScopedQuerysetMixin only protects which EXISTING rows a
        request can see/target, not what branch id is supplied in the
        request body for create/update.
        """
        request = self.context.get("request")
        if request is None:
            return branch
        from common.permissions.scoping import user_can_access_branch
        if not user_can_access_branch(request.user, branch.id):
            raise serializers.ValidationError("You are not authorized to create/move groups into this branch.")
        return branch

    def validate_parent(self, parent):
        """A group's parent must live in the same branch — never let a scope boundary be crossed via nesting."""
        if parent is None:
            return parent
        branch = self.initial_data.get("branch") if hasattr(self, "initial_data") else None
        # Fall back to the instance's current branch on partial update where branch isn't in the payload.
        target_branch_id = branch or (self.instance.branch_id if self.instance else None)
        if target_branch_id and str(parent.branch_id) != str(target_branch_id):
            raise serializers.ValidationError("Parent group must belong to the same branch.")
        return parent

    def validate_leader(self, leader):
        """
        Deprecated field, but still writable for backward compatibility
        (see extra_kwargs help_text) — it must still respect branch scope
        so it can't be used as a side-door to link a Member from another
        branch into this Group.
        """
        if leader is None:
            return leader
        target_branch_id = self.initial_data.get("branch") if hasattr(self, "initial_data") else None
        target_branch_id = target_branch_id or (self.instance.branch_id if self.instance else None)
        if target_branch_id and str(leader.branch_id) != str(target_branch_id):
            raise serializers.ValidationError("Leader must be a member of the same branch as the group.")
        return leader

    def get_leaders(self, obj):
        from apps.groups.serializers import active_leader_memberships

        memberships = active_leader_memberships(obj)
        return GroupLeaderSerializer(
            [
                {"member_id": m.member_id, "full_name": m.member.full_name, "joined_at": m.joined_at}
                for m in memberships
            ],
            many=True,
        ).data
