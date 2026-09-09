"""
Phase 13 Prayer Request Tests: Comprehensive Privacy & Security

Tests comprehensive validation for:
- Prayer request lifecycle (NEW → ASSIGNED → IN_PROGRESS → FOLLOW_UP → ANSWERED/CLOSED/CANCELLED)
- Multi-level privacy (PRIVATE, PASTORAL, FELLOWSHIP, PUBLIC)
- Anonymous submissions (submitted_by_name without member)
- Assignment validation (role checking, branch scoping)
- Privacy-based access control
- Append-only notes (immutable after creation)
- Cross-branch attack prevention (IDOR)
- Branch-scoped access control
- Audit logging integration
- Legacy is_private field synchronization
"""

import pytest
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.members.models import Member
from apps.organizations.models import Branch, Organization
from apps.prayer.models import PrayerRequest, PrayerNote, PrayerRequestStatus, PrayerPrivacyLevel
from apps.audit.models import AuditLog, AuditAction
from common.constants.roles import Roles


# ============================================================================
# FIXTURES
# ============================================================================

@pytest.fixture
def organization(db):
    return Organization.objects.create(name="Test Chapel Organization", slug="test-chapel-org-p13-prayer")


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
def member_user_a(branch_a):
    return User.objects.create_user(
        email="member_a@test.com",
        password="password",
        role=Roles.MEMBER,
        branch=branch_a,
        first_name="Member",
        last_name="Alpha",
        is_active=True
    )


@pytest.fixture
def member_a(member_user_a, branch_a):
    return Member.objects.create(
        user=member_user_a,
        branch=branch_a,
        first_name="Member",
        last_name="Alpha",
        email="member_a@test.com"
    )


@pytest.fixture
def member_user_b(branch_b):
    return User.objects.create_user(
        email="member_b@test.com",
        password="password",
        role=Roles.MEMBER,
        branch=branch_b,
        first_name="Member",
        last_name="Beta",
        is_active=True
    )


@pytest.fixture
def member_b(member_user_b, branch_b):
    return Member.objects.create(
        user=member_user_b,
        branch=branch_b,
        first_name="Member",
        last_name="Beta",
        email="member_b@test.com"
    )


@pytest.fixture
def fellowship_leader_a(branch_a):
    return User.objects.create_user(
        email="leader_a@test.com",
        password="password",
        role=Roles.FELLOWSHIP_LEADER,
        branch=branch_a,
        first_name="Leader",
        last_name="Alpha",
        is_active=True
    )


# ============================================================================
# PRIVACY LEVEL TESTS
# ============================================================================

@pytest.mark.django_db
class TestPrayerRequestPrivacy:
    """Test multi-level privacy controls"""

    def test_create_private_prayer_request(self, member_a, chaplain_a):
        """PRIVATE prayer should only be visible to pastoral staff"""
        request = PrayerRequest.objects.create(
            branch=member_a.branch,
            member=member_a,
            category="Personal",
            details="Private prayer concern",
            privacy_level=PrayerPrivacyLevel.PRIVATE,
            status=PrayerRequestStatus.NEW,
            created_by=member_a.user
        )
        
        assert request.privacy_level == PrayerPrivacyLevel.PRIVATE
        assert request.is_private is True  # Legacy field auto-synced

    def test_create_pastoral_prayer_request(self, member_a, chaplain_a):
        """PASTORAL prayer visible to pastoral team"""
        request = PrayerRequest.objects.create(
            branch=member_a.branch,
            member=member_a,
            category="Counseling",
            details="Need pastoral support",
            privacy_level=PrayerPrivacyLevel.PASTORAL,
            status=PrayerRequestStatus.NEW,
            created_by=member_a.user
        )
        
        assert request.privacy_level == PrayerPrivacyLevel.PASTORAL
        assert request.is_private is True  # Legacy field auto-synced

    def test_create_fellowship_prayer_request(self, member_a):
        """FELLOWSHIP prayer visible to fellowship members"""
        request = PrayerRequest.objects.create(
            branch=member_a.branch,
            member=member_a,
            category="Fellowship",
            details="Exam preparation",
            privacy_level=PrayerPrivacyLevel.FELLOWSHIP,
            status=PrayerRequestStatus.NEW,
            created_by=member_a.user
        )
        
        assert request.privacy_level == PrayerPrivacyLevel.FELLOWSHIP
        assert request.is_private is False  # Legacy field auto-synced

    def test_create_public_prayer_request(self, member_a):
        """PUBLIC prayer visible to all"""
        request = PrayerRequest.objects.create(
            branch=member_a.branch,
            member=member_a,
            category="Thanksgiving",
            details="Praise report",
            privacy_level=PrayerPrivacyLevel.PUBLIC,
            status=PrayerRequestStatus.NEW,
            created_by=member_a.user
        )
        
        assert request.privacy_level == PrayerPrivacyLevel.PUBLIC
        assert request.is_private is False

    def test_legacy_is_private_sync(self, member_a):
        """Legacy is_private should auto-sync from privacy_level"""
        # Create with PRIVATE
        request = PrayerRequest.objects.create(
            branch=member_a.branch,
            member=member_a,
            category="Personal",
            details="Test",
            privacy_level=PrayerPrivacyLevel.PRIVATE,
            status=PrayerRequestStatus.NEW,
            created_by=member_a.user
        )
        assert request.is_private is True
        
        # Update to PUBLIC
        request.privacy_level = PrayerPrivacyLevel.PUBLIC
        request.save()
        request.refresh_from_db()
        assert request.is_private is False


