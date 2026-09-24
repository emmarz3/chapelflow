"""
Seeds RolePermission grants for every role, matching the permission map
each ViewSet declares in `permission_action_map`. Idempotent — safe to
re-run.

Usage:
    python manage.py shell < scripts/seed_roles.py
    (or import and call seed_roles() from a management command)
"""
import os
import sys

import django

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")
django.setup()

from apps.accounts.models import Permission, Role, RolePermission, ScopeType  # noqa: E402
from common.constants.roles import PermissionCodes, Roles  # noqa: E402

# Role -> permission codes. SUPER_ADMIN is implicitly all-access (see
# User.has_perm_code) and is intentionally not listed here.
ROLE_GRANTS = {
    Roles.CHAPEL_ADMIN: [
        PermissionCodes.MEMBERS_VIEW, PermissionCodes.MEMBERS_CREATE, PermissionCodes.MEMBERS_UPDATE,
        PermissionCodes.MEMBERS_DELETE, PermissionCodes.MEMBERS_IMPORT,
        PermissionCodes.ATTENDANCE_VIEW, PermissionCodes.ATTENDANCE_CREATE, PermissionCodes.ATTENDANCE_EXPORT,
        PermissionCodes.EVENTS_VIEW, PermissionCodes.EVENTS_CREATE, PermissionCodes.EVENTS_UPDATE, PermissionCodes.EVENTS_DELETE,
        PermissionCodes.REPORTS_VIEW, PermissionCodes.REPORTS_EXPORT,
        PermissionCodes.AUDIT_VIEW,
        PermissionCodes.VOLUNTEERS_VIEW, PermissionCodes.VOLUNTEERS_CREATE,
        PermissionCodes.VOLUNTEERS_UPDATE, PermissionCodes.VOLUNTEERS_DELETE, PermissionCodes.VOLUNTEERS_ASSIGN,
        PermissionCodes.COMMUNICATIONS_VIEW, PermissionCodes.COMMUNICATIONS_CREATE,
        PermissionCodes.COMMUNICATIONS_UPDATE, PermissionCodes.COMMUNICATIONS_DELETE, PermissionCodes.COMMUNICATIONS_SEND,
        PermissionCodes.FINANCE_VIEW, PermissionCodes.FINANCE_CREATE, PermissionCodes.FINANCE_UPDATE, PermissionCodes.FINANCE_EXPORT,
        PermissionCodes.PASTORAL_VIEW, PermissionCodes.PASTORAL_CREATE, PermissionCodes.PASTORAL_UPDATE, PermissionCodes.PASTORAL_DELETE,
    ],
    Roles.PASTOR: [
        PermissionCodes.MEMBERS_VIEW,
        PermissionCodes.ATTENDANCE_VIEW,
        PermissionCodes.EVENTS_VIEW, PermissionCodes.EVENTS_CREATE, PermissionCodes.EVENTS_UPDATE,
        PermissionCodes.PASTORAL_VIEW, PermissionCodes.PASTORAL_CREATE, PermissionCodes.PASTORAL_UPDATE,
        PermissionCodes.REPORTS_VIEW,
    ],
    Roles.CHAPLAIN: [
        PermissionCodes.MEMBERS_VIEW,
        PermissionCodes.ATTENDANCE_VIEW,
        PermissionCodes.EVENTS_VIEW,
        PermissionCodes.GROUPS_VIEW, PermissionCodes.GROUPS_MANAGE_MEMBERS,
        PermissionCodes.COMMUNICATIONS_VIEW, PermissionCodes.COMMUNICATIONS_CREATE,
        PermissionCodes.REPORTS_VIEW, PermissionCodes.REPORTS_EXPORT,
        PermissionCodes.PASTORAL_VIEW, PermissionCodes.PASTORAL_CREATE, PermissionCodes.PASTORAL_UPDATE,
    ],
    Roles.STUDENT_CHAPLAIN: [
        PermissionCodes.MEMBERS_VIEW,
        PermissionCodes.ATTENDANCE_VIEW,
        PermissionCodes.EVENTS_VIEW, PermissionCodes.EVENTS_CREATE, PermissionCodes.EVENTS_UPDATE,
        PermissionCodes.GROUPS_VIEW, PermissionCodes.GROUPS_MANAGE_MEMBERS,
        PermissionCodes.COMMUNICATIONS_VIEW, PermissionCodes.COMMUNICATIONS_CREATE,
        PermissionCodes.REPORTS_VIEW, PermissionCodes.REPORTS_EXPORT,
        PermissionCodes.PASTORAL_VIEW, PermissionCodes.PASTORAL_CREATE,
    ],
    Roles.FINANCE_OFFICER: [
        PermissionCodes.FINANCE_VIEW, PermissionCodes.FINANCE_CREATE, PermissionCodes.FINANCE_UPDATE, PermissionCodes.FINANCE_EXPORT,
        PermissionCodes.REPORTS_VIEW, PermissionCodes.REPORTS_EXPORT,
    ],
    Roles.FELLOWSHIP_LEADER: [
        PermissionCodes.MEMBERS_VIEW,
        PermissionCodes.ATTENDANCE_VIEW, PermissionCodes.ATTENDANCE_CREATE,
        PermissionCodes.EVENTS_VIEW, PermissionCodes.EVENTS_CREATE, PermissionCodes.EVENTS_UPDATE,
        PermissionCodes.GROUPS_VIEW, PermissionCodes.GROUPS_MANAGE_MEMBERS,
        PermissionCodes.VOLUNTEERS_VIEW, PermissionCodes.VOLUNTEERS_CREATE, PermissionCodes.VOLUNTEERS_ASSIGN,
        PermissionCodes.COMMUNICATIONS_VIEW, PermissionCodes.COMMUNICATIONS_CREATE,
    ],
    Roles.COMMUNITY_LEADER: [
        PermissionCodes.MEMBERS_VIEW,
        PermissionCodes.ATTENDANCE_VIEW, PermissionCodes.ATTENDANCE_CREATE,
        PermissionCodes.EVENTS_VIEW, PermissionCodes.EVENTS_CREATE,
    ],
    Roles.MINISTRY_LEADER: [
        PermissionCodes.MEMBERS_VIEW,
        PermissionCodes.ATTENDANCE_VIEW, PermissionCodes.ATTENDANCE_CREATE,
        PermissionCodes.EVENTS_VIEW, PermissionCodes.EVENTS_CREATE, PermissionCodes.EVENTS_UPDATE,
    ],
    Roles.DEPARTMENT_LEADER: [
        PermissionCodes.MEMBERS_VIEW,
        PermissionCodes.ATTENDANCE_VIEW, PermissionCodes.ATTENDANCE_CREATE,
        PermissionCodes.EVENTS_VIEW,
    ],
    Roles.UNIT_LEADER: [
        PermissionCodes.MEMBERS_VIEW,
        PermissionCodes.ATTENDANCE_VIEW, PermissionCodes.ATTENDANCE_CREATE,
    ],
    # Current University Edition assignment-scoped leader roles (spec
    # section 1) -- equivalent in spirit to the legacy FELLOWSHIP_LEADER/
    # UNIT_LEADER/MINISTRY_LEADER above, plus volunteer-management grants
    # since these roles administer volunteer assignments within their
    # led Unit/Ministry Group (see test_phase9_volunteers.py).
    Roles.UNIT_HEAD: [
        PermissionCodes.MEMBERS_VIEW,
        PermissionCodes.ATTENDANCE_VIEW, PermissionCodes.ATTENDANCE_CREATE,
        PermissionCodes.EVENTS_VIEW, PermissionCodes.EVENTS_CREATE,
        PermissionCodes.GROUPS_VIEW, PermissionCodes.GROUPS_MANAGE_MEMBERS,
        PermissionCodes.VOLUNTEERS_VIEW, PermissionCodes.VOLUNTEERS_CREATE, PermissionCodes.VOLUNTEERS_ASSIGN,
        PermissionCodes.COMMUNICATIONS_VIEW, PermissionCodes.COMMUNICATIONS_CREATE,
    ],
    Roles.MINISTRY_GROUP_LEADER: [
        PermissionCodes.MEMBERS_VIEW,
        PermissionCodes.ATTENDANCE_VIEW, PermissionCodes.ATTENDANCE_CREATE,
        PermissionCodes.EVENTS_VIEW, PermissionCodes.EVENTS_CREATE, PermissionCodes.EVENTS_UPDATE,
        PermissionCodes.VOLUNTEERS_VIEW, PermissionCodes.VOLUNTEERS_CREATE, PermissionCodes.VOLUNTEERS_ASSIGN,
    ],
    Roles.VOLUNTEER: [
        PermissionCodes.EVENTS_VIEW,
        PermissionCodes.VOLUNTEERS_VIEW,
    ],
    Roles.MEMBER: [
        PermissionCodes.EVENTS_VIEW,
    ],
    Roles.VISITOR: [],
}


def seed_roles():
    total = 0
    for role, codes in ROLE_GRANTS.items():
        role_obj, _ = Role.objects.get_or_create(
            code=role,
            defaults={
                "name": dict(Roles.CHOICES).get(role, role.replace("_", " ").title()),
                "scope_type": ScopeType.GLOBAL if role in Roles.GLOBAL_SCOPE_ROLES else ScopeType.SELF if role == Roles.MEMBER else ScopeType.ASSIGNMENT if role in Roles.ASSIGNMENT_SCOPED_ROLES else ScopeType.BRANCH,
                "is_system": True,
                "requires_mfa": role in Roles.PRIVILEGED_ROLES,
            },
        )
        for code in codes:
            perm, _ = Permission.objects.get_or_create(code=code, defaults={"description": code.replace(".", " ").title()})
            _, created = RolePermission.objects.get_or_create(legacy_role_code=role, permission=perm)
            RolePermission.objects.get_or_create(role_obj=role_obj, permission=perm)
            total += 1 if created else 0
    print(f"Seeded role permissions ({total} new grants; existing grants left untouched).")


if __name__ == "__main__":
    seed_roles()
