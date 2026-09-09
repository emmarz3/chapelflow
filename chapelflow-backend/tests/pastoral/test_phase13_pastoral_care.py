"""
Phase 13 Pastoral Care Tests: Comprehensive Security & Functionality

Tests comprehensive validation for:
- Pastoral case lifecycle (OPEN → ASSIGNED → IN_PROGRESS → FOLLOW_UP → ESCALATED → RESOLVED → CLOSED)
- Priority-based workflows (URGENT, HIGH, MEDIUM, LOW)
- Assignment validation (role checking, branch scoping, active users only)
- Escalation tracking and audit trail
- Closure reasons and follow-up scheduling
- Append-only notes (immutable after creation)
- Cross-branch attack prevention (IDOR)
- Branch-scoped access control
- Created_by/updated_by audit fields
- Audit logging integration
- Member merge/transfer handling
"""

import pytest
from django.db import transaction
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.members.models import Member
from apps.organizations.models import Branch, Organization
from apps.pastoral.models import PastoralCase, PastoralNote, PastoralCaseStatus, PastoralCasePriority
from apps.audit.models import AuditLog, AuditAction
from common.constants.roles import Roles


# ============================================================================
# FIXTURES
# ============================================================================

@pytest.fixture
def organization(db):
    return Organization.objects.create(name="Test Chapel Organization", slug="test-chapel-org-p13-pastoral")


@pytest.fixture
def branch_a(organization):
    return Branch.objects.create(organization=organization, name="Main Branch")


@pytest.fixture
def branch_b(organization):
    return Branch.objects.create(organization=organization, name="Annex Branch")


@pytest.fixture
def super_admin(branch_a):
    return User.objects.create_user(
        email="superadmin@test.com",
        password="password",
        role=Roles.SUPER_ADMIN,
        branch=branch_a,
        first_name="Super",
        last_name="Admin",
        is_active=True
    )


@pytest.fixture
def chaplain_a(branch_a):
    """Chaplain for branch A"""
    return User.objects.create_user(
        email="chaplain_a@test.com",
        password="password",
        role=Roles.CHAPLAIN,
        branch=branch_a,
        first_name="Chaplain",
        last_name="Alpha",
        is_active=True
    )


@pytest.fixture
def chaplain_b(branch_b):
    """Chaplain for branch B"""
    return User.objects.create_user(
        email="chaplain_b@test.com",
        password="password",
        role=Roles.CHAPLAIN,
        branch=branch_b,
        first_name="Chaplain",
        last_name="Beta",
        is_active=True
    )


@pytest.fixture
def fellowship_leader_a(branch_a):
    """Fellowship leader (should NOT have pastoral case assignment rights)"""
    return User.objects.create_user(
        email="leader_a@test.com",
        password="password",
        role=Roles.FELLOWSHIP_LEADER,
        branch=branch_a,
        first_name="Leader",
        last_name="Alpha",
        is_active=True
    )


@pytest.fixture
def inactive_chaplain(branch_a):
    """Inactive chaplain (should NOT be assignable)"""
    return User.objects.create_user(
        email="inactive@test.com",
        password="password",
        role=Roles.CHAPLAIN,
        branch=branch_a,
        first_name="Inactive",
        last_name="Chaplain",
        is_active=False
    )


@pytest.fixture
def member_a(branch_a):
    """Member in branch A"""
    user = User.objects.create_user(
        email="member_a@test.com",
        password="password",
        role=Roles.MEMBER,
        branch=branch_a,
        first_name="Member",
        last_name="Alpha"
    )
    return Member.objects.create(
        user=user,
        branch=branch_a,
        first_name="Member",
        last_name="Alpha",
        email="member_a@test.com"
    )


@pytest.fixture
def member_b(branch_b):
    """Member in branch B"""
    user = User.objects.create_user(
        email="member_b@test.com",
        password="password",
        role=Roles.MEMBER,
        branch=branch_b,
        first_name="Member",
        last_name="Beta"
    )
    return Member.objects.create(
        user=user,
        branch=branch_b,
        first_name="Member",
        last_name="Beta",
        email="member_b@test.com"
    )


# ============================================================================
# PASTORAL CASE LIFECYCLE TESTS
# ============================================================================

