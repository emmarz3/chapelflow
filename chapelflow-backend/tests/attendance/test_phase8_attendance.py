import pytest
from django.utils import timezone


def _grant(role, *codes):
    from apps.accounts.models import Permission, RolePermission
    for code in codes:
        perm, _ = Permission.objects.get_or_create(code=code)
        RolePermission.objects.get_or_create(legacy_role_code=role, permission=perm)


@pytest.mark.django_db
class TestKioskDeviceAuthentication:
    """
    CRITICAL Phase 8 regression: KioskCheckInView previously accepted an
    OPTIONAL, completely unauthenticated device (an ID lookup with no
    secret and no is_active check), despite its own docstring calling it
    "device-authenticated". Confirmed as a real gap before this fix.
    """

    def test_kiosk_check_in_requires_device_id(self, api_client, chapel_admin_a, member_in_branch_a, seed_member_permissions):
        from apps.attendance.models import AttendanceSession

        session = AttendanceSession.objects.create(branch=member_in_branch_a.branch, label="Kiosk Test")
        api_client.force_authenticate(user=chapel_admin_a)
        response = api_client.post("/api/v1/attendance/check-in/", {
            "token": member_in_branch_a.qr_code.token, "session_id": str(session.id),
        }, format="json")
        assert response.status_code == 400  # device_id/device_secret now required fields

    def test_kiosk_check_in_with_valid_device_credentials_succeeds(
        self, api_client, chapel_admin_a, member_in_branch_a, branch_a, seed_member_permissions
    ):
        from apps.attendance.models import AttendanceSession, CheckInDevice

        session = AttendanceSession.objects.create(branch=branch_a, label="Kiosk Test")
        device = CheckInDevice.objects.create(branch=branch_a, name="Lobby Kiosk", device_identifier="KIOSK-001")
        device.set_secret("correct-secret")
        device.save()

        api_client.force_authenticate(user=chapel_admin_a)
        response = api_client.post("/api/v1/attendance/check-in/", {
            "token": member_in_branch_a.qr_code.token, "session_id": str(session.id),
            "device_id": str(device.id), "device_secret": "correct-secret",
        }, format="json")
        assert response.status_code == 201
        device.refresh_from_db()
        assert device.last_seen_at is not None

    def test_kiosk_check_in_with_wrong_secret_rejected(
        self, api_client, chapel_admin_a, member_in_branch_a, branch_a, seed_member_permissions
    ):
        from apps.attendance.models import AttendanceSession, CheckInDevice

        session = AttendanceSession.objects.create(branch=branch_a, label="Kiosk Test")
        device = CheckInDevice.objects.create(branch=branch_a, name="Lobby Kiosk", device_identifier="KIOSK-002")
        device.set_secret("correct-secret")
        device.save()

        api_client.force_authenticate(user=chapel_admin_a)
        response = api_client.post("/api/v1/attendance/check-in/", {
            "token": member_in_branch_a.qr_code.token, "session_id": str(session.id),
            "device_id": str(device.id), "device_secret": "wrong-guess",
        }, format="json")
        assert response.status_code == 400

    def test_revoked_device_cannot_check_anyone_in(
        self, api_client, chapel_admin_a, member_in_branch_a, branch_a, seed_member_permissions
    ):
        from apps.attendance.models import AttendanceSession, CheckInDevice

        session = AttendanceSession.objects.create(branch=branch_a, label="Kiosk Test")
        device = CheckInDevice.objects.create(branch=branch_a, name="Stolen Kiosk", device_identifier="KIOSK-003", is_active=False)
        device.set_secret("correct-secret")
        device.save()

        api_client.force_authenticate(user=chapel_admin_a)
        response = api_client.post("/api/v1/attendance/check-in/", {
            "token": member_in_branch_a.qr_code.token, "session_id": str(session.id),
            "device_id": str(device.id), "device_secret": "correct-secret",
        }, format="json")
        assert response.status_code == 400

    def test_device_from_another_branch_cannot_check_in_to_this_session(
        self, api_client, chapel_admin_a, member_in_branch_a, branch_a, branch_b, seed_member_permissions
    ):
        from apps.attendance.models import AttendanceSession, CheckInDevice

        session = AttendanceSession.objects.create(branch=branch_a, label="Kiosk Test")
        device = CheckInDevice.objects.create(branch=branch_b, name="Other Branch Kiosk", device_identifier="KIOSK-004")
        device.set_secret("correct-secret")
        device.save()

        api_client.force_authenticate(user=chapel_admin_a)
        response = api_client.post("/api/v1/attendance/check-in/", {
            "token": member_in_branch_a.qr_code.token, "session_id": str(session.id),
            "device_id": str(device.id), "device_secret": "correct-secret",
        }, format="json")
        assert response.status_code == 400

    def test_device_with_no_secret_set_cannot_check_in(
        self, api_client, chapel_admin_a, member_in_branch_a, branch_a, seed_member_permissions
    ):
        from apps.attendance.models import AttendanceSession, CheckInDevice

        session = AttendanceSession.objects.create(branch=branch_a, label="Kiosk Test")
        device = CheckInDevice.objects.create(branch=branch_a, name="Unprovisioned Kiosk", device_identifier="KIOSK-005")

        api_client.force_authenticate(user=chapel_admin_a)
        response = api_client.post("/api/v1/attendance/check-in/", {
            "token": member_in_branch_a.qr_code.token, "session_id": str(session.id),
            "device_id": str(device.id), "device_secret": "anything",
        }, format="json")
        assert response.status_code == 400


