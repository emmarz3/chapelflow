"""
Phase 16: Dashboard security tests.

Tests for:
- Authentication requirements
- Authorization (role-based access)
- IDOR (Insecure Direct Object Reference)
- Organization isolation
- Branch isolation
- Horizontal privilege escalation
- Vertical privilege escalation
- Sensitive data protection
"""
import pytest
from datetime import date, timedelta
from decimal import Decimal
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import Role
from apps.members.models import Member, MembershipStatus
from apps.organizations.models import Organization, Branch
from apps.attendance.models import AttendanceSession, AttendanceRecord
from apps.visitors.models import Visitor
from apps.finance.models import Giving, GivingCategory
from apps.pastoral.models import PastoralCase, PastoralCaseStatus
from apps.prayer.models import PrayerRequest, PrayerRequestStatus
from common.constants.roles import Roles

User = get_user_model()


@pytest.fixture
def organizations(db):
    """Create two separate organizations for isolation testing."""
    org_a = Organization.objects.create(name="Organization A", slug="org-a-p16-security")
    org_b = Organization.objects.create(name="Organization B", slug="org-b-p16-security")
    return {"org_a": org_a, "org_b": org_b}


@pytest.fixture
def branches(organizations):
    """Create branches for each organization."""
    branch_a1 = Branch.objects.create(
        name="Branch A1",
        organization=organizations["org_a"]
    )
    branch_a2 = Branch.objects.create(
        name="Branch A2",
        organization=organizations["org_a"]
    )
    branch_b1 = Branch.objects.create(
        name="Branch B1",
        organization=organizations["org_b"]
    )
    return {
        "branch_a1": branch_a1,
        "branch_a2": branch_a2,
        "branch_b1": branch_b1,
    }


@pytest.fixture
def users(branches):
    """Create users with different roles and scopes."""
    # Organization A users
    super_admin = User.objects.create_user(
        email="superadmin@test.com",
        password="testpass123",
        role=Roles.SUPER_ADMIN,
        branch=branches["branch_a1"],
    )
    
    chaplain_a = User.objects.create_user(
        email="chaplain_a@test.com",
        password="testpass123",
        role=Roles.CHAPLAIN,
        branch=branches["branch_a1"],
    )
    
    admin_a1 = User.objects.create_user(
        email="admin_a1@test.com",
        password="testpass123",
        role=Roles.CHAPEL_ADMIN,
        branch=branches["branch_a1"],
    )
    
    admin_a2 = User.objects.create_user(
        email="admin_a2@test.com",
        password="testpass123",
        role=Roles.CHAPEL_ADMIN,
        branch=branches["branch_a2"],
    )
    
    member_a1 = User.objects.create_user(
        email="member_a1@test.com",
        password="testpass123",
        role=Roles.MEMBER,
        branch=branches["branch_a1"],
    )
    
    # Organization B users
    admin_b1 = User.objects.create_user(
        email="admin_b1@test.com",
        password="testpass123",
        role=Roles.CHAPEL_ADMIN,
        branch=branches["branch_b1"],
    )
    
    member_b1 = User.objects.create_user(
        email="member_b1@test.com",
        password="testpass123",
        role=Roles.MEMBER,
        branch=branches["branch_b1"],
    )
    
    # User without branch
    no_branch_user = User.objects.create_user(
        email="nobranch@test.com",
        password="testpass123",
        role=Roles.MEMBER,
        branch=None,
    )
    
    return {
        "super_admin": super_admin,
        "chaplain_a": chaplain_a,
        "admin_a1": admin_a1,
        "admin_a2": admin_a2,
        "member_a1": member_a1,
        "admin_b1": admin_b1,
        "member_b1": member_b1,
        "no_branch": no_branch_user,
    }


