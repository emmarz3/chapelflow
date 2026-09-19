class Roles:
    """
    ChapelFlow CUC University Edition role model (Phase 0 alignment).

    LEGACY ROLES (see LEGACY_ROLES below) are kept as valid choices so
    existing User rows are never silently broken, but they are no longer
    assignable to new users (see scripts/migrate_legacy_roles.py) and are
    excluded from CHOICES shown in new-user-facing UIs going forward.
    Do not delete legacy values from CHOICES until the data migration in
    scripts/migrate_legacy_roles.py has been run and verified in every
    environment — removing them earlier would break FK/choice validation
    on any row still carrying the old value.
    """

    # --- Current University Edition roles (spec section 1) -------------
    SUPER_ADMIN = "SUPER_ADMIN"
    CHAPLAIN = "CHAPLAIN"
    STUDENT_CHAPLAIN = "STUDENT_CHAPLAIN"
    CHAPEL_ADMIN = "CHAPEL_ADMIN"
    ATTENDANCE_USHER = "ATTENDANCE_USHER"
    FELLOWSHIP_LEADER = "FELLOWSHIP_LEADER"
    UNIT_HEAD = "UNIT_HEAD"
    MINISTRY_GROUP_LEADER = "MINISTRY_GROUP_LEADER"
    MEMBER = "MEMBER"
    VISITOR = "VISITOR"

    CURRENT_CHOICES = [
        (SUPER_ADMIN, "Super Admin"),
        (CHAPLAIN, "Chaplain"),
        (STUDENT_CHAPLAIN, "Student Chaplain"),
        (CHAPEL_ADMIN, "Chapel Admin"),
        (ATTENDANCE_USHER, "Attendance Usher"),
        (FELLOWSHIP_LEADER, "Fellowship Leader"),
        (UNIT_HEAD, "Unit Head"),
        (MINISTRY_GROUP_LEADER, "Ministry/Group Leader"),
        (MEMBER, "Member"),
        (VISITOR, "Visitor"),
    ]

    # --- Legacy (pre-University-Edition) roles --------------------------
    # Kept ONLY so historic rows remain valid choices. New rows must never
    # be created with these. See docs/legacy_role_migration.md for the
    # mapping decisions and which ones are intentionally left ambiguous
    # (COMMUNITY_LEADER, MINISTRY_LEADER, DEPARTMENT_LEADER — see that doc).
    PASTOR = "PASTOR"
    FINANCE_OFFICER = "FINANCE_OFFICER"
    COMMUNITY_LEADER = "COMMUNITY_LEADER"
    MINISTRY_LEADER = "MINISTRY_LEADER"
    DEPARTMENT_LEADER = "DEPARTMENT_LEADER"
    UNIT_LEADER = "UNIT_LEADER"
    VOLUNTEER = "VOLUNTEER"

    LEGACY_CHOICES = [
        (PASTOR, "Pastor (legacy)"),
        (FINANCE_OFFICER, "Finance Officer (legacy)"),
        (COMMUNITY_LEADER, "Community Leader (legacy)"),
        (MINISTRY_LEADER, "Ministry Leader (legacy)"),
        (DEPARTMENT_LEADER, "Department Leader (legacy)"),
        (UNIT_LEADER, "Unit Leader (legacy)"),
        (VOLUNTEER, "Volunteer (legacy)"),
    ]

    LEGACY_ROLES = {r for r, _ in LEGACY_CHOICES}

    # Full choice list — used only for model field `choices=`, so existing
    # rows validate. Forms/serializers that assign a NEW role should use
    # CURRENT_CHOICES instead.
    CHOICES = CURRENT_CHOICES + LEGACY_CHOICES

    # Roles that operate across every branch/campus in the organization.
    GLOBAL_SCOPE_ROLES = {SUPER_ADMIN}

    # Org/university-wide (but not global-technical) scope — spec section 6.
    ORG_WIDE_SCOPE_ROLES = {CHAPLAIN}

    # Roles scoped to administering a single branch/chapel (as opposed to
    # GLOBAL_SCOPE_ROLES' org-wide reach or ORG_WIDE_SCOPE_ROLES' cross-branch
    # visibility). Referenced by apps/members/{signals,serializers,views}.py
    # for follow-up assignment eligibility and engagement-metrics scoping.
    BRANCH_SCOPE_ROLES = {CHAPEL_ADMIN}

    # Roles considered "privileged" -> MFA enforced, elevated audit detail.
    # NOTE: Chaplain is privileged (broad visibility) but must NEVER be
    # treated as SUPER_ADMIN — see spec section 9. Legacy PASTOR/
    # FINANCE_OFFICER are kept here only so already-existing accounts of
    # those roles keep their current MFA/audit posture until migrated.
    PRIVILEGED_ROLES = {
        SUPER_ADMIN, CHAPEL_ADMIN, CHAPLAIN, STUDENT_CHAPLAIN, PASTOR, FINANCE_OFFICER,
    }

    # Roles allowed to view pastoral care records (in addition to record
    # owner and explicitly assigned pastoral staff). Chaplain's access here
    # is a permission grant, not a superuser flag (spec section 9/15).
    PASTORAL_ACCESS_ROLES = {SUPER_ADMIN, CHAPEL_ADMIN, CHAPLAIN, STUDENT_CHAPLAIN, PASTOR}

    FINANCE_ACCESS_ROLES = {SUPER_ADMIN, CHAPEL_ADMIN, FINANCE_OFFICER}

    # Roles that lead a specific Fellowship/Unit/Ministry-Group and are
    # therefore scoped to their assignment(s) rather than branch-wide.
    ASSIGNMENT_SCOPED_ROLES = {FELLOWSHIP_LEADER, UNIT_HEAD, MINISTRY_GROUP_LEADER}


