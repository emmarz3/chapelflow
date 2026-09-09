from types import SimpleNamespace
from unittest.mock import patch

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase
from rest_framework import serializers

from apps.accounts.models import User
from apps.accounts.serializers import InstitutionalAccountSerializer
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