@pytest.fixture
def test_data(branches, users):
    """Create test data in different branches."""
    # Members in Branch A1
    members_a1 = []
    for i in range(5):
        member = Member.objects.create(
            branch=branches["branch_a1"],
            first_name=f"Member_A1_{i}",
            last_name="Test",
            membership_status=MembershipStatus.ACTIVE,
        )
        members_a1.append(member)
    
    # Members in Branch A2
    members_a2 = []
    for i in range(3):
        member = Member.objects.create(
            branch=branches["branch_a2"],
            first_name=f"Member_A2_{i}",
            last_name="Test",
            membership_status=MembershipStatus.ACTIVE,
        )
        members_a2.append(member)
    
    # Members in Branch B1
    members_b1 = []
    for i in range(4):
        member = Member.objects.create(
            branch=branches["branch_b1"],
            first_name=f"Member_B1_{i}",
            last_name="Test",
            membership_status=MembershipStatus.ACTIVE,
        )
        members_b1.append(member)
    
    # Giving data
    category = GivingCategory.objects.create(name="Tithe")
    
    Giving.objects.create(
        branch=branches["branch_a1"],
        member=members_a1[0],
        category=category,
        amount=Decimal("1000.00"),
        given_at=timezone.now(),
    )
    
    Giving.objects.create(
        branch=branches["branch_b1"],
        member=members_b1[0],
        category=category,
        amount=Decimal("2000.00"),
        given_at=timezone.now(),
    )
    
    # Pastoral cases
    PastoralCase.objects.create(
        branch=branches["branch_a1"],
        member=members_a1[0],
        status=PastoralCaseStatus.OPEN,
        assigned_to=users["chaplain_a"],
    )
    
    PastoralCase.objects.create(
        branch=branches["branch_b1"],
        member=members_b1[0],
        status=PastoralCaseStatus.OPEN,
        assigned_to=users["admin_b1"],
    )
    
    return {
        "members_a1": members_a1,
        "members_a2": members_a2,
        "members_b1": members_b1,
    }


# =============================================================================
# AUTHENTICATION TESTS
# =============================================================================

@pytest.mark.django_db
class TestDashboardAuthentication:
    """Test that all dashboard endpoints require authentication."""
    
    def test_admin_dashboard_requires_auth(self):
        """Admin dashboard rejects unauthenticated requests."""
        client = APIClient()
        response = client.get("/api/v1/dashboard/admin/")
        assert response.status_code in [401, 403]
    
    def test_pastor_dashboard_requires_auth(self):
        """Pastor dashboard rejects unauthenticated requests."""
        client = APIClient()
        response = client.get("/api/v1/dashboard/pastor/")
        assert response.status_code in [401, 403]
    
    def test_finance_dashboard_requires_auth(self):
        """Finance dashboard rejects unauthenticated requests."""
        client = APIClient()
        response = client.get("/api/v1/dashboard/finance/")
        assert response.status_code in [401, 403]
    
    def test_executive_dashboard_requires_auth(self):
        """Executive dashboard rejects unauthenticated requests."""
        client = APIClient()
        response = client.get("/api/v1/dashboard/executive/")
        assert response.status_code in [401, 403]
    
    def test_ministry_dashboard_requires_auth(self):
        """Ministry dashboard rejects unauthenticated requests."""
        client = APIClient()
        response = client.get("/api/v1/dashboard/ministry/")
        assert response.status_code in [401, 403]


# =============================================================================
# AUTHORIZATION TESTS
# =============================================================================

@pytest.mark.django_db
class TestDashboardAuthorization:
    """Test role-based access control for dashboards."""
    
    def test_admin_dashboard_requires_admin_role(self, users, test_data):
        """Admin dashboard rejects non-admin users."""
        client = APIClient()
        client.force_authenticate(user=users["member_a1"])
        
        response = client.get("/api/v1/dashboard/admin/")
        assert response.status_code == 403
        assert "not authorized" in response.json()["error"].lower()
    
    def test_admin_dashboard_allows_super_admin(self, users, test_data):
        """Admin dashboard allows super admin."""
        client = APIClient()
        client.force_authenticate(user=users["super_admin"])
        
        response = client.get("/api/v1/dashboard/admin/")
        assert response.status_code == 200
    
    def test_admin_dashboard_allows_chapel_admin(self, users, test_data):
        """Admin dashboard allows chapel admin."""
        client = APIClient()
        client.force_authenticate(user=users["admin_a1"])
        
        response = client.get("/api/v1/dashboard/admin/")
        assert response.status_code == 200
    
    def test_pastor_dashboard_requires_pastoral_role(self, users, test_data):
        """Pastor dashboard rejects non-pastoral users."""
        client = APIClient()
        client.force_authenticate(user=users["member_a1"])
        
        response = client.get("/api/v1/dashboard/pastor/")
        assert response.status_code == 403
    
    def test_pastor_dashboard_allows_chaplain(self, users, test_data):
        """Pastor dashboard allows chaplain."""
        client = APIClient()
        client.force_authenticate(user=users["chaplain_a"])
        
        response = client.get("/api/v1/dashboard/pastor/")
        assert response.status_code == 200
    
    def test_finance_dashboard_requires_finance_role(self, users, test_data):
        """Finance dashboard rejects non-finance users."""
        client = APIClient()
        client.force_authenticate(user=users["member_a1"])
        
        response = client.get("/api/v1/dashboard/finance/")
        assert response.status_code == 403
    
    def test_finance_dashboard_allows_admin(self, users, test_data):
        """Finance dashboard allows chapel admin."""
        client = APIClient()
        client.force_authenticate(user=users["admin_a1"])
        
        response = client.get("/api/v1/dashboard/finance/")
        assert response.status_code == 200
    
    def test_executive_dashboard_requires_leadership_role(self, users, test_data):
        """Executive dashboard rejects non-leadership users."""
        client = APIClient()
        client.force_authenticate(user=users["member_a1"])
        
        response = client.get("/api/v1/dashboard/executive/")
        assert response.status_code == 403
    
    def test_executive_dashboard_allows_chaplain(self, users, test_data):
        """Executive dashboard allows chaplain."""
        client = APIClient()
        client.force_authenticate(user=users["chaplain_a"])
        
        response = client.get("/api/v1/dashboard/executive/")
        assert response.status_code == 200


