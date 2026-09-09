"""
Phase 13 Comprehensive Security Tests: IDOR, Cross-Branch, Privacy

High-priority security tests for:
- IDOR (Insecure Direct Object Reference) attacks
- Cross-branch data access attempts
- Privacy escalation (accessing higher-privacy requests)
- Assignment privilege escalation
- Note immutability enforcement
- Audit log tampering prevention
- Member impersonation attempts
- Branch boundary violations
"""

import pytest
from django.db import IntegrityError
from rest_framework import status
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.members.models import Member
from apps.organizations.models import Branch, Organization
from apps.pastoral.models import PastoralCase, PastoralNote, PastoralCaseStatus, PastoralCasePriority
from apps.prayer.models import PrayerRequest, PrayerNote, PrayerRequestStatus, PrayerPrivacyLevel
from apps.audit.models import AuditLog
from common.constants.roles import Roles


# ============================================================================
# FIXTURES
# ============================================================================

@pytest.fixture
def organization(db):
    return Organization.objects.create(name="Test Chapel", slug="test-chapel-p13-sec")


@pytest.fixture
def branch_main(organization):
    return Branch.objects.create(organization=organization, name="Main Campus")


@pytest.fixture
def branch_annex(organization):
    return Branch.objects.create(organization=organization, name="Annex Campus")


@pytest.fixture
def super_admin(branch_main):
    return User.objects.create_user(
        email="superadmin@test.com", password="pass",
        role=Roles.SUPER_ADMIN, branch=branch_main,
        first_name="Super", last_name="Admin", is_active=True
    )


@pytest.fixture
def chaplain_main(branch_main):
    return User.objects.create_user(
        email="chaplain_main@test.com", password="pass",
        role=Roles.CHAPLAIN, branch=branch_main,
        first_name="Chaplain", last_name="Main", is_active=True
    )


@pytest.fixture
def chaplain_annex(branch_annex):
    return User.objects.create_user(
        email="chaplain_annex@test.com", password="pass",
        role=Roles.CHAPLAIN, branch=branch_annex,
        first_name="Chaplain", last_name="Annex", is_active=True
    )


@pytest.fixture
def attacker_user(branch_main):
    """Malicious user attempting unauthorized access"""
    return User.objects.create_user(
        email="attacker@test.com", password="pass",
        role=Roles.MEMBER, branch=branch_main,
        first_name="Attacker", last_name="User", is_active=True
    )


@pytest.fixture
def victim_user(branch_annex):
    """Victim user in different branch"""
    return User.objects.create_user(
        email="victim@test.com", password="pass",
        role=Roles.MEMBER, branch=branch_annex,
        first_name="Victim", last_name="User", is_active=True
    )


@pytest.fixture
def member_main(branch_main):
    user = User.objects.create_user(
        email="member_main@test.com", password="pass",
        role=Roles.MEMBER, branch=branch_main,
        first_name="Member", last_name="Main"
    )
    return Member.objects.create(
        user=user, branch=branch_main,
        first_name="Member", last_name="Main",
        email="member_main@test.com"
    )


@pytest.fixture
def member_annex(branch_annex):
    user = User.objects.create_user(
        email="member_annex@test.com", password="pass",
        role=Roles.MEMBER, branch=branch_annex,
        first_name="Member", last_name="Annex"
    )
    return Member.objects.create(
        user=user, branch=branch_annex,
        first_name="Member", last_name="Annex",
        email="member_annex@test.com"
    )


# ============================================================================
# PASTORAL CASE IDOR TESTS
# ============================================================================

