from rest_framework import serializers

from common.serializers.validators import ScopedFKValidationMixin
from .models import PastoralCase, PastoralNote


class PastoralNoteSerializer(ScopedFKValidationMixin, serializers.ModelSerializer):
    class Meta:
        model = PastoralNote
        fields = ["id", "case", "author", "note", "created_at"]
        read_only_fields = ["id", "author", "created_at"]
    
    def validate_case(self, case):
        """
        Phase 3: Validate case belongs to accessible branch AND user has
        object-level permission to access this specific case.
        """
        request = self.context.get('request')
        if not request or not request.user:
            raise serializers.ValidationError("Authentication required")
        
        # First check: case branch is accessible
        case = self.validate_related_branch_fk(case, 'case')
        
        # Second check: user has object-level permission to this specific case
        from common.permissions.rbac import IsPastoralAuthorized
        permission = IsPastoralAuthorized()
        
        if not permission.has_object_permission(request, None, case):
            raise serializers.ValidationError(
                "You are not authorized to add notes to this pastoral case."
            )
        
        return case


class PastoralCaseSerializer(ScopedFKValidationMixin, serializers.ModelSerializer):
    notes = PastoralNoteSerializer(many=True, read_only=True)

    class Meta:
        model = PastoralCase
        fields = [
            "id", "branch", "member", "assigned_to", "category", "summary",
            "priority", "status", "next_follow_up_date",
            "escalated_at", "escalated_by", "escalation_reason",
            "closed_at", "closure_reason",
            "created_by", "created_at", "updated_by", "updated_at",
            "notes",
        ]
        read_only_fields = [
            "id", "created_by", "created_at", "updated_by", "updated_at",
            "escalated_at", "escalated_by",  # Set via escalation action
            "closed_at",  # Auto-set when status=CLOSED
        ]
    
    def validate_branch(self, branch):
        """Phase 3: Validate user can access this branch."""
        return self.validate_branch_fk(branch)
    
    def validate_member(self, member):
        """Phase 3: Validate member belongs to accessible branch."""
        return self.validate_member_fk(member)
    
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
                f"Cannot assign pastoral cases to user with role '{user_role}'. "
                f"Only pastoral staff and administrators can be assigned pastoral cases."
            )
        
        # Verify user is active
        if not assigned_to.is_active:
            raise serializers.ValidationError(
                "Cannot assign pastoral case to inactive user."
            )
        
        return assigned_to
    
    def update(self, instance, validated_data):
        """
        Phase 13: Auto-set timestamps and track who updated.
        """
        request = self.context.get('request')
        if request and request.user:
            instance.updated_by = request.user
        
        # Auto-set closed_at when status changes to CLOSED
        if 'status' in validated_data:
            from django.utils import timezone
            if validated_data['status'] == 'CLOSED' and instance.status != 'CLOSED':
                instance.closed_at = timezone.now()
        
        return super().update(instance, validated_data)
