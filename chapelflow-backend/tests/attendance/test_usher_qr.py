from unittest.mock import patch

from django.test import TestCase
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.attendance.models import AttendanceCheckpoint, AttendanceRecord, AttendanceSession, AttendanceSessionState
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

    def test_student_scan_endpoint_returns_duplicate_without_creating_another_record(self):
        token = issue_checkpoint_token(self.checkpoint)["token"]
        client = APIClient()
        client.force_authenticate(self.student_user)

        first = client.post("/api/v1/attendance/student-scan/", {"token": token}, format="json")
        second = client.post("/api/v1/attendance/student-scan/", {"token": token}, format="json")

        self.assertEqual(first.status_code, 201)
        self.assertEqual(first.data["data"]["result"], "recorded")
        self.assertEqual(second.status_code, 200)
        self.assertEqual(second.data["data"]["result"], "duplicate")
        self.assertEqual(second.data["message"], "Attendance has already been recorded.")
        self.assertEqual(AttendanceRecord.objects.filter(session=self.session, member=self.student).count(), 1)

    def test_token_is_rejected_after_its_expires_at(self):
        issued = issue_checkpoint_token(self.checkpoint)
        token = issued["token"]
        expires_epoch = int(issued["expires_at"].timestamp())

        with patch("apps.attendance.services.time.time", return_value=expires_epoch + 1):
            with self.assertRaisesRegex(AttendanceError, "invalid or has expired"):
                student_scan_usher_token(token=token, user=self.student_user)

    def test_authenticated_usher_can_open_their_attendance_checkpoint(self):
        self.session.is_open = True
        self.session.state = AttendanceSessionState.OPEN
        self.session.save(update_fields=["is_open", "state"])
        client = APIClient()
        client.force_authenticate(self.usher)

        response = client.get("/api/v1/attendance/checkpoint/token/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["data"]["checkpoint_id"], str(self.checkpoint.id))

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

    def test_staff_and_guest_members_cannot_use_student_attendance_endpoints(self):
        token = issue_checkpoint_token(self.checkpoint)["token"]
        for community in (CommunityClassification.STAFF, CommunityClassification.GUEST):
            user = User.objects.create_user(
                email=f"{community.lower()}@example.edu",
                password="safe-password-123",
                first_name=community.title(),
                last_name="Member",
                role=Roles.MEMBER,
                branch=self.branch,
            )
            Member.objects.create(
                user=user,
                branch=self.branch,
                first_name=community.title(),
                last_name="Member",
                community=community,
            )
            client = APIClient()
            client.force_authenticate(user)
            for path in (
                "/api/v1/attendance/pass/",
                "/api/v1/attendance/identity-pass/",
                "/api/v1/attendance/history/me/",
            ):
                self.assertEqual(client.get(path).status_code, 403)
            self.assertEqual(client.post("/api/v1/attendance/student-scan/", {"token": token}).status_code, 403)
            with self.assertRaises(AttendanceError):
                student_scan_usher_token(token=token, user=user)
