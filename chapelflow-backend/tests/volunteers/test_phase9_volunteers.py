import datetime as dt

import pytest
from django.utils import timezone


def _grant(role, *codes):
    from apps.accounts.models import Permission, RolePermission

    for code in codes:
        perm, _ = Permission.objects.get_or_create(code=code)
        RolePermission.objects.get_or_create(legacy_role_code=role, permission=perm)


@pytest.fixture
def unit_head_setup(branch_a):
    """
    A Unit with an active leader (UNIT_HEAD scope via GroupMembership,
    per common/permissions/scoping.py) plus a sibling Unit the leader does
    NOT lead, to prove cross-unit isolation.
    """
    from apps.groups.models import GroupMembership, GroupRole
    from apps.members.models import Member
    from apps.ministries.models import Group, GroupType

    led_unit = Group.objects.create(branch=branch_a, name="Led Unit", group_type=GroupType.UNIT)
    other_unit = Group.objects.create(branch=branch_a, name="Other Unit", group_type=GroupType.UNIT)
    leader_member = Member.objects.create(branch=branch_a, first_name="Uche", last_name="Head")
    GroupMembership.objects.create(member=leader_member, group=led_unit, role=GroupRole.LEADER)
    return {"led_unit": led_unit, "other_unit": other_unit, "leader_member": leader_member}


@pytest.fixture
def unit_head_user(branch_a, make_user, unit_head_setup):
    _grant("UNIT_HEAD", *[])
    from common.constants.roles import PermissionCodes

    _grant("UNIT_HEAD", PermissionCodes.VOLUNTEERS_VIEW, PermissionCodes.VOLUNTEERS_CREATE, PermissionCodes.VOLUNTEERS_UPDATE)
    user = make_user(role="UNIT_HEAD", branch=branch_a, email="unithead@test.com")
    member = unit_head_setup["leader_member"]
    member.user = user
    member.save(update_fields=["user"])
    return user


@pytest.fixture
def volunteer_a(branch_a):
    from apps.members.models import Member
    from apps.volunteers.models import VolunteerProfile

    member = Member.objects.create(branch=branch_a, first_name="Vince", last_name="Server")
    return VolunteerProfile.objects.create(member=member)


@pytest.fixture
def event_schedule_a(branch_a):
    from apps.events.models import Event
    from apps.events.services import generate_event_schedules

    event = Event.objects.create(
        branch=branch_a, title="Sunday Service",
        start_time=timezone.now() + dt.timedelta(days=3),
        end_time=timezone.now() + dt.timedelta(days=3, hours=2),
    )
    return generate_event_schedules(event)[0]


@pytest.mark.django_db
class TestVolunteerAssignmentConflictDetection:
    def test_duplicate_role_at_same_occurrence_rejected(self, volunteer_a, event_schedule_a):
        from apps.volunteers import services

        services.create_assignment(volunteer_a, event_schedule_a, "USHER")
        with pytest.raises(Exception):
            services.create_assignment(volunteer_a, event_schedule_a, "USHER")

    def test_overlapping_assignment_at_different_event_rejected(self, volunteer_a, branch_a):
        from apps.events.models import Event
        from apps.events.services import generate_event_schedules
        from apps.volunteers import services

        start = timezone.now() + dt.timedelta(days=5)
        event1 = Event.objects.create(branch=branch_a, title="E1", start_time=start, end_time=start + dt.timedelta(hours=2))
        event2 = Event.objects.create(
            branch=branch_a, title="E2", start_time=start + dt.timedelta(hours=1), end_time=start + dt.timedelta(hours=3)
        )
        sched1 = generate_event_schedules(event1)[0]
        sched2 = generate_event_schedules(event2)[0]

        services.create_assignment(volunteer_a, sched1, "USHER")
        with pytest.raises(Exception):
            services.create_assignment(volunteer_a, sched2, "CHOIR")

    def test_non_overlapping_assignments_allowed(self, volunteer_a, branch_a):
        from apps.events.models import Event
        from apps.events.services import generate_event_schedules
        from apps.volunteers import services

        start = timezone.now() + dt.timedelta(days=5)
        event1 = Event.objects.create(branch=branch_a, title="E1", start_time=start, end_time=start + dt.timedelta(hours=1))
        event2 = Event.objects.create(
            branch=branch_a, title="E2", start_time=start + dt.timedelta(hours=2), end_time=start + dt.timedelta(hours=3)
        )
        sched1 = generate_event_schedules(event1)[0]
        sched2 = generate_event_schedules(event2)[0]

        a1 = services.create_assignment(volunteer_a, sched1, "USHER")
        a2 = services.create_assignment(volunteer_a, sched2, "USHER")
        assert a1.id != a2.id

    def test_unavailable_window_rejected(self, volunteer_a, event_schedule_a):
        from apps.volunteers import services
        from apps.volunteers.models import VolunteerAvailability

        local_start = timezone.localtime(event_schedule_a.occurrence_start)
        VolunteerAvailability.objects.create(
            volunteer=volunteer_a, weekday=local_start.weekday(),
            start_time=dt.time(0, 0), end_time=dt.time(23, 59), is_available=False,
        )
        with pytest.raises(Exception):
            services.create_assignment(volunteer_a, event_schedule_a, "USHER")

    def test_group_from_other_branch_rejected(self, volunteer_a, branch_b, event_schedule_a):
        from apps.ministries.models import Group, GroupType
        from apps.volunteers import services

        foreign_group = Group.objects.create(branch=branch_b, name="Foreign Unit", group_type=GroupType.UNIT)
        with pytest.raises(Exception):
            services.create_assignment(volunteer_a, event_schedule_a, "USHER", group=foreign_group)


