from django.test import TestCase
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.attendance.models import AttendanceCheckpoint, AttendanceRecord, AttendanceSession
from apps.attendance.services import AttendanceError, issue_checkpoint_token, student_scan_usher_token
from apps.members.models import CommunityClassification, Member
from apps.organizations.models import Branch, Organization
from common.constants.roles import Roles


class UsherQrAttendanceTests(TestCase):
    def setUp(self):
        organization = Organization.objects.create(name="Chrisland University", slug="cuc-test")
        self.branch = Branch.objects.create(organization=organization, name="Chrisland University Chapel", branch_type="CHAPEL")
        self.usher = User.objects.create_user(email="usher@example.edu", password="safe-password-123", first_name="Usher", last_name="One", role="ATTENDANCE_USHER", branch=self.branch)
        self.student_user = User.objects.create_user(email="student@example.edu", password="safe-password-123", first_name="Student", last_name="One", role=Roles.MEMBER, branch=self.branch)
        self.student = Member.objects.create(user=self.student_user, branch=self.branch, first_name="Student", last_name="One", community=CommunityClassification.STUDENT)
        self.session = AttendanceSession.objects.create(branch=self.branch, label="Sunday service")
        self.checkpoint = AttendanceCheckpoint.objects.create(session=self.session, usher=self.usher)

    def test_live_usher_token_records_only_the_authenticated_student_once(self):
        token = issue_checkpoint_token(self.checkpoint)["token"]
        record, created = student_scan_usher_token(token=token, user=self.student_user)
        self.assertTrue(created)
        self.assertEqual(record.member_id, self.student.id)
        self.assertEqual(record.checkpoint_id, self.checkpoint.id)
        _, created = student_scan_usher_token(token=token, user=self.student_user)
        self.assertFalse(created)
        self.assertEqual(AttendanceRecord.objects.filter(session=self.session, member=self.student).count(), 1)

    def test_modified_token_is_rejected(self):
        token = issue_checkpoint_token(self.checkpoint)["token"] + "tampered"
        with self.assertRaises(AttendanceError):
            student_scan_usher_token(token=token, user=self.student_user)

    def test_inactive_usher_token_is_rejected(self):
        token = issue_checkpoint_token(self.checkpoint)["token"]
        self.usher.is_active = False
        self.usher.save(update_fields=["is_active"])
        with self.assertRaises(AttendanceError):
            student_scan_usher_token(token=token, user=self.student_user)

    def test_identity_pass_is_private_and_cannot_be_used_as_a_live_usher_token(self):
        client = APIClient()
        client.force_authenticate(self.student_user)
        response = client.get("/api/v1/attendance/identity-pass/")
        self.assertEqual(response.status_code, 200)
        token = response.data["data"]["token"]
        self.assertNotIn(self.student_user.email, token)
        with self.assertRaises(AttendanceError):
            student_scan_usher_token(token=token, user=self.student_user)

    def test_staff_account_cannot_request_a_student_identity_pass(self):
        client = APIClient()
        client.force_authenticate(self.usher)
        response = client.get("/api/v1/attendance/identity-pass/")
        self.assertEqual(response.status_code, 403)
