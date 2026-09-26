"""
Phase 10 Communications & Notifications - Comprehensive Security Test Suite

Tests all 8 security vulnerabilities identified in PHASE10_INITIAL_AUDIT.md:
1. Authorization bypass in dispatch (CRITICAL)
2. Preference bypass (CRITICAL)
3. IDOR in delivery-status endpoint
4. Cross-branch announcement targeting
5. CUSTOM audience without target_groups validation
6. Mass assignment on status/timestamps
7. No idempotency protection
8. Lifecycle state violations

Test Structure:
- test_authorization_* : Tests services.authorize_audience integration
- test_preferences_* : Tests CommunicationPreference enforcement
- test_idor_* : Tests IDOR vulnerabilities
- test_cross_branch_* : Tests branch scoping
- test_mass_assignment_* : Tests read-only field protection
- test_idempotency_* : Tests duplicate dispatch prevention
- test_lifecycle_* : Tests state transition validation
"""
import uuid
from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from apps.accounts.models import Role
from apps.organizations.models import Branch, Organization
from apps.communications.models import (
    Announcement,
    AnnouncementStatus,
    AudienceType,
    CommunicationPreference,
)
from apps.communications.tasks import dispatch_announcement
from apps.ministries.models import Group
from apps.members.models import Member, MembershipStatus

User = get_user_model()


class Phase10SecurityTestCase(TestCase):
    """
    Base test case with Phase 10 fixtures.
    
    Fixtures:
    - 2 branches (branch_a, branch_b)
    - 2 staff users (staff_a for branch_a, staff_b for branch_b)
    - 4 members (2 per branch)
    - 2 groups (1 per branch)
    - Communication preferences for all members
    """
    
    def setUp(self):
        """Create test fixtures matching Phase 10 security requirements."""
        # Create branches
        _org_1 = Organization.objects.create(name="Branch A Org", slug="branch-7bc671a6")
        self.branch_a = Branch.objects.create(name="Branch A", organization=_org_1)
        _org_2 = Organization.objects.create(name="Branch B Org", slug="branch-c8060a89")
        self.branch_b = Branch.objects.create(name="Branch B", organization=_org_2)
        # Create roles
        from common.constants.roles import Roles, PermissionCodes
        from apps.accounts.models import Permission, RolePermission
        self.staff_role = Roles.CHAPEL_ADMIN
        for code in [
            PermissionCodes.COMMUNICATIONS_VIEW, PermissionCodes.COMMUNICATIONS_CREATE,
            PermissionCodes.COMMUNICATIONS_UPDATE, PermissionCodes.COMMUNICATIONS_DELETE,
            PermissionCodes.COMMUNICATIONS_SEND,
        ]:
            perm, _ = Permission.objects.get_or_create(code=code, defaults={"description": code})
            RolePermission.objects.get_or_create(legacy_role_code=self.staff_role, permission=perm)

        # Create staff users with COMMUNICATIONS_* permissions
        self.staff_a = User.objects.create_user(
            email="staff_a@test.com",
            password="test123",
            role=self.staff_role,
            branch=self.branch_a,
        )

        self.staff_b = User.objects.create_user(
            email="staff_b@test.com",
            password="test123",
            branch=self.branch_b,
        )
        
        # Create members
        self.member_a1 = Member.objects.create(
            branch=self.branch_a,
            first_name="Alice",
            last_name="Anderson",
            email="alice@test.com",
            membership_status=MembershipStatus.ACTIVE,
        )
        self.member_a1_user = User.objects.create_user(
            email="alice@test.com",
            password="test123",
        )
        self.member_a1_user.member_profile = self.member_a1
        self.member_a1_user.save()
        self.member_a1.user = self.member_a1_user
        self.member_a1.save()
        
        self.member_a2 = Member.objects.create(
            branch=self.branch_a,
            first_name="Aaron",
            last_name="Adams",
            email="aaron@test.com",
            membership_status=MembershipStatus.ACTIVE,
        )
        
        self.member_b1 = Member.objects.create(
            branch=self.branch_b,
            first_name="Bob",
            last_name="Brown",
            email="bob@test.com",
            membership_status=MembershipStatus.ACTIVE,
        )
        
        self.member_b2 = Member.objects.create(
            branch=self.branch_b,
            first_name="Betty",
            last_name="Baker",
            email="betty@test.com",
            membership_status=MembershipStatus.ACTIVE,
        )
        
        # Create groups
        self.group_a = Group.objects.create(
            branch=self.branch_a,
            name="Worship Team A",
        )
        
        self.group_b = Group.objects.create(
            branch=self.branch_b,
            name="Worship Team B",
        )
        
        # Create communication preferences
        self.pref_a1 = CommunicationPreference.objects.create(
            member=self.member_a1,
            email_enabled=True,
            announcements_enabled=True,
        )
        
        self.pref_a2 = CommunicationPreference.objects.create(
            member=self.member_a2,
            email_enabled=False,  # Opted out of email
            announcements_enabled=True,
        )
        
        self.pref_b1 = CommunicationPreference.objects.create(
            member=self.member_b1,
            email_enabled=True,
            announcements_enabled=False,  # Opted out of announcements
        )
        
        self.pref_b2 = CommunicationPreference.objects.create(
            member=self.member_b2,
            email_enabled=True,
            announcements_enabled=True,
        )
        
        # Setup API client
        self.client = APIClient()


