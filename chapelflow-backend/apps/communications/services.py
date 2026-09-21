"""
Phase 10: audience authorization + resolution, kept separate from
tasks.py/views.py so both the serializer (validation, synchronous) and
the Celery dispatch task (fan-out, async) share one source of truth for
"who is this Announcement actually allowed to reach."
"""
from rest_framework.exceptions import ValidationError

from common.constants.roles import Roles
from common.permissions.scoping import led_group_ids, user_can_access_branch

from .models import AudienceType


def authorize_branch(user, branch):
    """A caller may only ever create an Announcement in a branch they can access."""
    if not user_can_access_branch(user, branch.id):
        raise ValidationError({"branch": "You do not have access to this branch."})


def authorize_audience(user, branch, audience_type, target_groups, target_community):
    """
    Spec section 13: "A Fellowship Leader must not be able to turn a
    Fellowship campaign into a university-wide campaign by changing a
    request parameter." Enforced here, not just at the queryset level,
    because creation itself is the attack surface -- an assignment-scoped
    leader is restricted to CUSTOM/FELLOWSHIP/UNIT/MINISTRY audience types
    targeting *only* Group(s) they actively lead (GroupMembership(role=
    LEADER), never Group.leader). EVERYONE and STAFF_COMMUNITY are
    branch-wide/segment-wide reaches and are never available to them.
    """
    if user.role in Roles.ASSIGNMENT_SCOPED_ROLES:
        if audience_type in (AudienceType.EVERYONE, AudienceType.STAFF_COMMUNITY):
            raise ValidationError(
                {"audience_type": "Your role can only target the Group(s) you lead, not a branch-wide audience."}
            )
        if not target_groups:
            raise ValidationError({"target_groups": "You must target at least one Group you lead."})
        allowed_ids = set(led_group_ids(user))
        for group in target_groups:
            if group.id not in allowed_ids:
                raise ValidationError(
                    {"target_groups": f"You do not lead '{group.name}' and cannot target it."}
                )
        return

    # Non-assignment-scoped roles (Chapel Admin, Chaplain, Pastor, ...)
    # still can't cross branches even if they know another branch's
    # Group id.
    for group in target_groups:
        if group.branch_id != branch.id:
            raise ValidationError(
                {"target_groups": f"'{group.name}' belongs to a different branch."}
            )
    if audience_type == AudienceType.STAFF_COMMUNITY and not target_community:
        raise ValidationError({"target_community": "Required when audience_type is STAFF_COMMUNITY."})


def resolve_audience_members(announcement):
    """Applies audience_type + target_groups + target_membership_statuses + target_community."""
    from apps.members.models import Member

    members = Member.objects.filter(branch=announcement.branch)

    if announcement.audience_type == AudienceType.STAFF_COMMUNITY:
        members = members.filter(community=announcement.target_community or "STAFF")
    elif announcement.target_groups.exists():
        members = members.filter(group_memberships__group__in=announcement.target_groups.all()).distinct()
    # EVERYONE / CUSTOM-with-no-groups -> whole branch, no further filter.

    if announcement.target_membership_statuses:
        members = members.filter(membership_status__in=announcement.target_membership_statuses)

    return members


def filter_by_preference(members, channel):
    """
    Excludes members who opted out of this Announcement's channel, or out
    of announcements entirely. A member with no CommunicationPreference
    row (the common case -- most members never touch this) is treated as
    fully opted in, matching the model's default=True opt-out design.
    """
    from .models import CommunicationPreference

    opted_out_ids = set(
        CommunicationPreference.objects.filter(announcements_enabled=False).values_list("member_id", flat=True)
    )
    field = {"EMAIL": "email_enabled", "SMS": "sms_enabled", "PUSH": "push_enabled"}.get(channel)
    if field:
        opted_out_ids |= set(
            CommunicationPreference.objects.filter(**{field: False}).values_list("member_id", flat=True)
        )
    if not opted_out_ids:
        return members
    return members.exclude(id__in=opted_out_ids)
