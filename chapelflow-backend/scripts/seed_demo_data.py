"""
Seeds a realistic demo organization: multiple branches, one demo user for
EVERY role in the SRS (SUPER_ADMIN, CHAPEL_ADMIN, CHAPLAIN, PASTOR,
FINANCE_OFFICER, FELLOWSHIP_LEADER, MINISTRY_LEADER, DEPARTMENT_LEADER,
UNIT_LEADER, VOLUNTEER, MEMBER, VISITOR), actual ministry/fellowship/
department/unit Group records with assigned leaders ("unit heads"), group
memberships, an event, and giving categories. Uses obviously-fake data only.

Usage:
    python scripts/seed_demo_data.py
    (or: python manage.py shell < scripts/seed_demo_data.py)
"""
import os
import sys
from datetime import timedelta

import django

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")
django.setup()

from django.utils import timezone  # noqa: E402

from apps.accounts.models import User  # noqa: E402
from apps.events.models import Event, EventType  # noqa: E402
from apps.finance.models import GivingCategory  # noqa: E402
from apps.groups.models import GroupMembership, GroupRole  # noqa: E402
from apps.members.models import Member, MemberQRCode  # noqa: E402
from apps.ministries.models import Group, GroupType  # noqa: E402
from apps.organizations.models import Branch, Organization  # noqa: E402
from apps.volunteers.models import VolunteerProfile  # noqa: E402
from common.constants.roles import Roles  # noqa: E402

DEMO_PASSWORD = "ChangeMe123!"  # nosec: dev/demo only, never used in production seed data


def get_or_create_user(*, email=None, matric_no=None, role, branch, is_staff=False, is_superuser=False):
    lookup = {"email": email} if email else {"matric_no": matric_no}
    user, created = User.objects.get_or_create(
        **lookup,
        defaults={"role": role, "branch": branch, "is_staff": is_staff, "is_superuser": is_superuser},
    )
    if created:
        user.set_password(DEMO_PASSWORD)
        user.save()
    return user, created


def get_or_create_member(*, user, branch, first_name, last_name, email=""):
    member, _ = Member.objects.get_or_create(
        user=user, branch=branch, defaults={"first_name": first_name, "last_name": last_name, "email": email},
    )
    MemberQRCode.objects.get_or_create(member=member)
    return member


