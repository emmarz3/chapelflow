"""
Legacy role migration tool. See docs/legacy_role_migration.md for the
full mapping decisions and why Tier 2 is deliberately left manual.

Usage:
    python scripts/migrate_legacy_roles.py --report-tier-2   # CSV, no writes
    python scripts/migrate_legacy_roles.py --apply-tier-1    # safe, idempotent

Run from the project root with DJANGO_SETTINGS_MODULE set, same as the
other scripts/ entry points.
"""
import argparse
import csv
import os
import sys

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
django.setup()

from django.db import transaction  # noqa: E402

from apps.accounts.models import Role, User  # noqa: E402
from apps.groups.models import GroupMembership, GroupRole  # noqa: E402
from common.constants.roles import Roles  # noqa: E402

TIER_1_MAP = {
    Roles.PASTOR: Roles.CHAPLAIN,
    Roles.UNIT_LEADER: Roles.UNIT_HEAD,
    # VOLUNTEER is intentionally handled separately below: it becomes
    # MEMBER, not a 1:1 role swap, and a VolunteerProfile flag is left
    # in place so nothing about their volunteering is lost.
}

TIER_2_ROLES = [
    Roles.FINANCE_OFFICER,
    Roles.COMMUNITY_LEADER,
    Roles.MINISTRY_LEADER,
    Roles.DEPARTMENT_LEADER,
]


@transaction.atomic
def apply_tier_1(dry_run=False):
    changed = 0
    for old_role, new_role in TIER_1_MAP.items():
        qs = User.objects.filter(role=old_role) | User.objects.filter(role_obj__code=old_role)
        qs = qs.distinct()
        count = qs.count()
        if count and not dry_run:
            new_role_obj = Role.objects.get(code=new_role)
            qs.update(role=new_role, role_obj=new_role_obj)
        print(f"{old_role} -> {new_role}: {count} user(s)")
        changed += count

    volunteers = User.objects.filter(role=Roles.VOLUNTEER)
    v_count = volunteers.count()
    if v_count and not dry_run:
        from apps.volunteers.models import VolunteerProfile
        for user in volunteers:
            user.role = Roles.MEMBER
            user.save(update_fields=["role"])
            member = getattr(user, "member_profile", None)
            if member is not None:
                VolunteerProfile.objects.get_or_create(member=member)
            # else: user has no Member record yet (login-only legacy
            # account) -> role is migrated, VolunteerProfile is skipped
            # and flagged for manual follow-up rather than guessed at.
            else:
                print(f"  NOTE: {user} has no Member profile — VolunteerProfile not created, review manually.")
    print(f"{Roles.VOLUNTEER} -> {Roles.MEMBER} (+VolunteerProfile): {v_count} user(s)")
    changed += v_count

    print(f"\nTier 1 total: {changed} user(s) {'would be ' if dry_run else ''}migrated.")


def report_tier_2(output_path="tier2_migration_report.csv"):
    rows = []
    for user in User.objects.filter(role__in=TIER_2_ROLES).select_related("branch"):
        leader_of = list(
            GroupMembership.objects.filter(member__user=user, role=GroupRole.LEADER)
            .select_related("group")
            .values_list("group__name", flat=True)
        )
        rows.append({
            "user_id": str(user.id),
            "identifier": user.email or user.matric_no,
            "current_role": user.role,
            "branch": user.branch.name if user.branch else "",
            "group_leadership": "; ".join(leader_of),
        })

    with open(output_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["user_id", "identifier", "current_role", "branch", "group_leadership"])
        writer.writeheader()
        writer.writerows(rows)

    print(f"Wrote {len(rows)} row(s) needing manual review to {output_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply-tier-1", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--report-tier-2", action="store_true")
    args = parser.parse_args()

    if args.apply_tier_1:
        apply_tier_1(dry_run=args.dry_run)
    elif args.report_tier_2:
        report_tier_2()
    else:
        parser.print_help()
