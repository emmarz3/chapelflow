from rest_framework import serializers

from common.serializers.validators import ScopedFKValidationMixin
from .models import PrayerNote, PrayerRequest


class PrayerNoteSerializer(ScopedFKValidationMixin, serializers.ModelSerializer):
    class Meta:
        model = PrayerNote
        fields = ["id", "prayer_request", "author", "note", "created_at"]
        read_only_fields = ["id", "author", "created_at"]
    
    def validate_prayer_request(self, prayer_request):
        """Phase 3: Validate prayer request belongs to accessible branch."""
        return self.validate_related_branch_fk(prayer_request, 'prayer_request')


class PrayerRequestSerializer(ScopedFKValidationMixin, serializers.ModelSerializer):
    notes = PrayerNoteSerializer(many=True, read_only=True)

    class Meta:
        model = PrayerRequest
        fields = [
            "id", "branch", "member", "submitted_by_name", "created_by",
            "category", "details", 
            "privacy_level", "is_private",  # Both for backward compatibility
            "status", "assigned_to", 
            "answered_at", "closure_reason",
            "notes", "created_at", "updated_at",
        ]
        read_only_fields = [
            "id", "created_by", "created_at", "updated_at",
            "is_private",  # Auto-synced from privacy_level
            "answered_at",  # Auto-set when status=ANSWERED
        ]
    
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
        
        return super().update(instance, validated_data)
