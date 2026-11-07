from rest_framework import serializers

from common.serializers.validators import ScopedFKValidationMixin
from .models import PrayerNote, PrayerRequest, Testimony


class PrayerNoteSerializer(ScopedFKValidationMixin, serializers.ModelSerializer):
    class Meta:
        model = PrayerNote
        fields = ["id", "prayer_request", "author", "note", "created_at"]
        read_only_fields = ["id", "author", "created_at"]
    
    def validate_prayer_request(self, prayer_request):
        """Phase 3: Validate prayer request belongs to accessible branch."""
        return self.validate_related_branch_fk(prayer_request, 'prayer_request')


class PrayerRequestSerializer(ScopedFKValidationMixin, serializers.ModelSerializer):
<<<<<<< HEAD
    notes = serializers.SerializerMethodField()
=======
    notes = PrayerNoteSerializer(many=True, read_only=True)
>>>>>>> origin/main

    class Meta:
        model = PrayerRequest
        fields = [
            "id", "branch", "member", "submitted_by_name", "created_by",
            "category", "details", 
<<<<<<< HEAD
            "privacy_level", "consent_to_share", "is_private",  # Both for backward compatibility
=======
            "privacy_level", "is_private",  # Both for backward compatibility
>>>>>>> origin/main
            "status", "assigned_to", 
            "answered_at", "closure_reason",
            "notes", "created_at", "updated_at",
        ]
        read_only_fields = [
            "id", "created_by", "created_at", "updated_at",
            "is_private",  # Auto-synced from privacy_level
            "answered_at",  # Auto-set when status=ANSWERED
        ]
        extra_kwargs = {
            "branch": {"required": False},
            "member": {"required": False},
            "assigned_to": {"required": False},
        }

<<<<<<< HEAD
    def get_notes(self, instance):
        """Follow-up notes are private pastoral records, even on an owner's request."""
        if not self._is_pastoral_viewer():
            return []
        return PrayerNoteSerializer(instance.notes.all(), many=True, context=self.context).data

    def _is_pastoral_viewer(self):
        request = self.context.get("request")
        user = getattr(request, "user", None)
        if not user or not user.is_authenticated:
            return False
        from common.constants.roles import Roles

        role = user.get_role_code() if hasattr(user, "get_role_code") else user.role
        return role in Roles.PASTORAL_ACCESS_ROLES

    def to_representation(self, instance):
        data = super().to_representation(instance)
        request = self.context.get("request")
        user = getattr(request, "user", None)
        is_owner = bool(
            user and user.is_authenticated and instance.member_id
            and instance.member.user_id == user.id
        )
        if instance.privacy_level == "PUBLIC" and not is_owner and not self._is_pastoral_viewer():
            # Public sharing exposes the prayer content, not the requester's identity
            # or internal assignment/audit identifiers.
            data.update({"member": None, "submitted_by_name": "", "created_by": None, "assigned_to": None})
        return data

=======
>>>>>>> origin/main
    def validate(self, attrs):
        request = self.context.get("request")
        if not request or not request.user:
            return attrs
        from common.constants.roles import Roles

        role = request.user.get_role_code() if hasattr(request.user, "get_role_code") else request.user.role
        if role not in Roles.PASTORAL_ACCESS_ROLES:
            protected_fields = {"branch", "member", "assigned_to", "status", "closure_reason"}
            submitted = protected_fields.intersection(attrs)
            if submitted:
                raise serializers.ValidationError({field: "This field is managed by the pastoral team." for field in submitted})
            privacy_level = attrs.get("privacy_level", getattr(self.instance, "privacy_level", "PRIVATE"))
            if privacy_level not in {"PRIVATE", "PASTORAL"}:
                raise serializers.ValidationError({"privacy_level": "Submit a private or pastoral request. A pastoral leader can approve wider sharing after consent."})
