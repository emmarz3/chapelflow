from datetime import timedelta

import pytest
from django.utils import timezone

from apps.attendance.models import AttendanceSession
from apps.attendance.services import _attendance_window_is_open


@pytest.mark.django_db
def test_super_admin_can_start_pause_resume_and_stop_attendance(api_client, make_user, branch_a):
    admin = make_user(email="admin@controls.test", role="SUPER_ADMIN", is_superuser=True)
    api_client.force_authenticate(user=admin)
    now = timezone.now()
    response = api_client.post("/api/v1/attendance/sessions/", {
        "branch": str(branch_a.id), "label": "Chapel worship",
        "window_opens_at": (now - timedelta(minutes=1)).isoformat(),
        "window_closes_at": (now + timedelta(hours=1)).isoformat(),
    }, format="json")
    assert response.status_code == 201, response.data
    session = AttendanceSession.objects.get(pk=response.data["data"]["id"])
    assert _attendance_window_is_open(session)
    for action, expected_open in [("pause", False), ("resume", True), ("close", False)]:
        result = api_client.post(f"/api/v1/attendance/sessions/{session.id}/{action}/")
        assert result.status_code == 200, result.data
        session.refresh_from_db()
        assert _attendance_window_is_open(session) is expected_open
    assert session.state == "CLOSED"
    assert session.is_open is False
    assert session.closed_at is not None
    assert api_client.post(f"/api/v1/attendance/sessions/{session.id}/resume/").status_code == 400


@pytest.mark.django_db
def test_attendance_rejects_reversed_time_window(api_client, make_user, branch_a):
    api_client.force_authenticate(user=make_user(email="admin@window.test", role="SUPER_ADMIN"))
    now = timezone.now()
    response = api_client.post("/api/v1/attendance/sessions/", {
        "branch": str(branch_a.id), "window_opens_at": now.isoformat(),
        "window_closes_at": (now - timedelta(hours=1)).isoformat(),
    }, format="json")
    assert response.status_code == 400
    assert not AttendanceSession.objects.exists()


@pytest.mark.django_db
def test_member_cannot_start_or_stop_attendance(api_client, make_user, branch_a):
    session = AttendanceSession.objects.create(branch=branch_a)
    api_client.force_authenticate(user=make_user(email="member@controls.test", role="MEMBER", branch=branch_a))
    assert api_client.post("/api/v1/attendance/sessions/", {"branch": str(branch_a.id)}, format="json").status_code == 403
    assert api_client.post(f"/api/v1/attendance/sessions/{session.id}/close/").status_code == 403
    session.refresh_from_db()
    assert session.is_open


@pytest.mark.django_db
@pytest.mark.parametrize("role,group_type", [
    ("CHAPLAIN", None), ("STUDENT_CHAPLAIN", None), ("ATTENDANCE_USHER", None),
    ("UNIT_HEAD", "UNIT"), ("FELLOWSHIP_LEADER", "FELLOWSHIP"),
])
def test_super_admin_creates_chapel_institutional_accounts(api_client, make_user, branch_a, role, group_type):
    from apps.accounts.models import User
    from apps.ministries.models import Group
    from apps.organizations.models import Branch

    chapel_branch = Branch.objects.create(
        organization=branch_a.organization,
        name="Chrisland University Chapel",
        branch_type="CHAPEL",
    )

    api_client.force_authenticate(user=make_user(email="admin@provision.test", role="SUPER_ADMIN"))
    payload = {
        "email": f"{role.lower()}@chapel.test", "first_name": "Chapel", "last_name": "Leader",
        "role": role, "password": "Temporary-Account-483!", "password_change_required": True,
    }
    if group_type:
        group = Group.objects.create(branch=chapel_branch, name="Chapel group", group_type=group_type)
        payload["institutional_group"] = str(group.id)
    response = api_client.post("/api/v1/auth/institutional-accounts/", payload, format="json")
    assert response.status_code == 201, response.data
    account = User.objects.get(email=payload["email"])
    assert account.branch_id == chapel_branch.id
    assert account.role == role
    assert account.check_password(payload["password"])
    assert account.password_change_required
    assert "password" not in response.data["data"]


@pytest.mark.django_db
def test_member_cannot_create_institutional_account(api_client, make_user, branch_a):
    api_client.force_authenticate(user=make_user(email="member@provision.test", branch=branch_a))
    assert api_client.post("/api/v1/auth/institutional-accounts/", {}, format="json").status_code == 403
