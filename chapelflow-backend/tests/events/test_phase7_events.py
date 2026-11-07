import datetime as dt

import pytest
from django.utils import timezone


def _grant(role, *codes):
    from apps.accounts.models import Permission, RolePermission
    for code in codes:
        perm, _ = Permission.objects.get_or_create(code=code)
        RolePermission.objects.get_or_create(legacy_role_code=role, permission=perm)


@pytest.fixture
def events_admin(branch_a):
    from apps.accounts.models import User
    from common.constants.roles import Roles, PermissionCodes
    _grant(Roles.CHAPEL_ADMIN, PermissionCodes.EVENTS_VIEW, PermissionCodes.EVENTS_CREATE,
           PermissionCodes.EVENTS_UPDATE, PermissionCodes.EVENTS_DELETE)
    return User.objects.create_user(email="events_admin@test.com", password="Pass12345!", role=Roles.CHAPEL_ADMIN, branch=branch_a)


@pytest.fixture
def member_a(branch_a):
    from apps.members.models import Member, MemberQRCode
    m = Member.objects.create(branch=branch_a, first_name="Reg", last_name="Istrant")
    MemberQRCode.objects.get_or_create(member=m)
    return m


@pytest.mark.django_db
class TestEventScheduleGeneration:
    def test_creating_non_recurring_event_generates_one_schedule(self, api_client, events_admin, branch_a):
        api_client.force_authenticate(user=events_admin)
        now = timezone.now() + dt.timedelta(days=5)
        response = api_client.post("/api/v1/events/", {
            "branch": str(branch_a.id), "title": "Sunday Service",
            "start_time": now.isoformat(), "end_time": (now + dt.timedelta(hours=2)).isoformat(),
        }, format="json")
        assert response.status_code == 201
        assert len(response.data["data"]["schedules"]) == 1

    def test_weekly_recurring_event_generates_multiple_schedules(self, api_client, events_admin, branch_a):
        api_client.force_authenticate(user=events_admin)
        start = timezone.now() + dt.timedelta(days=1)
        end_date = (start + dt.timedelta(weeks=3)).date()
        response = api_client.post("/api/v1/events/", {
            "branch": str(branch_a.id), "title": "Weekly Bible Study",
            "start_time": start.isoformat(), "end_time": (start + dt.timedelta(hours=1)).isoformat(),
            "frequency": "WEEKLY", "recurrence_end_date": end_date.isoformat(),
        }, format="json")
        assert response.status_code == 201
        assert len(response.data["data"]["schedules"]) == 4

    def test_recurring_event_requires_recurrence_end_date(self, api_client, events_admin, branch_a):
        api_client.force_authenticate(user=events_admin)
        start = timezone.now() + dt.timedelta(days=1)
        response = api_client.post("/api/v1/events/", {
            "branch": str(branch_a.id), "title": "Bad Recurrence",
            "start_time": start.isoformat(), "end_time": (start + dt.timedelta(hours=1)).isoformat(),
            "frequency": "WEEKLY",
        }, format="json")
        assert response.status_code == 400

    def test_end_time_before_start_time_rejected(self, api_client, events_admin, branch_a):
        api_client.force_authenticate(user=events_admin)
        start = timezone.now() + dt.timedelta(days=1)
        response = api_client.post("/api/v1/events/", {
            "branch": str(branch_a.id), "title": "Backwards",
            "start_time": start.isoformat(), "end_time": (start - dt.timedelta(hours=1)).isoformat(),
        }, format="json")
        assert response.status_code == 400

    def test_registration_deadline_must_be_before_start(self, api_client, events_admin, branch_a):
        api_client.force_authenticate(user=events_admin)
        start = timezone.now() + dt.timedelta(days=1)
        response = api_client.post("/api/v1/events/", {
            "branch": str(branch_a.id), "title": "Bad Deadline",
            "start_time": start.isoformat(), "end_time": (start + dt.timedelta(hours=1)).isoformat(),
            "registration_deadline": (start + dt.timedelta(hours=2)).isoformat(),
        }, format="json")
        assert response.status_code == 400