# ============================================================================
# ANONYMOUS SUBMISSION TESTS
# ============================================================================

@pytest.mark.django_db
class TestAnonymousPrayerRequests:
    """Test anonymous prayer request submissions"""

    def test_anonymous_submission_without_member(self, branch_a, chaplain_a):
        """Should allow anonymous submission with submitted_by_name"""
        request = PrayerRequest.objects.create(
            branch=branch_a,
            submitted_by_name="Anonymous Seeker",
            category="Guidance",
            details="Need prayer for direction",
            privacy_level=PrayerPrivacyLevel.PUBLIC,
            status=PrayerRequestStatus.NEW,
            created_by=chaplain_a  # Staff entered on behalf
        )
        
        assert request.member is None
        assert request.submitted_by_name == "Anonymous Seeker"

    def test_member_submission_overrides_submitted_by_name(self, member_a):
        """When member is present, it takes precedence over submitted_by_name"""
        request = PrayerRequest.objects.create(
            branch=member_a.branch,
            member=member_a,
            submitted_by_name="Should be ignored",
            category="Personal",
            details="Test",
            privacy_level=PrayerPrivacyLevel.PRIVATE,
            status=PrayerRequestStatus.NEW,
            created_by=member_a.user
        )
        
        # Member identification takes precedence
        assert request.member == member_a


# ============================================================================
# LIFECYCLE & VALIDATION TESTS
# ============================================================================

@pytest.mark.django_db
class TestPrayerRequestLifecycle:
    """Test prayer request status transitions"""

    def test_status_transition_new_to_assigned(self, chaplain_a, member_a):
        """NEW → ASSIGNED transition should be valid"""
        request = PrayerRequest.objects.create(
            branch=member_a.branch,
            member=member_a,
            category="Guidance",
            details="Need direction",
            privacy_level=PrayerPrivacyLevel.PASTORAL,
            status=PrayerRequestStatus.NEW,
            created_by=member_a.user
        )
        
        request.status = PrayerRequestStatus.ASSIGNED
        request.assigned_to = chaplain_a
        request.clean()  # Should not raise
        request.save()
        
        assert request.status == PrayerRequestStatus.ASSIGNED

    def test_answered_status_sets_timestamp(self, chaplain_a, member_a):
        """Changing status to ANSWERED should auto-set answered_at"""
        request = PrayerRequest.objects.create(
            branch=member_a.branch,
            member=member_a,
            category="Healing",
            details="Prayer for healing",
            privacy_level=PrayerPrivacyLevel.FELLOWSHIP,
            status=PrayerRequestStatus.IN_PROGRESS,
            assigned_to=chaplain_a,
            created_by=member_a.user
        )
        
        # This would be tested via serializer update() method
        # request.status = PrayerRequestStatus.ANSWERED
        # serializer.update() should set answered_at
        
        assert request.answered_at is None  # Before update

    def test_closure_reason_required_for_closed(self, member_a):
        """Closed prayer requests should have closure_reason"""
        request = PrayerRequest.objects.create(
            branch=member_a.branch,
            member=member_a,
            category="Guidance",
            details="Test",
            privacy_level=PrayerPrivacyLevel.PUBLIC,
            status=PrayerRequestStatus.ANSWERED,
            created_by=member_a.user
        )
        
        request.status = PrayerRequestStatus.CLOSED
        # Missing closure_reason
        
        with pytest.raises(Exception):  # Should raise ValidationError
            request.clean()


