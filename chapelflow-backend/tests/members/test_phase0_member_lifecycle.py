import pytest


@pytest.mark.django_db
class TestPhase0MemberCreationLockdown:
    """
    Spec section 3 (mandatory): normal administrators must NOT create
    members manually, under ANY permission grant — not even Super Admin.
    """

    def test_chapel_admin_with_members_create_permission_still_blocked(
        self, api_client, chapel_admin_a, branch_a, seed_member_permissions
    ):
        # seed_member_permissions grants MEMBERS_CREATE, proving the block
        # isn't just "no permission was seeded" — POST /members/ has no
        # action mapped at all, so HasRolePermission fails closed (403)
        # before create() is even reached.
        api_client.force_authenticate(user=chapel_admin_a)
        response = api_client.post("/api/v1/members/", {
            "branch": str(branch_a.id), "first_name": "Manual", "last_name": "Create",
        })
        assert response.status_code == 403

    def test_super_admin_also_cannot_manually_create_a_member(self, api_client, super_admin, branch_a):
        api_client.force_authenticate(user=super_admin)
        response = api_client.post("/api/v1/members/", {
            "branch": str(branch_a.id), "first_name": "Super", "last_name": "Bypass",
        })
        assert response.status_code == 405

    def test_import_csv_path_remains_available_as_separate_workflow(
        self, api_client, chapel_admin_a, branch_a, seed_member_permissions
    ):
        import io
        from django.core.files.uploadedfile import SimpleUploadedFile

        csv_content = f"first_name,last_name,branch_id\nJane,Doe,{branch_a.id}\n".encode()
        upload = SimpleUploadedFile("members.csv", csv_content, content_type="text/csv")

        api_client.force_authenticate(user=chapel_admin_a)
        response = api_client.post("/api/v1/members/import/", {"file": upload}, format="multipart")
        assert response.status_code == 200
        assert response.data["data"]["created"] == 1


@pytest.mark.django_db
class TestSelfRegistrationPipeline:
    """Spec section 3: the ONLY normal path a Member gets created through."""

    def test_register_creates_user_and_member_together(self, api_client, branch_a):
        response = api_client.post("/api/v1/auth/register/", {
            "matric_no": "swe/2025/010",
            "password": "StrongPass123!",
            "first_name": "Chidi",
            "last_name": "Okafor",
            "branch": str(branch_a.id),
            "community": "STUDENT",
            "academic_level": "100",
        })
        assert response.status_code == 201
        assert "access" in response.data["data"]

        from apps.accounts.models import User
        from apps.members.models import Member

        user = User.objects.get(matric_no="SWE/2025/010")
        assert user.role == "MEMBER"
        member = Member.objects.get(user=user)
        assert member.branch_id == branch_a.id
        assert member.community == "STUDENT"
        assert member.academic_level == "100"
        assert member.qr_code is not None

    def test_student_registration_requires_an_academic_level(self, api_client, branch_a):
        response = api_client.post("/api/v1/auth/register/", {
            "matric_no": "swe/2025/011",
            "password": "StrongPass123!",
            "first_name": "Missing",
            "last_name": "Level",
            "branch": str(branch_a.id),
            "community": "STUDENT",
        })

        assert response.status_code == 400
        assert "academic_level" in response.data["errors"]

    def test_jupeb_registration_is_saved_in_jupeb_level(self, api_client, branch_a):
        response = api_client.post("/api/v1/auth/register/", {
            "matric_no": "jup/2026/012",
            "password": "StrongPass123!",
            "first_name": "Jupeb",
            "last_name": "Student",
            "branch": str(branch_a.id),
            "community": "STUDENT",
            "academic_level": "JUPEB",
        })

        assert response.status_code == 201
        from apps.members.models import Member
        assert Member.objects.get(user__matric_no="JUP/2026/012").academic_level == "JUPEB"

    @pytest.mark.parametrize(
        ("community", "email"),
        [("STAFF", "staff.member@example.edu.ng"), ("GUEST", "guest.member@example.com")],
    )
    def test_staff_and_guest_registration_require_email_not_matric_number(
        self, api_client, branch_a, community, email
    ):
        response = api_client.post("/api/v1/auth/register/", {
            "email": email,
            "password": "StrongPass123!",
            "first_name": "Email",
            "last_name": "Only",
            "branch": str(branch_a.id),
            "community": community,
        })

        assert response.status_code == 201
        from apps.accounts.models import User
        from apps.members.models import Member

        user = User.objects.get(email=email)
        member = Member.objects.get(user=user)
        assert user.matric_no is None
        assert member.community == community
        assert member.academic_level == ""
        assert response.data["data"]["user"]["community"] == community

    def test_register_requires_email_or_matric_no(self, api_client, branch_a):
        response = api_client.post("/api/v1/auth/register/", {
            "password": "StrongPass123!",
            "first_name": "No",
            "last_name": "Identifier",
            "branch": str(branch_a.id),
        })
        assert response.status_code == 400