@pytest.mark.django_db
class TestEventRegistrationCapacityAndWaitlist:
    def _make_event(self, branch_a, capacity=None, requires_registration=True, deadline=None):
        from apps.events.models import Event
        from apps.events.services import generate_event_schedules
        event = Event.objects.create(
            branch=branch_a, title="Capacity Test", requires_registration=requires_registration, capacity=capacity,
            start_time=timezone.now() + dt.timedelta(days=2),
            end_time=timezone.now() + dt.timedelta(days=2, hours=1),
            registration_deadline=deadline,
        )
        return generate_event_schedules(event)[0]

    def test_registration_within_capacity_is_confirmed(self, api_client, branch_a, member_a):
        from common.constants.roles import Roles, PermissionCodes
        _grant(Roles.MEMBER, PermissionCodes.EVENTS_VIEW)
        schedule = self._make_event(branch_a, capacity=5)
        api_client.force_authenticate(user=member_a.user or _member_user(member_a, branch_a))
        response = api_client.post("/api/v1/event-registrations/", {
            "schedule": str(schedule.id), "member": str(member_a.id),
        }, format="json")
        assert response.status_code == 201
        assert response.data["data"]["status"] == "CONFIRMED"

    def test_registration_over_capacity_is_waitlisted(self, api_client, branch_a):
        from apps.members.models import Member, MemberQRCode
        from common.constants.roles import Roles, PermissionCodes
        _grant(Roles.CHAPEL_ADMIN, PermissionCodes.EVENTS_VIEW)
        schedule = self._make_event(branch_a, capacity=1)

        from apps.accounts.models import User
        staff = User.objects.create_user(email="staffcap@test.com", password="Pass12345!", role=Roles.CHAPEL_ADMIN, branch=branch_a)
        api_client.force_authenticate(user=staff)

        m1 = Member.objects.create(branch=branch_a, first_name="First", last_name="In")
        MemberQRCode.objects.get_or_create(member=m1)
        m2 = Member.objects.create(branch=branch_a, first_name="Second", last_name="In")
        MemberQRCode.objects.get_or_create(member=m2)

        r1 = api_client.post("/api/v1/event-registrations/", {"schedule": str(schedule.id), "member": str(m1.id)}, format="json")
        r2 = api_client.post("/api/v1/event-registrations/", {"schedule": str(schedule.id), "member": str(m2.id)}, format="json")
        assert r1.data["data"]["status"] == "CONFIRMED"
        assert r2.data["data"]["status"] == "WAITLISTED"

    def test_duplicate_registration_rejected(self, api_client, branch_a, member_a):
        from common.constants.roles import Roles, PermissionCodes
        from apps.accounts.models import User
        _grant(Roles.CHAPEL_ADMIN, PermissionCodes.EVENTS_VIEW)
        staff = User.objects.create_user(email="staffdup@test.com", password="Pass12345!", role=Roles.CHAPEL_ADMIN, branch=branch_a)
        schedule = self._make_event(branch_a, capacity=5)
        api_client.force_authenticate(user=staff)
        api_client.post("/api/v1/event-registrations/", {"schedule": str(schedule.id), "member": str(member_a.id)}, format="json")
        r2 = api_client.post("/api/v1/event-registrations/", {"schedule": str(schedule.id), "member": str(member_a.id)}, format="json")
        assert r2.status_code == 400

    def test_registration_past_deadline_rejected(self, api_client, branch_a, member_a):
        from common.constants.roles import Roles, PermissionCodes
        from apps.accounts.models import User
        _grant(Roles.CHAPEL_ADMIN, PermissionCodes.EVENTS_VIEW)
        staff = User.objects.create_user(email="staffdl@test.com", password="Pass12345!", role=Roles.CHAPEL_ADMIN, branch=branch_a)
        schedule = self._make_event(branch_a, capacity=5, deadline=timezone.now() - dt.timedelta(hours=1))
        api_client.force_authenticate(user=staff)
        response = api_client.post("/api/v1/event-registrations/", {"schedule": str(schedule.id), "member": str(member_a.id)}, format="json")
        assert response.status_code == 400

    def test_registration_without_requires_registration_rejected(self, api_client, branch_a, member_a):
        from common.constants.roles import Roles, PermissionCodes
        from apps.accounts.models import User
        _grant(Roles.CHAPEL_ADMIN, PermissionCodes.EVENTS_VIEW)
        staff = User.objects.create_user(email="staffnoreg@test.com", password="Pass12345!", role=Roles.CHAPEL_ADMIN, branch=branch_a)
        schedule = self._make_event(branch_a, requires_registration=False)
        api_client.force_authenticate(user=staff)
        response = api_client.post("/api/v1/event-registrations/", {"schedule": str(schedule.id), "member": str(member_a.id)}, format="json")
        assert response.status_code == 400

    def test_cancelling_confirmed_promotes_waitlisted(self, api_client, branch_a):
        from apps.members.models import Member, MemberQRCode
        from apps.events.models import EventRegistration
        from common.constants.roles import Roles, PermissionCodes
        from apps.accounts.models import User
        _grant(Roles.CHAPEL_ADMIN, PermissionCodes.EVENTS_VIEW, PermissionCodes.EVENTS_UPDATE)
        staff = User.objects.create_user(email="staffcancel@test.com", password="Pass12345!", role=Roles.CHAPEL_ADMIN, branch=branch_a)
        schedule = self._make_event(branch_a, capacity=1)

        m1 = Member.objects.create(branch=branch_a, first_name="First", last_name="In")
        MemberQRCode.objects.get_or_create(member=m1)
        m2 = Member.objects.create(branch=branch_a, first_name="Second", last_name="In")
        MemberQRCode.objects.get_or_create(member=m2)

        api_client.force_authenticate(user=staff)
        r1 = api_client.post("/api/v1/event-registrations/", {"schedule": str(schedule.id), "member": str(m1.id)}, format="json")
        api_client.post("/api/v1/event-registrations/", {"schedule": str(schedule.id), "member": str(m2.id)}, format="json")

        cancel_resp = api_client.post(f"/api/v1/event-registrations/{r1.data['data']['id']}/cancel/")
        assert cancel_resp.status_code == 200
        assert cancel_resp.data["data"]["status"] == "CANCELLED"

        m2_reg = EventRegistration.objects.get(schedule=schedule, member=m2)
        assert m2_reg.status == "CONFIRMED"

    def test_recancelled_member_can_reregister(self, api_client, branch_a, member_a):
        from common.constants.roles import Roles, PermissionCodes
        from apps.accounts.models import User
        _grant(Roles.CHAPEL_ADMIN, PermissionCodes.EVENTS_VIEW, PermissionCodes.EVENTS_UPDATE)
        staff = User.objects.create_user(email="staffrereg@test.com", password="Pass12345!", role=Roles.CHAPEL_ADMIN, branch=branch_a)
        schedule = self._make_event(branch_a, capacity=5)
        api_client.force_authenticate(user=staff)

        r1 = api_client.post("/api/v1/event-registrations/", {"schedule": str(schedule.id), "member": str(member_a.id)}, format="json")
        api_client.post(f"/api/v1/event-registrations/{r1.data['data']['id']}/cancel/")

        r2 = api_client.post("/api/v1/event-registrations/", {"schedule": str(schedule.id), "member": str(member_a.id)}, format="json")
        assert r2.status_code == 200  # reactivation, not a new row -> 200 not 201
        assert r2.data["data"]["status"] == "CONFIRMED"


