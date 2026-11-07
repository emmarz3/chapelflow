"""
Phase 9: Custom permissions for volunteer management.

Supports self-service scenarios where volunteers can manage their own data
while still respecting staff permissions for broader management.

Permission Hierarchy:
1. Staff with VOLUNTEERS_* permissions can manage any volunteer in scope
2. Volunteers can manage their own profile/availability/assignments
3. Users without permissions are denied
"""
from rest_framework import permissions


class IsVolunteerOwnerOrStaff(permissions.BasePermission):
    """
    Allow access if:
    - User has staff permissions (via RBAC, checked separately)
    - OR user is the volunteer (for self-service operations)
    
    Usage:
    - Can be combined with HasRolePermission to allow staff OR owner access
    - Views should check this after RBAC for owner-specific operations
    
    Note: This permission relies on the view having already run queryset
    scoping, so we know the object is at least in the user's branch scope.
    """
    
    def has_object_permission(self, request, view, obj):
        """
        Check if user owns the volunteer-related object.
        
        Object types supported:
        - VolunteerProfile: check if obj.member.user == request.user
        - VolunteerAssignment: check if obj.volunteer.member.user == request.user
        - VolunteerAvailability: check if obj.volunteer.member.user == request.user
        """
        # If no user, deny
        if not request.user or not request.user.is_authenticated:
            return False
        
        # Determine the user associated with this volunteer object
        volunteer_user = None
        
        if hasattr(obj, 'member'):
            # VolunteerProfile
            volunteer_user = obj.member.user if obj.member else None
        elif hasattr(obj, 'volunteer'):
            # VolunteerAssignment or VolunteerAvailability
            volunteer_user = obj.volunteer.member.user if obj.volunteer and obj.volunteer.member else None
        
        # Allow if user owns this volunteer data
        if volunteer_user and volunteer_user == request.user:
            return True
        
        # Staff permissions are handled by HasRolePermission separately
        # If we get here, user is not the owner
        return False


class CanManageOwnAvailability(permissions.BasePermission):
    """
    Allow volunteers to manage their own availability windows.
    
    This is a more restrictive version of IsVolunteerOwnerOrStaff specifically
    for availability management, where we want to encourage self-service.
    
    Usage in view:
    ```python
    permission_classes = [HasRolePermission | CanManageOwnAvailability]
    ```
    
    This allows either:
    - Staff with VOLUNTEERS_* permissions, OR
    - The volunteer managing their own availability
    """
    
    def has_permission(self, request, view):
        """Allow authenticated users to attempt availability operations."""
        return request.user and request.user.is_authenticated
    
    def has_object_permission(self, request, view, obj):
        """
        Check if user owns this availability window.
        
        For VolunteerAvailability objects only.
        """
        if not request.user or not request.user.is_authenticated:
            return False
        
        # Check if this is the volunteer's own availability
        if hasattr(obj, 'volunteer'):
            volunteer_user = obj.volunteer.member.user if obj.volunteer and obj.volunteer.member else None
            return volunteer_user == request.user
        
        return False


class CanViewOwnAssignments(permissions.BasePermission):
    """
    Allow volunteers to view their own assignments.
    
    Read-only permission for volunteers to see what they're assigned to.
    Volunteers cannot modify assignments (must go through staff or
    confirm/decline actions).
    
    Usage in view:
    ```python
    permission_classes = [HasRolePermission | CanViewOwnAssignments]
    ```
    """
    
    def has_permission(self, request, view):
        """Allow authenticated users to attempt viewing assignments."""
        # Only allow read operations
        if request.method not in permissions.SAFE_METHODS:
            return False
        
        return request.user and request.user.is_authenticated
    
    def has_object_permission(self, request, view, obj):
        """
        Check if user is viewing their own assignment.
        
        For VolunteerAssignment objects only.
        """
        if not request.user or not request.user.is_authenticated:
            return False
        
        # Only allow read operations
        if request.method not in permissions.SAFE_METHODS:
            return False
        
        # Check if this is the volunteer's own assignment
        if hasattr(obj, 'volunteer'):
            volunteer_user = obj.volunteer.member.user if obj.volunteer and obj.volunteer.member else None
            return volunteer_user == request.user
        
        return False


class CanRespondToOwnAssignment(permissions.BasePermission):
    """
    Allow volunteers to confirm/decline their own assignments.
    
    This supports the self-service workflow where volunteers respond to
    assignments without requiring staff intervention.
    
    Usage in view actions:
    ```python
    @action(detail=True, methods=["post"])
    def confirm(self, request, pk=None):
        self.permission_classes = [HasRolePermission | CanRespondToOwnAssignment]
        self.check_permissions(request)
        ...
    ```
    
    Security:
    - Volunteers can only confirm/decline, not complete (staff-only)
    - Cannot modify hours_logged or other sensitive fields
    - Cannot bypass conflict detection
    """
    
    def has_permission(self, request, view):
        """Allow authenticated users to attempt responding to assignments."""
        return request.user and request.user.is_authenticated
    
    def has_object_permission(self, request, view, obj):
        """
        Check if user is responding to their own assignment.
        
        For VolunteerAssignment objects only.
        Checks that the action is confirm or decline (not complete).
        """
        if not request.user or not request.user.is_authenticated:
            return False
        
        # Check if this is the volunteer's own assignment
        if hasattr(obj, 'volunteer'):
            volunteer_user = obj.volunteer.member.user if obj.volunteer and obj.volunteer.member else None
            if volunteer_user != request.user:
                return False
            
            # Allow confirm/decline actions only (complete is staff-only)
            # This is checked by view action name if available
            if hasattr(view, 'action'):
                return view.action in ['confirm', 'decline']
            
            return True
        
        return False


class ReadOnly(permissions.BasePermission):
    """
    Read-only permission (GET, HEAD, OPTIONS only).
    
    Utility permission for endpoints that should be read-only for certain users.
    """
    
    def has_permission(self, request, view):
        return request.method in permissions.SAFE_METHODS
    
    def has_object_permission(self, request, view, obj):
        return request.method in permissions.SAFE_METHODS