# =============================================================================
# ORGANIZATION ISOLATION TESTS
# =============================================================================

@pytest.mark.django_db
class TestOrganizationIsolation:
    """Test that Organization A cannot access Organization B's data."""
    
    def test_admin_dashboard_organization_isolation(self, users, test_data):
        """Admin from Org A sees only Org A data."""
        client = APIClient()
        client.force_authenticate(user=users["admin_a1"])
        
        response = client.get("/api/v1/dashboard/admin/")
        assert response.status_code == 200
        
        data = response.json()["data"]
        
        # Should see Branch A1 members (5)
        assert data["members"]["total_members"] == 5
        assert data["members"]["active_members"] == 5
    
    def test_admin_dashboard_cannot_see_other_org(self, users, test_data):
        """Admin from Org B cannot see Org A data."""
        client = APIClient()
        client.force_authenticate(user=users["admin_b1"])
        
        response = client.get("/api/v1/dashboard/admin/")
        assert response.status_code == 200
        
        data = response.json()["data"]
        
        # Should see Branch B1 members (4), not Org A members
        assert data["members"]["total_members"] == 4
        assert data["members"]["active_members"] == 4
    
    def test_finance_dashboard_organization_isolation(self, users, test_data):
        """Finance dashboard isolates giving by organization."""
        # Admin A1 should see $1000 from Branch A1
        client = APIClient()
        client.force_authenticate(user=users["admin_a1"])
        
        response = client.get("/api/v1/dashboard/finance/")
        assert response.status_code == 200
        
        data = response.json()["data"]
        assert Decimal(data["giving"]["total_giving"]) == Decimal("1000.00")
    
    def test_finance_dashboard_cannot_see_other_org_giving(self, users, test_data):
        """Finance dashboard cannot see other org's giving."""
        # Admin B1 should see $2000 from Branch B1, not Org A's $1000
        client = APIClient()
        client.force_authenticate(user=users["admin_b1"])
        
        response = client.get("/api/v1/dashboard/finance/")
        assert response.status_code == 200
        
        data = response.json()["data"]
        assert Decimal(data["giving"]["total_giving"]) == Decimal("2000.00")
    
    def test_pastor_dashboard_organization_isolation(self, users, test_data):
        """Pastor dashboard isolates pastoral cases by organization."""
        client = APIClient()
        client.force_authenticate(user=users["chaplain_a"])
        
        response = client.get("/api/v1/dashboard/pastor/")
        assert response.status_code == 200
        
        data = response.json()["data"]
        
        # Should see 1 case from Org A, not Org B's case
        assert data["pastoral_cases"]["total_cases"] == 1
    
    def test_super_admin_sees_all_organizations(self, users, test_data):
        """Super admin sees data across all organizations."""
        client = APIClient()
        client.force_authenticate(user=users["super_admin"])
        
        response = client.get("/api/v1/dashboard/admin/")
        assert response.status_code == 200
        
        data = response.json()["data"]
        
        # Should see all members: 5 (A1) + 3 (A2) + 4 (B1) = 12
        assert data["members"]["total_members"] == 12