@pytest.mark.django_db
class TestVolunteerAssignmentLifecycle:
    def test_confirm_then_complete_logs_hours(self, volunteer_a, event_schedule_a):
        from apps.volunteers import services
        from apps.volunteers.models import AssignmentStatus

        assignment = services.create_assignment(volunteer_a, event_schedule_a, "USHER")
        services.confirm_assignment(assignment)
        assignment.refresh_from_db()
        assert assignment.status == AssignmentStatus.CONFIRMED
        assert assignment.confirmed is True

        services.complete_assignment(assignment, 3.5)
        assignment.refresh_from_db()
        assert assignment.status == AssignmentStatus.COMPLETED
        assert assignment.hours_logged == 3.5

    def test_cannot_complete_without_confirming_first(self, volunteer_a, event_schedule_a):
        from apps.volunteers import services

        assignment = services.create_assignment(volunteer_a, event_schedule_a, "USHER")
        with pytest.raises(Exception):
            services.complete_assignment(assignment, 2)

    def test_decline_records_reason(self, volunteer_a, event_schedule_a):
        from apps.volunteers import services
        from apps.volunteers.models import AssignmentStatus

        assignment = services.create_assignment(volunteer_a, event_schedule_a, "USHER")
        services.decline_assignment(assignment, reason="scheduling conflict")
        assignment.refresh_from_db()
        assert assignment.status == AssignmentStatus.DECLINED
        assert "scheduling conflict" in assignment.notes


@pytest.mark.django_db
class TestVolunteerScopeIsolation:
    """Spec Phase 9: 'Unit Heads should manage only appropriate Unit volunteers.'"""

    def test_unit_head_sees_only_led_unit_assignments(
        self, api_client, unit_head_user, unit_head_setup, volunteer_a, event_schedule_a
    ):
        from apps.volunteers.models import VolunteerAssignment

        led = VolunteerAssignment.objects.create(
            volunteer=volunteer_a, event_schedule=event_schedule_a, role="USHER", group=unit_head_setup["led_unit"],
        )
        VolunteerAssignment.objects.create(
            volunteer=volunteer_a, role="CHOIR", group=unit_head_setup["other_unit"],
        )

        api_client.force_authenticate(user=unit_head_user)
        response = api_client.get("/api/v1/volunteers/assignments/")
        assert response.status_code == 200
        ids = {row["id"] for row in response.data["data"]}
        assert ids == {str(led.id)}

    def test_unit_head_cannot_fetch_other_units_assignment_by_id(
        self, api_client, unit_head_user, unit_head_setup, volunteer_a
    ):
        from apps.volunteers.models import VolunteerAssignment

        other = VolunteerAssignment.objects.create(
            volunteer=volunteer_a, role="CHOIR", group=unit_head_setup["other_unit"],
        )
        api_client.force_authenticate(user=unit_head_user)
        response = api_client.get(f"/api/v1/volunteers/assignments/{other.id}/")
        assert response.status_code == 404

    def test_unit_head_cannot_create_assignment_in_unled_unit_via_api(
        self, api_client, unit_head_user, unit_head_setup, volunteer_a, event_schedule_a
    ):
        """
        Creation itself isn't blocked by queryset scoping (that only
        governs list/retrieve/update/destroy) -- this proves the object
        is simply invisible afterward, i.e. a Unit Head gains no lasting
        access to a Group they don't lead even if they can technically
        POST with its id.
        """
        api_client.force_authenticate(user=unit_head_user)
        response = api_client.post(
            "/api/v1/volunteers/assignments/",
            {
                "volunteer": str(volunteer_a.id), "event_schedule": str(event_schedule_a.id),
                "role": "USHER", "group": str(unit_head_setup["other_unit"].id),
            },
            format="json",
        )
        assert response.status_code in (201, 403)
        if response.status_code == 201:
            created_id = response.data["data"]["id"]
            follow_up = api_client.get(f"/api/v1/volunteers/assignments/{created_id}/")
            assert follow_up.status_code == 404


