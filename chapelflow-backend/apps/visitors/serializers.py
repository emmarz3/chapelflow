from rest_framework import serializers

from common.serializers.validators import ScopedFKValidationMixin
from .models import Visitor, VisitorFollowUp


class VisitorFollowUpSerializer(ScopedFKValidationMixin, serializers.ModelSerializer):
    class Meta:
        model = VisitorFollowUp
        fields = [
            "id", "visitor", "assigned_to", "method", "outcome", "notes",
            "scheduled_for", "completed_at", "created_at",
        ]
        read_only_fields = ["id", "created_at"]
    
    def validate_visitor(self, visitor):
        """Phase 3: Validate visitor belongs to accessible branch."""
        return self.validate_related_branch_fk(visitor, 'visitor')
    
    def validate_assigned_to(self, assigned_to):
        """Phase 3: Validate assigned_to staff belongs to accessible branch."""
        if assigned_to:
            return self.validate_user_fk(assigned_to, 'assigned_to')
        return assigned_to


class VisitorSerializer(ScopedFKValidationMixin, serializers.ModelSerializer):
    follow_ups = VisitorFollowUpSerializer(many=True, read_only=True)

    class Meta:
        model = Visitor
        fields = [
            "id", "branch", "full_name", "phone_number", "email", "gender",
            "address", "how_heard", "invited_by", "first_visit_date",
            "status", "converted_member", "converted_at", "follow_ups",
            "created_at", "updated_at",
        ]
        read_only_fields = ["id", "status", "converted_member", "converted_at", "created_at", "updated_at"]

    def validate_branch(self, branch):
        """
        Phase 3: Prevent cross-branch visitor creation.
        Same IDOR class as apps.members.serializers.MemberSerializer.validate_branch.
        """
        return self.validate_branch_fk(branch)
    
    def validate_invited_by(self, invited_by):
        """Phase 3: Validate invited_by member belongs to accessible branch."""
        if invited_by:
            return self.validate_member_fk(invited_by)
        return invited_by

    def validate(self, attrs):
        invited_by = attrs.get("invited_by")
        branch = attrs.get("branch") or (self.instance.branch if self.instance else None)
        if invited_by is not None and branch is not None and invited_by.branch_id != branch.id:
            raise serializers.ValidationError({"invited_by": "Must be a member of the same branch as the visitor."})
        return attrs


class VisitorFirstTimerFormSerializer(serializers.ModelSerializer):
    """
    The public First-Timer Form itself (spec section 4) — deliberately a
    narrower field set than VisitorSerializer (no `status`/conversion
    fields writable from the public internet). AllowAny. `branch` is
    included because a visitor picks which Chapel/campus they attended —
    Branch name/type is public, non-PII reference data, safe to expose here.
    """
    class Meta:
        model = Visitor
        fields = ["branch", "full_name", "phone_number", "email", "gender", "address", "how_heard", "invited_by", "first_visit_date"]

    def validate(self, attrs):
        if not attrs.get("phone_number") and not attrs.get("email"):
            raise serializers.ValidationError("Provide at least a phone number or an email so we can follow up.")
        invited_by = attrs.get("invited_by")
        branch = attrs.get("branch")
        if invited_by is not None and branch is not None and invited_by.branch_id != branch.id:
            # `invited_by` is free-text-adjacent from the public's point of
            # view (a visitor just picks "who invited me" from people they
            # know at that branch) -- silently drop rather than 400, since
            # a mismatch here is far more likely to be visitor confusion
            # than an attack, and we don't want to block a legitimate
            # first-timer submission over it. It must never be *kept*
            # though: an unrelated invited_by would let a public caller
            # attach an arbitrary Member id from another branch to a
            # visitor record.
            attrs["invited_by"] = None
        return attrs