# =============================================================================
# BRANCH ISOLATION TESTS
# =============================================================================

@pytest.mark.django_db
class TestBranchIsolation:
    """Test that Branch A1 cannot access Branch A2's data (same org)."""
    
    def test_admin_sees_only_their_branch(self, users, test_data):
        """Admin from Branch A1 sees only Branch A1 data."""
        client = APIClient()
        client.force_authenticate(user=users["admin_a1"])
        
        response = client.get("/api/v1/dashboard/admin/")
        assert response.status_code == 200
        
        data = response.json()["data"]
        
        # Should see Branch A1 members (5), not Branch A2 members (3)
        assert data["members"]["total_members"] == 5
    
    def test_other_branch_admin_sees_different_count(self, users, test_data):
        """Admin from Branch A2 sees only Branch A2 data."""
        client = APIClient()
        client.force_authenticate(user=users["admin_a2"])
        
        response = client.get("/api/v1/dashboard/admin/")
        assert response.status_code == 200
        
        data = response.json()["data"]
        
        # Should see Branch A2 members (3), not Branch A1 members (5)
        assert data["members"]["total_members"] == 3
    
    def test_chaplain_sees_all_branches_in_org(self, users, test_data):
        """Chaplain sees all branches in their organization."""
        client = APIClient()
        client.force_authenticate(user=users["chaplain_a"])
        
        response = client.get("/api/v1/dashboard/admin/")
        assert response.status_code == 200
        
        data = response.json()["data"]
        
        # Should see both Branch A1 (5) and Branch A2 (3) = 8 total
        assert data["members"]["total_members"] == 8
    
    def test_user_without_branch_sees_nothing(self, users, test_data):
        """User without branch sees no data."""
        client = APIClient()
        # Create a chapel admin without branch for this test
        admin_no_branch = User.objects.create_user(
            email="admin_nobranch@test.com",
            password="testpass123",
            role=Roles.CHAPEL_ADMIN,
            branch=None,
        )
        client.force_authenticate(user=admin_no_branch)
        
        response = client.get("/api/v1/dashboard/admin/")
        assert response.status_code == 200
        
        data = response.json()["data"]
        
        # Should see 0 members
        assert data["members"]["total_members"] == 0


# =============================================================================
# HORIZONTAL PRIVILEGE ESCALATION TESTS
# =============================================================================

@pytest.mark.django_db
class TestHorizontalPrivilegeEscalation:
    """Test that users cannot access peer users' scoped data."""
    
    def test_member_dashboard_shows_only_own_data(self, users, test_data):
        """Member sees only their own dashboard data."""
        # Create member profile for member_a1
        member_profile = Member.objects.create(
            user=users["member_a1"],
            branch=users["member_a1"].branch,
            first_name="Test",
            last_name="Member",
            membership_status=MembershipStatus.ACTIVE,
        )
        
        client = APIClient()
        client.force_authenticate(user=users["member_a1"])
        
        response = client.get("/api/v1/dashboard/member/")
        assert response.status_code == 200
        
        data = response.json()["data"]
        assert data["membership_status"] == MembershipStatus.ACTIVE
    
    def test_member_cannot_access_other_member_dashboard(self, users, test_data):
        """Member cannot manipulate request to see other member's data."""
        # This test verifies the endpoint doesn't accept member_id parameter
        member_profile_a = Member.objects.create(
            user=users["member_a1"],
            branch=users["member_a1"].branch,
            first_name="Member",
            last_name="A",
            membership_status=MembershipStatus.ACTIVE,
        )
        
        member_profile_b = Member.objects.create(
            user=users["member_b1"],
            branch=users["member_b1"].branch,
            first_name="Member",
            last_name="B",
            membership_status=MembershipStatus.INACTIVE,
        )
        
        client = APIClient()
        client.force_authenticate(user=users["member_a1"])
        
        # Attempt to access other member's data via query param
        response = client.get(f"/api/v1/dashboard/member/?member_id={member_profile_b.id}")
        assert response.status_code == 200
        
        data = response.json()["data"]
        
        # Should still see their own status (ACTIVE), not member B's (INACTIVE)
        assert data["membership_status"] == MembershipStatus.ACTIVE


# =============================================================================
# VERTICAL PRIVILEGE ESCALATION TESTS
# =============================================================================