class AuthorizationBypassTests(Phase10SecurityTestCase):
    """
    Test Fix #1: Authorization bypass in dispatch_announcement task
    
    Vulnerability: Old dispatch_announcement bypassed services.authorize_audience
    Fix: Now calls services.resolve_audience_members() which enforces authorization
    """
    
    @patch('apps.notifications.tasks.send_notification_to_members.delay')
    def test_dispatch_respects_audience_authorization(self, mock_notify):
        """
        Dispatch should use services.resolve_audience_members which enforces
        branch scoping and group membership validation.
        """
        announcement = Announcement.objects.create(
            branch=self.branch_a,
            title="Test Announcement",
            body="Test body",
            audience_type=AudienceType.EVERYONE,
            status=AnnouncementStatus.QUEUED,
            created_by=self.staff_a,
        )
        
        # Execute dispatch
        dispatch_announcement(str(announcement.id))
        
        # Verify dispatch was called
        self.assertTrue(mock_notify.called)
        
        # Verify only branch_a members were included
        call_args = mock_notify.call_args[1]
        member_ids = call_args['member_ids']
        
        # Should only include member_a1 (member_a2 opted out of email)
        self.assertEqual(len(member_ids), 1)
        self.assertIn(str(self.member_a1.id), member_ids)
        
        # Verify status transitioned correctly
        announcement.refresh_from_db()
        self.assertEqual(announcement.status, AnnouncementStatus.COMPLETED)
    
    def test_view_create_calls_authorize_audience(self):
        """
        Creating announcement via view should call services.authorize_audience
        to validate the user can target the specified audience.
        """
        self.client.force_authenticate(user=self.staff_a)
        
        response = self.client.post('/api/v1/communications/announcements/', {
            'branch': self.branch_a.id,
            'title': 'Test Announcement',
            'body': 'Test body',
            'audience_type': AudienceType.EVERYONE,
        })
        
        # Should succeed for authorized user
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        # Verify announcement created with DRAFT status
        announcement = Announcement.objects.get(id=response.data['data']['id'])
        self.assertEqual(announcement.status, AnnouncementStatus.DRAFT)