@pytest.mark.django_db
class TestPastoralCaseIDOR:
    """Test IDOR vulnerabilities in pastoral cases"""

    def test_idor_cannot_read_other_branch_case_via_direct_id(
        self, chaplain_main, chaplain_annex, member_annex
    ):
        """Attacker cannot read cases from other branch by guessing ID"""
        # Victim's case in branch_annex
        victim_case = PastoralCase.objects.create(
            branch=member_annex.branch,
            member=member_annex,
            category="Confidential Counseling",
            summary="Highly sensitive information",
            priority=PastoralCasePriority.HIGH,
            status=PastoralCaseStatus.OPEN,
            created_by=chaplain_annex,
            updated_by=chaplain_annex
        )
        
        # Attacker from branch_main tries to access
        client = APIClient()
        client.force_authenticate(user=chaplain_main)
        
        response = client.get(f"/api/pastoral/cases/{victim_case.id}/")
        
        # Must return 404 (not 403) to prevent info disclosure
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_idor_cannot_update_other_branch_case(
        self, chaplain_main, chaplain_annex, member_annex
    ):
        """Attacker cannot update cases from other branch"""
        victim_case = PastoralCase.objects.create(
            branch=member_annex.branch,
            member=member_annex,
            category="Counseling",
            summary="Original summary",
            priority=PastoralCasePriority.MEDIUM,
            status=PastoralCaseStatus.OPEN,
            created_by=chaplain_annex,
            updated_by=chaplain_annex
        )
        
        client = APIClient()
        client.force_authenticate(user=chaplain_main)
        
        # Attempt to hijack case
        response = client.patch(
            f"/api/pastoral/cases/{victim_case.id}/",
            {
                "summary": "Attacker modified this",
                "assigned_to": chaplain_main.id
            },
            format="json"
        )
        
        assert response.status_code == status.HTTP_404_NOT_FOUND
        
        # Verify case unchanged
        victim_case.refresh_from_db()
        assert victim_case.summary == "Original summary"
        assert victim_case.assigned_to != chaplain_main

    def test_idor_cannot_delete_other_branch_case(
        self, chaplain_main, chaplain_annex, member_annex
    ):
        """Attacker cannot delete cases from other branch"""
        victim_case = PastoralCase.objects.create(
            branch=member_annex.branch,
            member=member_annex,
            category="Counseling",
            summary="Victim case",
            priority=PastoralCasePriority.MEDIUM,
            status=PastoralCaseStatus.OPEN,
            created_by=chaplain_annex,
            updated_by=chaplain_annex
        )
        
        client = APIClient()
        client.force_authenticate(user=chaplain_main)
        
        response = client.delete(f"/api/pastoral/cases/{victim_case.id}/")
        
        # Should be blocked
        assert response.status_code in [
            status.HTTP_404_NOT_FOUND,
            status.HTTP_403_FORBIDDEN,
            status.HTTP_405_METHOD_NOT_ALLOWED  # If deletion disabled
        ]
        
        # Verify case still exists
        assert PastoralCase.objects.filter(id=victim_case.id).exists()

    def test_idor_list_endpoint_filters_by_branch(
        self, chaplain_main, chaplain_annex, member_main, member_annex
    ):
        """List endpoint must only return cases from user's branch"""
        # Create cases in both branches
        case_main = PastoralCase.objects.create(
            branch=member_main.branch,
            member=member_main,
            category="Counseling",
            summary="Main branch case",
            priority=PastoralCasePriority.MEDIUM,
            status=PastoralCaseStatus.OPEN,
            created_by=chaplain_main,
            updated_by=chaplain_main
        )
        
        case_annex = PastoralCase.objects.create(
            branch=member_annex.branch,
            member=member_annex,
            category="Counseling",
            summary="Annex branch case",
            priority=PastoralCasePriority.MEDIUM,
            status=PastoralCaseStatus.OPEN,
            created_by=chaplain_annex,
            updated_by=chaplain_annex
        )
        
        # Chaplain_main queries list
        client = APIClient()
        client.force_authenticate(user=chaplain_main)
        
        response = client.get("/api/pastoral/cases/")
        assert response.status_code == status.HTTP_200_OK
        
        returned_ids = [item["id"] for item in response.data["results"]]
        
        # Should only see own branch
        assert case_main.id in returned_ids
        assert case_annex.id not in returned_ids


# ============================================================================
# PRAYER REQUEST IDOR TESTS
# ============================================================================

