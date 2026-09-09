from django.test import TestCase
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.members.models import CommunityClassification, Member
from apps.organizations.models import Branch, Organization
from common.constants.roles import Roles


class StudentProfileTests(TestCase):
    def setUp(self):
        organization = Organization.objects.create(name="Chrisland University", slug="profile-test")
        self.branch = Branch.objects.create(organization=organization, name="Chrisland University Chapel", branch_type="CHAPEL")
        self.student = User.objects.create_user(email="student@cuc.edu", password="safe-password-123", first_name="Student", last_name="One", role=Roles.MEMBER, branch=self.branch)
        self.member = Member.objects.create(user=self.student, branch=self.branch, first_name="Student", last_name="One", community=CommunityClassification.STUDENT)
        self.usher = User.objects.create_user(email="usher@cuc.edu", password="safe-password-123", first_name="Usher", last_name="One", role=Roles.ATTENDANCE_USHER, branch=self.branch)

    def test_student_can_update_only_personal_contact_fields(self):
        client = APIClient()
        client.force_authenticate(self.student)
        response = client.patch("/api/v1/auth/profile/", {"phone_number": "08000000000", "emergency_contact_name": "Parent"}, format="json")
        self.assertEqual(response.status_code, 200)
        self.student.refresh_from_db()
        self.member.refresh_from_db()
        self.assertEqual(self.student.phone_number, "08000000000")
        self.assertEqual(self.member.emergency_contact_name, "Parent")

    def test_staff_cannot_use_student_profile_endpoint(self):
        client = APIClient()
        client.force_authenticate(self.usher)
        self.assertEqual(client.get("/api/v1/auth/profile/").status_code, 403)