@pytest.mark.django_db
class TestEventRegistrationScopeSecurity:
    def test_cannot_register_into_schedule_from_another_branch(self, api_client, branch_a, branch_b, member_a):
        from apps.events.models import Event
        from apps.events.services import generate_event_schedules
        from common.constants.roles import Roles, PermissionCodes
        from apps.accounts.models import User

        _grant(Roles.CHAPEL_ADMIN, PermissionCodes.EVENTS_VIEW)
        staff_a = User.objects.create_user(email="staffscope@test.com", password="Pass12345!", role=Roles.CHAPEL_ADMIN, branch=branch_a)

        event_b = Event.objects.create(
            branch=branch_b, title="Other Branch Event", requires_registration=True,
            start_time=timezone.now() + dt.timedelta(days=2), end_time=timezone.now() + dt.timedelta(days=2, hours=1),
        )
        schedule_b = generate_event_schedules(event_b)[0]

        api_client.force_authenticate(user=staff_a)
        response = api_client.post("/api/v1/event-registrations/", {
            "schedule": str(schedule_b.id), "member": str(member_a.id),
        }, format="json")
        assert response.status_code == 404


@pytest.mark.django_db
class TestEventCalendar:
    def test_calendar_day_view_returns_only_that_day(self, api_client, events_admin, branch_a):
        from apps.events.models import Event
        from apps.events.services import generate_event_schedules

        target_day = timezone.now().date() + dt.timedelta(days=10)
        in_range = Event.objects.create(
            branch=branch_a, title="In Range",
            start_time=timezone.make_aware(dt.datetime.combine(target_day, dt.time(9, 0))),
            end_time=timezone.make_aware(dt.datetime.combine(target_day, dt.time(10, 0))),
        )
        generate_event_schedules(in_range)
        out_of_range = Event.objects.create(
            branch=branch_a, title="Out of Range",
            start_time=timezone.make_aware(dt.datetime.combine(target_day + dt.timedelta(days=5), dt.time(9, 0))),
            end_time=timezone.make_aware(dt.datetime.combine(target_day + dt.timedelta(days=5), dt.time(10, 0))),
        )
        generate_event_schedules(out_of_range)

        api_client.force_authenticate(user=events_admin)
        response = api_client.get(f"/api/v1/events/calendar/?view=day&date={target_day.isoformat()}")
        assert response.status_code == 200
        titles = [s["event"] for s in response.data["data"]]
        assert len(titles) == 1

    def test_calendar_scoped_to_own_branch(self, api_client, events_admin, branch_a, branch_b):
        from apps.events.models import Event
        from apps.events.services import generate_event_schedules

        target_day = timezone.now().date() + dt.timedelta(days=11)
        own = Event.objects.create(
            branch=branch_a, title="Own Branch",
            start_time=timezone.make_aware(dt.datetime.combine(target_day, dt.time(9, 0))),
            end_time=timezone.make_aware(dt.datetime.combine(target_day, dt.time(10, 0))),
        )
        generate_event_schedules(own)
        other = Event.objects.create(
            branch=branch_b, title="Other Branch",
            start_time=timezone.make_aware(dt.datetime.combine(target_day, dt.time(9, 0))),
            end_time=timezone.make_aware(dt.datetime.combine(target_day, dt.time(10, 0))),
        )
        generate_event_schedules(other)

        api_client.force_authenticate(user=events_admin)
        response = api_client.get(f"/api/v1/events/calendar/?view=day&date={target_day.isoformat()}")
        assert len(response.data["data"]) == 1

    def test_calendar_invalid_view_rejected(self, api_client, events_admin):
        api_client.force_authenticate(user=events_admin)
        response = api_client.get("/api/v1/events/calendar/?view=fortnight")
        assert response.status_code == 400


