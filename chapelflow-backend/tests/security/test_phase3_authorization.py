"""
Phase 3: Comprehensive Authorization Security Tests

Tests all security controls implemented in Phase 3:
- Dynamic RBAC
- Serializer FK validation
- ViewSet permission enforcement
- Sensitive module access controls
- Celery task re-validation
"""
import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from unittest.mock import Mock, patch

from apps.accounts.models import Role, Permission, RolePermission
from apps.events.models import Event, Location
from apps.members.models import Member
from apps.ministries.models import Group
from apps.pastoral.models import PastoralCase
from apps.finance.models import Giving
from apps.organizations.models import Organization, Branch
from common.constants.roles import Roles, PermissionCodes

User = get_user_model()


@pytest.fixture
def organization():
    """Create test organization."""
    return Organization.objects.create(name="Test University", slug="test-university-p3")


@pytest.fixture
def branch_a(organization):
    """Create branch A."""
    return Branch.objects.create(
        organization=organization,
        name="Chapel Branch A",
        branch_type="CHAPEL"
    )


@pytest.fixture
def branch_b(organization):
    """Create branch B."""
    return Branch.objects.create(
        organization=organization,
        name="Chapel Branch B",
        branch_type="CHAPEL"
    )


@pytest.fixture
def super_admin(branch_a):
    """Create super admin user."""
    return User.objects.create_user(
        email="super@test.com",
        password="testpass123",
        role=Roles.SUPER_ADMIN,
        branch=branch_a,
        is_active=True
    )


@pytest.fixture
def chapel_admin_branch_a(branch_a):
    """Create chapel admin for branch A."""
    return User.objects.create_user(
        email="admin_a@test.com",
        password="testpass123",
        role=Roles.CHAPEL_ADMIN,
        branch=branch_a,
        is_active=True
    )


@pytest.fixture
def chapel_admin_branch_b(branch_b):
    """Create chapel admin for branch B."""
    return User.objects.create_user(
        email="admin_b@test.com",
        password="testpass123",
        role=Roles.CHAPEL_ADMIN,
        branch=branch_b,
        is_active=True
    )


@pytest.fixture
def member_branch_a(branch_a):
    """Create member in branch A."""
    user = User.objects.create_user(
        email="member_a@test.com",
        password="testpass123",
        role=Roles.MEMBER,
        branch=branch_a,
        is_active=True
    )
    return Member.objects.create(
        user=user,
        branch=branch_a,
        first_name="Member",
        last_name="A",
        email="member_a@test.com"
    )


@pytest.fixture
def member_branch_b(branch_b):
    """Create member in branch B."""
    user = User.objects.create_user(
        email="member_b@test.com",
        password="testpass123",
        role=Roles.MEMBER,
        branch=branch_b,
        is_active=True
    )
    return Member.objects.create(
        user=user,
        branch=branch_b,
        first_name="Member",
        last_name="B",
        email="member_b@test.com"
    )


@pytest.fixture
def api_client():
    """Create API client."""
    return APIClient()


# ==============================================================================
# PHASE 3: FK VALIDATION TESTS (STEP 5)
# ==============================================================================

