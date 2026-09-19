from types import SimpleNamespace
from unittest.mock import patch

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase
from rest_framework import serializers
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.accounts.models import User
from apps.accounts.serializers import InstitutionalAccountSerializer
from apps.audit.models import AuditLog
from apps.organizations.models import Branch, Organization


class SuperAdminAccountTests(TestCase):
    def setUp(self):
        organization = Organization.objects.create(name="Chrisland University", slug="cuc-admin-test")
        self.branch = Branch.objects.create(
            organization=organization, name="Chrisland University Chapel", branch_type="CHAPEL"
        )
        self.admin = User.objects.create_superuser(
            email="admin@example.edu", password="An-appropriately-long-test-password-123",
            first_name="Admin", last_name="One",
        )

    def test_only_two_active_usher_accounts_can_be_provisioned(self):
        request = SimpleNamespace(user=self.admin)
        for number in (1, 2):
            serializer = InstitutionalAccountSerializer(
                data={
                    "email": f"usher{number}@example.edu", "first_name": "Usher", "last_name": str(number),
                    "password": "An-appropriately-long-test-password-123", "role": "ATTENDANCE_USHER",
                },
                context={"request": request},
            )
            self.assertTrue(serializer.is_valid(), serializer.errors)
            serializer.save()
        third = InstitutionalAccountSerializer(
            data={
                "email": "usher3@example.edu", "first_name": "Usher", "last_name": "Three",
                "password": "An-appropriately-long-test-password-123", "role": "ATTENDANCE_USHER",
            },
            context={"request": request},
        )
        self.assertTrue(third.is_valid(), third.errors)
        with self.assertRaises(serializers.ValidationError):
            third.save()

    def test_bootstrap_is_idempotent_and_refuses_a_conflicting_identity(self):
        # The existing test admin establishes the single-admin condition.
        with patch.dict("os.environ", {"SUPER_ADMIN_EMAIL": "admin@example.edu", "SUPER_ADMIN_PASSWORD": "not-used"}):
            call_command("bootstrap_super_admin")
        self.assertEqual(User.objects.filter(role="SUPER_ADMIN").count(), 1)
        with patch.dict("os.environ", {"SUPER_ADMIN_EMAIL": "other@example.edu", "SUPER_ADMIN_PASSWORD": "not-used"}):
            with self.assertRaises(CommandError):
                call_command("bootstrap_super_admin")

    def test_super_admin_issues_temporary_password_and_user_must_replace_it(self):
        account = User.objects.create_user(
            email="leader@example.edu",
            password="Original-password-123!",
            role="UNIT_HEAD",
            branch=self.branch,
        )
        client = APIClient()
        client.force_authenticate(self.admin)

        response = client.post(f"/api/v1/auth/institutional-accounts/{account.id}/password-reset/")

        self.assertEqual(response.status_code, 200)
        temporary_password = response.data["data"]["temporary_password"]
        self.assertGreaterEqual(len(temporary_password), 12)
        account.refresh_from_db()
        self.assertTrue(account.check_password(temporary_password))
        self.assertFalse(account.check_password("Original-password-123!"))
        self.assertTrue(account.password_change_required)

        audit = AuditLog.objects.get(
            action="PASSWORD_CHANGE",
            resource_id=str(account.id),
            user=self.admin,
        )
        self.assertNotIn(temporary_password, str(audit.metadata))

        # A real JWT is restricted to identity/password endpoints until the
        # temporary credential has been replaced.
        client.force_authenticate(user=None)
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {AccessToken.for_user(account)}")
        blocked = client.get("/api/v1/auth/sessions/")
        self.assertEqual(blocked.status_code, 401)

        changed = client.post("/api/v1/auth/change-password/", {
            "old_password": temporary_password,
            "new_password": "A-new-private-password-456!",
        })
        self.assertEqual(changed.status_code, 200)
        account.refresh_from_db()
        self.assertFalse(account.password_change_required)
        self.assertTrue(account.check_password("A-new-private-password-456!"))

    def test_non_super_admin_cannot_issue_temporary_password(self):
        account = User.objects.create_user(
            email="leader2@example.edu",
            password="Original-password-123!",
            role="UNIT_HEAD",
            branch=self.branch,
        )
        chapel_admin = User.objects.create_user(
            email="chapel-admin@example.edu",
            password="Chapel-admin-password-123!",
            role="CHAPEL_ADMIN",
            branch=self.branch,
        )
        client = APIClient()
        client.force_authenticate(chapel_admin)

        response = client.post(f"/api/v1/auth/institutional-accounts/{account.id}/password-reset/")

        self.assertEqual(response.status_code, 403)
        account.refresh_from_db()
        self.assertTrue(account.check_password("Original-password-123!"))

    def test_public_password_reset_request_directs_user_to_super_admin(self):
        client = APIClient()

        response = client.post("/api/v1/auth/password-reset/", {"email": "unknown@example.edu"})

        self.assertEqual(response.status_code, 200)
        self.assertIn("Super Admin", response.data["message"])