class PreferenceBypassTests(Phase10SecurityTestCase):
    """
    Test Fix #2: Preference bypass in dispatch and volunteer reminders
    
    Vulnerability: Old dispatch ignored CommunicationPreference
    Fix: Now calls services.filter_by_preference() for each channel
    """
    
    @patch('apps.notifications.tasks.send_notification_to_members.delay')
    def test_dispatch_filters_by_email_preference(self, mock_notify):
        """
        Members with email_enabled=False should not receive email announcements.
        """
        announcement = Announcement.objects.create(
            branch=self.branch_a,
            title="Test Announcement",
            body="Test body",
            audience_type=AudienceType.EVERYONE,
            channels=['EMAIL'],
            status=AnnouncementStatus.QUEUED,
            created_by=self.staff_a,
        )
        
        # Execute dispatch
        dispatch_announcement(str(announcement.id))
        
        # Verify only member_a1 was included (member_a2 opted out)
        call_args = mock_notify.call_args[1]
        member_ids = call_args['member_ids']
        
        self.assertEqual(len(member_ids), 1)
        self.assertIn(str(self.member_a1.id), member_ids)
        self.assertNotIn(str(self.member_a2.id), member_ids)
    
    @patch('apps.notifications.tasks.send_notification_to_members.delay')
    def test_dispatch_filters_by_announcements_preference(self, mock_notify):
        """
        Members with announcements_enabled=False should not receive any announcements.
        """
        announcement = Announcement.objects.create(
            branch=self.branch_b,
            title="Test Announcement",
            body="Test body",
            audience_type=AudienceType.EVERYONE,
            channels=['EMAIL'],
            status=AnnouncementStatus.QUEUED,
            created_by=self.staff_b,
        )
        
        # Execute dispatch (branch_b: member_b1 opted out of announcements)
        dispatch_announcement(str(announcement.id))
        
        # Verify only member_b2 was included
        call_args = mock_notify.call_args[1]
        member_ids = call_args['member_ids']
        
        self.assertEqual(len(member_ids), 1)
        self.assertIn(str(self.member_b2.id), member_ids)
        self.assertNotIn(str(self.member_b1.id), member_ids)
    
    @patch('apps.notifications.tasks.deliver_notification.delay')
    def test_volunteer_reminder_respects_preferences(self, mock_deliver):
        """
        Phase 9 volunteer reminders should respect communication preferences.
        """
        from apps.volunteers.models import Volunteer, VolunteerAssignment, AssignmentStatus
        from apps.volunteers.tasks import send_assignment_reminder
        from apps.events.models import Event, EventSchedule
        
        # Create volunteer and assignment
        volunteer = Volunteer.objects.create(
            member=self.member_a2,  # member_a2 has email_enabled=False
            branch=self.branch_a,
        )
        
        event = Event.objects.create(
            branch=self.branch_a,
            title="Test Event",
        )
        
        schedule = EventSchedule.objects.create(
            event=event,
            occurrence_start=timezone.now() + timedelta(hours=2),
        )
        
        assignment = VolunteerAssignment.objects.create(
            volunteer=volunteer,
            event_schedule=schedule,
            status=AssignmentStatus.CONFIRMED,
        )
        
        # Send reminder
        send_assignment_reminder(str(assignment.id))
        
        # Should NOT send notification (email disabled)
        self.assertFalse(mock_deliver.called)
        
        # Should mark as reminded to prevent retry
        assignment.refresh_from_db()
        self.assertIsNotNone(assignment.reminder_sent_at)