def seed_demo_data():
    org, _ = Organization.objects.get_or_create(name="CUC Demo Network", slug="cuc-demo-network")

    # --------------------------------------------------------------------
    # Branches -- a real deployment is multi-branch; the demo data must
    # reflect that, not just a single chapel.
    # --------------------------------------------------------------------
    branches = {}
    branch_specs = [
        ("main_campus", "Chrisland University Chapel", "CHAPEL", "Ota", "Nigeria"),
        ("postgraduate", "Postgraduate Chapel", "CHAPEL", "Ota", "Nigeria"),
        ("staff_chapel", "Staff & Community Chapel", "CHAPEL", "Ota", "Nigeria"),
        ("city_branch", "City Campus Branch", "BRANCH", "Lagos", "Nigeria"),
    ]
    for key, name, btype, city, country in branch_specs:
        branch, _ = Branch.objects.get_or_create(
            organization=org, name=name, defaults={"branch_type": btype, "city": city, "country": country},
        )
        branches[key] = branch

    main = branches["main_campus"]
    pg = branches["postgraduate"]
    staff = branches["staff_chapel"]
    city = branches["city_branch"]

    # --------------------------------------------------------------------
    # Users -- one per role in the SRS, spread realistically across
    # branches (SUPER_ADMIN is org-wide; everyone else is branch-scoped).
    # --------------------------------------------------------------------
    created_users = {}

    created_users["super_admin"], _ = get_or_create_user(
        email="super.admin@demo.chapelflow.test", role=Roles.SUPER_ADMIN, branch=None,
        is_staff=True, is_superuser=True,
    )

    role_specs = [
        ("chapel_admin_main", "chapel.admin.main@demo.chapelflow.test", Roles.CHAPEL_ADMIN, main),
        ("chapel_admin_pg", "chapel.admin.pg@demo.chapelflow.test", Roles.CHAPEL_ADMIN, pg),
        ("chaplain", "chaplain@demo.chapelflow.test", Roles.CHAPLAIN, main),
        ("pastor", "pastor@demo.chapelflow.test", Roles.PASTOR, main),
        ("finance_officer", "finance@demo.chapelflow.test", Roles.FINANCE_OFFICER, main),
        ("fellowship_leader", "fellowship.leader@demo.chapelflow.test", Roles.FELLOWSHIP_LEADER, main),
        ("community_leader", "community.leader@demo.chapelflow.test", Roles.COMMUNITY_LEADER, main),
        ("ministry_leader", "ministry.leader@demo.chapelflow.test", Roles.MINISTRY_LEADER, main),
        ("department_leader", "department.leader@demo.chapelflow.test", Roles.DEPARTMENT_LEADER, main),
        ("unit_leader", "unit.leader@demo.chapelflow.test", Roles.UNIT_LEADER, main),
        ("volunteer_user", "volunteer@demo.chapelflow.test", Roles.VOLUNTEER, main),
        ("visitor_user", "visitor@demo.chapelflow.test", Roles.VISITOR, main),
    ]
    for key, email, role, branch in role_specs:
        created_users[key], _ = get_or_create_user(email=email, role=role, branch=branch)

    # Matric-number student/member logins (one per relevant branch).
    student_main, _ = get_or_create_user(matric_no="DEMO/2024/001", role=Roles.MEMBER, branch=main)
    student_pg, _ = get_or_create_user(matric_no="PGD/2023/014", role=Roles.MEMBER, branch=pg)
    student_city, _ = get_or_create_user(matric_no="CTY/2025/007", role=Roles.MEMBER, branch=city)
    created_users["student_main"] = student_main
    created_users["student_pg"] = student_pg
    created_users["student_city"] = student_city

    # --------------------------------------------------------------------
    # Member profiles -- link the leadership users to Member records too,
    # since group.leader / GroupMembership point at Member, not User.
    # --------------------------------------------------------------------
    leader_member_specs = [
        ("fellowship_leader", "Tolu", "Adebayo"),
        ("community_leader", "Ngozi", "Chukwu"),
        ("ministry_leader", "Chidinma", "Okafor"),
        ("department_leader", "Emeka", "Nwosu"),
        ("unit_leader", "Blessing", "Eze"),
        ("volunteer_user", "Femi", "Balogun"),
    ]
    leader_members = {}
    for key, first, last in leader_member_specs:
        leader_members[key] = get_or_create_member(
            user=created_users[key], branch=main, first_name=first, last_name=last,
            email=created_users[key].email,
        )

    demo_member_main = get_or_create_member(
        user=student_main, branch=main, first_name="Demo", last_name="Student", email="demo.student@example.test",
    )
    get_or_create_member(user=student_pg, branch=pg, first_name="Demo", last_name="PGStudent")
    get_or_create_member(user=student_city, branch=city, first_name="Demo", last_name="CityStudent")

    # --------------------------------------------------------------------
    # Groups -- ministries, fellowships, communities, departments, and
    # units, each with an assigned leader ("unit head" for UNIT-type
    # groups). Young Adults Fellowship -> Grace Community -> Sound &
    # Technical Unit demonstrates the real Fellowship -> Community -> Unit
    # hierarchy via the self-referencing `parent` field, matching how CU
    # chapel structures actually nest (not just a flat list of groups).
    # --------------------------------------------------------------------
    group_specs = [
        ("Media Ministry", GroupType.MINISTRY, main, "ministry_leader", None),
        ("Choir Ministry", GroupType.MINISTRY, main, None, None),
        ("Young Adults Fellowship", GroupType.FELLOWSHIP, main, "fellowship_leader", None),
        ("Postgraduate Fellowship", GroupType.FELLOWSHIP, pg, None, None),
        ("Grace Community", GroupType.COMMUNITY, main, "community_leader", "Young Adults Fellowship"),
        ("Faith Community", GroupType.COMMUNITY, main, None, "Young Adults Fellowship"),
        ("Ushering Department", GroupType.DEPARTMENT, main, "department_leader", None),
        ("Protocol Department", GroupType.DEPARTMENT, main, None, None),
        ("Sound & Technical Unit", GroupType.UNIT, main, "unit_leader", "Grace Community"),
        ("Prayer Unit", GroupType.UNIT, main, None, "Grace Community"),
    ]
    groups = {}
    for name, gtype, branch, leader_key, parent_name in group_specs:
        leader_member = leader_members.get(leader_key) if leader_key else None
        parent_group = groups.get(parent_name) if parent_name else None
        group, _ = Group.objects.get_or_create(
            branch=branch, name=name,
            defaults={"group_type": gtype, "leader": leader_member, "parent": parent_group},
        )
        # Backfill leader/parent if the group already existed without them.
        update_fields = []
        if leader_member and group.leader_id != leader_member.id:
            group.leader = leader_member
            update_fields.append("leader")
        if parent_group and group.parent_id != parent_group.id:
            group.parent = parent_group
            update_fields.append("parent")
        if update_fields:
            group.save(update_fields=update_fields)
        groups[name] = group

    # Membership: put the leaders in their own groups as LEADER, and the
    # demo student into a couple of groups as an ordinary MEMBER.
    for key, group_name in [
        ("ministry_leader", "Media Ministry"),
        ("fellowship_leader", "Young Adults Fellowship"),
        ("community_leader", "Grace Community"),
        ("department_leader", "Ushering Department"),
        ("unit_leader", "Sound & Technical Unit"),
    ]:
        GroupMembership.objects.get_or_create(
            member=leader_members[key], group=groups[group_name], defaults={"role": GroupRole.LEADER},
        )

    GroupMembership.objects.get_or_create(
        member=demo_member_main, group=groups["Young Adults Fellowship"], defaults={"role": GroupRole.MEMBER},
    )
    GroupMembership.objects.get_or_create(
        member=demo_member_main, group=groups["Grace Community"], defaults={"role": GroupRole.MEMBER},
    )
    GroupMembership.objects.get_or_create(
        member=demo_member_main, group=groups["Prayer Unit"], defaults={"role": GroupRole.MEMBER},
    )

    # --------------------------------------------------------------------
    # Volunteer profile for the volunteer demo user.
    # --------------------------------------------------------------------
    VolunteerProfile.objects.get_or_create(
        member=leader_members["volunteer_user"], defaults={"skills": ["ushering", "media"]},
    )

    # --------------------------------------------------------------------
    # A demo event + giving categories, as before.
    # --------------------------------------------------------------------
    event_type, _ = EventType.objects.get_or_create(name="Sunday Service")
    Event.objects.get_or_create(
        branch=main, title="Sunday Worship Service", event_type=event_type,
        defaults={
            "start_time": timezone.now() + timedelta(days=1),
            "end_time": timezone.now() + timedelta(days=1, hours=2),
            "is_public": True,
        },
    )

    for name in ["Tithe", "Offering", "Building Fund", "Missions"]:
        GivingCategory.objects.get_or_create(name=name)

    # --------------------------------------------------------------------
    # Summary
    # --------------------------------------------------------------------
    print("Demo data seeded.")
    print(f"  Organization: {org.name}")
    print(f"  Branches ({len(branches)}):")
    for b in branches.values():
        print(f"    - {b.name} ({b.branch_type}, {b.city})")
    print(f"  Groups ({len(groups)}):")
    for g in groups.values():
        leader_name = g.leader.full_name if g.leader else "(unassigned)"
        parent_note = f" (under {g.parent.name})" if g.parent_id else ""
        print(f"    - {g.name} [{g.group_type}]{parent_note} @ {g.branch.name} -- leader: {leader_name}")
    print("  Demo login credentials (password for all: 'ChangeMe123!'):")
    for key, user in created_users.items():
        ident = user.email or user.matric_no
        print(f"    {key} ({user.role}): {ident}")


if __name__ == "__main__":
    seed_demo_data()