class PermissionCodes:
    """
    Phase 3: Enhanced fine-grained action permissions. Stored/checked via
    the Permission and RolePermission models (see apps.accounts.models) so
    they can be reconfigured without a code deploy.
    """
    # Members
    MEMBERS_VIEW = "members.view"
    MEMBERS_CREATE = "members.create"
    MEMBERS_UPDATE = "members.update"
    MEMBERS_DELETE = "members.delete"
    MEMBERS_IMPORT = "members.import"
    MEMBERS_TRANSFER = "members.transfer"
    MEMBERS_MERGE = "members.merge"
    MEMBERS_DEACTIVATE = "members.deactivate"

    # Attendance
    ATTENDANCE_VIEW = "attendance.view"
    ATTENDANCE_CREATE = "attendance.create"
    ATTENDANCE_EXPORT = "attendance.export"
    ATTENDANCE_MANAGE_DEVICES = "attendance.manage_devices"

    # Events
    EVENTS_VIEW = "events.view"
    EVENTS_CREATE = "events.create"
    EVENTS_UPDATE = "events.update"
    EVENTS_DELETE = "events.delete"
    EVENTS_PUBLISH = "events.publish"
    EVENTS_CANCEL = "events.cancel"

    # Groups
    GROUPS_VIEW = "groups.view"
    GROUPS_CREATE = "groups.create"
    GROUPS_UPDATE = "groups.update"
    GROUPS_DELETE = "groups.delete"
    GROUPS_MANAGE_MEMBERS = "groups.manage_members"

    # Volunteers
    VOLUNTEERS_VIEW = "volunteers.view"
    VOLUNTEERS_CREATE = "volunteers.create"
    VOLUNTEERS_UPDATE = "volunteers.update"
    VOLUNTEERS_DELETE = "volunteers.delete"
    VOLUNTEERS_ASSIGN = "volunteers.assign"

    # Visitors
    VISITORS_VIEW = "visitors.view"
    VISITORS_CREATE = "visitors.create"
    VISITORS_UPDATE = "visitors.update"
    VISITORS_DELETE = "visitors.delete"
    VISITORS_CONVERT = "visitors.convert"
    VISITORS_FOLLOW_UP = "visitors.follow_up"

    # Communications
    COMMUNICATIONS_VIEW = "communications.view"
    COMMUNICATIONS_CREATE = "communications.create"
    COMMUNICATIONS_UPDATE = "communications.update"
    COMMUNICATIONS_DELETE = "communications.delete"
    COMMUNICATIONS_SEND = "communications.send"

    # Finance
    FINANCE_VIEW = "finance.view"
    FINANCE_CREATE = "finance.create"
    FINANCE_UPDATE = "finance.update"
    FINANCE_DELETE = "finance.delete"
    FINANCE_EXPORT = "finance.export"

    # Pastoral
    PASTORAL_VIEW = "pastoral.view"
    PASTORAL_CREATE = "pastoral.create"
    PASTORAL_UPDATE = "pastoral.update"
    PASTORAL_DELETE = "pastoral.delete"

    # Prayer
    PRAYER_VIEW = "prayer.view"
    PRAYER_CREATE = "prayer.create"
    PRAYER_UPDATE = "prayer.update"
    PRAYER_DELETE = "prayer.delete"

    # Households
    HOUSEHOLDS_VIEW = "households.view"
    HOUSEHOLDS_CREATE = "households.create"
    HOUSEHOLDS_UPDATE = "households.update"
    HOUSEHOLDS_DELETE = "households.delete"

    # Reports
    REPORTS_VIEW = "reports.view"
    REPORTS_CREATE = "reports.create"
    REPORTS_EXPORT = "reports.export"

    # Audit
    AUDIT_VIEW = "audit.view"

    # Roles & Permissions (Phase 3)
    ROLE_MANAGE = "roles.manage"
    ROLES_VIEW = "roles.view"
    ROLES_CREATE = "roles.create"
    ROLES_UPDATE = "roles.update"
    ROLES_DELETE = "roles.delete"
    ROLES_ASSIGN = "roles.assign"
    PERMISSIONS_VIEW = "permissions.view"
    PERMISSIONS_MANAGE = "permissions.manage"

    # System
    SYSTEM_CONFIG = "system.config"
    SYSTEM_ADMIN = "system.admin"
