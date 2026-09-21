"""
Phase 11: Member Follow-Up Security Tests

Tests security controls for:
- MemberFollowUp IDOR prevention
- Cross-branch access prevention
- Assignment authorization
- Scope filtering (pastoral vs assigned staff)
"""
import pytest
from datetime import timedelta
from django.utils import timezone
from django.contrib.auth import get_user_model

from apps.members.models import Member, MemberFollowUp, MembershipStatus, MemberFollowUpMilestone
from apps.organizations.models import Branch, Organization
from common.constants.roles import Roles, PermissionCodes

User = get_user_model()


@pytest.mark.django_db
class TestMemberFollowUpSecurity:
    """Security tests for MemberFollowUp model and API."""
    
    @pytest.fixture
    def branches(self):
        """Create two branches for isolation testing."""
        _org_1 = Organization.objects.create(name="Branch A Org", slug="branch-81484132")
        branch_a = Branch.objects.create(name="Branch A", organization=_org_1)
        _org_2 = Organization.objects.create(name="Branch B Org", slug="branch-8ac329f8")
        branch_b = Branch.objects.create(name="Branch B", organization=_org_2)
        return branch_a, branch_b
    
    @pytest.fixture
    def users(self, branches):
        """Create users in different branches with different roles."""
        branch_a, branch_b = branches
        
        # Branch A users
        pastoral_a = User.objects.create_user(
            email="pastoral_a@test.com",
            password="test123",
            role=Roles.PASTOR,
            branch=branch_a
        )
        
        staff_a = User.objects.create_user(
            email="staff_a@test.com",
            password="test123",
            role=Roles.CHAPEL_ADMIN,
            branch=branch_a
        )
        
        # Branch B users
        pastoral_b = User.objects.create_user(
            email="pastoral_b@test.com",
            password="test123",
            role=Roles.PASTOR,
            branch=branch_b
        )
        
        return {
            'pastoral_a': pastoral_a,
            'staff_a': staff_a,
            'pastoral_b': pastoral_b
        }
    
    @pytest.fixture
    def members(self, branches, users):
        """Create members in different branches."""
        branch_a, branch_b = branches
        
        member_a = Member.objects.create(
            branch=branch_a,
            first_name="Alice",
            last_name="Anderson",
            email="alice@test.com",
            membership_status=MembershipStatus.ACTIVE
        )
        
        member_b = Member.objects.create(
            branch=branch_b,
            first_name="Bob",
            last_name="Brown",
            email="bob@test.com",
            membership_status=MembershipStatus.ACTIVE
        )
        
        return member_a, member_b
    
    @pytest.fixture
    def follow_ups(self, members, users):
        """Create follow-up records."""
        member_a, member_b = members
        
        # Follow-up in Branch A
        followup_a = MemberFollowUp.objects.create(
            member=member_a,
            milestone=MemberFollowUpMilestone.DAY_7,
            assigned_to=users['pastoral_a'],
            scheduled_for=timezone.now() + timedelta(days=7),
            notes="Test follow-up A"
        )
        
        # Follow-up in Branch B
        followup_b = MemberFollowUp.objects.create(
            member=member_b,
            milestone=MemberFollowUpMilestone.DAY_7,
            assigned_to=users['pastoral_b'],
            scheduled_for=timezone.now() + timedelta(days=7),
            notes="Test follow-up B"
        )
        
        return followup_a, followup_b
    
    def test_cross_branch_access_denied(self, client, users, follow_ups):
        """Test that pastoral staff cannot access follow-ups from other branches."""
        followup_a, followup_b = follow_ups
        
        # Login as Branch A pastoral staff
        client.force_login(users['pastoral_a'])
        
        # Try to access Branch B follow-up
        response = client.get(f'/api/members/follow-ups/{followup_b.id}/')
        
        # Should be 404 (filtered out by queryset) or 403
        assert response.status_code in [403, 404], \
            "Pastoral staff should not access follow-ups from other branches"
    
    def test_assigned_staff_can_view_own_assignment(self, client, users, members):
        """Test that assigned staff can view their own follow-up assignments."""
        member_a, _ = members
        
        # Create follow-up assigned to staff_a
        followup = MemberFollowUp.objects.create(
            member=member_a,
            milestone=MemberFollowUpMilestone.DAY_30,
            assigned_to=users['staff_a'],
            scheduled_for=timezone.now() + timedelta(days=30)
        )
        
        # Login as assigned staff
        client.force_login(users['staff_a'])
        
        # Should be able to view
        response = client.get(f'/api/members/follow-ups/{followup.id}/')
        assert response.status_code == 200, \
            "Assigned staff should view their own assignments"
    
    def test_unassigned_staff_cannot_view_others_assignments(self, client, branches, users, members):
        """Test that staff cannot view follow-ups assigned to others (unless pastoral)."""
        branch_a, _ = branches
        member_a, _ = members
        
        # Create another staff member
        other_staff = User.objects.create_user(
            email="other@test.com",
            password="test123",
            role=Roles.CHAPEL_ADMIN,
            branch=branch_a
        )
        
        # Create follow-up assigned to pastoral_a
        followup = MemberFollowUp.objects.create(
            member=member_a,
            milestone=MemberFollowUpMilestone.DAY_90,
            assigned_to=users['pastoral_a'],
            scheduled_for=timezone.now() + timedelta(days=90)
        )
        
        # Login as other_staff (not assigned, not pastoral role)
        client.force_login(other_staff)
        
        # Should not see in list
        response = client.get('/api/members/follow-ups/')
        assert response.status_code == 200
        assert followup.id not in [f['id'] for f in response.data.get('results', [])], \
            "Unassigned staff should not see others' assignments"
    
    def test_cannot_reassign_to_other_branch(self, client, users, follow_ups):
        """Test that follow-ups cannot be reassigned to staff from different branch."""
        followup_a, _ = follow_ups
        
        # Login as Branch A pastoral staff
        client.force_login(users['pastoral_a'])
        
        # Try to reassign to Branch B pastoral staff
        response = client.patch(
            f'/api/members/follow-ups/{followup_a.id}/',
            data={'assigned_to': str(users['pastoral_b'].id)},
            content_type='application/json'
        )
        
        # Should fail validation
        assert response.status_code == 400, \
            "Cannot reassign follow-up to staff from different branch"
        assert 'assigned_to' in response.data or 'same branch' in str(response.data).lower()
    
    def test_cannot_change_member_or_milestone(self, client, users, follow_ups, members):
        """Test that member and milestone are read-only (cannot be changed via API)."""
        followup_a, _ = follow_ups
        _, member_b = members
        
        # Login as pastoral staff
        client.force_login(users['pastoral_a'])
        
        # Try to change member
        response = client.patch(
            f'/api/members/follow-ups/{followup_a.id}/',
            data={'member': str(member_b.id)},
            content_type='application/json'
        )
        
        # Should succeed but member unchanged (read-only field ignored)
        followup_a.refresh_from_db()
        assert followup_a.member.id != member_b.id, \
            "Member field should be read-only"
        
        # Try to change milestone
        response = client.patch(
            f'/api/members/follow-ups/{followup_a.id}/',
            data={'milestone': MemberFollowUpMilestone.DAY_90},
            content_type='application/json'
        )
        
        followup_a.refresh_from_db()
        assert followup_a.milestone == MemberFollowUpMilestone.DAY_7, \
            "Milestone field should be read-only"
    
    def test_cannot_create_followup_via_api(self, client, users, members):
        """Test that follow-ups cannot be created via API (only via signal)."""
        member_a, _ = members
        
        # Login as pastoral staff
        client.force_login(users['pastoral_a'])
        
        # Try to create follow-up
        response = client.post(
            '/api/members/follow-ups/',
            data={
                'member': str(member_a.id),
                'milestone': MemberFollowUpMilestone.DAY_7,
                'scheduled_for': (timezone.now() + timedelta(days=7)).isoformat()
            },
            content_type='application/json'
        )
        
        # Should be 405 Method Not Allowed (POST not in http_method_names)
        assert response.status_code == 405, \
            "Follow-ups should not be created via API"
    
    def test_cannot_delete_followup_via_api(self, client, users, follow_ups):
        """Test that follow-ups cannot be deleted via API."""
        followup_a, _ = follow_ups
        
        # Login as pastoral staff
        client.force_login(users['pastoral_a'])
        
        # Try to delete
        response = client.delete(f'/api/members/follow-ups/{followup_a.id}/')
        
        # Should be 405 Method Not Allowed (DELETE not in http_method_names)
        assert response.status_code == 405, \
            "Follow-ups should not be deletable via API"
    
    def test_pastoral_sees_all_branch_followups(self, client, branches, users, members):
        """Test that pastoral staff see all follow-ups in their branch."""
        branch_a, _ = branches
        member_a, _ = members
        
        # Create follow-ups assigned to different staff
        other_staff = User.objects.create_user(
            email="staffx@test.com",
            password="test123",
            role=Roles.CHAPEL_ADMIN,
            branch=branch_a
        )
        
        followup1 = MemberFollowUp.objects.create(
            member=member_a,
            milestone=MemberFollowUpMilestone.DAY_7,
            assigned_to=users['pastoral_a'],
            scheduled_for=timezone.now() + timedelta(days=7)
        )
        
        followup2 = MemberFollowUp.objects.create(
            member=member_a,
            milestone=MemberFollowUpMilestone.DAY_30,
            assigned_to=other_staff,
            scheduled_for=timezone.now() + timedelta(days=30)
        )
        
        # Login as pastoral staff
        client.force_login(users['pastoral_a'])
        
        # Should see both
        response = client.get('/api/members/follow-ups/')
        assert response.status_code == 200
        
        followup_ids = [f['id'] for f in response.data.get('results', [])]
        assert followup1.id in followup_ids, "Pastoral should see their own assignments"
        assert followup2.id in followup_ids, "Pastoral should see all branch assignments"


