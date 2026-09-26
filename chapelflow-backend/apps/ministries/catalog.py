"""Default Fellowship and Chapel Unit groups for Chrisland University Chapel."""

from .models import Group, GroupType


STANDARD_CHAPEL_GROUPS = (
    (GroupType.UNIT, "Intercessory"),
    (GroupType.UNIT, "Chapel Protocol"),
    (GroupType.UNIT, "Music"),
    (GroupType.UNIT, "Instrumentalist"),
    (GroupType.UNIT, "Ushering"),
    (GroupType.UNIT, "Sanctuary Keepers"),
    (GroupType.UNIT, "Media & ICT"),
    (GroupType.UNIT, "Social Media"),
    (GroupType.UNIT, "Library"),
    (GroupType.UNIT, "Drama Team"),
    (GroupType.UNIT, "Technical & Sound"),
    (GroupType.UNIT, "Treasurer"),
    (GroupType.FELLOWSHIP, "SEL Fellowship"),
    (GroupType.FELLOWSHIP, "Love Fellowship"),
    (GroupType.FELLOWSHIP, "Truth Fellowship"),
    (GroupType.FELLOWSHIP, "Favour Fellowship"),
    (GroupType.FELLOWSHIP, "Integrity Fellowship"),
    (GroupType.FELLOWSHIP, "Righteousness Fellowship"),
    (GroupType.FELLOWSHIP, "Mercy Fellowship"),
    (GroupType.FELLOWSHIP, "Excellence Fellowship"),
    (GroupType.FELLOWSHIP, "Grace Fellowship"),
    (GroupType.FELLOWSHIP, "Outstanding Fellowship"),
    (GroupType.FELLOWSHIP, "Peace Fellowship"),
)


def ensure_standard_chapel_groups(branch):
    """Create any missing default groups without reactivating disabled groups."""
    created = []
    for group_type, name in STANDARD_CHAPEL_GROUPS:
        group, was_created = Group.objects.get_or_create(
            branch=branch,
            name=name,
            group_type=group_type,
            defaults={"is_active": True},
        )
        if was_created:
            created.append(group)
    return created
