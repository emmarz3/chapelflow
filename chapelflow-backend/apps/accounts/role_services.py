"""
Phase 3: Role management services.

Handles role assignment, permission granting, and authorization checks
for role management operations. Enforces self-escalation prevention and
scope hierarchy.
"""
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction

from apps.accounts.models import Role, RoleAssignmentHistory, RolePermission, ScopeType
from common.constants.roles import Roles


# Scope hierarchy (higher index = broader scope)
SCOPE_HIERARCHY = [
    ScopeType.SELF,        # Lowest
    ScopeType.ASSIGNMENT,
    ScopeType.BRANCH,
    ScopeType.ORG_WIDE,
    ScopeType.GLOBAL,      # Highest
]


def check_role_grant_permission(granter, role_to_grant: Role) -> tuple[bool, str]:
    """
    Phase 3: Check if granter can assign role_to_grant to another user.
    
    Prevents users from granting roles/permissions they don't possess.
    
    Returns: (can_grant: bool, reason: str)
    """
    # Super Admin can grant anything
    granter_code = granter.get_role_code() if hasattr(granter, 'get_role_code') else granter.role
    if granter_code == Roles.SUPER_ADMIN:
        return True, ""
    
    granter_role = granter.get_role_obj() if hasattr(granter, 'get_role_obj') else None
    if not granter_role:
        return False, "Granter has no role assigned"
    
    # Cannot grant inactive role
    if not role_to_grant.is_active:
        return False, f"Role '{role_to_grant.name}' is inactive and cannot be assigned"
    
    # Cannot grant a role with broader scope than own
    try:
        granter_scope_level = SCOPE_HIERARCHY.index(granter_role.scope_type)
        target_scope_level = SCOPE_HIERARCHY.index(role_to_grant.scope_type)
    except ValueError:
        return False, "Invalid scope type"
    
    if target_scope_level > granter_scope_level:
        return False, f"Cannot grant role with broader scope ({role_to_grant.scope_type}) than own ({granter_role.scope_type})"
    
    # Cannot grant permissions granter doesn't have
    role_permissions = set(
        role_to_grant.permissions.values_list("permission__code", flat=True)
    )
    granter_permissions = set(
        granter_role.permissions.values_list("permission__code", flat=True)
    )
    
    missing_perms = role_permissions - granter_permissions
    if missing_perms:
        return False, f"Cannot grant role with permissions you don't possess: {', '.join(list(missing_perms)[:3])}"
    
    return True, ""


@transaction.atomic
def assign_role_to_user(user, new_role: Role, changed_by, reason: str = ""):
    """
    Phase 3: Assign a role to a user with audit trail.
    
    Args:
        user: User to assign role to
        new_role: Role object to assign
        changed_by: User making the change
        reason: Reason for role change
    
    Raises:
        PermissionDenied: If changed_by cannot grant this role
        ValidationError: If user is changing their own role
    """
    # Prevent self-modification
    if user.id == changed_by.id:
        raise ValidationError("You cannot change your own role. Contact an administrator.")
    
    # Check if granter has permission
    can_grant, error_msg = check_role_grant_permission(changed_by, new_role)
    if not can_grant:
        raise PermissionDenied(error_msg)
    
    # Get previous role for audit
    previous_role = user.role_obj
    previous_code = user.get_role_code() if hasattr(user, 'get_role_code') else user.role
    
    # Assign new role
    user.role_obj = new_role
    user.role = None  # Clear legacy field when setting role_obj
    user.save(update_fields=["role_obj", "role"])
    
    # Create audit record
    RoleAssignmentHistory.objects.create(
        user=user,
        previous_role=previous_role,
        previous_role_code=previous_code,
        new_role=new_role,
        new_role_code=new_role.code,
        reason=reason,
        changed_by=changed_by,
    )
    
    # Invalidate role cache
    from django.core.cache import cache
    cache.delete(f"user_role:{user.id}")
    cache.delete(f"legacy_role_obj:{previous_code}")