@pytest.mark.django_db
class TestVerticalPrivilegeEscalation:
    """Test that low-privilege users cannot access high-privilege dashboards."""
    
    def test_member_cannot_access_finance_dashboard(self, users, test_data):
        """Regular member cannot access finance dashboard."""
        client = APIClient()
        client.force_authenticate(user=users["member_a1"])
        
        response = client.get("/api/v1/dashboard/finance/")
        assert response.status_code == 403
    
    def test_member_cannot_access_pastor_dashboard(self, users, test_data):
        """Regular member cannot access pastor dashboard."""
        client = APIClient()
        client.force_authenticate(user=users["member_a1"])
        
        response = client.get("/api/v1/dashboard/pastor/")
        assert response.status_code == 403
    
    def test_member_cannot_access_executive_dashboard(self, users, test_data):
        """Regular member cannot access executive dashboard."""
        client = APIClient()
        client.force_authenticate(user=users["member_a1"])
        
        response = client.get("/api/v1/dashboard/executive/")
        assert response.status_code == 403
    
    def test_admin_cannot_escalate_to_super_admin_scope(self, users, test_data):
        """Chapel admin sees branch scope, not global scope."""
        client = APIClient()
        client.force_authenticate(user=users["admin_a1"])
        
        response = client.get("/api/v1/dashboard/admin/")
        assert response.status_code == 200
        
        data = response.json()["data"]
        
        # Should see only Branch A1 (5), not all orgs (12)
        assert data["members"]["total_members"] == 5
        assert data["members"]["total_members"] != 12


# =============================================================================
# SENSITIVE DATA PROTECTION TESTS
# =============================================================================

@pytest.mark.django_db
class TestSensitiveDataProtection:
    """Test that sensitive data is not exposed in dashboard responses."""
    
    def test_pastor_dashboard_no_pastoral_notes(self, users, test_data):
        """Pastor dashboard does not expose pastoral notes."""
        client = APIClient()
        client.force_authenticate(user=users["chaplain_a"])
        
        response = client.get("/api/v1/dashboard/pastor/")
        assert response.status_code == 200
        
        data = response.json()["data"]
        
        # Response should have aggregate counts only
        assert "pastoral_cases" in data
        assert "total_cases" in data["pastoral_cases"]
        assert "open_cases" in data["pastoral_cases"]
        
        # Should NOT contain notes, member names, or case details
        response_str = str(response.json())
        assert "notes" not in response_str.lower()
        assert "case_details" not in response_str.lower()
    
    def test_pastor_dashboard_no_prayer_content(self, users, test_data):
        """Pastor dashboard does not expose prayer request content."""
        client = APIClient()
        client.force_authenticate(user=users["chaplain_a"])
        
        response = client.get("/api/v1/dashboard/pastor/")
        assert response.status_code == 200
        
        data = response.json()["data"]
        
        # Response should have aggregate counts only
        assert "prayer_requests" in data
        assert "total_requests" in data["prayer_requests"]
        
        # Should NOT contain prayer content or details
        response_str = str(response.json())
        assert "prayer_text" not in response_str.lower()
        assert "request_details" not in response_str.lower()
    
    def test_finance_dashboard_no_donor_pii(self, users, test_data):
        """Finance dashboard does not expose donor PII."""
        client = APIClient()
        client.force_authenticate(user=users["admin_a1"])
        
        response = client.get("/api/v1/dashboard/finance/")
        assert response.status_code == 200
        
        data = response.json()["data"]
        
        # Should have aggregate giving data
        assert "giving" in data
        assert "total_giving" in data["giving"]
        
        # Should NOT contain member names, emails, or phone numbers
        response_str = str(response.json())
        assert "@" not in response_str  # No email addresses
        assert "member__email" not in response_str.lower()
        assert "member__phone" not in response_str.lower()
    
    def test_member_dashboard_no_other_member_data(self, users, test_data):
        """Member dashboard does not leak other members' data."""
        member_profile = Member.objects.create(
            user=users["member_a1"],
            branch=users["member_a1"].branch,
            first_name="Test",
            last_name="Member",
            email="test@example.com",
            phone_number="1234567890",
            membership_status=MembershipStatus.ACTIVE,
        )
        
        client = APIClient()
        client.force_authenticate(user=users["member_a1"])
        
        response = client.get("/api/v1/dashboard/member/")
        assert response.status_code == 200
        
        # Verify response contains only expected fields
        data = response.json()["data"]
        assert set(data.keys()) == {"membership_status", "groups", "upcoming_registrations", "recent_attendance_count"}