@pytest.mark.django_db
class TestDeviceSecretRotationAndRevocation:
    def test_rotate_secret_returns_new_plaintext_secret_once(self, api_client, chapel_admin_a, branch_a, seed_member_permissions):
        from apps.attendance.models import CheckInDevice

        device = CheckInDevice.objects.create(branch=branch_a, name="Kiosk", device_identifier="KIOSK-ROT")
        api_client.force_authenticate(user=chapel_admin_a)
        response = api_client.post(f"/api/v1/attendance/devices/{device.id}/rotate-secret/")
        assert response.status_code == 200
        assert "device_secret" in response.data["data"]

        device.refresh_from_db()
        assert device.verify_secret(response.data["data"]["device_secret"])

    def test_secret_never_exposed_via_read_endpoints(self, api_client, chapel_admin_a, branch_a, seed_member_permissions):
        from apps.attendance.models import CheckInDevice

        device = CheckInDevice.objects.create(branch=branch_a, name="Kiosk", device_identifier="KIOSK-READ")
        device.set_secret("super-secret")
        device.save()

        api_client.force_authenticate(user=chapel_admin_a)
        response = api_client.get(f"/api/v1/attendance/devices/{device.id}/")
        assert "secret_hash" not in response.data["data"]
        assert "device_secret" not in response.data["data"]

    def test_revoke_action_deactivates_device(self, api_client, chapel_admin_a, branch_a, seed_member_permissions):
        from apps.attendance.models import CheckInDevice

        device = CheckInDevice.objects.create(branch=branch_a, name="Kiosk", device_identifier="KIOSK-REV")
        api_client.force_authenticate(user=chapel_admin_a)
        response = api_client.post(f"/api/v1/attendance/devices/{device.id}/revoke/")
        assert response.status_code == 200
        device.refresh_from_db()
        assert device.is_active is False


@pytest.mark.django_db
class TestAttendanceAnalytics:
    def test_analytics_counts_check_ins_and_trend(self, api_client, chapel_admin_a, member_in_branch_a, seed_member_permissions):
        from apps.attendance.models import AttendanceRecord, AttendanceSession

        session = AttendanceSession.objects.create(branch=member_in_branch_a.branch, label="S1")
        AttendanceRecord.objects.create(session=session, member=member_in_branch_a, method="MANUAL", checked_in_at=timezone.now())

        api_client.force_authenticate(user=chapel_admin_a)
        response = api_client.get("/api/v1/attendance/records/analytics/")
        assert response.status_code == 200
        data = response.data["data"]
        assert data["total_check_ins"] == 1
        assert data["unique_members_present"] == 1
        assert len(data["daily_trend"]) == 1

    def test_analytics_scoped_to_own_branch(self, api_client, chapel_admin_a, branch_a, branch_b, seed_member_permissions):
        from apps.attendance.models import AttendanceRecord, AttendanceSession
        from apps.members.models import Member, MemberQRCode

        session_a = AttendanceSession.objects.create(branch=branch_a, label="A")
        member_a = Member.objects.create(branch=branch_a, first_name="In", last_name="ScopeA")
        MemberQRCode.objects.get_or_create(member=member_a)
        AttendanceRecord.objects.create(session=session_a, member=member_a, method="MANUAL", checked_in_at=timezone.now())

        session_b = AttendanceSession.objects.create(branch=branch_b, label="B")
        member_b = Member.objects.create(branch=branch_b, first_name="Out", last_name="ScopeB")
        MemberQRCode.objects.get_or_create(member=member_b)
        AttendanceRecord.objects.create(session=session_b, member=member_b, method="MANUAL", checked_in_at=timezone.now())

        api_client.force_authenticate(user=chapel_admin_a)
        response = api_client.get("/api/v1/attendance/records/analytics/")
        assert response.data["data"]["total_check_ins"] == 1

    def test_member_history_returns_only_own_scope_member(
        self, api_client, chapel_admin_a, member_in_branch_a, branch_b, seed_member_permissions
    ):
        from apps.attendance.models import AttendanceRecord, AttendanceSession
        from apps.members.models import Member, MemberQRCode

        session = AttendanceSession.objects.create(branch=member_in_branch_a.branch, label="S1")
        AttendanceRecord.objects.create(session=session, member=member_in_branch_a, method="MANUAL", checked_in_at=timezone.now())

        other_member = Member.objects.create(branch=branch_b, first_name="Other", last_name="Branch")
        MemberQRCode.objects.get_or_create(member=other_member)
        session_b = AttendanceSession.objects.create(branch=branch_b, label="S2")
        AttendanceRecord.objects.create(session=session_b, member=other_member, method="MANUAL", checked_in_at=timezone.now())

        api_client.force_authenticate(user=chapel_admin_a)
        own_history = api_client.get(f"/api/v1/attendance/records/member-history/?member_id={member_in_branch_a.id}")
        assert len(own_history.data["data"]) == 1

        other_history = api_client.get(f"/api/v1/attendance/records/member-history/?member_id={other_member.id}")
        assert other_history.data["data"] == []  # out-of-scope member -> empty, not an error leaking existence


