"""
Server-side authorization primitives.

IMPORTANT: the frontend must never be relied on to hide buttons. Every
view that touches organization-sensitive data MUST combine:

  1. A permission class from this module (role/action check), AND
  2. Branch-scoped queryset filtering (see common.permissions.scoping)

Bypassing either one is a security bug, not a style choice.
"""
from rest_framework.permissions import BasePermission, SAFE_METHODS

from common.constants.roles import Roles


def user_requires_mfa(user) -> bool:
    """
    Phase 3: Check if user's role requires MFA. Uses Role model if available,
    falls back to settings.MFA_ENFORCED_ROLES for legacy roles.
    """
    from django.conf import settings
    
    # Try new role system first
    role_obj = user.get_role_obj() if hasattr(user, 'get_role_obj') else None
    if role_obj and getattr(settings, "MFA_ENFORCE_ROLE_OBJECTS", True):
        return role_obj.requires_mfa
    
    # Fall back to legacy settings
    mfa_roles = getattr(settings, 'MFA_ENFORCED_ROLES', [])
    role_code = user.get_role_code() if hasattr(user, 'get_role_code') else user.role
    return role_code in mfa_roles


def user_has_completed_required_mfa(user) -> bool:
    """
    Spec section 18: any user whose role requires MFA must complete
    MFA enrollment before they can use any RBAC-protected endpoint.
    
    Phase 3: Now uses Role.requires_mfa field for dynamic configuration.
    
    Deliberately checked BEFORE the Super Admin bypass - Super Admin
    is required to have MFA and must not be exempt just because it
    bypasses ordinary permission-code checks.

    The enrollment/confirmation endpoints themselves
    (apps.accounts.views.MFAEnrollView/MFAConfirmView) use plain
    IsAuthenticated, not this check, so a user blocked here can still
    reach them to actually complete setup.
    """
    if not user_requires_mfa(user):
        return True
    return bool(getattr(user, "mfa_enabled", False))


class IsAuthenticatedAndActive(BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.is_active)


class IsSuperAdmin(BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.role == Roles.SUPER_ADMIN)


class IsChapelAdminOrSuperAdmin(BasePermission):
    """
    Used by administrative actions that shouldn't be gated by a
    RolePermission code (e.g. resetting another user's MFA) — deliberately
    role-based rather than permission-code-based, since this is closer to
    an account-security operation than an ordinary CRUD action. Still
    subject to the same MFA-completion requirement as everything else.
    """
    def has_permission(self, request, view):
        user = request.user
        return bool(
            user and user.is_authenticated and user.is_active
            and user.role in {Roles.SUPER_ADMIN, Roles.CHAPEL_ADMIN}
            and user_has_completed_required_mfa(user)
        )


class HasRolePermission(BasePermission):
    """
    Generic permission-code checker. Views declare:

        permission_action_map = {
            "list": PermissionCodes.MEMBERS_VIEW,
            "create": PermissionCodes.MEMBERS_CREATE,
            ...
        }

    Phase 3: Works with both legacy role strings and new Role objects.
    Super admins implicitly pass every check. All other roles are checked
    against the RolePermission table (apps.accounts.models), which is
    seeded by scripts/seed_roles.py and editable by admins at runtime.
    """

    def has_permission(self, request, view):
        user = request.user
        if not (user and user.is_authenticated and user.is_active):
            return False
        if not user_has_completed_required_mfa(user):
            return False
        
        # Phase 3: Use get_role_code() for backward compatibility
        role_code = user.get_role_code() if hasattr(user, 'get_role_code') else getattr(user, 'role', None)
        if role_code == Roles.SUPER_ADMIN:
            return True

        action_map = getattr(view, "permission_action_map", {})
        if hasattr(view, "action") and view.action is not None:
            required_code = action_map.get(view.action)
        else:
            # Plain APIView (no `.action`): key the map by lowercase HTTP method.
            required_code = action_map.get(request.method.lower())

        if required_code is None:
            # No explicit mapping declared for this action -> fail closed.
            return False

        return user.has_perm_code(required_code)


class ReadOnlyOrHasPermission(HasRolePermission):
    """Allows safe (GET/HEAD/OPTIONS) methods for anyone with view access."""

    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            view_code = getattr(view, "view_permission_code", None)
            if view_code and (request.user.role == Roles.SUPER_ADMIN or request.user.has_perm_code(view_code)):
                return True
        return super().has_permission(request, view)


class IsPastoralAuthorized(BasePermission):
    """
    Pastoral records are the most sensitive data in the system. A member
    must NEVER access another member's pastoral case. Access is limited to:
      - the member the case is about,
      - staff in Roles.PASTORAL_ACCESS_ROLES (with MFA),
      - staff explicitly assigned to the case (checked at object level).
    
    Phase 3: MFA is now required for all pastoral access to protect
    highly sensitive counseling records.
    """

    def has_permission(self, request, view):
        user = request.user
        if not (user and user.is_authenticated and user.is_active):
            return False
        
        # Phase 3: Require MFA for pastoral access (most sensitive data)
        if not user_has_completed_required_mfa(user):
            return False
        
        return True

    def has_object_permission(self, request, view, obj):
        user = request.user
        if user.role in Roles.PASTORAL_ACCESS_ROLES:
            return True
        assigned_to = getattr(obj, "assigned_to_id", None)
        if assigned_to and assigned_to == user.id:
            return True
        member = getattr(obj, "member", None)
        if member and getattr(member, "user_id", None) == user.id:
            return True
        return False


class IsFinanceAuthorized(BasePermission):
    def has_permission(self, request, view):
        user = request.user
        return bool(
            user and user.is_authenticated and user.is_active
            and user.role in Roles.FINANCE_ACCESS_ROLES
            and user_has_completed_required_mfa(user)
        )