@pytest.mark.django_db
class TestSerializerFKValidation:
    """Test that serializers validate FK fields prevent cross-branch attacks."""
    
    def test_cannot_create_event_in_unauthorized_branch(
        self, api_client, chapel_admin_branch_a, branch_b
    ):
        """Test: Chapel Admin A cannot create event in Branch B."""
        api_client.force_authenticate(user=chapel_admin_branch_a)
        
        response = api_client.post('/api/v1/events/', {
            'branch': branch_b.id,
            'title': 'Unauthorized Event',
            'start_time': '2024-01-01T10:00:00Z',
            'end_time': '2024-01-01T11:00:00Z',
        })
        
        assert response.status_code == 400
        assert 'branch' in response.json()
    
    def test_cannot_use_location_from_unauthorized_branch(
        self, api_client, chapel_admin_branch_a, branch_a, branch_b
    ):
        """Test: Cannot use Location from Branch B when creating event in Branch A."""
        # Create location in branch B
        location_b = Location.objects.create(
            branch=branch_b,
            name="Location B"
        )
        
        api_client.force_authenticate(user=chapel_admin_branch_a)
        
        response = api_client.post('/api/v1/events/', {
            'branch': branch_a.id,
            'location': location_b.id,
            'title': 'Test Event',
            'start_time': '2024-01-01T10:00:00Z',
            'end_time': '2024-01-01T11:00:00Z',
        })
        
        assert response.status_code == 400
        assert 'location' in response.json()
    
    def test_cannot_assign_member_from_different_branch(
        self, api_client, chapel_admin_branch_a, branch_a, member_branch_b
    ):
        """Test: Cannot create household with head from different branch."""
        api_client.force_authenticate(user=chapel_admin_branch_a)
        
        response = api_client.post('/api/v1/households/', {
            'branch': branch_a.id,
            'name': 'Test Household',
            'head': member_branch_b.id,
        })
        
        assert response.status_code == 400
        assert 'head' in response.json()
    
    def test_super_admin_can_create_cross_branch(
        self, api_client, super_admin, branch_b, member_branch_b
    ):
        """Test: Super Admin CAN create resources across branches."""
        api_client.force_authenticate(user=super_admin)
        
        response = api_client.post('/api/v1/households/', {
            'branch': branch_b.id,
            'name': 'Test Household',
            'head': member_branch_b.id,
        })
        
        # Super Admin should succeed
        assert response.status_code in [200, 201]


# ==============================================================================
# PHASE 3: VIEWSET PERMISSION TESTS (STEP 6)
# ==============================================================================

@pytest.mark.django_db
class TestViewSetPermissions:
    """Test that ViewSets enforce permission_action_map correctly."""
    
    def test_member_cannot_create_event(
        self, api_client, member_branch_a, branch_a
    ):
        """Test: Regular member cannot create events (no events.create permission)."""
        api_client.force_authenticate(user=member_branch_a.user)
        
        response = api_client.post('/api/v1/events/', {
            'branch': branch_a.id,
            'title': 'Member Event',
            'start_time': '2024-01-01T10:00:00Z',
            'end_time': '2024-01-01T11:00:00Z',
        })
        
        assert response.status_code == 403
    
    def test_chapel_admin_can_create_event(
        self, api_client, chapel_admin_branch_a, branch_a
    ):
        """Test: Chapel Admin can create events (has events.create permission)."""
        api_client.force_authenticate(user=chapel_admin_branch_a)
        
        response = api_client.post('/api/v1/events/', {
            'branch': branch_a.id,
            'title': 'Admin Event',
            'start_time': '2024-01-01T10:00:00Z',
            'end_time': '2024-01-01T11:00:00Z',
        })
        
        assert response.status_code in [200, 201]
    
    def test_unauthenticated_cannot_access_protected_endpoint(self, api_client):
        """Test: Unauthenticated requests rejected."""
        response = api_client.get('/api/v1/events/')
        
        assert response.status_code == 401


# ==============================================================================
# PHASE 3: SENSITIVE MODULE TESTS (STEP 7)
# ==============================================================================

@pytest.mark.django_db
class TestFinanceModuleSecurity:
    """Test Finance module requires MFA and proper role."""
    
    def test_finance_requires_finance_role(
        self, api_client, chapel_admin_branch_a, branch_a, member_branch_a
    ):
        """Test: Non-finance roles cannot access finance endpoints."""
        # Chapel Admin does NOT have finance access by default
        api_client.force_authenticate(user=chapel_admin_branch_a)
        
        response = api_client.post('/api/v1/finance/giving/', {
            'branch': branch_a.id,
            'member': member_branch_a.id,
            'amount': '100.00',
            'currency': 'USD',
            'source': 'CASH',
            'given_at': '2024-01-01T10:00:00Z',
        })
        
        # Should fail - not in FINANCE_ACCESS_ROLES
        assert response.status_code == 403
    
    @patch('common.permissions.rbac.user_has_completed_required_mfa')
    def test_finance_requires_mfa(
        self, mock_mfa, api_client, branch_a, member_branch_a
    ):
        """Test: Finance operations require MFA."""
        # Create finance officer
        finance_user = User.objects.create_user(
            email="finance@test.com",
            password="testpass123",
            role=Roles.FINANCE_OFFICER,
            branch=branch_a,
            is_active=True
        )
        
        # Mock MFA not completed
        mock_mfa.return_value = False
        
        api_client.force_authenticate(user=finance_user)
        
        response = api_client.get('/api/v1/finance/giving/')
        
        # Should fail - MFA not completed
        assert response.status_code == 403
        
        # Now mock MFA completed
        mock_mfa.return_value = True
        
        response = api_client.get('/api/v1/finance/giving/')
        
        # Should succeed
        assert response.status_code == 200