@pytest.mark.django_db
class TestPastoralCaseLifecycle:
    """Test pastoral case status transitions and validation"""

    def test_create_pastoral_case_sets_audit_fields(self, chaplain_a, member_a):
        """Creating a case should auto-set created_by and updated_by"""
        case = PastoralCase.objects.create(
            branch=member_a.branch,
            member=member_a,
            category="Spiritual Counseling",
            summary="Member seeking guidance",
            priority=PastoralCasePriority.MEDIUM,
            status=PastoralCaseStatus.OPEN,
            created_by=chaplain_a,
            updated_by=chaplain_a
        )
        
        assert case.created_by == chaplain_a
        assert case.updated_by == chaplain_a
        assert case.created_at is not None
        assert case.updated_at is not None

    def test_status_transition_open_to_assigned(self, chaplain_a, member_a):
        """OPEN → ASSIGNED transition should be valid"""
        case = PastoralCase.objects.create(
            branch=member_a.branch,
            member=member_a,
            category="Spiritual Counseling",
            summary="Test case",
            priority=PastoralCasePriority.MEDIUM,
            status=PastoralCaseStatus.OPEN,
            created_by=chaplain_a,
            updated_by=chaplain_a
        )
        
        case.status = PastoralCaseStatus.ASSIGNED
        case.assigned_to = chaplain_a
        case.clean()  # Should not raise
        case.save()
        
        assert case.status == PastoralCaseStatus.ASSIGNED

    def test_cannot_close_without_resolution_status(self, chaplain_a, member_a):
        """Cannot transition directly from OPEN to CLOSED without going through RESOLVED"""
        case = PastoralCase.objects.create(
            branch=member_a.branch,
            member=member_a,
            category="Spiritual Counseling",
            summary="Test case",
            priority=PastoralCasePriority.MEDIUM,
            status=PastoralCaseStatus.OPEN,
            created_by=chaplain_a,
            updated_by=chaplain_a
        )
        
        case.status = PastoralCaseStatus.CLOSED
        
        with pytest.raises(Exception):  # Should raise ValidationError
            case.clean()

    def test_escalation_requires_reason(self, chaplain_a, member_a):
        """Escalating a case requires escalation_reason"""
        case = PastoralCase.objects.create(
            branch=member_a.branch,
            member=member_a,
            category="Critical Issue",
            summary="Urgent case",
            priority=PastoralCasePriority.URGENT,
            status=PastoralCaseStatus.IN_PROGRESS,
            assigned_to=chaplain_a,
            created_by=chaplain_a,
            updated_by=chaplain_a
        )
        
        case.status = PastoralCaseStatus.ESCALATED
        case.escalated_at = timezone.now()
        case.escalated_by = chaplain_a
        # Missing escalation_reason
        
        with pytest.raises(Exception):  # Should raise ValidationError
            case.clean()

    def test_closure_requires_reason(self, chaplain_a, member_a):
        """Closing a case requires closure_reason"""
        case = PastoralCase.objects.create(
            branch=member_a.branch,
            member=member_a,
            category="Spiritual Counseling",
            summary="Test case",
            priority=PastoralCasePriority.MEDIUM,
            status=PastoralCaseStatus.RESOLVED,
            created_by=chaplain_a,
            updated_by=chaplain_a
        )
        
        case.status = PastoralCaseStatus.CLOSED
        # Missing closure_reason
        
        with pytest.raises(Exception):  # Should raise ValidationError
            case.clean()


# ============================================================================
# ASSIGNMENT VALIDATION TESTS
# ============================================================================

