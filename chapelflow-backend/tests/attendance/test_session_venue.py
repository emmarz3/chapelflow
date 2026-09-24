import pytest

from apps.attendance.models import AttendanceSession


@pytest.mark.django_db
def test_create_attendance_session_with_venue_returns_and_stores_venue(
    api_client, chapel_admin_a, seed_member_permissions
):
    api_client.force_authenticate(user=chapel_admin_a)

    response = api_client.post(
        "/api/v1/attendance/sessions/",
        {
            "branch": str(chapel_admin_a.branch_id),
            "label": "Sunday Service",
            "venue": "Marquee",
        },
        format="json",
    )

    assert response.status_code == 201
    session = AttendanceSession.objects.get(id=response.data["data"]["id"])
    assert session.venue == "Marquee"
    assert response.data["data"]["venue"] == "Marquee"