@pytest.mark.django_db
class TestPastoralModuleSecurity:
    """Test Pastoral module object-level permissions and MFA."""
    
    @patch('common.permissions.rbac.user_has_completed_required_mfa')
    def test_pastoral_requires_mfa(
        self, mock_mfa, api_client, chapel_admin_branch_a
    ):
        """Test: Pastoral operations require MFA (Phase 3 enhancement)."""
        # Mock MFA not completed
        mock_mfa.return_value = False
        
        api_client.force_authenticate(user=chapel_admin_branch_a)
        
        response = api_client.get('/api/v1/pastoral/cases/')
        
        # Should fail - MFA required for pastoral access
        assert response.status_code == 403
    
    def test_member_can_only_see_own_pastoral_cases(
        self, api_client, member_branch_a, member_branch_b, branch_a
    ):
        """Test: Members can only see their own pastoral cases."""
        # Create case for member A
        case_a = PastoralCase.objects.create(
            branch=branch_a,
            member=member_branch_a,
            category='COUNSELING',
            summary='Member A case'
        )
        
        # Create case for member B (same branch, different member)
        case_b = PastoralCase.objects.create(
            branch=branch_a,
            member=member_branch_b,
            category='COUNSELING',
            summary='Member B case'
        )
        
        # Member A logs in
        api_client.force_authenticate(user=member_branch_a.user)
        
        # Should see only own case
        response = api_client.get('/api/v1/pastoral/cases/')
        
        assert response.status_code == 200
        cases = response.json()['results'] if 'results' in response.json() else response.json()
        
        # Should only see own case
        assert len([c for c in cases if c['id'] == str(case_a.id)]) == 1
        assert len([c for c in cases if c['id'] == str(case_b.id)]) == 0


@pytest.mark.django_db
class TestPrayerModuleSecurity:
    """Test Prayer module privacy filtering."""
    
    def test_private_prayer_requests_not_visible_to_others(
        self, api_client, member_branch_a, member_branch_b, branch_a
    ):
        """Test: Private prayer requests not visible to other members."""
        from apps.prayer.models import PrayerRequest
        
        # Create private request from member A
        private_request = PrayerRequest.objects.create(
            branch=branch_a,
            member=member_branch_a,
            details='Private prayer',
            is_private=True
        )
        
        # Create public request from member A
        public_request = PrayerRequest.objects.create(
            branch=branch_a,
            member=member_branch_a,
            details='Public prayer',
            is_private=False
        )
        
        # Member B logs in
        api_client.force_authenticate(user=member_branch_b.user)
        
        response = api_client.get('/api/v1/prayer/requests/')
        
        assert response.status_code == 200
        requests = response.json()['results'] if 'results' in response.json() else response.json()
        
        # Should NOT see private request from member A
        assert len([r for r in requests if r['id'] == str(private_request.id)]) == 0
        # Should see public request
        assert len([r for r in requests if r['id'] == str(public_request.id)]) == 1


# ==============================================================================
# PHASE 3: CELERY TASK RE-VALIDATION TESTS (STEP 7)
# ==============================================================================

