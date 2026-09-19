"""Server-side access rules for ChapelFlow's public media library."""

from common.constants.roles import Roles


MEDIA_UNIT_NAMES = {
    "media",
    "media unit",
    "social media",
    "social media unit",
}


def is_media_unit_leader(user) -> bool:
    """Return whether a unit leader is assigned to an approved media unit."""
    if not getattr(user, "is_authenticated", False):
        return False
    role = user.get_role_code() if hasattr(user, "get_role_code") else user.role
    group = getattr(user, "institutional_group", None)
    return bool(
        role in {Roles.UNIT_HEAD, Roles.UNIT_LEADER}
        and group
        and group.is_active
        and group.group_type == "UNIT"
        and group.name.strip().casefold() in MEDIA_UNIT_NAMES
    )


def user_has_media_management_access(user) -> bool:
    """Allow chapel content managers and the Media/Social Media unit leaders."""
    if not getattr(user, "is_authenticated", False):
        return False
    role = user.get_role_code() if hasattr(user, "get_role_code") else user.role
    return role in {Roles.SUPER_ADMIN, Roles.CHAPEL_ADMIN, Roles.CHAPLAIN} or is_media_unit_leader(user)