@pytest.mark.django_db
class TestPrayerRequestIDOR:
    """Test IDOR vulnerabilities in prayer requests"""

    def test_idor_cannot_read_other_branch_private_prayer(
        self, attacker_user, victim_user, branch_main, branch_annex
    ):
        """Attacker cannot read private prayers from other branch"""
        # Victim's private prayer
        victim_member = Member.objects.create(
            user=victim_user, branch=branch_annex,
            first_name="Victim", last_name="User",
            email="victim@test.com"
        )
        
        victim_prayer = PrayerRequest.objects.create(
            branch=branch_annex,
            member=victim_member,
            category="Personal Crisis",
            details="Highly confidential prayer request",
            privacy_level=PrayerPrivacyLevel.PRIVATE,
            status=PrayerRequestStatus.NEW,
            created_by=victim_user
        )
        
        # Attacker tries to access
        client = APIClient()
        client.force_authenticate(user=attacker_user)
        
        response = client.get(f"/api/prayer/requests/{victim_prayer.id}/")
        
        # Must be blocked
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_idor_cannot_escalate_privacy_level(
        self, chaplain_main, member_main
    ):
        """Regular member cannot access PASTORAL-level prayer not assigned to them"""
        # Create pastoral-level prayer for member_main
        pastoral_prayer = PrayerRequest.objects.create(
            branch=member_main.branch,
            member=member_main,
            category="Pastoral Care",
            details="Sensitive pastoral matter",
            privacy_level=PrayerPrivacyLevel.PASTORAL,
            status=PrayerRequestStatus.ASSIGNED,
            assigned_to=chaplain_main,
            created_by=member_main.user
        )
        
        # Another regular member in same branch tries to access
        other_user = User.objects.create_user(
            email="other@test.com", password="pass",
            role=Roles.MEMBER, branch=member_main.branch,
            first_name="Other", last_name="Member"
        )
        
        client = APIClient()
        client.force_authenticate(user=other_user)
        
        response = client.get(f"/api/prayer/requests/{pastoral_prayer.id}/")
        
        # Should be blocked (privacy escalation attempt)
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_idor_cannot_modify_privacy_level_to_bypass_access(
        self, chaplain_main, member_main
    ):
        """Attacker cannot change privacy_level to PUBLIC to gain access"""
        # Create private prayer
        private_prayer = PrayerRequest.objects.create(
            branch=member_main.branch,
            member=member_main,
            category="Personal",
            details="Private details",
            privacy_level=PrayerPrivacyLevel.PRIVATE,
            status=PrayerRequestStatus.NEW,
            created_by=member_main.user
        )
        
        # Another member tries to change privacy to PUBLIC
        attacker = User.objects.create_user(
            email="attacker2@test.com", password="pass",
            role=Roles.MEMBER, branch=member_main.branch,
            first_name="Attacker", last_name="Two"
        )
        
        client = APIClient()
        client.force_authenticate(user=attacker)
        
        # Attempt to downgrade privacy
        response = client.patch(
            f"/api/prayer/requests/{private_prayer.id}/",
            {"privacy_level": PrayerPrivacyLevel.PUBLIC},
            format="json"
        )
        
        # Should be blocked (404 because they can't even see it)
        assert response.status_code == status.HTTP_404_NOT_FOUND
        
        # Verify privacy unchanged
        private_prayer.refresh_from_db()
        assert private_prayer.privacy_level == PrayerPrivacyLevel.PRIVATE


# ============================================================================
# ASSIGNMENT PRIVILEGE ESCALATION TESTS
# ============================================================================