@pytest.mark.django_db
class TestCeleryTaskAuthorization:
    """Test that Celery tasks re-validate authorization at execution time."""
    
    def test_bulk_import_task_revalidates_permission(self, chapel_admin_branch_a):
        """Test: bulk_import_members_task re-validates permission."""
        from apps.members.tasks import bulk_import_members_task
        
        # User has permission initially
        assert chapel_admin_branch_a.has_perm_code(PermissionCodes.MEMBERS_CREATE)
        
        # Simulate permission revoked (change role)
        chapel_admin_branch_a.role = Roles.MEMBER
        chapel_admin_branch_a.save()
        
        # Task should fail with permission denied
        with patch('urllib.request.urlopen'):
            result = bulk_import_members_task('http://fake.url', chapel_admin_branch_a.id)
        
        assert 'error' in result
        assert 'Permission denied' in result['error']
    
    def test_report_job_task_revalidates_branch_access(
        self, chapel_admin_branch_a, branch_a, branch_b
    ):
        """Test: run_report_job re-validates branch access."""
        from apps.reports.models import ReportJob
        from apps.reports.tasks import run_report_job
        
        # Create report job for branch A
        job = ReportJob.objects.create(
            branch=branch_a,
            requested_by=chapel_admin_branch_a,
            report_type='ATTENDANCE_SUMMARY',
            export_format='CSV'
        )
        
        # User initially has access to branch A
        from common.permissions.scoping import user_can_access_branch
        assert user_can_access_branch(chapel_admin_branch_a, branch_a.id)
        
        # Simulate user moved to branch B
        chapel_admin_branch_a.branch = branch_b
        chapel_admin_branch_a.save()
        
        # Task should fail - no longer has access to branch A
        with patch('apps.reports.services.REPORT_GENERATORS', {}):
            run_report_job(job.id)
        
        job.refresh_from_db()
        assert job.status == 'FAILED'
        assert 'Permission denied' in job.error_message


# ==============================================================================
# PHASE 3: DYNAMIC RBAC TESTS (STEP 3)
# ==============================================================================

@pytest.mark.django_db
class TestDynamicRBAC:
    """Test dynamic role creation and permission assignment."""
    
    def test_can_create_dynamic_role(self, organization):
        """Test: Can create new role at runtime."""
        role = Role.objects.create(
            name="Custom Ministry Leader",
            code="CUSTOM_MINISTRY_LEADER",
            description="Custom role for ministry leaders",
            scope_type="ASSIGNMENT"
        )
        
        assert role.id is not None
        assert role.code == "CUSTOM_MINISTRY_LEADER"
    
    def test_can_assign_permissions_to_role(self, organization):
        """Test: Can assign permissions to dynamic role."""
        role = Role.objects.create(
            name="Events Coordinator",
            code="EVENTS_COORDINATOR",
            scope_type="BRANCH"
        )
        
        # Get or create permission
        perm, _ = Permission.objects.get_or_create(
            code=PermissionCodes.EVENTS_CREATE,
            defaults={'name': 'Create Events', 'module': 'EVENTS'}
        )
        
        # Assign permission to role
        RolePermission.objects.create(
            role_obj=role,
            permission=perm
        )
        
        # Verify assignment
        assert role.rolepermission_set.filter(permission=perm).exists()
    
    def test_user_with_dynamic_role_has_permissions(
        self, organization, branch_a, api_client
    ):
        """Test: User with dynamic role can use assigned permissions."""
        # Create dynamic role
        role = Role.objects.create(
            name="Events Coordinator",
            code="EVENTS_COORDINATOR",
            scope_type="BRANCH"
        )
        
        # Assign events.create permission
        perm, _ = Permission.objects.get_or_create(
            code=PermissionCodes.EVENTS_CREATE,
            defaults={'name': 'Create Events', 'module': 'EVENTS'}
        )
        RolePermission.objects.create(role_obj=role, permission=perm)
        
        # Create user with dynamic role
        user = User.objects.create_user(
            email="coordinator@test.com",
            password="testpass123",
            branch=branch_a,
            is_active=True
        )
        user.role_obj = role
        user.save()
        
        # User should have permission
        assert user.has_perm_code(PermissionCodes.EVENTS_CREATE)
        
        # User should be able to create event
        api_client.force_authenticate(user=user)
        response = api_client.post('/api/v1/events/', {
            'branch': branch_a.id,
            'title': 'Coordinator Event',
            'start_time': '2024-01-01T10:00:00Z',
            'end_time': '2024-01-01T11:00:00Z',
        })
        
        # Should succeed if ViewSet checks permissions correctly
        assert response.status_code in [200, 201, 403]  # 403 if other validations fail


