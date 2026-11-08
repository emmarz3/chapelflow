"""Super Admin institutional office provisioning and authorization regression tests."""
from django.test import TestCase
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.ministries.models import Group
from apps.organizations.models import Branch, Organization


class InstitutionalOfficeTests(TestCase):
    def setUp(self):
        org = Organization.objects.create(name="Chrisland University", slug="office-provisioning-test")
        self.branch = Branch.objects.create(
            organization=org, name="Chrisland University Chapel", branch_type="CHAPEL"
        )
        self.admin = User.objects.create_superuser(
            email="office-admin@example.edu.ng", password="Secure-Admin-Password-568!",
        )
        self.client = APIClient()
        self.client.force_authenticate(self.admin)
        self.music = Group.objects.create(branch=self.branch, name="Music", group_type="UNIT")
        self.ushering = Group.objects.create(branch=self.branch, name="Ushering", group_type="UNIT")
        self.fellowship = Group.objects.create(
            branch=self.branch, name="Love Campus Fellowship", group_type="FELLOWSHIP"
        )
        self.path = "/api/v1/auth/institutional-accounts/"

    def provision(self, office, role, group=None, n=0):
        payload = {
            "email": f"{office.lower()}-{n}@example.edu.ng",
            "first_name": "Test",
            "last_name": "Leader",
            "password": "Secure-Test-Password-387!",
            "role": role,
            "institutional_office": office,
        }
        if group:
            payload["institutional_group"] = str(group.pk)
        return self.client.post(self.path, payload, format="json")

    def test_unit_heads_and_assistants_share_one_correct_community(self):
        for office in ("HEAD_OF_MUSIC", "ASSISTANT_HEAD_OF_MUSIC"):
            response = self.provision(office, "UNIT_HEAD", self.music)
            self.assertEqual(response.status_code, 201, response.data)
            account = User.objects.get(pk=response.data["data"]["id"])
            self.assertEqual(account.institutional_office, office)
            self.assertEqual(account.institutional_group_id, self.music.id)
        # The same group serves both positions; no duplicated group is created.
        self.assertEqual(Group.objects.filter(name="Music", branch=self.branch).count(), 1)

    def test_hostel_coordinator_offices_can_be_created_without_inventing_groups(self):
        for office in (
            "MALE_HOSTEL_FELLOWSHIP_COORDINATOR",
            "FEMALE_HOSTEL_FELLOWSHIP_COORDINATOR_1",
            "FEMALE_HOSTEL_FELLOWSHIP_COORDINATOR_2",
        ):
            response = self.provision(office, "HOSTEL_COORDINATOR")
            self.assertEqual(response.status_code, 201, response.data)
            account = User.objects.get(pk=response.data["data"]["id"])
            self.assertEqual(account.role, "HOSTEL_COORDINATOR")
            self.assertIsNone(account.institutional_group_id)
        self.assertFalse(Group.objects.filter(name__icontains="Hostel").exists())

    def test_annex_assistant_chaplain_account_is_distinct_and_scoped(self):
        response = self.provision(
            "ASSISTANT_STUDENT_CHAPLAIN_VLBC_ANNEX", "ASSISTANT_STUDENT_CHAPLAIN"
        )
        self.assertEqual(response.status_code, 201, response.data)
        account = User.objects.get(pk=response.data["data"]["id"])
        self.assertEqual(account.role, "ASSISTANT_STUDENT_CHAPLAIN")
        self.assertEqual(account.branch_id, self.branch.id)

    def test_role_office_and_group_mismatches_are_rejected(self):
        bad = [
            ("HEAD_OF_MUSIC", "UNIT_HEAD", self.ushering),
            ("HEAD_OF_MUSIC", "FELLOWSHIP_LEADER", self.music),
            ("FELLOWSHIP_LEADER", "FELLOWSHIP_LEADER", self.music),
            ("MALE_HOSTEL_FELLOWSHIP_COORDINATOR", "HOSTEL_COORDINATOR", self.music),
            ("ASSISTANT_STUDENT_CHAPLAIN_VLBC_ANNEX", "STUDENT_CHAPLAIN", None),
        ]
        for n, (office, role, group) in enumerate(bad):
            response = self.provision(office, role, group, n=n)
            self.assertEqual(response.status_code, 400, response.data)
        self.assertEqual(User.objects.filter(created_by=self.admin).count(), 0)

    def test_fellowship_leader_requires_a_valid_fellowship(self):
        response = self.provision("FELLOWSHIP_LEADER", "FELLOWSHIP_LEADER", self.fellowship)
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data["data"]["institutional_office"], "FELLOWSHIP_LEADER")

    def test_non_admin_cannot_provision_office(self):
        coordinator = User.objects.create_user(
            email="office-outsider@example.edu.ng", password="Secure-Role-Password-873!",
            role="HOSTEL_COORDINATOR", branch=self.branch,
        )
        self.client.force_authenticate(coordinator)
        response = self.provision("CHAPLAIN", "CHAPLAIN")
        self.assertEqual(response.status_code, 403)