@transaction.atomic
def grant_permission_to_role(role: Role, permission_code: str, granted_by):
    """
    Phase 3: Grant a permission to a role.
    
    Args:
        role: Role to grant permission to
        permission_code: Permission code to grant
        granted_by: User granting the permission
    
    Raises:
        PermissionDenied: If granted_by doesn't have this permission
        ValidationError: If permission doesn't exist
    """
    from apps.accounts.models import Permission
    
    # Verify permission exists
    try:
        permission = Permission.objects.get(code=permission_code, is_active=True)
    except Permission.DoesNotExist:
        raise ValidationError(f"Permission '{permission_code}' does not exist or is inactive")
    
    # Super Admin can grant any permission
    granter_code = granted_by.get_role_code() if hasattr(granted_by, 'get_role_code') else granted_by.role
    if granter_code != Roles.SUPER_ADMIN:
        # Check if granter has this permission
        if not granted_by.has_perm_code(permission_code):
            raise PermissionDenied(f"You cannot grant permission '{permission_code}' because you don't possess it")
    
    # Grant permission (get_or_create to avoid duplicates)
    RolePermission.objects.get_or_create(
        role_obj=role,
        permission=permission,
        defaults={"legacy_role_code": None}
    )


@transaction.atomic
def revoke_permission_from_role(role: Role, permission_code: str, revoked_by):
    """
    Phase 3: Revoke a permission from a role.
    
    Args:
        role: Role to revoke permission from
        permission_code: Permission code to revoke
        revoked_by: User revoking the permission
    
    Raises:
        PermissionDenied: If revoked_by cannot manage roles
    """
    from common.constants.roles import PermissionCodes
    
    # Only users with ROLES_UPDATE can revoke permissions
    if not revoked_by.has_perm_code(PermissionCodes.ROLE_MANAGE):
        raise PermissionDenied("You don't have permission to manage role permissions")
    
    # Revoke permission
    RolePermission.objects.filter(
        role_obj=role,
        permission__code=permission_code
    ).delete()


def can_user_manage_roles(user) -> bool:
    """Check if user has permission to manage roles."""
    from common.constants.roles import PermissionCodes
    return user.has_perm_code(PermissionCodes.ROLE_MANAGE)


def can_user_create_role(user) -> bool:
    """Check if user has permission to create custom roles."""
    role_code = user.get_role_code() if hasattr(user, 'get_role_code') else user.role
    # Only Super Admin can create roles for now
    # Can be extended to check specific ROLES_CREATE permission in future
    return role_code == Roles.SUPER_ADMIN


def can_user_delete_role(user, role: Role) -> bool:
    """Check if user can delete given role."""
    # System roles cannot be deleted
    if role.is_system:
        return False
    
    # Must be Super Admin
    role_code = user.get_role_code() if hasattr(user, 'get_role_code') else user.role
    return role_code == Roles.SUPER_ADMIN


def validate_role_data(code: str, name: str, scope_type: str, assignment_group_types: list = None):
    """
    Validate role data before creation/update.
    
    Args:
        code: Role code (must be unique, uppercase, alphanumeric + underscore)
        name: Display name
        scope_type: Must be valid ScopeType
        assignment_group_types: Required if scope_type is ASSIGNMENT
    
    Raises:
        ValidationError: If validation fails
    """
    import re
    
    # Validate code format
    if not code:
        raise ValidationError("Role code is required")
    
    if not re.match(r'^[A-Z][A-Z0-9_]*$', code):
        raise ValidationError("Role code must be uppercase alphanumeric with underscores only")
    
    if len(code) > 32:
        raise ValidationError("Role code must be 32 characters or less")
    
    # Validate name
    if not name or not name.strip():
        raise ValidationError("Role name is required")
    
    # Validate scope type
    if scope_type not in [choice[0] for choice in ScopeType.choices]:
        raise ValidationError(f"Invalid scope type: {scope_type}")
    
    # Validate assignment group types
    if scope_type == ScopeType.ASSIGNMENT:
        if not assignment_group_types:
            raise ValidationError("assignment_group_types is required for ASSIGNMENT scope")
        
        valid_types = ["FELLOWSHIP", "UNIT", "MINISTRY"]
        for group_type in assignment_group_types:
            if group_type not in valid_types:
                raise ValidationError(f"Invalid group type: {group_type}. Must be one of {valid_types}")
    
    # Check for reserved codes (prevent creating roles that conflict with constants)
    reserved_codes = [
        Roles.SUPER_ADMIN, Roles.CHAPLAIN, Roles.CHAPEL_ADMIN,
        Roles.FELLOWSHIP_LEADER, Roles.UNIT_HEAD, Roles.MINISTRY_GROUP_LEADER,
        Roles.MEMBER, Roles.VISITOR
    ]
    
    if code in reserved_codes:
        # Only allow if updating existing system role
        existing = Role.objects.filter(code=code, is_system=True).first()
        if not existing:
            raise ValidationError(f"Role code '{code}' is reserved for system use")