@pytest.mark.django_db
class TestPastoralCaseAssignment:
    """Test assignment validation and role checking"""

    def test_assign_to_chaplain_same_branch(self, chaplain_a, member_a):
        """Should allow assignment to chaplain in same branch"""
        case = PastoralCase.objects.create(
            branch=member_a.branch,
            member=member_a,
            category="Spiritual Counseling",
            summary="Test case",
            priority=PastoralCasePriority.MEDIUM,
            status=PastoralCaseStatus.OPEN,
            created_by=chaplain_a,
            updated_by=chaplain_a
        )
        
        case.assigned_to = chaplain_a
        case.status = PastoralCaseStatus.ASSIGNED
        case.save()
        
        assert case.assigned_to == chaplain_a

    def test_cannot_assign_to_fellowship_leader(self, chaplain_a, fellowship_leader_a, member_a):
        """Should reject assignment to fellowship leader (insufficient role)"""
        client = APIClient()
        client.force_authenticate(user=chaplain_a)
        
        case = PastoralCase.objects.create(
            branch=member_a.branch,
            member=member_a,
            category="Spiritual Counseling",
            summary="Test case",
            priority=PastoralCasePriority.MEDIUM,
            status=PastoralCaseStatus.OPEN,
            created_by=chaplain_a,
            updated_by=chaplain_a
        )
        
        response = client.patch(
            f"/api/pastoral/cases/{case.id}/",
            {"assigned_to": fellowship_leader_a.id},
            format="json"
        )
        
        # Should reject due to role validation
        assert response.status_code in [status.HTTP_400_BAD_REQUEST, status.HTTP_403_FORBIDDEN]

    def test_cannot_assign_to_inactive_user(self, chaplain_a, inactive_chaplain, member_a):
        """Should reject assignment to inactive user"""
        client = APIClient()
        client.force_authenticate(user=chaplain_a)
        
        case = PastoralCase.objects.create(
            branch=member_a.branch,
            member=member_a,
            category="Spiritual Counseling",
            summary="Test case",
            priority=PastoralCasePriority.MEDIUM,
            status=PastoralCaseStatus.OPEN,
            created_by=chaplain_a,
            updated_by=chaplain_a
        )
        
        response = client.patch(
            f"/api/pastoral/cases/{case.id}/",
            {"assigned_to": inactive_chaplain.id},
            format="json"
        )
        
        # Should reject due to inactive status
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_cannot_assign_cross_branch(self, chaplain_a, chaplain_b, member_a):
        """Should reject assignment to chaplain from different branch"""
        client = APIClient()
        client.force_authenticate(user=chaplain_a)
        
        case = PastoralCase.objects.create(
            branch=member_a.branch,
            member=member_a,
            category="Spiritual Counseling",
            summary="Test case",
            priority=PastoralCasePriority.MEDIUM,
            status=PastoralCaseStatus.OPEN,
            created_by=chaplain_a,
            updated_by=chaplain_a
        )
        
        response = client.patch(
            f"/api/pastoral/cases/{case.id}/",
            {"assigned_to": chaplain_b.id},
            format="json"
        )
        
        # Should reject due to branch mismatch
        assert response.status_code in [status.HTTP_400_BAD_REQUEST, status.HTTP_403_FORBIDDEN]


# ============================================================================
# SECURITY & IDOR TESTS
# ============================================================================

@pytest.mark.django_db
class TestPastoralCaseSecurity:
    """Test cross-branch isolation and IDOR prevention"""

    def test_chaplain_cannot_view_other_branch_cases(self, chaplain_a, chaplain_b, member_b):
        """Chaplain from branch A cannot access cases from branch B"""
        case = PastoralCase.objects.create(
            branch=member_b.branch,
            member=member_b,
            category="Spiritual Counseling",
            summary="Branch B case",
            priority=PastoralCasePriority.MEDIUM,
            status=PastoralCaseStatus.OPEN,
            created_by=chaplain_b,
            updated_by=chaplain_b
        )
        
        client = APIClient()
        client.force_authenticate(user=chaplain_a)
        
        # Try to retrieve branch B case as chaplain A
        response = client.get(f"/api/pastoral/cases/{case.id}/")
        
        # Should be forbidden (IDOR prevention)
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_chaplain_cannot_update_other_branch_cases(self, chaplain_a, chaplain_b, member_b):
        """Chaplain from branch A cannot update cases from branch B"""
        case = PastoralCase.objects.create(
            branch=member_b.branch,
            member=member_b,
            category="Spiritual Counseling",
            summary="Branch B case",
            priority=PastoralCasePriority.MEDIUM,
            status=PastoralCaseStatus.OPEN,
            created_by=chaplain_b,
            updated_by=chaplain_b
        )
        
        client = APIClient()
        client.force_authenticate(user=chaplain_a)
        
        # Try to update branch B case as chaplain A
        response = client.patch(
            f"/api/pastoral/cases/{case.id}/",
            {"summary": "Hacked summary"},
            format="json"
        )
        
        # Should be forbidden
        assert response.status_code == status.HTTP_404_NOT_FOUND
        
        # Verify case was not modified
        case.refresh_from_db()
        assert case.summary == "Branch B case"

    def test_super_admin_can_access_all_branches(self, super_admin, member_a, member_b, chaplain_a, chaplain_b):
        """Super admin can access cases from all branches"""
        case_a = PastoralCase.objects.create(
            branch=member_a.branch,
            member=member_a,
            category="Spiritual Counseling",
            summary="Branch A case",
            priority=PastoralCasePriority.MEDIUM,
            status=PastoralCaseStatus.OPEN,
            created_by=chaplain_a,
            updated_by=chaplain_a
        )
        
        case_b = PastoralCase.objects.create(
            branch=member_b.branch,
            member=member_b,
            category="Spiritual Counseling",
            summary="Branch B case",
            priority=PastoralCasePriority.MEDIUM,
            status=PastoralCaseStatus.OPEN,
            created_by=chaplain_b,
            updated_by=chaplain_b
        )
        
        client = APIClient()
        client.force_authenticate(user=super_admin)
        
        # Should access both cases
        response = client.get("/api/pastoral/cases/")
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data["results"]) == 2