@pytest.mark.django_db
class TestEventReminderTask:
    def test_default_reminder_scheduled_on_event_creation(self, branch_a):
        from apps.events.models import Event, EventReminder
        from apps.events.services import generate_event_schedules

        event = Event.objects.create(
            branch=branch_a, title="Reminder Test",
            start_time=timezone.now() + dt.timedelta(days=3),
            end_time=timezone.now() + dt.timedelta(days=3, hours=1),
        )
        generate_event_schedules(event)
        assert EventReminder.objects.filter(schedule__event=event).exists()

    def test_short_notice_event_gets_no_default_reminder(self, branch_a):
        """An event starting in under 24h shouldn't get a reminder scheduled for the past."""
        from apps.events.models import Event, EventReminder
        from apps.events.services import generate_event_schedules

        event = Event.objects.create(
            branch=branch_a, title="Short Notice",
            start_time=timezone.now() + dt.timedelta(hours=2),
            end_time=timezone.now() + dt.timedelta(hours=3),
        )
        generate_event_schedules(event)
        assert not EventReminder.objects.filter(schedule__event=event).exists()

    def test_due_reminder_sends_notification_to_confirmed_registrants_only(self, branch_a, member_a):
        from apps.events.models import Event, EventReminder, EventRegistration, EventRegistrationStatus
        from apps.events.services import generate_event_schedules
        from apps.events.tasks import send_due_event_reminders
        from apps.notifications.models import Notification
        from apps.members.models import Member, MemberQRCode
        from apps.accounts.models import User
        from common.constants.roles import Roles

        member_a.user = User.objects.create_user(email="regnotif@test.com", password="Pass12345!", role=Roles.MEMBER, branch=branch_a)
        member_a.save()

        event = Event.objects.create(
            branch=branch_a, title="Reminder Fire Test", requires_registration=True,
            start_time=timezone.now() + dt.timedelta(days=5), end_time=timezone.now() + dt.timedelta(days=5, hours=1),
        )
        schedule = generate_event_schedules(event)[0]
        EventRegistration.objects.create(schedule=schedule, member=member_a, status=EventRegistrationStatus.CONFIRMED)

        waitlisted_member = Member.objects.create(branch=branch_a, first_name="Wait", last_name="Listed")
        MemberQRCode.objects.get_or_create(member=waitlisted_member)
        waitlisted_member.user = User.objects.create_user(email="waitnotif@test.com", password="Pass12345!", role=Roles.MEMBER, branch=branch_a)
        waitlisted_member.save()
        EventRegistration.objects.create(schedule=schedule, member=waitlisted_member, status=EventRegistrationStatus.WAITLISTED)

        reminder = EventReminder.objects.create(schedule=schedule, send_at=timezone.now() - dt.timedelta(minutes=1))
        result = send_due_event_reminders()

        assert result["reminders_processed"] == 1
        assert result["notifications_created"] == 1  # only the CONFIRMED registrant
        reminder.refresh_from_db()
        assert reminder.sent is True
        assert Notification.objects.filter(recipient=member_a.user).exists()
        assert not Notification.objects.filter(recipient=waitlisted_member.user).exists()

    def test_reminder_task_does_not_reprocess_sent_reminders(self, branch_a, member_a):
        from apps.events.models import Event, EventReminder
        from apps.events.services import generate_event_schedules
        from apps.events.tasks import send_due_event_reminders

        event = Event.objects.create(
            branch=branch_a, title="Already Sent",
            start_time=timezone.now() + dt.timedelta(days=5), end_time=timezone.now() + dt.timedelta(days=5, hours=1),
        )
        schedule = generate_event_schedules(event)[0]
        EventReminder.objects.create(schedule=schedule, send_at=timezone.now() - dt.timedelta(minutes=1), sent=True)

        result = send_due_event_reminders()
        assert result["reminders_processed"] == 0


def _member_user(member, branch):
    from apps.accounts.models import User
    from common.constants.roles import Roles
    user = User.objects.create_user(email=f"m{member.id}@test.com", password="Pass12345!", role=Roles.MEMBER, branch=branch)
    member.user = user
    member.save()
    return user
