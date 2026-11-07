"""
Branch/organization data isolation.

Every list/detail endpoint touching organization-sensitive data MUST mix
in BranchScopedQuerysetMixin (or replicate its logic) so that:

  - SUPER_ADMIN sees everything,
  - everyone else only ever sees rows within their assigned branch(es),
  - a user cannot bypass this by editing an ID in the URL, because the
    object is filtered OUT of the queryset entirely (404, not 403,
    which additionally avoids leaking existence of other branches' data).
"""
from django.core.exceptions import FieldDoesNotExist

from common.constants.roles import Roles

# Phase 3: Maps an assignment-scoped role to the Group.group_type it's
# allowed to lead. This is now also stored in Role.assignment_group_types
# for dynamic roles, but kept here for legacy role compatibility.
ROLE_TO_GROUP_TYPE = {
    Roles.FELLOWSHIP_LEADER: "FELLOWSHIP",
    Roles.UNIT_HEAD: "UNIT",
    Roles.MINISTRY_GROUP_LEADER: "MINISTRY",
}


def get_role_code(user) -> str:
    """Phase 3: Safely get role code from either new or legacy system."""
    if hasattr(user, 'get_role_code'):
        return user.get_role_code()
    return getattr(user, 'role', Roles.MEMBER)


def get_assignment_group_types(user) -> list:
    """
    Phase 3: Get group types this user can lead.
    
    Tries Role.assignment_group_types first (dynamic roles),
    falls back to ROLE_TO_GROUP_TYPE mapping (legacy roles).
    """
    # Try new Role model first
    if hasattr(user, 'get_role_obj'):
        role_obj = user.get_role_obj()
        if role_obj and role_obj.assignment_group_types:
            return role_obj.assignment_group_types
    
    # Fall back to legacy mapping
    role_code = get_role_code(user)
    group_type = ROLE_TO_GROUP_TYPE.get(role_code)
    return [group_type] if group_type else []


def led_group_ids(user):
    """
    Group IDs where `user` is an active LEADER, per apps.groups.GroupMembership
    — NOT apps.ministries.Group.leader. Group.leader is a single FK kept
    only for backward compatibility; GroupMembership is the source of
    truth and is what makes multiple leaders per Fellowship/Unit/Ministry
    possible without any scoping code changing (spec section 7).

    Phase 3: Now uses Role.assignment_group_types for dynamic configuration.
    
    Restricted to the Group type matching the user's specific leadership
    role (spec section 6) — a FELLOWSHIP_LEADER never sees Units or
    Ministries just because they also happen to lead a Fellowship.
    Returns an empty list for any role that isn't assignment-scoped, or
    for an assignment-scoped user with no Member profile yet.
    """
    from apps.groups.models import GroupMembership, GroupRole

    group_types = get_assignment_group_types(user)
    if not group_types:
        return []

    # Institutional leaders are provisioned as staff accounts and may not
    # have a Member profile. Their explicit, validated assignment is still
    # a legitimate scope source and never grants access outside the role's
    # permitted group type.
    assigned_group_id = getattr(user, "institutional_group_id", None)
    if assigned_group_id:
        from apps.ministries.models import Group
        if Group.objects.filter(id=assigned_group_id, is_active=True, group_type__in=group_types).exists():
            return [assigned_group_id]
    
    member = getattr(user, "member_profile", None)
    if member is None:
        return []
    
    return list(
        GroupMembership.objects.filter(
            member=member, 
            role=GroupRole.LEADER, 
            is_active=True, 
            group__group_type__in=group_types,
        ).values_list("group_id", flat=True)
    )