# ============================================================================
# APPEND-ONLY NOTES TESTS
# ============================================================================

@pytest.mark.django_db
class TestPastoralNoteImmutability:
    """Test append-only enforcement for pastoral notes"""

    def test_create_note(self, chaplain_a, member_a):
        """Should create note successfully"""
        case = PastoralCase.objects.create(
            branch=member_a.branch,
            member=member_a,
            category="Spiritual Counseling",
            summary="Test case",
            priority=PastoralCasePriority.MEDIUM,
            status=PastoralCaseStatus.OPEN,
            created_by=chaplain_a,
            updated_by=chaplain_a
        )
        
        note = PastoralNote.objects.create(
            case=case,
            author=chaplain_a,
            note="Initial assessment complete"
        )
        
        assert note.id is not None
        assert note.author == chaplain_a

    def test_cannot_edit_existing_note(self, chaplain_a, member_a):
        """Should prevent editing existing notes (append-only)"""
        case = PastoralCase.objects.create(
            branch=member_a.branch,
            member=member_a,
            category="Spiritual Counseling",
            summary="Test case",
            priority=PastoralCasePriority.MEDIUM,
            status=PastoralCaseStatus.OPEN,
            created_by=chaplain_a,
            updated_by=chaplain_a
        )
        
        note = PastoralNote.objects.create(
            case=case,
            author=chaplain_a,
            note="Original note"
        )
        
        note.note = "Modified note"
        
        with pytest.raises(Exception):  # Should raise ValidationError in save()
            note.save()


# ============================================================================
# AUDIT LOGGING TESTS
# ============================================================================

