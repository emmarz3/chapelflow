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
        assert member.qr_code is not None

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
        from apps.members.models import Member, MemberQRCode

        keep = Member.objects.create(branch=branch_a, first_name="Keep", last_name="Me")
        MemberQRCode.objects.get_or_create(member=keep)
        merged = Member.objects.create(branch=branch_a, first_name="Merge", last_name="Me")
        MemberQRCode.objects.get_or_create(member=merged)

        api_client.force_authenticate(user=chapel_admin_a)
        response = api_client.post("/api/v1/members/merge/", {"keep_id": str(keep.id), "merge_id": str(merged.id)})
        assert response.status_code == 200

        merged.refresh_from_db()
        assert merged.membership_status == "INACTIVE"