class IDORTests(Phase10SecurityTestCase):
    """
    Test Fix #3: IDOR in delivery-status endpoint
    
    Vulnerability: Branch scoping not enforced on delivery-status
    Fix: get_object() enforces branch scoping via BranchScopedQuerysetMixin
    """
    
    def test_delivery_status_respects_branch_scoping(self):
        """
        Staff should only see delivery status for announcements in their scope.
        """
        announcement_a = Announcement.objects.create(
            branch=self.branch_a,
            title="Branch A Announcement",
            body="Test",
            status=AnnouncementStatus.COMPLETED,
            created_by=self.staff_a,
        )
        
        announcement_b = Announcement.objects.create(
            branch=self.branch_b,
            title="Branch B Announcement",
            body="Test",
            status=AnnouncementStatus.COMPLETED,
            created_by=self.staff_b,
        )
        
        # staff_a should access branch_a announcement
        self.client.force_authenticate(user=self.staff_a)
        response = self.client.get(
            f'/api/v1/communications/announcements/{announcement_a.id}/delivery-status/'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # staff_a should NOT access branch_b announcement
        response = self.client.get(
            f'/api/v1/communications/announcements/{announcement_b.id}/delivery-status/'
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class CrossBranchTargetingTests(Phase10SecurityTestCase):
    """
    Test Fix #4: Cross-branch announcement targeting
    
    Vulnerability: Staff could create announcements targeting other branches
    Fix: Branch scoping enforced in views and services
    """
    
    def test_cannot_create_announcement_for_other_branch(self):
        """
        Staff should only create announcements for branches in their scope.
        """
        self.client.force_authenticate(user=self.staff_a)
        
        # Try to create announcement for branch_b
        response = self.client.post('/api/v1/communications/announcements/', {
            'branch': self.branch_b.id,
            'title': 'Unauthorized Announcement',
            'body': 'Test',
            'audience_type': AudienceType.EVERYONE,
        })
        
        # Should fail validation (branch not in accessible scope)
        self.assertIn(response.status_code, [status.HTTP_400_BAD_REQUEST, status.HTTP_403_FORBIDDEN])
    
    def test_cannot_target_groups_from_other_branch(self):
        """
        CUSTOM audience should only allow groups from same branch.
        """
        self.client.force_authenticate(user=self.staff_a)
        
        response = self.client.post('/api/v1/communications/announcements/', {
            'branch': self.branch_a.id,
            'title': 'Test',
            'body': 'Test',
            'audience_type': AudienceType.CUSTOM,
            'target_groups': [self.group_b.id],  # Group from branch_b!
        })
        
        # Should fail validation
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class MassAssignmentTests(Phase10SecurityTestCase):
    """
    Test Fix #5: Mass assignment on server-controlled fields
    
    Vulnerability: Clients could set status, timestamps, failure_reason
    Fix: Marked read_only in serializer
    """
    
    def test_cannot_set_status_on_create(self):
        """
        Status should always be DRAFT on creation, not client-controlled.
        """
        self.client.force_authenticate(user=self.staff_a)
        
        response = self.client.post('/api/v1/communications/announcements/', {
            'branch': self.branch_a.id,
            'title': 'Test',
            'body': 'Test',
            'audience_type': AudienceType.EVERYONE,
            'status': AnnouncementStatus.COMPLETED,  # Try to bypass lifecycle
        })
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        # Status should be DRAFT regardless of input
        announcement = Announcement.objects.get(id=response.data['data']['id'])
        self.assertEqual(announcement.status, AnnouncementStatus.DRAFT)
    
    def test_cannot_set_timestamps_on_update(self):
        """
        Lifecycle timestamps should not be client-writable.
        """
        announcement = Announcement.objects.create(
            branch=self.branch_a,
            title="Test",
            body="Test",
            status=AnnouncementStatus.DRAFT,
            created_by=self.staff_a,
        )
        
        self.client.force_authenticate(user=self.staff_a)
        
        fake_time = timezone.now() - timedelta(days=10)
        response = self.client.patch(
            f'/api/v1/communications/announcements/{announcement.id}/',
            {
                'sending_started_at': fake_time.isoformat(),
                'completed_at': fake_time.isoformat(),
            }
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Timestamps should remain None (not set by client)
        announcement.refresh_from_db()
        self.assertIsNone(announcement.sending_started_at)
        self.assertIsNone(announcement.completed_at)


class IdempotencyTests(Phase10SecurityTestCase):
    """
    Test Fix #6: No idempotency protection in dispatch
    
    Vulnerability: Dispatching twice sent duplicate notifications
    Fix: select_for_update() + status check prevents re-dispatch
    """
    
    @patch('apps.notifications.tasks.send_notification_to_members.delay')
    def test_dispatch_is_idempotent(self, mock_notify):
        """
        Dispatching the same announcement twice should not send duplicates.
        """
        announcement = Announcement.objects.create(
            branch=self.branch_a,
            title="Test",
            body="Test",
            audience_type=AudienceType.EVERYONE,
            status=AnnouncementStatus.QUEUED,
            created_by=self.staff_a,
        )
        
        # First dispatch
        result1 = dispatch_announcement(str(announcement.id))
        self.assertEqual(result1['status'], 'completed')
        
        # Reset mock
        mock_notify.reset_mock()
        
        # Second dispatch (should skip)
        result2 = dispatch_announcement(str(announcement.id))
        self.assertEqual(result2['status'], 'skipped')
        self.assertEqual(result2['reason'], 'not in QUEUED status')
        
        # Notification should NOT be sent again
        self.assertFalse(mock_notify.called)


class LifecycleTests(Phase10SecurityTestCase):
    """
    Test Fix #7: Lifecycle state violations
    
    Vulnerability: No validation of state transitions
    Fix: Views enforce DRAFT-only updates, publish validates state
    """
    
    def test_cannot_update_published_announcement(self):
        """
        Only DRAFT announcements can be updated.
        """
        announcement = Announcement.objects.create(
            branch=self.branch_a,
            title="Test",
            body="Test",
            status=AnnouncementStatus.COMPLETED,
            created_by=self.staff_a,
        )
        
        self.client.force_authenticate(user=self.staff_a)
        
        response = self.client.patch(
            f'/api/v1/communications/announcements/{announcement.id}/',
            {'title': 'Updated Title'}
        )
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('Cannot update announcement', str(response.data))
    
    def test_cannot_publish_non_draft_announcement(self):
        """
        Only DRAFT announcements can be published.
        """
        announcement = Announcement.objects.create(
            branch=self.branch_a,
            title="Test",
            body="Test",
            status=AnnouncementStatus.COMPLETED,
            created_by=self.staff_a,
        )
        
        self.client.force_authenticate(user=self.staff_a)
        
        response = self.client.post(
            f'/api/v1/communications/announcements/{announcement.id}/publish/'
        )
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('Cannot publish', str(response.data))
    
    def test_cannot_cancel_completed_announcement(self):
        """
        COMPLETED announcements cannot be cancelled (historical protection).
        """
        announcement = Announcement.objects.create(
            branch=self.branch_a,
            title="Test",
            body="Test",
            status=AnnouncementStatus.COMPLETED,
            created_by=self.staff_a,
        )
        
        self.client.force_authenticate(user=self.staff_a)
        
        response = self.client.post(
            f'/api/v1/communications/announcements/{announcement.id}/cancel/',
            {'reason': 'Test cancellation'}
        )
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('Cannot cancel', str(response.data))
    
    @patch('apps.communications.tasks.dispatch_announcement.delay')
    def test_publish_transitions_to_queued(self, mock_dispatch):
        """
        Publishing should transition DRAFT -> QUEUED and queue dispatch task.
        """
        announcement = Announcement.objects.create(
            branch=self.branch_a,
            title="Test",
            body="Test",
            status=AnnouncementStatus.DRAFT,
            created_by=self.staff_a,
            audience_type=AudienceType.EVERYONE,
        )
        
        self.client.force_authenticate(user=self.staff_a)
        
        response = self.client.post(
            f'/api/v1/communications/announcements/{announcement.id}/publish/'
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Verify status changed
        announcement.refresh_from_db()
        self.assertEqual(announcement.status, AnnouncementStatus.QUEUED)
        
        # Verify dispatch task queued
        self.assertTrue(mock_dispatch.called)


class CommunicationPreferenceTests(Phase10SecurityTestCase):
    """
    Test CommunicationPreference viewset security.
    """
    
    def test_member_can_view_own_preferences(self):
        """
        Members should see only their own preferences.
        """
        self.client.force_authenticate(user=self.member_a1_user)
        
        response = self.client.get('/api/v1/communications/preferences/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['data']), 1)
        self.assertEqual(response.data['data'][0]['member'], self.member_a1.id)
    
    def test_member_can_update_own_preferences(self):
        """
        Members can change their own notification preferences.
        """
        self.client.force_authenticate(user=self.member_a1_user)
        
        response = self.client.patch(
            f'/api/v1/communications/preferences/{self.pref_a1.id}/',
            {
                'email_enabled': False,
                'announcements_enabled': False,
            }
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        self.pref_a1.refresh_from_db()
        self.assertFalse(self.pref_a1.email_enabled)
        self.assertFalse(self.pref_a1.announcements_enabled)
    
    def test_cannot_change_preference_member(self):
        """
        Member field is immutable after creation.
        """
        self.client.force_authenticate(user=self.member_a1_user)
        
        response = self.client.patch(
            f'/api/v1/communications/preferences/{self.pref_a1.id}/',
            {'member': self.member_a2.id}  # Try to change member
        )
        
        # Update should succeed but member unchanged
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        self.pref_a1.refresh_from_db()
        self.assertEqual(self.pref_a1.member, self.member_a1)
