"""Server-side access rules for ChapelFlow's public media library."""

from common.constants.roles import Roles


MEDIA_UNIT_NAMES = {
    "media",
    "media unit",
    "media team",
    "media ministry",
    "media & ict",
    "social media",
    "social media unit",
    "social media team",
    "social media ministry",
}


def is_media_unit_leader(user) -> bool:
    """Return whether a unit leader is assigned to an approved media unit."""
    if not getattr(user, "is_authenticated", False):
        return False
    role = user.get_role_code() if hasattr(user, "get_role_code") else user.role
    group = getattr(user, "institutional_group", None)
    return bool(
        role in {
            Roles.UNIT_HEAD,
            Roles.UNIT_LEADER,
            Roles.MINISTRY_GROUP_LEADER,
            Roles.MINISTRY_LEADER,
        }
        and group
        and group.is_active
        and group.group_type in {"UNIT", "MINISTRY"}
        and group.name.strip().casefold() in MEDIA_UNIT_NAMES
    )


def user_has_media_management_access(user) -> bool:
    """Allow only the chapel pastoral roles and assigned media-group leaders."""
    if not getattr(user, "is_authenticated", False):
        return False
    role = user.get_role_code() if hasattr(user, "get_role_code") else user.role
    return role in {
        Roles.SUPER_ADMIN,
        Roles.CHAPLAIN,
        Roles.STUDENT_CHAPLAIN,
    } or is_media_unit_leader(user)