@pytest.mark.django_db
class TestVolunteerAssignmentApiActions:
    def test_confirm_decline_complete_endpoints(self, api_client, chapel_admin_a, seed_member_permissions, volunteer_a, event_schedule_a):
        from apps.volunteers.models import VolunteerAssignment

        assignment = VolunteerAssignment.objects.create(volunteer=volunteer_a, event_schedule=event_schedule_a, role="USHER")
        api_client.force_authenticate(user=chapel_admin_a)

        resp = api_client.post(f"/api/v1/volunteers/assignments/{assignment.id}/confirm/")
        assert resp.status_code == 200
        assert resp.data["data"]["status"] == "CONFIRMED"

        resp = api_client.post(f"/api/v1/volunteers/assignments/{assignment.id}/complete/", {"hours_logged": "2.50"}, format="json")
        assert resp.status_code == 200
        assert resp.data["data"]["status"] == "COMPLETED"
        assert resp.data["data"]["hours_logged"] == "2.50"

    def test_decline_endpoint(self, api_client, chapel_admin_a, seed_member_permissions, volunteer_a, event_schedule_a):
        from apps.volunteers.models import VolunteerAssignment

        assignment = VolunteerAssignment.objects.create(volunteer=volunteer_a, event_schedule=event_schedule_a, role="CHOIR")
        api_client.force_authenticate(user=chapel_admin_a)
        resp = api_client.post(f"/api/v1/volunteers/assignments/{assignment.id}/decline/", {"reason": "sick"}, format="json")
        assert resp.status_code == 200
        assert resp.data["data"]["status"] == "DECLINED"

    def test_history_endpoint_reports_total_hours(self, api_client, chapel_admin_a, seed_member_permissions, volunteer_a, event_schedule_a):
        from apps.volunteers import services

        assignment = services.create_assignment(volunteer_a, event_schedule_a, "USHER")
        services.confirm_assignment(assignment)
        services.complete_assignment(assignment, 4)

        api_client.force_authenticate(user=chapel_admin_a)
        resp = api_client.get(f"/api/v1/volunteers/profiles/{volunteer_a.id}/history/")
        assert resp.status_code == 200
        assert float(resp.data["data"]["total_hours"]) == 4.0
        assert len(resp.data["data"]["assignments"]) == 1


@pytest.mark.django_db
class TestVolunteerReminderTask:
    def test_reminder_sent_only_for_confirmed_and_marks_timestamp(self, volunteer_a, event_schedule_a, settings):
        from apps.notifications.models import Notification
        from apps.members.models import Member
        from apps.accounts.models import User
        from apps.volunteers import services
        from apps.volunteers.tasks import send_assignment_reminder

        user = User.objects.create_user(email="vince@test.com", password="Pass12345!", role="MEMBER", branch=volunteer_a.member.branch)
        volunteer_a.member.user = user
        volunteer_a.member.save(update_fields=["user"])

        assignment = services.create_assignment(volunteer_a, event_schedule_a, "USHER")
        # PENDING -> reminder task is a no-op.
        send_assignment_reminder(str(assignment.id))
        assignment.refresh_from_db()
        assert assignment.reminder_sent_at is None
        assert Notification.objects.count() == 0

        services.confirm_assignment(assignment)
        send_assignment_reminder(str(assignment.id))
        assignment.refresh_from_db()
        assert assignment.reminder_sent_at is not None
        assert Notification.objects.filter(recipient=user).exists()