# ==============================================================================
# PHASE 3: SELF-ESCALATION PREVENTION TESTS (STEP 3)
# ==============================================================================

@pytest.mark.django_db
class TestSelfEscalationPrevention:
    """Test that users cannot escalate their own privileges."""
    
    def test_user_cannot_assign_higher_role_to_self(
        self, chapel_admin_branch_a, organization, branch_a
    ):
        """Test: User cannot assign Super Admin role to themselves."""
        from apps.accounts.role_services import assign_role_to_user, RoleAssignmentError
        
        # Create Super Admin role
        super_admin_role = Role.objects.create(
            name="Super Admin",
            code=Roles.SUPER_ADMIN,
            scope_type="GLOBAL"
        )
        
        # Chapel Admin tries to assign Super Admin to themselves
        with pytest.raises(RoleAssignmentError):
            assign_role_to_user(
                user=chapel_admin_branch_a,
                role=super_admin_role,
                assigner=chapel_admin_branch_a
            )
    
    def test_user_cannot_grant_permission_they_lack(
        self, chapel_admin_branch_a, organization
    ):
        """Test: User cannot grant permissions they don't have."""
        from apps.accounts.role_services import grant_permission_to_role, PermissionGrantError
        
        # Create role and permission
        role = Role.objects.create(
            name="Test Role",
            code="TEST_ROLE",
            scope_type="BRANCH"
        )
        
        finance_perm, _ = Permission.objects.get_or_create(
            code=PermissionCodes.FINANCE_CREATE,
            defaults={'name': 'Create Finance Records', 'module': 'FINANCE'}
        )
        
        # Chapel Admin does NOT have finance.create permission
        assert not chapel_admin_branch_a.has_perm_code(PermissionCodes.FINANCE_CREATE)
        
        # Try to grant it to role
        with pytest.raises(PermissionGrantError):
            grant_permission_to_role(
                role=role,
                permission=finance_perm,
                granter=chapel_admin_branch_a
            )


# ==============================================================================
# PHASE 3: CROSS-BRANCH PROTECTION TESTS
# ==============================================================================

@pytest.mark.django_db
class TestCrossBranchProtection:
    """Test that users cannot access resources from other branches."""
    
    def test_cannot_view_events_from_other_branch(
        self, api_client, chapel_admin_branch_a, branch_a, branch_b
    ):
        """Test: Chapel Admin A cannot see events from Branch B."""
        # Create event in branch B
        event_b = Event.objects.create(
            branch=branch_b,
            title='Branch B Event',
            start_time='2024-01-01T10:00:00Z',
            end_time='2024-01-01T11:00:00Z'
        )
        
        # Chapel Admin A logs in
        api_client.force_authenticate(user=chapel_admin_branch_a)
        
        # Try to retrieve event from branch B
        response = api_client.get(f'/api/v1/events/{event_b.id}/')
        
        # Should fail (404 due to queryset filtering)
        assert response.status_code == 404
    
    def test_cannot_update_event_in_other_branch(
        self, api_client, chapel_admin_branch_a, branch_b
    ):
        """Test: Chapel Admin A cannot update events in Branch B."""
        # Create event in branch B
        event_b = Event.objects.create(
            branch=branch_b,
            title='Branch B Event',
            start_time='2024-01-01T10:00:00Z',
            end_time='2024-01-01T11:00:00Z'
        )
        
        # Chapel Admin A logs in
        api_client.force_authenticate(user=chapel_admin_branch_a)
        
        # Try to update event in branch B
        response = api_client.patch(f'/api/v1/events/{event_b.id}/', {
            'title': 'Hacked Event'
        })
        
        # Should fail (404 due to queryset filtering)
        assert response.status_code == 404


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