@pytest.mark.django_db
class TestMemberManagementActions:
    """Spec section 8: deactivate/reactivate/merge, with audit trail."""

    def test_deactivate_and_reactivate(self, api_client, chapel_admin_a, member_in_branch_a, seed_member_permissions):
        api_client.force_authenticate(user=chapel_admin_a)

        response = api_client.post(f"/api/v1/members/{member_in_branch_a.id}/deactivate/")
        assert response.status_code == 200
        assert response.data["data"]["membership_status"] == "INACTIVE"

        response = api_client.post(f"/api/v1/members/{member_in_branch_a.id}/reactivate/")
        assert response.status_code == 200
        assert response.data["data"]["membership_status"] == "ACTIVE"

        from apps.members.models import MembershipHistory
        assert MembershipHistory.objects.filter(member=member_in_branch_a).count() == 2

    def test_deactivate_writes_audit_log(self, api_client, chapel_admin_a, member_in_branch_a, seed_member_permissions):
        api_client.force_authenticate(user=chapel_admin_a)
        api_client.post(f"/api/v1/members/{member_in_branch_a.id}/deactivate/")

        from apps.audit.models import AuditLog
        assert AuditLog.objects.filter(action="MEMBER_DEACTIVATE", resource_id=str(member_in_branch_a.id)).exists()

    def test_merge_reassigns_and_deactivates(self, api_client, chapel_admin_a, branch_a, seed_member_permissions):
        from apps.audit.models import AuditLog
        from apps.members.models import Member, MemberQRCode, MembershipHistory
        from apps.notifications.models import Notification

        keep = Member.objects.create(branch=branch_a, first_name="Keep", last_name="Me")
        MemberQRCode.objects.get_or_create(member=keep)
        merged = Member.objects.create(branch=branch_a, first_name="Merge", last_name="Me")
        MemberQRCode.objects.get_or_create(member=merged)
        notification = Notification.objects.create(
            recipient=None,
            recipient_member=merged,
            channel="IN_APP",
            title="Merge me",
            body="This notification must follow the canonical member.",
        )

        api_client.force_authenticate(user=chapel_admin_a)
        response = api_client.post("/api/v1/members/merge/", {"keep_id": str(keep.id), "merge_id": str(merged.id)})
        assert response.status_code == 200

        merged.refresh_from_db()
        notification.refresh_from_db()
        assert merged.membership_status == "INACTIVE"
        assert notification.recipient_member_id == keep.id
        assert MemberQRCode.objects.get(member=merged).is_active is False

        history = MembershipHistory.objects.get(member=merged, note__startswith="Merged into member")
        assert history.previous_status == "ACTIVE"
        assert history.new_status == "INACTIVE"
        assert history.changed_by == chapel_admin_a
        assert AuditLog.objects.filter(
            action="MEMBER_MERGE",
            resource_id=str(keep.id),
            metadata__merged_member_id=str(merged.id),
        ).exists()

    def test_merge_consolidates_unique_member_relationships(
        self, api_client, chapel_admin_a, branch_a, seed_member_permissions
    ):
        from django.utils import timezone

        from apps.attendance.models import (
            AttendanceCorrection,
            AttendanceRecord,
            AttendanceSession,
        )
        from apps.communications.models import CommunicationPreference
        from apps.groups.models import GroupMembership
        from apps.members.models import Member, MemberTag
        from apps.ministries.models import Group

        keep = Member.objects.create(branch=branch_a, first_name="Canonical", last_name="Member")
        merged = Member.objects.create(branch=branch_a, first_name="Duplicate", last_name="Member")

        MemberTag.objects.create(member=keep, label="student")
        MemberTag.objects.create(member=merged, label="student")
        MemberTag.objects.create(member=merged, label="choir")

        group = Group.objects.create(branch=branch_a, name="Merge Test Unit", group_type="UNIT")
        GroupMembership.objects.create(member=keep, group=group, role="MEMBER", is_active=False)
        GroupMembership.objects.create(member=merged, group=group, role="LEADER", is_active=True)

        session = AttendanceSession.objects.create(branch=branch_a, label="Merge Test Service")
        now = timezone.now()
        keep_record = AttendanceRecord.objects.create(
            session=session,
            member=keep,
            method="MANUAL",
            status="LATE",
            checked_in_at=now,
        )
        merged_record = AttendanceRecord.objects.create(
            session=session,
            member=merged,
            method="MANUAL",
            status="PRESENT",
            checked_in_at=now - timezone.timedelta(minutes=10),
        )
        correction = AttendanceCorrection.objects.create(
            record=merged_record,
            previous_status="LATE",
            new_status="PRESENT",
            reason="Verified at the door",
            corrected_by=chapel_admin_a,
        )

        keep_preference = CommunicationPreference.objects.create(member=keep)
        CommunicationPreference.objects.create(
            member=merged,
            email_enabled=False,
            announcements_enabled=False,
        )

        api_client.force_authenticate(user=chapel_admin_a)
        response = api_client.post("/api/v1/members/merge/", {
            "keep_id": str(keep.id),
            "merge_id": str(merged.id),
        })
        assert response.status_code == 200

        assert set(keep.tags.values_list("label", flat=True)) == {"student", "choir"}
        membership = GroupMembership.objects.get(member=keep, group=group)
        assert membership.role == "LEADER"
        assert membership.is_active is True
        assert GroupMembership.objects.filter(group=group).count() == 1

        keep_record.refresh_from_db()
        correction.refresh_from_db()
        assert AttendanceRecord.objects.filter(session=session).count() == 1
        assert keep_record.status == "PRESENT"
        assert keep_record.checked_in_at == merged_record.checked_in_at
        assert correction.record_id == keep_record.id

        keep_preference.refresh_from_db()
        assert keep_preference.email_enabled is False
        assert keep_preference.announcements_enabled is False
        assert CommunicationPreference.objects.filter(member=merged).exists() is False

    def test_merge_rejects_members_from_different_branches(self, api_client, super_admin, branch_a, branch_b):
        from apps.members.models import Member, MembershipHistory

        keep = Member.objects.create(branch=branch_a, first_name="Branch", last_name="A")
        merged = Member.objects.create(branch=branch_b, first_name="Branch", last_name="B")

        api_client.force_authenticate(user=super_admin)
        response = api_client.post("/api/v1/members/merge/", {
            "keep_id": str(keep.id),
            "merge_id": str(merged.id),
        })

        assert response.status_code == 400
        merged.refresh_from_db()
        assert merged.membership_status == "ACTIVE"
        assert MembershipHistory.objects.filter(member=merged, note__startswith="Merged into member").exists() is False