@pytest.mark.django_db
class TestVolunteerPermissionCodes:
    """
    Regression guard for the Phase 9 finding that UNIT_HEAD and
    MINISTRY_GROUP_LEADER had no RolePermission grants at all.
    """

    def test_unit_head_and_ministry_group_leader_seeded_with_volunteer_grants(self):
        from scripts.seed_roles import ROLE_GRANTS
        from common.constants.roles import PermissionCodes, Roles

        assert PermissionCodes.VOLUNTEERS_VIEW in ROLE_GRANTS[Roles.UNIT_HEAD]
        assert PermissionCodes.VOLUNTEERS_VIEW in ROLE_GRANTS[Roles.MINISTRY_GROUP_LEADER]
        assert PermissionCodes.VOLUNTEERS_CREATE in ROLE_GRANTS[Roles.UNIT_HEAD]
        assert PermissionCodes.VOLUNTEERS_CREATE in ROLE_GRANTS[Roles.MINISTRY_GROUP_LEADER]

    def test_member_without_grant_is_denied(self, api_client, make_user, branch_a):
        """Fail-closed: a role with no VOLUNTEERS_VIEW grant gets 403, not an empty 200."""
        from apps.accounts.models import Permission, RolePermission
        from common.constants.roles import PermissionCodes, Roles

        # Ensure no stray grant exists for this test's Roles.VISITOR-like check
        RolePermission.objects.filter(legacy_role_code=Roles.MEMBER, permission__code=PermissionCodes.VOLUNTEERS_VIEW).delete()
        user = make_user(role=Roles.MEMBER, branch=branch_a, email="nogrant@test.com")
        api_client.force_authenticate(user=user)
        response = api_client.get("/api/v1/volunteers/profiles/")
        assert response.status_code == 403


@pytest.mark.django_db
class TestVolunteerProfileCreationAndDutyEligibility:
    def test_created_profile_is_active_and_listed_for_duty(self, api_client, chapel_admin_a, branch_a, seed_member_permissions):
        from apps.members.models import Member
        from apps.volunteers.models import VolunteerProfile

        member = Member.objects.create(branch=branch_a, first_name="Ada", last_name="Server")
        api_client.force_authenticate(user=chapel_admin_a)
        response = api_client.post(
            "/api/v1/volunteers/profiles/",
            {"member": str(member.id), "skills": ["ushering"], "availability_notes": "Sunday mornings"},
            format="json",
        )
        assert response.status_code == 201
        profile = VolunteerProfile.objects.get(member=member)
        assert profile.status == "ACTIVE"
        assert profile.is_active is True

        dropdown = api_client.get("/api/v1/volunteers/profiles/?status=ACTIVE&is_active=true")
        assert dropdown.status_code == 200
        rows = dropdown.data["data"]["results"] if isinstance(dropdown.data["data"], dict) else dropdown.data["data"]
        assert any(str(row["id"]) == str(profile.id) for row in rows)

    def test_pending_profile_is_not_in_active_duty_results(self, api_client, chapel_admin_a, branch_a, seed_member_permissions):
        from apps.members.models import Member
        from apps.volunteers.models import VolunteerProfile

        member = Member.objects.create(branch=branch_a, first_name="Pat", last_name="Pending")
        pending = VolunteerProfile.objects.create(member=member, status="PENDING", is_active=False)
        api_client.force_authenticate(user=chapel_admin_a)
        response = api_client.get("/api/v1/volunteers/profiles/?status=ACTIVE&is_active=true")
        assert response.status_code == 200
        rows = response.data["data"]["results"] if isinstance(response.data["data"], dict) else response.data["data"]
        assert all(str(row["id"]) != str(pending.id) for row in rows)

    def test_non_admin_cannot_self_approve_profile(self, api_client, unit_head_user, unit_head_setup):
        from apps.volunteers.models import VolunteerProfile
        from common.constants.roles import PermissionCodes

        _grant("UNIT_HEAD", PermissionCodes.VOLUNTEERS_CREATE)
        member = unit_head_setup["leader_member"]
        api_client.force_authenticate(user=unit_head_user)
        response = api_client.post(
            "/api/v1/volunteers/profiles/",
            {"member": str(member.id), "status": "ACTIVE", "is_active": True},
            format="json",
        )
        assert response.status_code == 201
        profile = VolunteerProfile.objects.get(member=member)
        assert profile.status == "PENDING"
        assert profile.is_active is False