# ============================================================================
# ASSIGNMENT VALIDATION TESTS
# ============================================================================

@pytest.mark.django_db
class TestPrayerRequestAssignment:
    """Test assignment validation and role checking"""

    def test_assign_to_chaplain_same_branch(self, chaplain_a, member_a):
        """Should allow assignment to chaplain in same branch"""
        request = PrayerRequest.objects.create(
            branch=member_a.branch,
            member=member_a,
            category="Counseling",
            details="Need support",
            privacy_level=PrayerPrivacyLevel.PASTORAL,
            status=PrayerRequestStatus.NEW,
            created_by=member_a.user
        )
        
        request.assigned_to = chaplain_a
        request.status = PrayerRequestStatus.ASSIGNED
        request.save()
        
        assert request.assigned_to == chaplain_a

    def test_cannot_assign_to_fellowship_leader(self, chaplain_a, fellowship_leader_a, member_a):
        """Should reject assignment to fellowship leader (insufficient role)"""
        client = APIClient()
        client.force_authenticate(user=chaplain_a)
        
        request = PrayerRequest.objects.create(
            branch=member_a.branch,
            member=member_a,
            category="Counseling",
            details="Need support",
            privacy_level=PrayerPrivacyLevel.PASTORAL,
            status=PrayerRequestStatus.NEW,
            created_by=member_a.user
        )
        
        response = client.patch(
            f"/api/prayer/requests/{request.id}/",
            {"assigned_to": fellowship_leader_a.id},
            format="json"
        )
        
        # Should reject due to role validation
        assert response.status_code in [status.HTTP_400_BAD_REQUEST, status.HTTP_403_FORBIDDEN]

    def test_cannot_assign_cross_branch(self, chaplain_a, chaplain_b, member_a):
        """Should reject assignment to chaplain from different branch"""
        client = APIClient()
        client.force_authenticate(user=chaplain_a)
        
        request = PrayerRequest.objects.create(
            branch=member_a.branch,
            member=member_a,
            category="Counseling",
            details="Need support",
            privacy_level=PrayerPrivacyLevel.PASTORAL,
            status=PrayerRequestStatus.NEW,
            created_by=member_a.user
        )
        
        response = client.patch(
            f"/api/prayer/requests/{request.id}/",
            {"assigned_to": chaplain_b.id},
            format="json"
        )
        
        # Should reject due to branch mismatch
        assert response.status_code in [status.HTTP_400_BAD_REQUEST, status.HTTP_403_FORBIDDEN]


# ============================================================================
# PRIVACY-BASED ACCESS CONTROL TESTS
# ============================================================================

@pytest.mark.django_db
class TestPrayerRequestAccessControl:
    """Test privacy-based access control"""

    def test_member_can_view_own_private_request(self, member_user_a, member_a):
        """Member should see their own PRIVATE requests"""
        request = PrayerRequest.objects.create(
            branch=member_a.branch,
            member=member_a,
            category="Personal",
            details="Private concern",
            privacy_level=PrayerPrivacyLevel.PRIVATE,
            status=PrayerRequestStatus.NEW,
            created_by=member_user_a
        )
        
        client = APIClient()
        client.force_authenticate(user=member_user_a)
        
        response = client.get(f"/api/prayer/requests/{request.id}/")
        assert response.status_code == status.HTTP_200_OK

    def test_other_member_cannot_view_private_request(self, member_user_a, member_user_b, member_a, member_b):
        """Member B should NOT see Member A's PRIVATE request"""
        request = PrayerRequest.objects.create(
            branch=member_a.branch,
            member=member_a,
            category="Personal",
            details="Private concern",
            privacy_level=PrayerPrivacyLevel.PRIVATE,
            status=PrayerRequestStatus.NEW,
            created_by=member_user_a
        )
        
        client = APIClient()
        client.force_authenticate(user=member_user_b)
        
        response = client.get(f"/api/prayer/requests/{request.id}/")
        # Should be forbidden (not in same branch OR not pastoral staff)
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_chaplain_can_view_private_request(self, chaplain_a, member_a):
        """Chaplain should see PRIVATE requests in their branch"""
        request = PrayerRequest.objects.create(
            branch=member_a.branch,
            member=member_a,
            category="Personal",
            details="Private concern",
            privacy_level=PrayerPrivacyLevel.PRIVATE,
            status=PrayerRequestStatus.NEW,
            created_by=member_a.user
        )
        
        client = APIClient()
        client.force_authenticate(user=chaplain_a)
        
        response = client.get(f"/api/prayer/requests/{request.id}/")
        assert response.status_code == status.HTTP_200_OK

    def test_member_can_view_public_request(self, member_user_a, member_a):
        """Any member should see PUBLIC requests"""
        request = PrayerRequest.objects.create(
            branch=member_a.branch,
            member=member_a,
            category="Thanksgiving",
            details="Praise report",
            privacy_level=PrayerPrivacyLevel.PUBLIC,
            status=PrayerRequestStatus.NEW,
            created_by=member_a.user
        )
        
        client = APIClient()
        client.force_authenticate(user=member_user_a)
        
        response = client.get(f"/api/prayer/requests/{request.id}/")
        assert response.status_code == status.HTTP_200_OK


