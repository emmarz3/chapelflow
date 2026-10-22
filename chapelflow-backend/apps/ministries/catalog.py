"""Default Fellowship and Chapel Unit groups for Chrisland University Chapel."""

from .models import Group, GroupType


STANDARD_CHAPEL_GROUPS = (
    (GroupType.UNIT, "Intercessory"),
    (GroupType.UNIT, "Treasurer"),
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
    (GroupType.FELLOWSHIP, "Love Campus Fellowship"),
    (GroupType.FELLOWSHIP, "Truth Campus Fellowship"),
    (GroupType.FELLOWSHIP, "Favour Campus Fellowship"),
    (GroupType.FELLOWSHIP, "Integrity Campus Fellowship"),
    (GroupType.FELLOWSHIP, "Righteousness Campus Fellowship"),
    (GroupType.FELLOWSHIP, "Mercy Campus Fellowship"),
    (GroupType.FELLOWSHIP, "Excellence Campus Fellowship"),
    (GroupType.FELLOWSHIP, "Grace Campus Fellowship"),
    (GroupType.FELLOWSHIP, "Outstanding Campus Fellowship"),
    (GroupType.FELLOWSHIP, "Peace Campus Fellowship"),
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