<<<<<<< HEAD
            if "consent_to_share" in attrs:
                owner_id = self.instance.member.user_id if self.instance and self.instance.member_id else None
                if self.instance and owner_id != request.user.id:
                    raise serializers.ValidationError({"consent_to_share": "Only the requester can change sharing consent."})
        elif "consent_to_share" in attrs:
            raise serializers.ValidationError({"consent_to_share": "Only the requester can provide sharing consent."})

        has_consent = attrs.get(
            "consent_to_share",
            getattr(self.instance, "consent_to_share", False),
        )
        target_privacy = attrs.get("privacy_level", getattr(self.instance, "privacy_level", "PRIVATE"))
        if attrs.get("consent_to_share") is False:
            target_privacy = "PRIVATE"
        has_requester = bool(
            (self.instance and self.instance.member_id)
            or attrs.get("member")
            or (role not in Roles.PASTORAL_ACCESS_ROLES and getattr(request.user, "member_profile", None))
        )
        if target_privacy in {"PUBLIC", "FELLOWSHIP"} and not (has_consent and has_requester):
            raise serializers.ValidationError({"privacy_level": "The requester must consent before this request can be shared with the community."})
=======
>>>>>>> origin/main
        return attrs
    
    def validate_branch(self, branch):
        """Phase 3: Validate user can access this branch."""
        return self.validate_branch_fk(branch)
    
    def validate_member(self, member):
        """Phase 3: Validate member belongs to accessible branch."""
        if member:
            return self.validate_member_fk(member)
        return member
    
    def validate_assigned_to(self, assigned_to):
        """
        Phase 13: Enhanced validation for assignment.
        
        Checks:
        1. User belongs to accessible branch (existing)
        2. User has appropriate role (pastoral/chaplain access)
        3. User is active
        """
        if not assigned_to:
            return assigned_to
        
        # Existing branch validation
        assigned_to = self.validate_user_fk(assigned_to, 'assigned_to')
<<<<<<< HEAD

        # The assignee must be authorized for this specific care record.
        # Actor-level org-wide scope alone is insufficient: it must not let a
        # request in one branch be handed to staff assigned to another.
        request = self.context.get("request")
        request_branch_id = (
            self.instance.branch_id
            if self.instance
            else self.initial_data.get("branch") or getattr(request.user, "branch_id", None)
        )
        if request_branch_id and str(assigned_to.branch_id) != str(request_branch_id):
            raise serializers.ValidationError(
                "Cannot assign a prayer request to staff from another branch."
            )
=======
>>>>>>> origin/main
        
        # Phase 13: Verify user has pastoral role
        from common.constants.roles import Roles
        
        acceptable_roles = (
            list(Roles.PASTORAL_ACCESS_ROLES) + 
            list(Roles.GLOBAL_SCOPE_ROLES)
        )
        
        user_role = assigned_to.get_role_code() if hasattr(assigned_to, 'get_role_code') else getattr(assigned_to, 'role', None)
        
        if user_role not in acceptable_roles:
            raise serializers.ValidationError(
                f"Cannot assign prayer requests to user with role '{user_role}'. "
                f"Only pastoral staff and administrators can be assigned prayer requests."
            )
        
        # Verify user is active
        if not assigned_to.is_active:
            raise serializers.ValidationError(
                "Cannot assign prayer request to inactive user."
            )
        
        return assigned_to
    
    def update(self, instance, validated_data):
        """
        Phase 13: Auto-set answered_at when status changes to ANSWERED.
        """
        # Auto-set answered_at when status changes to ANSWERED
        if 'status' in validated_data:
            from django.utils import timezone
            if validated_data['status'] == 'ANSWERED' and instance.status != 'ANSWERED':
                instance.answered_at = timezone.now()
<<<<<<< HEAD

        if validated_data.get("consent_to_share") is False and instance.privacy_level in {"PUBLIC", "FELLOWSHIP"}:
            validated_data["privacy_level"] = "PRIVATE"
=======
>>>>>>> origin/main
        
        return super().update(instance, validated_data)


class TestimonySerializer(serializers.ModelSerializer):
    member_name = serializers.CharField(source="member.full_name", read_only=True)
    reviewer_name = serializers.CharField(source="reviewed_by.get_full_name", read_only=True)

    class Meta:
        model = Testimony
        fields = [
            "id", "branch", "member", "member_name", "title", "details", "consent_to_publish",
            "status", "reviewed_by", "reviewer_name", "reviewed_at", "rejection_reason", "created_at", "updated_at",
        ]
        read_only_fields = [
            "id", "branch", "member", "member_name", "status", "reviewed_by", "reviewer_name",
            "reviewed_at", "rejection_reason", "created_at", "updated_at",
        ]