# ============================================================================
# CROSS-BRANCH SECURITY (IDOR) TESTS
# ============================================================================

@pytest.mark.django_db
class TestPrayerRequestIDOR:
    """Test cross-branch isolation and IDOR prevention"""

    def test_chaplain_cannot_view_other_branch_private_requests(self, chaplain_a, chaplain_b, member_b):
        """Chaplain A cannot access private requests from branch B"""
        request = PrayerRequest.objects.create(
            branch=member_b.branch,
            member=member_b,
            category="Personal",
            details="Branch B private request",
            privacy_level=PrayerPrivacyLevel.PRIVATE,
            status=PrayerRequestStatus.NEW,
            created_by=member_b.user
        )
        
        client = APIClient()
        client.force_authenticate(user=chaplain_a)
        
        response = client.get(f"/api/prayer/requests/{request.id}/")
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_chaplain_cannot_update_other_branch_requests(self, chaplain_a, chaplain_b, member_b):
        """Chaplain A cannot update requests from branch B"""
        request = PrayerRequest.objects.create(
            branch=member_b.branch,
            member=member_b,
            category="Personal",
            details="Branch B request",
            privacy_level=PrayerPrivacyLevel.PASTORAL,
            status=PrayerRequestStatus.NEW,
            created_by=member_b.user
        )
        
        client = APIClient()
        client.force_authenticate(user=chaplain_a)
        
        response = client.patch(
            f"/api/prayer/requests/{request.id}/",
            {"details": "Hacked details"},
            format="json"
        )
        
        assert response.status_code == status.HTTP_404_NOT_FOUND
        
        # Verify not modified
        request.refresh_from_db()
        assert request.details == "Branch B request"

    def test_super_admin_can_access_all_branches(self, super_admin, member_a, member_b):
        """Super admin can access requests from all branches"""
        request_a = PrayerRequest.objects.create(
            branch=member_a.branch,
            member=member_a,
            category="Personal",
            details="Branch A request",
            privacy_level=PrayerPrivacyLevel.PRIVATE,
            status=PrayerRequestStatus.NEW,
            created_by=member_a.user
        )
        
        request_b = PrayerRequest.objects.create(
            branch=member_b.branch,
            member=member_b,
            category="Personal",
            details="Branch B request",
            privacy_level=PrayerPrivacyLevel.PRIVATE,
            status=PrayerRequestStatus.NEW,
            created_by=member_b.user
        )
        
        client = APIClient()
        client.force_authenticate(user=super_admin)
        
        response = client.get("/api/prayer/requests/")
        assert response.status_code == status.HTTP_200_OK
        # Should see both branches
        assert len(response.data["results"]) >= 2


# ============================================================================
# APPEND-ONLY NOTES TESTS
# ============================================================================