class BranchScopedQuerysetMixin:
    """
    Mix into any ModelViewSet/generic view whose model has a `branch`
    field (directly, or reachable via `branch_field_lookup`, e.g.
    "member__branch" for a related model).

    IMPORTANT: subclasses must override `get_base_queryset()`, NOT
    `get_queryset()`. If a subclass overrides `get_queryset()` directly,
    Python's method resolution means the subclass's version wins outright
    and this mixin's filtering is silently never applied — a real branch
    isolation bug this project has already hit once. Overriding
    `get_base_queryset()` instead makes that mistake structurally
    impossible: `get_queryset()` is defined ONLY here, always applies the
    branch filter, and always calls `get_base_queryset()` for the
    unfiltered starting point (select_related/prefetch_related etc. go
    there).
    """

    # The FK path to the branch, e.g. "branch" (direct) or "member__branch"
    # / "session__branch" (traversed). Special case: set to "id" when the
    # model IS organizations.Branch itself (there's no "branch" field to
    # traverse — the row's own primary key is the branch) — see the
    # is_self_lookup handling below, mirroring the existing "id" special
    # case _apply_leader_scope already uses for group_field_lookup.
    branch_field_lookup = "branch"

    # Set on a subclass to enable Fellowship/Unit/Ministry leader scoping
    # (spec section 6/7) on top of branch scoping. Use "id" if the model
    # IS ministries.Group itself, or the FK field name (e.g. "group") if
    # the model points AT a Group. Left None (default) means assignment-
    # scoped roles fall through to ordinary branch scoping for that
    # ViewSet — appropriate for models with no meaningful Group axis.
    group_field_lookup = None

    def get_base_queryset(self):
        """Override this in subclasses to supply the unfiltered queryset."""
        return super().get_queryset()

    def _apply_leader_scope(self, qs, user):
        """
        Further restrict `qs` to rows tied to a Group the user actively
        leads, per apps.groups.GroupMembership (spec section 6/7) — a
        no-op unless both the ViewSet declares group_field_lookup AND the
        user's role is one of the assignment-scoped leader roles.
        
        Phase 3: Now uses get_assignment_group_types() for dynamic roles.
        """
        if not self.group_field_lookup:
            return qs
        
        group_types = get_assignment_group_types(user)
        if not group_types:
            return qs
        
        allowed_ids = led_group_ids(user)
        lookup = "id" if self.group_field_lookup == "id" else f"{self.group_field_lookup}_id"
        return qs.filter(**{f"{lookup}__in": allowed_ids})

    def get_queryset(self):
        qs = self.get_base_queryset()
        user = self.request.user

        if not user or not user.is_authenticated:
            return qs.none()

        # Phase 3: Use get_role_code() for compatibility
        role_code = get_role_code(user)
        
        if role_code in Roles.GLOBAL_SCOPE_ROLES:
            return qs

        # Self-lookup: the ViewSet's model IS organizations.Branch, so
        # there's no FK to traverse — the row's own pk is the branch, and
        # "organization" is a direct field rather than reachable via a
        # "branch__" prefix. Every other model goes through the normal
        # (possibly dotted) branch_field_lookup path below.
        is_self_lookup = self.branch_field_lookup == "id"
        if not is_self_lookup:
            try:
                qs.model._meta.get_field(self.branch_field_lookup.split("__")[0])
            except FieldDoesNotExist:
                return qs.none()

        if role_code in Roles.ORG_WIDE_SCOPE_ROLES:
            # Spec section 6/9: Chaplain gets organization/university-wide
            # visibility — every branch under their own Organization — but
            # is NOT global like Super Admin (never sees other orgs) and
            # never bypasses this via any technical/system-config flag.
            user_branch_id = getattr(user, "branch_id", None)
            if not user_branch_id:
                return qs.none()
            org_id = user.branch.organization_id
            org_lookup = "organization_id" if is_self_lookup else f"{self.branch_field_lookup}__organization_id"
            return qs.filter(**{org_lookup: org_id})

        user_branch_id = getattr(user, "branch_id", None)
        if not user_branch_id:
            # A staff/leader account with no assigned branch sees nothing,
            # rather than defaulting to "everything" (fail closed).
            return qs.none()

        lookup = "id" if is_self_lookup else f"{self.branch_field_lookup}_id"
        qs = qs.filter(**{lookup: user_branch_id})
        return self._apply_leader_scope(qs, user)


def get_accessible_branch_ids(user):
    """
    List of Branch ids `user` can see data for -- the list-returning
    counterpart to user_can_access_branch, for views that need to filter
    a queryset with `branch_id__in=...` rather than check a single branch.
    Same three-tier scope: SUPER_ADMIN sees every branch, an org-wide role
    (e.g. CHAPLAIN) sees every branch in their own organization, everyone
    else sees only their own assigned branch (or nothing, if unassigned).
    """
    from apps.organizations.models import Branch

    role_code = get_role_code(user)

    if role_code in Roles.GLOBAL_SCOPE_ROLES:
        return list(Branch.objects.values_list("id", flat=True))

    if role_code in Roles.ORG_WIDE_SCOPE_ROLES:
        user_branch_id = getattr(user, "branch_id", None)
        if not user_branch_id:
            return []
        return list(
            Branch.objects.filter(organization_id=user.branch.organization_id).values_list("id", flat=True)
        )

    user_branch_id = getattr(user, "branch_id", None)
    return [user_branch_id] if user_branch_id else []


def user_can_access_branch(user, branch_id) -> bool:
    """Phase 3: Check if user can access given branch (works with both role systems)."""
    role_code = get_role_code(user)
    
    if role_code in Roles.GLOBAL_SCOPE_ROLES:
        return True
    if role_code in Roles.ORG_WIDE_SCOPE_ROLES:
        user_branch_id = getattr(user, "branch_id", None)
        if not user_branch_id:
            return False
        from apps.organizations.models import Branch

        branch = Branch.objects.filter(id=branch_id).only("organization_id").first()
        if branch is None:
            return False
        return branch.organization_id == user.branch.organization_id
    return getattr(user, "branch_id", None) == branch_id


def user_can_access_group(user, group) -> bool:
    """
    Can `user` administer (e.g. transfer a member into/out of) this
    Fellowship/Unit/Ministry `group`? Branch/org scope always applies
    first (a Chapel Admin in Branch A can never touch Branch B's groups,
    even if they somehow guessed a real Group id). On top of that, an
    assignment-scoped leader (FELLOWSHIP_LEADER/UNIT_HEAD/
    MINISTRY_GROUP_LEADER) is further restricted to Groups they actively
    lead via GroupMembership(role=LEADER) — never Group.leader (see
    docs/university_structure.md) — so a Fellowship Leader of Fellowship
    A cannot transfer members into Fellowship B just by knowing its id.
    
    Phase 3: Now uses get_assignment_group_types() for dynamic roles.
    """
    if not user_can_access_branch(user, group.branch_id):
        return False
    
    group_types = get_assignment_group_types(user)
    if group_types:
        return group.id in led_group_ids(user)
    
    return True
