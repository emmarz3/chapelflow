"""
Phase 3: Serializer validation helpers for authorization.

These validators ensure that foreign key fields in request bodies
cannot be used to bypass scope restrictions. Every FK pointing to
branch-scoped or organization-sensitive data must be validated.

Critical security principle: NEVER TRUST CLIENT-SUPPLIED IDs
"""
from rest_framework import serializers

from common.permissions.scoping import user_can_access_branch, user_can_access_group


class ScopedFKValidationMixin:
    """
    Phase 3: Mixin for serializers that provides FK scope validation methods.
    
    Usage:
        class EventSerializer(ScopedFKValidationMixin, serializers.ModelSerializer):
            def validate_branch(self, branch):
                return self.validate_branch_fk(branch)
            
            def validate_location(self, location):
                return self.validate_related_branch_fk(location, 'location')
    """
    
    def validate_branch_fk(self, branch):
        """
        Validate that user can access the specified branch.
        
        Use for direct branch FK fields like Event.branch, Member.branch
        """
        request = self.context.get('request')
        if not request or not request.user:
            raise serializers.ValidationError("Authentication required")
        
        if not user_can_access_branch(request.user, branch.id):
            raise serializers.ValidationError(
                "You are not authorized to create/assign resources in this branch."
            )
        
        return branch
    
    def validate_related_branch_fk(self, obj, field_name):
        """
        Validate that user can access the branch of a related object.
        
        Use for FKs to objects that have a branch field, like:
        - Event.location (Location has branch)
        - AttendanceSession.event (Event has branch)
        - VolunteerAssignment.volunteer (VolunteerProfile has branch)
        
        Args:
            obj: The related object instance
            field_name: Name of the field (for error messages)
        """
        request = self.context.get('request')
        if not request or not request.user:
            raise serializers.ValidationError("Authentication required")
        
        if not obj:
            return obj
        
        # Get branch from related object
        branch_id = getattr(obj, 'branch_id', None)
        if not branch_id:
            # Try traversing one level (e.g., session.event.branch)
            related = getattr(obj, 'event', None) or getattr(obj, 'group', None)
            if related:
                branch_id = getattr(related, 'branch_id', None)
        
        if branch_id and not user_can_access_branch(request.user, branch_id):
            raise serializers.ValidationError(
                f"The selected {field_name} belongs to a branch you cannot access."
            )
        
        return obj
    
    def validate_member_fk(self, member):
        """
        Validate that user can access the specified member.
        
        Checks that member's branch is within user's scope.
        """
        request = self.context.get('request')
        if not request or not request.user:
            raise serializers.ValidationError("Authentication required")
        
        if not member:
            return member
        
        member_branch_id = getattr(member, 'branch_id', None)
        if member_branch_id and not user_can_access_branch(request.user, member_branch_id):
            raise serializers.ValidationError(
                "The selected member belongs to a branch you cannot access."
            )
        
        return member
    
    def validate_group_fk(self, group):
        """
        Validate that user can access/administer the specified group.
        
        Uses user_can_access_group which checks both branch scope and
        leader scope for assignment-scoped roles.
        """
        request = self.context.get('request')
        if not request or not request.user:
            raise serializers.ValidationError("Authentication required")
        
        if not group:
            return group
        
        if not user_can_access_group(request.user, group):
            raise serializers.ValidationError(
                "You are not authorized to assign members to this group."
            )
        
        return group
    
    def validate_user_fk(self, user, field_name='user'):
        """
        Validate assignment of a user FK field (like assigned_to, created_by).
        
        Ensures user can only assign staff from their own scope.
        """
        request = self.context.get('request')
        if not request or not request.user:
            raise serializers.ValidationError("Authentication required")
        
        if not user:
            return user
        
        # Check if assigned user's branch is accessible
        user_branch_id = getattr(user, 'branch_id', None)
        if user_branch_id and not user_can_access_branch(request.user, user_branch_id):
            raise serializers.ValidationError(
                f"The selected {field_name} belongs to a branch you cannot access."
            )
        
        return user
    
    def prevent_ownership_change(self, field_name, error_message=None):
        """
        Prevent changing ownership fields on update.
        
        Use in validate() method for fields like 'user', 'created_by', 'member'
        that should not be changed after creation.
        
        Example:
            def validate(self, attrs):
                attrs = super().validate(attrs)
                self.prevent_ownership_change('user', 'Cannot change member account link')
                return attrs
        """
        if not self.instance:
            # Creating - no restriction
            return
        
        field_value = self.initial_data.get(field_name)
        if field_value is None:
            # Field not in request - no change attempted
            return
        
        instance_value = getattr(self.instance, field_name, None)
        instance_value_id = getattr(instance_value, 'id', instance_value)
        
        # Compare IDs (handle both object and ID submission)
        if hasattr(field_value, 'id'):
            submitted_id = field_value.id
        else:
            submitted_id = field_value
        
        if str(instance_value_id) != str(submitted_id):
            msg = error_message or f"Cannot change {field_name} on existing record"
            raise serializers.ValidationError({field_name: msg})


def validate_college_department_consistency(college, department):
    """
    Phase 3: Validate that Department belongs to the specified College.
    
    Prevents:
        POST /members/ with college=A and department from college=B
    
    Returns: (college, department) if valid
    Raises: ValidationError if inconsistent
    """
    if not college or not department:
        return college, department
    
    if department.college_id != college.id:
        raise serializers.ValidationError({
            'department': f"Department '{department.name}' does not belong to college '{college.name}'"
        })
    
    return college, department


def validate_schedule_belongs_to_event(schedule, expected_event_id=None):
    """
    Phase 3: Validate that EventSchedule belongs to the expected Event.
    
    Prevents:
        POST /registrations/ with schedule from different event
    """
    if not schedule:
        return schedule
    
    if expected_event_id and schedule.event_id != expected_event_id:
        raise serializers.ValidationError(
            "The selected schedule does not belong to this event."
        )
    
    return schedule


class ReadOnlyOwnershipFieldsMixin:
    """
    Phase 3: Makes ownership fields read-only to prevent tampering.
    
    Usage:
        class MySerializer(ReadOnlyOwnershipFieldsMixin, serializers.ModelSerializer):
            ownership_fields = ['user', 'created_by', 'member', 'owner']
            
            class Meta:
                model = MyModel
                fields = '__all__'
    
    The mixin automatically makes listed fields read-only in Meta.
    """
    ownership_fields = []
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Make ownership fields read-only
        for field_name in self.ownership_fields:
            if field_name in self.fields:
                self.fields[field_name].read_only = True


def get_request_user(context):
    """Helper to safely get request user from serializer context."""
    request = context.get('request')
    if request and hasattr(request, 'user'):
        return request.user
    return None
