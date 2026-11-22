import pyotp
from django.test import TransactionTestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.accounts.data_reset import RESET_PHRASE
from apps.accounts.models import MFADevice, User
from apps.audit.models import AuditLog
from apps.members.models import Member
from apps.organizations.models import Branch, Organization
from apps.social.models import SocialPost


class AdminDataResetTests(TransactionTestCase):
    def setUp(self):
        self.password = "Long-test-password-123!"
        self.admin = User.objects.create_superuser(
            email="admin@example.edu", password=self.password, first_name="Admin", last_name="One",
        )
        self.secret = pyotp.random_base32()
        MFADevice.objects.create(user=self.admin, secret=self.secret, confirmed=True)
        self.admin.mfa_enabled = True
        self.admin.save(update_fields=["mfa_enabled"])
        org = Organization.objects.create(name="Testing", slug="testing-reset")
        self.branch = Branch.objects.create(organization=org, name="Test branch", branch_type="CHAPEL")
        self.member_user = User.objects.create_user(
            email="student@example.edu", password="Student-password-123!", role="MEMBER",
            first_name="Student", last_name="One",
        )
        self.member = Member.objects.create(user=self.member_user, branch=self.branch,
                                            first_name="Student", last_name="One")
        self.client = APIClient()
        self.client.force_authenticate(user=self.admin)

    def credentials(self, **extra):
        return {"password": self.password, "otp": pyotp.TOTP(self.secret).now(), **extra}

    def test_reset_requires_mfa_password_phrase_and_fresh_preview(self):
        url = "/api/v1/auth/admin/data-reset/"
        preview = self.client.get(url)
        self.assertEqual(preview.status_code, 200, preview.data)
        self.assertGreaterEqual(preview.data["data"]["accounts_to_remove"], 1)
        token = preview.data["data"]["token"]
        refused = self.client.post(url, self.credentials(token=token, confirmation="wrong",
                                                          backup_acknowledged=True), format="json")
        self.assertEqual(refused.status_code, 400)
        refused = self.client.post(url, {"token": token, "confirmation": RESET_PHRASE,
                                         "backup_acknowledged": True, "password": "wrong", "otp": "000000"}, format="json")
        self.assertEqual(refused.status_code, 403)
        self.assertTrue(User.objects.filter(pk=self.member_user.pk).exists())
        User.objects.create_user(email="new@example.edu", password="Student-password-123!", role="MEMBER")
        stale = self.client.post(url, self.credentials(token=token, confirmation=RESET_PHRASE,
                                                        backup_acknowledged=True), format="json")
        self.assertEqual(stale.status_code, 409, stale.data)
        self.assertTrue(User.objects.filter(pk=self.member_user.pk).exists())

    def test_full_reset_keeps_admin_and_mfa_but_removes_other_records(self):
        url = "/api/v1/auth/admin/data-reset/"
        old_token = str(AccessToken.for_user(self.admin))
        token = self.client.get(url).data["data"]["token"]
        response = self.client.post(url, self.credentials(token=token, confirmation=RESET_PHRASE,
                                                          backup_acknowledged=True), format="json")
        self.assertEqual(response.status_code, 200, response.data)
        self.assertFalse(User.objects.filter(pk=self.member_user.pk).exists())
        self.assertEqual(Member.objects.count(), 0)
        self.assertFalse(User.objects.filter(pk=self.admin.pk).exists())
        restored = User.objects.get(email="admin@example.edu")
        self.assertNotEqual(restored.pk, self.admin.pk)
        self.assertTrue(restored.check_password(self.password))
        self.assertEqual(restored.mfa_device.secret, self.secret)
        self.assertTrue(restored.mfa_device.confirmed)
        self.assertEqual(AuditLog.objects.filter(resource_type="application.DatabaseReset").count(), 1)
        old_client = APIClient()
        old_client.credentials(HTTP_AUTHORIZATION=f"Bearer {old_token}")
        self.assertEqual(old_client.get("/api/v1/auth/me/").status_code, 401)

    def test_erase_one_account_and_profile_keeps_admin(self):
        post = SocialPost.objects.create(branch=self.branch, author=self.member_user, caption="Delete this post")
        url = f"/api/v1/auth/admin/accounts/{self.member_user.pk}/erase/"
        denied = self.client.post(url, self.credentials(confirmation="wrong"), format="json")
        self.assertEqual(denied.status_code, 400)
        result = self.client.post(url, self.credentials(confirmation="student@example.edu"), format="json")
        self.assertEqual(result.status_code, 200, result.data)
        self.assertFalse(User.objects.filter(pk=self.member_user.pk).exists())
        self.assertFalse(Member.objects.filter(pk=self.member.pk).exists())
        self.assertFalse(SocialPost.objects.filter(pk=post.pk).exists())
        self.assertTrue(User.objects.filter(pk=self.admin.pk).exists())

    def test_non_admin_and_unconfirmed_mfa_cannot_reset(self):
        url = "/api/v1/auth/admin/data-reset/"
        self.client.force_authenticate(user=self.member_user)
        self.assertEqual(self.client.get(url).status_code, 403)
        self.client.force_authenticate(user=self.admin)
        MFADevice.objects.filter(user=self.admin).update(confirmed=False)
        self.assertEqual(self.client.get(url).status_code, 403)
        self.assertTrue(User.objects.filter(pk=self.member_user.pk).exists())

    def test_admin_cannot_erase_self_or_another_super_admin(self):
        url = f"/api/v1/auth/admin/accounts/{self.admin.pk}/erase/"
        response = self.client.post(url, self.credentials(confirmation="admin@example.edu"), format="json")
        self.assertEqual(response.status_code, 404)
        self.assertTrue(User.objects.filter(pk=self.admin.pk).exists())

    def test_launch_reset_preserves_configuration_and_removes_assignments(self):
        from apps.accounts.models import Role, Permission, RolePermission
        from apps.ministries.models import Group
        from apps.university.models import University, College, Department
        role = Role.objects.create(code="CUSTOM_ROLE", name="Custom", scope_type="SELF", created_by=self.member_user)
        permission = Permission.objects.create(code="custom.view", name="Custom view")
        grant = RolePermission.objects.create(role_obj=role, permission=permission)
        group = Group.objects.create(branch=self.branch, name="Launch unit", group_type="UNIT", leader=self.member)
        uni = University.objects.create(organization=self.branch.organization, name="University", slug="launch-uni")
        college = College.objects.create(university=uni, name="College")
        department = Department.objects.create(college=college, name="Programme")
        self.admin.branch = self.branch
        self.admin.photo_url = "https://example.com/test-photo.jpg"
        self.admin.save()
        preview = self.client.get("/api/v1/auth/admin/data-reset/").data["data"]
        self.assertIn("university.Department", preview["preserved_configuration"])
        response = self.client.post("/api/v1/auth/admin/data-reset/", self.credentials(
            token=preview["token"], confirmation=RESET_PHRASE, backup_acknowledged=True,
        ), format="json")
        self.assertEqual(response.status_code, 200, response.data)
        self.assertTrue(Branch.objects.filter(pk=self.branch.pk).exists())
        self.assertTrue(Department.objects.filter(pk=department.pk).exists())
        self.assertTrue(RolePermission.objects.filter(pk=grant.pk).exists())
        self.assertEqual(RolePermission.objects.count(), 1)
        role.refresh_from_db()
        group.refresh_from_db()
        self.assertIsNone(role.created_by_id)
        self.assertIsNone(group.leader_id)
        restored = User.objects.get(email=self.admin.email)
        self.assertEqual(restored.branch_id, self.branch.pk)
        self.assertEqual(restored.photo_url, "")
        self.assertEqual(User.objects.count(), 1)
        self.assertEqual(Member.objects.count(), 0)
        # Retained integer PKs must not collide with subsequent inserts.
        Permission.objects.create(code="after.reset", name="After reset")

    def test_reset_rolls_back_when_configuration_restore_fails(self):
        from unittest.mock import patch
        from apps.accounts.data_reset import reset_database, reset_preview
        token = reset_preview(self.admin)["token"]
        with patch("apps.accounts.data_reset.serializers.deserialize", side_effect=RuntimeError("restore failed")):
            with self.assertRaises(RuntimeError):
                reset_database(self.admin, token)
        self.assertTrue(User.objects.filter(pk=self.admin.pk).exists())
        self.assertTrue(User.objects.filter(pk=self.member_user.pk).exists())
        self.assertTrue(Member.objects.filter(pk=self.member.pk).exists())
        self.assertTrue(Branch.objects.filter(pk=self.branch.pk).exists())