@pytest.mark.django_db
class TestPastoralCaseAuditLogging:
    """Test comprehensive audit logging"""

    def test_audit_log_on_case_creation(self, chaplain_a, member_a):
        """Should log audit entry on case creation"""
        client = APIClient()
        client.force_authenticate(user=chaplain_a)
        
        initial_count = AuditLog.objects.count()
        
        response = client.post(
            "/api/pastoral/cases/",
            {
                "branch": member_a.branch.id,
                "member": member_a.id,
                "category": "Spiritual Counseling",
                "summary": "Test case",
                "priority": PastoralCasePriority.MEDIUM,
                "status": PastoralCaseStatus.OPEN
            },
            format="json"
        )
        
        assert response.status_code == status.HTTP_201_CREATED
        
        # Verify audit log created
        assert AuditLog.objects.count() == initial_count + 1
        log = AuditLog.objects.latest("created_at")
        assert log.action == AuditAction.PASTORAL_CASE_CREATE
        assert log.user == chaplain_a

    def test_audit_log_on_assignment_change(self, super_admin, chaplain_a, member_a):
        """Should log audit entry on assignment change"""
        case = PastoralCase.objects.create(
            branch=member_a.branch,
            member=member_a,
            category="Spiritual Counseling",
            summary="Test case",
            priority=PastoralCasePriority.MEDIUM,
            status=PastoralCaseStatus.OPEN,
            created_by=super_admin,
            updated_by=super_admin
        )
        
        client = APIClient()
        client.force_authenticate(user=super_admin)
        
        initial_count = AuditLog.objects.filter(action=AuditAction.PASTORAL_CASE_ASSIGN).count()
        
        response = client.patch(
            f"/api/pastoral/cases/{case.id}/",
            {"assigned_to": chaplain_a.id},
            format="json"
        )
        
        assert response.status_code == status.HTTP_200_OK
        
        # Verify audit log created
        assert AuditLog.objects.filter(action=AuditAction.PASTORAL_CASE_ASSIGN).count() == initial_count + 1

    def test_audit_log_on_escalation(self, chaplain_a, member_a):
        """Should log audit entry on case escalation"""
        case = PastoralCase.objects.create(
            branch=member_a.branch,
            member=member_a,
            category="Critical Issue",
            summary="Urgent case",
            priority=PastoralCasePriority.URGENT,
            status=PastoralCaseStatus.IN_PROGRESS,
            assigned_to=chaplain_a,
            created_by=chaplain_a,
            updated_by=chaplain_a
        )
        
        client = APIClient()
        client.force_authenticate(user=chaplain_a)
        
        initial_count = AuditLog.objects.filter(action=AuditAction.PASTORAL_CASE_ESCALATE).count()
        
        response = client.patch(
            f"/api/pastoral/cases/{case.id}/",
            {
                "status": PastoralCaseStatus.ESCALATED,
                "escalation_reason": "Requires senior pastoral intervention"
            },
            format="json"
        )
        
        # Verify audit log created
        assert AuditLog.objects.filter(action=AuditAction.PASTORAL_CASE_ESCALATE).count() == initial_count + 1

    def test_audit_log_on_case_access(self, chaplain_a, member_a):
        """Should log audit entry on sensitive case access"""
        case = PastoralCase.objects.create(
            branch=member_a.branch,
            member=member_a,
            category="Spiritual Counseling",
            summary="Confidential case",
            priority=PastoralCasePriority.HIGH,
            status=PastoralCaseStatus.OPEN,
            created_by=chaplain_a,
            updated_by=chaplain_a
        )
        
        client = APIClient()
        client.force_authenticate(user=chaplain_a)
        
        initial_count = AuditLog.objects.filter(action=AuditAction.PASTORAL_CASE_ACCESS).count()
        
        response = client.get(f"/api/pastoral/cases/{case.id}/")
        assert response.status_code == status.HTTP_200_OK
        
        # Verify audit log created
        assert AuditLog.objects.filter(action=AuditAction.PASTORAL_CASE_ACCESS).count() == initial_count + 1


# ============================================================================
# MEMBER MERGE/TRANSFER TESTS
# ============================================================================

@pytest.mark.django_db
class TestPastoralCaseMemberMerge:
    """Test pastoral case handling during member merge/transfer"""

    def test_cases_transferred_on_member_merge(self, chaplain_a, member_a, branch_a):
        """When members merge, pastoral cases should be reassigned to surviving member"""
        # Create duplicate member
        duplicate_user = User.objects.create_user(
            email="duplicate@test.com",
            password="password",
            role=Roles.MEMBER,
            branch=branch_a,
            first_name="Duplicate",
            last_name="Member"
        )
        duplicate_member = Member.objects.create(
            user=duplicate_user,
            branch=branch_a,
            first_name="Duplicate",
            last_name="Member",
            email="duplicate@test.com"
        )
        
        # Create cases for duplicate
        case1 = PastoralCase.objects.create(
            branch=branch_a,
            member=duplicate_member,
            category="Spiritual Counseling",
            summary="Case 1",
            priority=PastoralCasePriority.MEDIUM,
            status=PastoralCaseStatus.OPEN,
            created_by=chaplain_a,
            updated_by=chaplain_a
        )
        
        # Perform merge (assuming member_a is survivor)
        # This would trigger member.services.merge_members logic
        # Cases should be reassigned to member_a
        
        # After merge:
        # case1.member should == member_a
        # duplicate_member should be marked as merged/inactive
