import uuid

from django.db import models


class GroupType(models.TextChoices):
    """
    Chapel-side structure only (Fellowship/Unit/Ministry — spec section 7).
    DEPARTMENT is kept ONLY so any existing rows stay valid; it must never
    be used again — academic Department now lives in apps.university.
    Department, which is a separate hierarchy (University -> College ->
    Department), not a Chapel Group. See docs/university_structure.md.
    """
    MINISTRY = "MINISTRY", "Ministry"
    FELLOWSHIP = "FELLOWSHIP", "Fellowship"
    UNIT = "UNIT", "Unit"
    SMALL_GROUP = "SMALL_GROUP", "Small Group"
    COMMUNITY = "COMMUNITY", "Community (legacy)"
    DEPARTMENT = "DEPARTMENT", "Department (legacy — do not use, see apps.university)"


class Group(models.Model):
    """
    Unified model for ministries, fellowships, departments, units, and
    small groups. A single table (distinguished by `group_type`) avoids
    duplicating near-identical structures and duplicate M2M membership
    tables for what is fundamentally the same relationship shape.

    DEPRECATION NOTE (Phase 0 remediation): the `leader` field below is
    deprecated. Leadership is now sourced from `groups.GroupMembership`
    (`role=LEADER`, `is_active=True`), which supports multiple leaders per
    Group — something a single FK never could. See that field's own
    help_text, `common/permissions/scoping.py::led_group_ids()`, and
    `docs/university_structure.md` for the full picture and removal plan.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    branch = models.ForeignKey("organizations.Branch", on_delete=models.PROTECT, related_name="groups")
    parent = models.ForeignKey("self", null=True, blank=True, on_delete=models.SET_NULL, related_name="children")
    name = models.CharField(max_length=255)
    group_type = models.CharField(max_length=20, choices=GroupType.choices)
    description = models.TextField(blank=True)
    leader = models.ForeignKey(
        "members.Member", null=True, blank=True, on_delete=models.SET_NULL, related_name="led_groups",
        help_text="DEPRECATED (Phase 0 remediation): kept only for backward "
                  "compatibility with existing data/reports. Do not read this "
                  "for scoping or new leadership listings — a Group can have "
                  "multiple leaders, and this single FK cannot represent that. "
                  "Use active groups.GroupMembership rows with role=LEADER "
                  "instead (see common.permissions.scoping.led_group_ids and "
                  "docs/university_structure.md). The column is intentionally "
                  "NOT dropped yet — see that doc for the removal plan.",
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "ministries_group"
        indexes = [models.Index(fields=["branch", "group_type"])]
        # Phase 5: Prevent duplicate group names within same branch and type
        # (e.g., two "Fellowship Alpha" groups in same branch would be confusing)
        constraints = [
            models.UniqueConstraint(
                fields=["branch", "name", "group_type"],
                name="unique_group_name_per_branch_type"
            )
        ]

    def __str__(self):
        return f"{self.name} ({self.group_type})"
