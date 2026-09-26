from django.core.management import call_command
from django.test import TestCase

from apps.ministries.models import Group
from apps.organizations.models import Branch, Organization


class BootstrapChapelTests(TestCase):
    def test_command_is_idempotent(self):
        call_command("bootstrap_chapel")
        call_command("bootstrap_chapel")

        self.assertEqual(Organization.objects.filter(slug="chrisland").count(), 1)
        self.assertEqual(Branch.objects.filter(name="Chrisland University Chapel").count(), 1)
        self.assertEqual(
            Group.objects.filter(name="Chapel Protocol", group_type="UNIT").count(), 1
        )