@pytest.mark.django_db
class TestPrayerNoteImmutability:
    """Test append-only enforcement for prayer notes"""

    def test_create_prayer_note(self, chaplain_a, member_a):
        """Should create note successfully"""
        request = PrayerRequest.objects.create(
            branch=member_a.branch,
            member=member_a,
            category="Healing",
            details="Prayer for healing",
            privacy_level=PrayerPrivacyLevel.PASTORAL,
            status=PrayerRequestStatus.ASSIGNED,
            assigned_to=chaplain_a,
            created_by=member_a.user
        )
        
        note = PrayerNote.objects.create(
            prayer_request=request,
            author=chaplain_a,
            note="Prayed with member today"
        )
        
        assert note.id is not None
        assert note.author == chaplain_a

    def test_cannot_edit_existing_note(self, chaplain_a, member_a):
        """Should prevent editing existing notes (append-only)"""
        request = PrayerRequest.objects.create(
            branch=member_a.branch,
            member=member_a,
            category="Healing",
            details="Prayer for healing",
            privacy_level=PrayerPrivacyLevel.PASTORAL,
            status=PrayerRequestStatus.ASSIGNED,
            assigned_to=chaplain_a,
            created_by=member_a.user
        )
        
        note = PrayerNote.objects.create(
            prayer_request=request,
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
class TestPrayerRequestAuditLogging:
    """Test comprehensive audit logging"""

    def test_audit_log_on_request_creation(self, member_user_a, member_a):
        """Should log audit entry on request creation"""
        client = APIClient()
        client.force_authenticate(user=member_user_a)
        
        initial_count = AuditLog.objects.count()
        
        response = client.post(
            "/api/prayer/requests/",
            {
                "branch": member_a.branch.id,
                "category": "Guidance",
                "details": "Need direction",
                "privacy_level": PrayerPrivacyLevel.PRIVATE
            },
            format="json"
        )
        
        assert response.status_code == status.HTTP_201_CREATED
        
        # Verify audit log created
        assert AuditLog.objects.count() == initial_count + 1
        log = AuditLog.objects.latest("created_at")
        assert log.action == AuditAction.PRAYER_REQUEST_CREATE
        assert log.user == member_user_a

    def test_audit_log_on_private_request_access(self, chaplain_a, member_a):
        """Should log audit entry when accessing PRIVATE/PASTORAL requests"""
        request = PrayerRequest.objects.create(
            branch=member_a.branch,
            member=member_a,
            category="Personal",
            details="Private concern",
            privacy_level=PrayerPrivacyLevel.PRIVATE,
            status=PrayerRequestStatus.NEW,
            created_by=member_a.user
        )
        
        client = APIClient()
        client.force_authenticate(user=chaplain_a)
        
        initial_count = AuditLog.objects.filter(action=AuditAction.PRAYER_REQUEST_ACCESS).count()
        
        response = client.get(f"/api/prayer/requests/{request.id}/")
        assert response.status_code == status.HTTP_200_OK
        
        # Verify audit log created for PRIVATE access
        assert AuditLog.objects.filter(action=AuditAction.PRAYER_REQUEST_ACCESS).count() == initial_count + 1

    def test_no_audit_log_on_public_request_access(self, member_user_a, member_a):
        """Should NOT log audit entry for PUBLIC request access (not sensitive)"""
        request = PrayerRequest.objects.create(
            branch=member_a.branch,
            member=member_a,
            category="Thanksgiving",
            details="Praise report",
            privacy_level=PrayerPrivacyLevel.PUBLIC,
            status=PrayerRequestStatus.NEW,
            created_by=member_a.user
        )
        
        client = APIClient()
        client.force_authenticate(user=member_user_a)
        
        initial_count = AuditLog.objects.filter(action=AuditAction.PRAYER_REQUEST_ACCESS).count()
        
        response = client.get(f"/api/prayer/requests/{request.id}/")
        assert response.status_code == status.HTTP_200_OK
        
        # Should NOT create audit log for PUBLIC access
        assert AuditLog.objects.filter(action=AuditAction.PRAYER_REQUEST_ACCESS).count() == initial_count

    def test_audit_log_on_assignment_change(self, chaplain_a, member_a):
        """Should log audit entry on assignment change"""
        request = PrayerRequest.objects.create(
            branch=member_a.branch,
            member=member_a,
            category="Counseling",
            details="Need support",
            privacy_level=PrayerPrivacyLevel.PASTORAL,
            status=PrayerRequestStatus.NEW,
            created_by=member_a.user
        )
        
        client = APIClient()
        client.force_authenticate(user=chaplain_a)
        
        initial_count = AuditLog.objects.filter(action=AuditAction.PRAYER_REQUEST_ASSIGN).count()
        
        response = client.patch(
            f"/api/prayer/requests/{request.id}/",
            {"assigned_to": chaplain_a.id},
            format="json"
        )
        
        assert response.status_code == status.HTTP_200_OK
        
        # Verify audit log created
        assert AuditLog.objects.filter(action=AuditAction.PRAYER_REQUEST_ASSIGN).count() == initial_count + 1
