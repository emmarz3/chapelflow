import pytest
from django.utils import timezone


@pytest.mark.django_db
class TestAttendanceDuplicatePrevention:
    def test_qr_check_in_creates_record(self, api_client, chapel_admin_a, member_in_branch_a, seed_member_permissions):
        from apps.attendance.models import AttendanceSession

        session = AttendanceSession.objects.create(branch=member_in_branch_a.branch, label="Sunday Service")
        api_client.force_authenticate(user=chapel_admin_a)

        response = api_client.post(
            "/api/v1/attendance/qr-check-in/",
            {"token": member_in_branch_a.qr_code.token, "session_id": str(session.id)},
            format="json",
        )
        assert response.status_code == 201
        assert response.data["data"]["method"] == "QR_CODE"

    def test_duplicate_qr_check_in_does_not_create_second_record(
        self, api_client, chapel_admin_a, member_in_branch_a, seed_member_permissions
    ):
        from apps.attendance.models import AttendanceRecord, AttendanceSession

        session = AttendanceSession.objects.create(branch=member_in_branch_a.branch, label="Sunday Service")
        api_client.force_authenticate(user=chapel_admin_a)

        first = api_client.post(
            "/api/v1/attendance/qr-check-in/",
            {"token": member_in_branch_a.qr_code.token, "session_id": str(session.id)},
            format="json",
        )
        second = api_client.post(
            "/api/v1/attendance/qr-check-in/",
            {"token": member_in_branch_a.qr_code.token, "session_id": str(session.id)},
            format="json",
        )

        assert first.status_code == 201
        assert second.status_code == 200
        assert first.data["data"]["id"] == second.data["data"]["id"]
        assert AttendanceRecord.objects.filter(session=session, member=member_in_branch_a).count() == 1

    def test_invalid_qr_token_rejected(self, api_client, chapel_admin_a, member_in_branch_a, seed_member_permissions):
        from apps.attendance.models import AttendanceSession

        session = AttendanceSession.objects.create(branch=member_in_branch_a.branch, label="Sunday Service")
        api_client.force_authenticate(user=chapel_admin_a)

        response = api_client.post(
            "/api/v1/attendance/qr-check-in/",
            {"token": "totally-bogus-token", "session_id": str(session.id)},
            format="json",
        )
        assert response.status_code == 400
        assert response.data["success"] is False


@pytest.mark.django_db
class TestOfflineSyncIdempotency:
    def test_sync_is_idempotent_on_replay(
        self, api_client, chapel_admin_a, member_in_branch_a, seed_member_permissions
    ):
        from apps.attendance.models import AttendanceRecord, AttendanceSession

        session = AttendanceSession.objects.create(branch=member_in_branch_a.branch, label="Midweek")
        api_client.force_authenticate(user=chapel_admin_a)

        payload = {
            "records": [
                {
                    "client_record_id": "offline-batch-001",
                    "member_id": str(member_in_branch_a.id),
                    "session_id": str(session.id),
                    "checked_in_at": timezone.now().isoformat(),
                    "method": "SELF_CHECK_IN",
                }
            ]
        }

        first = api_client.post("/api/v1/attendance/sync/", payload, format="json")
        second = api_client.post("/api/v1/attendance/sync/", payload, format="json")

        assert first.status_code == 200
        assert first.data["data"]["results"][0]["status"] == "synced"
        assert second.data["data"]["results"][0]["status"] == "already_synced"
        assert first.data["data"]["results"][0]["record_id"] == second.data["data"]["results"][0]["record_id"]
        assert AttendanceRecord.objects.filter(client_record_id="offline-batch-001").count() == 1

    def test_sync_missing_client_record_id_fails_that_row_only(
        self, api_client, chapel_admin_a, member_in_branch_a, seed_member_permissions
    ):
        from apps.attendance.models import AttendanceSession

        session = AttendanceSession.objects.create(branch=member_in_branch_a.branch, label="Midweek")
        api_client.force_authenticate(user=chapel_admin_a)

        response = api_client.post(
            "/api/v1/attendance/sync/",
            {"records": [{"member_id": str(member_in_branch_a.id), "session_id": str(session.id), "checked_in_at": timezone.now().isoformat()}]},
            format="json",
        )
        # Serializer-level validation catches the missing required field before it reaches the service.
        assert response.status_code == 400