@pytest.mark.django_db
class TestPastoralAbsenceFlagging:
    def test_flags_member_with_no_recent_attendance(self, branch_a):
        from apps.members.models import Member, MemberQRCode
        from apps.pastoral.models import PastoralCase
        from apps.pastoral.tasks import flag_members_with_prolonged_absence

        member = Member.objects.create(branch=branch_a, first_name="Absent", last_name="Long")
        MemberQRCode.objects.get_or_create(member=member)

        result = flag_members_with_prolonged_absence()
        assert result["cases_created"] == 1
        assert PastoralCase.objects.filter(member=member, category="ATTENDANCE_FOLLOW_UP").exists()

    def test_does_not_flag_member_with_recent_attendance(self, branch_a):
        from apps.members.models import Member, MemberQRCode
        from apps.attendance.models import AttendanceRecord, AttendanceSession
        from apps.pastoral.models import PastoralCase
        from apps.pastoral.tasks import flag_members_with_prolonged_absence

        member = Member.objects.create(branch=branch_a, first_name="Present", last_name="Recent")
        MemberQRCode.objects.get_or_create(member=member)
        session = AttendanceSession.objects.create(branch=branch_a, label="Recent")
        AttendanceRecord.objects.create(session=session, member=member, method="MANUAL", checked_in_at=timezone.now())

        flag_members_with_prolonged_absence()
        assert not PastoralCase.objects.filter(member=member, category="ATTENDANCE_FOLLOW_UP").exists()

    def test_does_not_open_duplicate_case_while_one_is_already_open(self, branch_a):
        from apps.members.models import Member, MemberQRCode
        from apps.pastoral.models import PastoralCase
        from apps.pastoral.tasks import flag_members_with_prolonged_absence

        member = Member.objects.create(branch=branch_a, first_name="Absent", last_name="AlreadyFlagged")
        MemberQRCode.objects.get_or_create(member=member)

        flag_members_with_prolonged_absence()
        result2 = flag_members_with_prolonged_absence()
        assert result2["cases_created"] == 0
        assert PastoralCase.objects.filter(member=member, category="ATTENDANCE_FOLLOW_UP").count() == 1

    def test_flagging_respects_pastoral_access_restrictions(self, api_client, branch_a, seed_member_permissions):
        """A plain member with no pastoral access must not be able to see an auto-flagged case about someone else."""
        from apps.accounts.models import User
        from apps.members.models import Member, MemberQRCode
        from apps.pastoral.tasks import flag_members_with_prolonged_absence
        from common.constants.roles import Roles

        absent_member = Member.objects.create(branch=branch_a, first_name="Absent", last_name="Private")
        MemberQRCode.objects.get_or_create(member=absent_member)
        flag_members_with_prolonged_absence()

        outsider_user = User.objects.create_user(email="outsider@test.com", password="Pass12345!", role=Roles.MEMBER, branch=branch_a)
        api_client.force_authenticate(user=outsider_user)
        response = api_client.get("/api/v1/pastoral/cases/")
        assert response.status_code in (200, 403)
        if response.status_code == 200:
            ids = [c["id"] if isinstance(c, dict) else c for c in response.data.get("data", response.data.get("results", []))]
            case_ids = [str(c) for c in ids]
            from apps.pastoral.models import PastoralCase
            flagged_case = PastoralCase.objects.get(member=absent_member)
            assert str(flagged_case.id) not in case_ids