@pytest.mark.django_db
class TestEngagementMetricsSecurity:
    """Security tests for EngagementMetrics model and API."""
    
    def test_engagement_metrics_readonly(self, client, branches, users, members):
        """Test that engagement metrics cannot be modified via API."""
        from apps.members.models import EngagementMetrics
        
        branch_a, _ = branches
        member_a, _ = members
        
        # Create metrics
        metrics = EngagementMetrics.objects.create(
            member=member_a,
            engagement_score=75
        )
        
        # Login as pastoral staff
        client.force_login(users['pastoral_a'])
        
        # Try to update
        response = client.patch(
            f'/api/members/engagement/{member_a.id}/',
            data={'engagement_score': 100},
            content_type='application/json'
        )
        
        # Should be 405 (ReadOnlyModelViewSet)
        assert response.status_code == 405, \
            "Engagement metrics should be read-only"
    
    def test_member_can_view_own_metrics_only(self, client, branches, members):
        """Test that regular members can only view their own engagement metrics."""
        from apps.members.models import EngagementMetrics
        
        branch_a, _ = branches
        member_a, member_b = members
        
        # Create user accounts linked to members
        user_a = User.objects.create_user(
            email="user_a@test.com",
            password="test123",
            role=Roles.MEMBER,
            branch=branch_a
        )
        user_a.member_profile = member_a
        user_a.save()
        
        # Create metrics for both
        metrics_a = EngagementMetrics.objects.create(member=member_a, engagement_score=80)
        metrics_b = EngagementMetrics.objects.create(member=member_b, engagement_score=60)
        
        # Login as member A
        client.force_login(user_a)
        
        # Should see own metrics
        response = client.get(f'/api/members/engagement/{member_a.id}/')
        assert response.status_code == 200
        
        # Should not see other member's metrics
        response = client.get(f'/api/members/engagement/{member_b.id}/')
        assert response.status_code in [403, 404], \
            "Members should not view other members' engagement metrics"