# =============================================================================
# FILTER BYPASS TESTS
# =============================================================================

@pytest.mark.django_db
class TestFilterBypass:
    """Test that query parameter manipulation cannot bypass authorization."""
    
    def test_cannot_bypass_org_filter(self, users, branches, test_data):
        """Cannot access other org's data via organization_id parameter."""
        client = APIClient()
        client.force_authenticate(user=users["admin_a1"])
        
        # Attempt to access Org B data via query param
        org_b_id = branches["branch_b1"].organization_id
        response = client.get(f"/api/v1/dashboard/admin/?organization_id={org_b_id}")
        
        # Should still see only own organization's data
        assert response.status_code == 200
        data = response.json()["data"]
        
        # Should see Branch A1 members (5), not Org B members (4)
        assert data["members"]["total_members"] == 5
    
    def test_cannot_bypass_branch_filter(self, users, branches, test_data):
        """Cannot access other branch's data via branch_id parameter."""
        client = APIClient()
        client.force_authenticate(user=users["admin_a1"])
        
        # Attempt to access Branch A2 data via query param
        branch_a2_id = branches["branch_a2"].id
        response = client.get(f"/api/v1/dashboard/admin/?branch_id={branch_a2_id}")
        
        # Should still see only own branch's data
        assert response.status_code == 200
        data = response.json()["data"]
        
        # Should see Branch A1 members (5), not Branch A2 members (3)
        assert data["members"]["total_members"] == 5
    
    def test_ministry_dashboard_validates_ministry_access(self, users, branches):
        """Ministry dashboard validates ministry access."""
        from apps.groups.models import Group, GroupType
        
        # Create ministry in Branch A1
        ministry_a = Group.objects.create(
            branch=branches["branch_a1"],
            name="Ministry A",
            group_type=GroupType.MINISTRY,
            is_active=True,
        )
        
        # Create ministry in Branch B1
        ministry_b = Group.objects.create(
            branch=branches["branch_b1"],
            name="Ministry B",
            group_type=GroupType.MINISTRY,
            is_active=True,
        )
        
        client = APIClient()
        client.force_authenticate(user=users["admin_a1"])
        
        # Attempt to access Ministry B (different org) via ministry_id
        response = client.get(f"/api/v1/dashboard/ministry/?ministry_id={ministry_b.id}")
        
        # Should be rejected (404 - not found in scoped queryset)
        assert response.status_code == 404
        assert "not found" in response.json()["error"].lower() or "denied" in response.json()["error"].lower()


# =============================================================================
# AGGREGATE DATA LEAKAGE TESTS
# =============================================================================

@pytest.mark.django_db
class TestAggregateDataLeakage:
    """Test that aggregate counts don't leak data from restricted scopes."""
    
    def test_member_count_respects_scope(self, users, test_data):
        """Member counts don't include other orgs/branches."""
        # Test multiple users at different scopes
        test_cases = [
            (users["admin_a1"], 5),   # Branch A1 only
            (users["admin_a2"], 3),   # Branch A2 only
            (users["admin_b1"], 4),   # Branch B1 only
            (users["chaplain_a"], 8), # All of Org A (A1+A2)
            (users["super_admin"], 12), # All orgs
        ]
        
        for user, expected_count in test_cases:
            client = APIClient()
            client.force_authenticate(user=user)
            
            response = client.get("/api/v1/dashboard/admin/")
            assert response.status_code == 200
            
            data = response.json()["data"]
            assert data["members"]["total_members"] == expected_count, \
                f"User {user.email} should see {expected_count} members"
    
    def test_giving_totals_respect_scope(self, users, test_data):
        """Giving totals don't include other orgs/branches."""
        # Branch A1 has $1000, Branch B1 has $2000
        test_cases = [
            (users["admin_a1"], Decimal("1000.00")),  # Branch A1
            (users["admin_b1"], Decimal("2000.00")),  # Branch B1
            (users["super_admin"], Decimal("3000.00")),  # All
        ]
        
        for user, expected_total in test_cases:
            client = APIClient()
            client.force_authenticate(user=user)
            
            response = client.get("/api/v1/dashboard/finance/")
            assert response.status_code == 200
            
            data = response.json()["data"]
            assert Decimal(data["giving"]["total_giving"]) == expected_total, \
                f"User {user.email} should see {expected_total} total giving"
