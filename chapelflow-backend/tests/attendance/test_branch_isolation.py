import pytest
from django.utils import timezone


def _grant_chaplain(codes):
    from apps.accounts.models import Permission, RolePermission
    from common.constants.roles import Roles

    for code in codes:
        perm, _ = Permission.objects.get_or_create(code=code)
        RolePermission.objects.get_or_create(legacy_role_code=Roles.CHAPLAIN, permission=perm)


@pytest.mark.django_db
class TestAttendanceRecordBranchIsolation:
    """
    Phase 1 fix regression tests: both viewsets used to hand-roll
    branch-only scoping (missing the Chaplain org-wide tier), same root
    cause as the other four Phase 1 scoping fixes.
    """

    def test_chapel_admin_sees_only_own_branch_records(
        self, api_client, chapel_admin_a, seed_member_permissions, member_in_branch_a, branch_a, branch_b
    ):
        from apps.attendance.models import AttendanceRecord, AttendanceSession

        session_a = AttendanceSession.objects.create(branch=branch_a, label="Sunday Service A")
        session_b = AttendanceSession.objects.create(branch=branch_b, label="Sunday Service B")
        record_a = AttendanceRecord.objects.create(
            session=session_a, member=member_in_branch_a, method="MANUAL", checked_in_at=timezone.now()
        )
        AttendanceRecord.objects.create(session=session_b, method="MANUAL", checked_in_at=timezone.now())

        api_client.force_authenticate(user=chapel_admin_a)
        response = api_client.get("/api/v1/attendance/records/")
        assert response.status_code == 200
        ids = {row["id"] for row in response.data["data"]}
        assert ids == {str(record_a.id)}

    def test_chaplain_sees_records_across_own_org_not_other_orgs(
        self, api_client, make_user, branch_a, branch_b, branch_org2, seed_member_permissions
    ):
        from apps.attendance.models import AttendanceRecord, AttendanceSession
        from common.constants.roles import PermissionCodes

        _grant_chaplain([PermissionCodes.ATTENDANCE_VIEW])
        session_a = AttendanceSession.objects.create(branch=branch_a, label="A")
        session_b = AttendanceSession.objects.create(branch=branch_b, label="B")
        session_other_org = AttendanceSession.objects.create(branch=branch_org2, label="Other org")
        record_a = AttendanceRecord.objects.create(session=session_a, method="MANUAL", checked_in_at=timezone.now())
        record_b = AttendanceRecord.objects.create(session=session_b, method="MANUAL", checked_in_at=timezone.now())
        AttendanceRecord.objects.create(session=session_other_org, method="MANUAL", checked_in_at=timezone.now())

        chaplain = make_user(role="CHAPLAIN", branch=branch_a, email="chaplain-att@test.com")
        api_client.force_authenticate(user=chaplain)
        response = api_client.get("/api/v1/attendance/records/")
        assert response.status_code == 200
        ids = {row["id"] for row in response.data["data"]}
        assert ids == {str(record_a.id), str(record_b.id)}


@pytest.mark.django_db
class TestVisitorAttendanceBranchIsolation:
    def test_chapel_admin_sees_only_own_branch_visitors(
        self, api_client, chapel_admin_a, seed_member_permissions, branch_a, branch_b
    ):
        from apps.attendance.models import AttendanceSession, VisitorAttendance

        session_a = AttendanceSession.objects.create(branch=branch_a, label="A")
        session_b = AttendanceSession.objects.create(branch=branch_b, label="B")
        visitor_a = VisitorAttendance.objects.create(session=session_a, full_name="Vince Visitor", checked_in_at=timezone.now())
        VisitorAttendance.objects.create(session=session_b, full_name="Vera Visitor", checked_in_at=timezone.now())

        api_client.force_authenticate(user=chapel_admin_a)
        response = api_client.get("/api/v1/attendance/visitors/")
        assert response.status_code == 200
        ids = {row["id"] for row in response.data["data"]}
        assert ids == {str(visitor_a.id)}

    def test_chapel_admin_cannot_fetch_another_branchs_visitor_by_id(
        self, api_client, chapel_admin_a, seed_member_permissions, branch_b
    ):
        from apps.attendance.models import AttendanceSession, VisitorAttendance

        session_b = AttendanceSession.objects.create(branch=branch_b, label="B")
        visitor_b = VisitorAttendance.objects.create(session=session_b, full_name="Vera Visitor", checked_in_at=timezone.now())

        api_client.force_authenticate(user=chapel_admin_a)
        response = api_client.get(f"/api/v1/attendance/visitors/{visitor_b.id}/")
        assert response.status_code == 404