@pytest.mark.django_db
class TestAssignmentPrivilegeEscalation:
    """Test privilege escalation via assignment manipulation"""

    def test_cannot_assign_to_self_without_authorization(
        self, member_main, chaplain_main
    ):
        """Regular member cannot assign pastoral case to themselves"""
        case = PastoralCase.objects.create(
            branch=member_main.branch,
            member=member_main,
            category="Counseling",
            summary="Test case",
            priority=PastoralCasePriority.MEDIUM,
            status=PastoralCaseStatus.OPEN,
            created_by=chaplain_main,
            updated_by=chaplain_main
        )
        
        client = APIClient()
        client.force_authenticate(user=member_main.user)
        
        # Member tries to assign case to themselves
        response = client.patch(
            f"/api/pastoral/cases/{case.id}/",
            {"assigned_to": member_main.user.id},
            format="json"
        )
        
        # Should be rejected
        assert response.status_code in [
            status.HTTP_400_BAD_REQUEST,
            status.HTTP_403_FORBIDDEN,
            status.HTTP_404_NOT_FOUND
        ]

    def test_cannot_assign_cross_branch_to_gain_access(
        self, chaplain_main, chaplain_annex, member_annex
    ):
        """Chaplain cannot assign themselves to cases in other branch"""
        # Case in branch_annex
        case = PastoralCase.objects.create(
            branch=member_annex.branch,
            member=member_annex,
            category="Counseling",
            summary="Annex case",
            priority=PastoralCasePriority.MEDIUM,
            status=PastoralCaseStatus.OPEN,
            created_by=chaplain_annex,
            updated_by=chaplain_annex
        )
        
        client = APIClient()
        client.force_authenticate(user=chaplain_main)
        
        # Try to assign to self (cross-branch)
        response = client.patch(
            f"/api/pastoral/cases/{case.id}/",
            {"assigned_to": chaplain_main.id},
            format="json"
        )
        
        # Should be blocked
        assert response.status_code == status.HTTP_404_NOT_FOUND


# ============================================================================
# NOTE IMMUTABILITY TESTS
# ============================================================================

@pytest.mark.django_db
class TestNoteImmutabilityEnforcement:
    """Test append-only enforcement cannot be bypassed"""

    def test_cannot_edit_pastoral_note_after_creation(
        self, chaplain_main, member_main
    ):
        """Pastoral notes must be immutable after creation"""
        case = PastoralCase.objects.create(
            branch=member_main.branch,
            member=member_main,
            category="Counseling",
            summary="Test case",
            priority=PastoralCasePriority.MEDIUM,
            status=PastoralCaseStatus.OPEN,
            created_by=chaplain_main,
            updated_by=chaplain_main
        )
        
        note = PastoralNote.objects.create(
            case=case,
            author=chaplain_main,
            note="Original note content"
        )
        
        client = APIClient()
        client.force_authenticate(user=chaplain_main)
        
        # Attempt to edit via API
        response = client.patch(
            f"/api/pastoral/notes/{note.id}/",
            {"note": "Tampered content"},
            format="json"
        )
        
        # Should be rejected
        assert response.status_code in [
            status.HTTP_403_FORBIDDEN,
            status.HTTP_405_METHOD_NOT_ALLOWED
        ]
        
        # Verify unchanged
        note.refresh_from_db()
        assert note.note == "Original note content"

    def test_cannot_delete_pastoral_note(
        self, chaplain_main, member_main
    ):
        """Pastoral notes cannot be deleted"""
        case = PastoralCase.objects.create(
            branch=member_main.branch,
            member=member_main,
            category="Counseling",
            summary="Test case",
            priority=PastoralCasePriority.MEDIUM,
            status=PastoralCaseStatus.OPEN,
            created_by=chaplain_main,
            updated_by=chaplain_main
        )
        
        note = PastoralNote.objects.create(
            case=case,
            author=chaplain_main,
            note="Important record"
        )
        
        client = APIClient()
        client.force_authenticate(user=chaplain_main)
        
        # Attempt to delete
        response = client.delete(f"/api/pastoral/notes/{note.id}/")
        
        # Should be rejected
        assert response.status_code in [
            status.HTTP_403_FORBIDDEN,
            status.HTTP_405_METHOD_NOT_ALLOWED
        ]
        
        # Verify still exists
        assert PastoralNote.objects.filter(id=note.id).exists()

    def test_cannot_edit_prayer_note_after_creation(
        self, chaplain_main, member_main
    ):
        """Prayer notes must be immutable after creation"""
        prayer = PrayerRequest.objects.create(
            branch=member_main.branch,
            member=member_main,
            category="Healing",
            details="Prayer for healing",
            privacy_level=PrayerPrivacyLevel.PASTORAL,
            status=PrayerRequestStatus.ASSIGNED,
            assigned_to=chaplain_main,
            created_by=member_main.user
        )
        
        note = PrayerNote.objects.create(
            prayer_request=prayer,
            author=chaplain_main,
            note="Original prayer note"
        )
        
        client = APIClient()
        client.force_authenticate(user=chaplain_main)
        
        # Attempt to edit
        response = client.patch(
            f"/api/prayer/notes/{note.id}/",
            {"note": "Tampered prayer note"},
            format="json"
        )
        
        # Should be rejected
        assert response.status_code in [
            status.HTTP_403_FORBIDDEN,
            status.HTTP_405_METHOD_NOT_ALLOWED
        ]
        
        # Verify unchanged
        note.refresh_from_db()
        assert note.note == "Original prayer note"


