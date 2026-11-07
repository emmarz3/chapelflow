"""Server-side access rule for ChapelFlow's restricted inventory register."""

from common.constants.roles import Roles


PROTOCOL_UNIT_NAMES = {
    "chapel protocol",
    "chapel protocol unit",
    "protocol unit",
}


def user_has_inventory_access(user) -> bool:
    """Allow only Chaplain, Student Chaplain, and the Chapel Protocol Unit Head."""
    if not getattr(user, "is_authenticated", False):
        return False
    role = user.get_role_code() if hasattr(user, "get_role_code") else user.role
    if role in {Roles.CHAPLAIN, Roles.STUDENT_CHAPLAIN}:
        return True
    group = getattr(user, "institutional_group", None)
    return bool(
        role in {Roles.UNIT_HEAD, Roles.UNIT_LEADER}
        and group
        and group.group_type == "UNIT"
        and group.name.strip().casefold() in PROTOCOL_UNIT_NAMES
    )