# ============================================================================
# AUDIT LOG PROTECTION TESTS
# ============================================================================

@pytest.mark.django_db
class TestAuditLogProtection:
    """Test audit logs cannot be tampered with"""

    def test_audit_logs_are_created(self, chaplain_main, member_main):
        """Verify audit logs are actually created"""
        initial_count = AuditLog.objects.count()
        
        client = APIClient()
        client.force_authenticate(user=chaplain_main)
        
        # Create pastoral case
        response = client.post(
            "/api/pastoral/cases/",
            {
                "branch": member_main.branch.id,
                "member": member_main.id,
                "category": "Counseling",
                "summary": "Test case",
                "priority": PastoralCasePriority.MEDIUM,
                "status": PastoralCaseStatus.OPEN
            },
            format="json"
        )
        
        assert response.status_code == status.HTTP_201_CREATED
        
        # Verify audit log created
        assert AuditLog.objects.count() > initial_count

    def test_audit_logs_cannot_be_deleted_via_api(self, super_admin):
        """Audit logs should not be deletable via API"""
        # This assumes no DELETE endpoint exists for AuditLog
        # If endpoint exists, it should be 405 METHOD_NOT_ALLOWED
        client = APIClient()
        client.force_authenticate(user=super_admin)
        
        # Try to access audit log deletion endpoint (should not exist)
        response = client.delete("/api/audit/logs/1/")
        
        # Should be 404 (no endpoint) or 405 (method not allowed)
        assert response.status_code in [
            status.HTTP_404_NOT_FOUND,
            status.HTTP_405_METHOD_NOT_ALLOWED
        ]


# ============================================================================
# BRANCH BOUNDARY VIOLATION TESTS
# ============================================================================

@pytest.mark.django_db
class TestBranchBoundaryViolations:
    """Test attempts to violate branch boundaries"""

    def test_cannot_create_case_for_member_in_other_branch(
        self, chaplain_main, member_annex
    ):
        """Chaplain cannot create case for member in different branch"""
        client = APIClient()
        client.force_authenticate(user=chaplain_main)
        
        response = client.post(
            "/api/pastoral/cases/",
            {
                "branch": member_annex.branch.id,
                "member": member_annex.id,
                "category": "Counseling",
                "summary": "Cross-branch attempt",
                "priority": PastoralCasePriority.MEDIUM,
                "status": PastoralCaseStatus.OPEN
            },
            format="json"
        )
        
        # Should be rejected
        assert response.status_code in [
            status.HTTP_400_BAD_REQUEST,
            status.HTTP_403_FORBIDDEN
        ]

    def test_cannot_transfer_case_to_other_branch_via_update(
        self, chaplain_main, chaplain_annex, member_main, branch_annex
    ):
        """Cannot move case to different branch via update"""
        case = PastoralCase.objects.create(
            branch=member_main.branch,
            member=member_main,
            category="Counseling",
            summary="Main branch case",
            priority=PastoralCasePriority.MEDIUM,
            status=PastoralCaseStatus.OPEN,
            created_by=chaplain_main,
            updated_by=chaplain_main
        )
        
        client = APIClient()
        client.force_authenticate(user=chaplain_main)
        
        # Attempt to change branch
        response = client.patch(
            f"/api/pastoral/cases/{case.id}/",
            {"branch": branch_annex.id},
            format="json"
        )
        
        # Branch should be immutable or rejected
        case.refresh_from_db()
        assert case.branch.id != branch_annex.id
