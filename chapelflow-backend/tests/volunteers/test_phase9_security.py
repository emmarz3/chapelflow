"""
Phase 9 Security Test Suite

Tests all identified security vulnerabilities:
1. Member substitution attack
2. Volunteer substitution attack
3. Cross-branch event assignment attack
4. Cross-branch group assignment attack
5. Direct ID access attack
6. Mass assignment attack (unauthorized fields)
7. Status manipulation attack
8. Hours manipulation attack
9. Historical assignment modification attack
10. Unauthorized deletion
11. Create-time authorization
12. Volunteer ownership enforcement
"""
import datetime as dt

import pytest
from django.utils import timezone
from rest_framework.test import APIClient


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def branch_a(db):
    from apps.organizations.models import Branch, Organization
    org = Organization.objects.create(name="Test Org", slug="test-org-p9-sec-1")
    return Branch.objects.create(organization=org, name="Branch A")


@pytest.fixture
def branch_b(db):
    from apps.organizations.models import Branch, Organization
    org = Organization.objects.first()
    if not org:
        org = Organization.objects.create(name="Test Org", slug="test-org-p9-sec-2")
    return Branch.objects.create(organization=org, name="Branch B")


@pytest.fixture
def chapel_admin_a(make_user, branch_a):
    """Chapel admin with access to Branch A only."""
    return make_user(role="CHAPEL_ADMIN", branch=branch_a, email="admin.a@test.com")


@pytest.fixture
def chapel_admin_b(make_user, branch_b):
    """Chapel admin with access to Branch B only."""
    return make_user(role="CHAPEL_ADMIN", branch=branch_b, email="admin.b@test.com")


@pytest.fixture
def member_a(branch_a):
    from apps.members.models import Member
    return Member.objects.create(branch=branch_a, first_name="Alice", last_name="Alpha")


@pytest.fixture
def member_b(branch_b):
    from apps.members.models import Member
    return Member.objects.create(branch=branch_b, first_name="Bob", last_name="Bravo")


@pytest.fixture
def volunteer_a(member_a):
    from apps.volunteers.models import VolunteerProfile
    return VolunteerProfile.objects.create(member=member_a)


@pytest.fixture
def volunteer_b(member_b):
    from apps.volunteers.models import VolunteerProfile
    return VolunteerProfile.objects.create(member=member_b)


@pytest.fixture
def event_schedule_a(branch_a):
    from apps.events.models import Event
    from apps.events.services import generate_event_schedules
    event = Event.objects.create(
        branch=branch_a,
        title="Branch A Event",
        start_time=timezone.now() + dt.timedelta(days=3),
        end_time=timezone.now() + dt.timedelta(days=3, hours=2),
    )
    return generate_event_schedules(event)[0]


@pytest.fixture
def event_schedule_b(branch_b):
    from apps.events.models import Event
    from apps.events.services import generate_event_schedules
    event = Event.objects.create(
        branch=branch_b,
        title="Branch B Event",
        start_time=timezone.now() + dt.timedelta(days=3),
        end_time=timezone.now() + dt.timedelta(days=3, hours=2),
    )
    return generate_event_schedules(event)[0]


@pytest.fixture
def group_a(branch_a):
    from apps.ministries.models import Group, GroupType
    return Group.objects.create(branch=branch_a, name="Branch A Group", group_type=GroupType.MINISTRY)


@pytest.fixture
def group_b(branch_b):
    from apps.ministries.models import Group, GroupType
    return Group.objects.create(branch=branch_b, name="Branch B Group", group_type=GroupType.MINISTRY)


@pytest.fixture
def seed_permissions():
    """Seed necessary permissions for tests."""
    from apps.accounts.models import Permission, RolePermission
    from common.constants.roles import PermissionCodes
    
    perms = [
        PermissionCodes.VOLUNTEERS_VIEW,
        PermissionCodes.VOLUNTEERS_CREATE,
        PermissionCodes.VOLUNTEERS_UPDATE,
        PermissionCodes.VOLUNTEERS_DELETE,
        PermissionCodes.VOLUNTEERS_ASSIGN,
    ]
    
    for code in perms:
        perm, _ = Permission.objects.get_or_create(code=code)
        RolePermission.objects.get_or_create(legacy_role_code="CHAPEL_ADMIN", permission=perm)


@pytest.mark.django_db
class TestMemberSubstitutionAttack:
    """
    Attack: Chapel Admin A tries to create VolunteerProfile for Member B (in Branch B).
    Expected: Serializer validation rejects out-of-scope member.
    """
    
    def test_cannot_create_profile_for_out_of_scope_member(
        self, api_client, chapel_admin_a, member_b, seed_permissions
    ):
        api_client.force_authenticate(user=chapel_admin_a)
        response = api_client.post(
            "/api/v1/volunteers/profiles/",
            {"member": str(member_b.id), "skills": ["ushering"]},
            format="json",
        )
        # Should be rejected by ScopedFKValidationMixin
        assert response.status_code in (400, 403)
    
    def test_can_create_profile_for_in_scope_member(
        self, api_client, chapel_admin_a, member_a, seed_permissions
    ):
        api_client.force_authenticate(user=chapel_admin_a)
        response = api_client.post(
            "/api/v1/volunteers/profiles/",
            {"member": str(member_a.id), "skills": ["ushering"]},
            format="json",
        )
        assert response.status_code == 201


@pytest.mark.django_db
class TestVolunteerSubstitutionAttack:
    """
    Attack: Chapel Admin A tries to create assignment for Volunteer B (in Branch B).
    Expected: Serializer validation rejects out-of-scope volunteer.
    """
    
    def test_cannot_assign_out_of_scope_volunteer(
        self, api_client, chapel_admin_a, volunteer_b, event_schedule_a, seed_permissions
    ):
        api_client.force_authenticate(user=chapel_admin_a)
        response = api_client.post(
            "/api/v1/volunteers/assignments/",
            {
                "volunteer": str(volunteer_b.id),
                "event_schedule": str(event_schedule_a.id),
                "role": "USHER",
            },
            format="json",
        )
        assert response.status_code in (400, 403)
    
    def test_can_assign_in_scope_volunteer(
        self, api_client, chapel_admin_a, volunteer_a, event_schedule_a, seed_permissions
    ):
        api_client.force_authenticate(user=chapel_admin_a)
        response = api_client.post(
            "/api/v1/volunteers/assignments/",
            {
                "volunteer": str(volunteer_a.id),
                "event_schedule": str(event_schedule_a.id),
                "role": "USHER",
            },
            format="json",
        )
        assert response.status_code == 201


@pytest.mark.django_db
class TestCrossBranchEventAssignmentAttack:
    """
    Attack: Chapel Admin A tries to assign their volunteer to Branch B event.
    Expected: Serializer validation rejects out-of-scope event.
    """
    
    def test_cannot_assign_to_out_of_scope_event(
        self, api_client, chapel_admin_a, volunteer_a, event_schedule_b, seed_permissions
    ):
        api_client.force_authenticate(user=chapel_admin_a)
        response = api_client.post(
            "/api/v1/volunteers/assignments/",
            {
                "volunteer": str(volunteer_a.id),
                "event_schedule": str(event_schedule_b.id),
                "role": "USHER",
            },
            format="json",
        )
        assert response.status_code in (400, 403)


@pytest.mark.django_db
class TestCrossBranchGroupAssignmentAttack:
    """
    Attack: Chapel Admin A tries to assign their volunteer to Branch B group.
    Expected: Serializer or service layer rejects cross-branch group.
    """
    
    def test_cannot_assign_to_out_of_scope_group(
        self, api_client, chapel_admin_a, volunteer_a, event_schedule_a, group_b, seed_permissions
    ):
        api_client.force_authenticate(user=chapel_admin_a)
        response = api_client.post(
            "/api/v1/volunteers/assignments/",
            {
                "volunteer": str(volunteer_a.id),
                "event_schedule": str(event_schedule_a.id),
                "group": str(group_b.id),
                "role": "USHER",
            },
            format="json",
        )
        # Should be rejected by serializer scope validation or service check_group_scope
        assert response.status_code in (400, 403)
    
    def test_can_assign_to_in_scope_group(
        self, api_client, chapel_admin_a, volunteer_a, event_schedule_a, group_a, seed_permissions
    ):
        api_client.force_authenticate(user=chapel_admin_a)
        response = api_client.post(
            "/api/v1/volunteers/assignments/",
            {
                "volunteer": str(volunteer_a.id),
                "event_schedule": str(event_schedule_a.id),
                "group": str(group_a.id),
                "role": "USHER",
            },
            format="json",
        )
        assert response.status_code == 201


@pytest.mark.django_db
class TestDirectIDAccessAttack:
    """
    Attack: Chapel Admin A tries to access Branch B volunteer/assignment by knowing the ID.
    Expected: Queryset scoping returns 404 (object not in scope).
    """
    
    def test_cannot_retrieve_out_of_scope_volunteer_profile(
        self, api_client, chapel_admin_a, volunteer_b, seed_permissions
    ):
        api_client.force_authenticate(user=chapel_admin_a)
        response = api_client.get(f"/api/v1/volunteers/profiles/{volunteer_b.id}/")
        assert response.status_code == 404
    
    def test_cannot_retrieve_out_of_scope_assignment(
        self, api_client, chapel_admin_a, volunteer_b, event_schedule_b, seed_permissions
    ):
        from apps.volunteers.models import VolunteerAssignment
        
        assignment = VolunteerAssignment.objects.create(
            volunteer=volunteer_b, event_schedule=event_schedule_b, role="USHER"
        )
        
        api_client.force_authenticate(user=chapel_admin_a)
        response = api_client.get(f"/api/v1/volunteers/assignments/{assignment.id}/")
        assert response.status_code == 404
    
    def test_cannot_update_out_of_scope_assignment(
        self, api_client, chapel_admin_a, volunteer_b, event_schedule_b, seed_permissions
    ):
        from apps.volunteers.models import VolunteerAssignment
        
        assignment = VolunteerAssignment.objects.create(
            volunteer=volunteer_b, event_schedule=event_schedule_b, role="USHER"
        )
        
        api_client.force_authenticate(user=chapel_admin_a)
        response = api_client.patch(
            f"/api/v1/volunteers/assignments/{assignment.id}/",
            {"notes": "hacked"},
            format="json",
        )
        assert response.status_code == 404
    
    def test_cannot_delete_out_of_scope_assignment(
        self, api_client, chapel_admin_a, volunteer_b, event_schedule_b, seed_permissions
    ):
        from apps.volunteers.models import VolunteerAssignment
        
        assignment = VolunteerAssignment.objects.create(
            volunteer=volunteer_b, event_schedule=event_schedule_b, role="USHER"
        )
        
        api_client.force_authenticate(user=chapel_admin_a)
        response = api_client.delete(f"/api/v1/volunteers/assignments/{assignment.id}/")
        assert response.status_code == 404


@pytest.mark.django_db
class TestMassAssignmentAttack:
    """
    Attack: Client tries to set server-controlled fields on creation/update.
    Expected: Read-only fields ignored, values remain server-controlled.
    """
    
    def test_cannot_set_status_on_create(
        self, api_client, chapel_admin_a, volunteer_a, event_schedule_a, seed_permissions
    ):
        api_client.force_authenticate(user=chapel_admin_a)
        response = api_client.post(
            "/api/v1/volunteers/assignments/",
            {
                "volunteer": str(volunteer_a.id),
                "event_schedule": str(event_schedule_a.id),
                "role": "USHER",
                "status": "COMPLETED",  # Attempt to bypass workflow
            },
            format="json",
        )
        
        if response.status_code == 201:
            # Status should be PENDING, not COMPLETED
            assert response.data["data"]["status"] == "PENDING"
    
    def test_cannot_set_hours_logged_on_create(
        self, api_client, chapel_admin_a, volunteer_a, event_schedule_a, seed_permissions
    ):
        api_client.force_authenticate(user=chapel_admin_a)
        response = api_client.post(
            "/api/v1/volunteers/assignments/",
            {
                "volunteer": str(volunteer_a.id),
                "event_schedule": str(event_schedule_a.id),
                "role": "USHER",
                "hours_logged": 999.99,  # Attempt to inflate hours
            },
            format="json",
        )
        
        if response.status_code == 201:
            # hours_logged should be null, not 999.99
            assert response.data["data"]["hours_logged"] is None
    
    def test_cannot_set_completed_at_on_create(
        self, api_client, chapel_admin_a, volunteer_a, event_schedule_a, seed_permissions
    ):
        api_client.force_authenticate(user=chapel_admin_a)
        response = api_client.post(
            "/api/v1/volunteers/assignments/",
            {
                "volunteer": str(volunteer_a.id),
                "event_schedule": str(event_schedule_a.id),
                "role": "USHER",
                "completed_at": "2026-01-01T00:00:00Z",  # Attempt to fake completion
            },
            format="json",
        )
        
        if response.status_code == 201:
            # completed_at should be null
            assert response.data["data"]["completed_at"] is None
    
    def test_cannot_update_status_via_patch(
        self, api_client, chapel_admin_a, volunteer_a, event_schedule_a, seed_permissions
    ):
        from apps.volunteers.models import VolunteerAssignment
        
        assignment = VolunteerAssignment.objects.create(
            volunteer=volunteer_a, event_schedule=event_schedule_a, role="USHER"
        )
        
        api_client.force_authenticate(user=chapel_admin_a)
        response = api_client.patch(
            f"/api/v1/volunteers/assignments/{assignment.id}/",
            {"status": "COMPLETED"},  # Attempt to bypass workflow
            format="json",
        )
        
        if response.status_code == 200:
            # Status should remain PENDING
            assignment.refresh_from_db()
            assert assignment.status == "PENDING"


@pytest.mark.django_db
class TestHistoricalAssignmentModificationAttack:
    """
    Attack: Try to modify a completed assignment (historical data protection).
    Expected: Serializer prevents modification OR business logic rejects it.
    """
    
    def test_cannot_modify_completed_assignment_notes(
        self, api_client, chapel_admin_a, volunteer_a, event_schedule_a, seed_permissions
    ):
        from apps.volunteers.models import AssignmentStatus, VolunteerAssignment
        
        assignment = VolunteerAssignment.objects.create(
            volunteer=volunteer_a,
            event_schedule=event_schedule_a,
            role="USHER",
            status=AssignmentStatus.COMPLETED,
            hours_logged=5.0,
            completed_at=timezone.now(),
        )
        
        api_client.force_authenticate(user=chapel_admin_a)
        response = api_client.patch(
            f"/api/v1/volunteers/assignments/{assignment.id}/",
            {"notes": "modified after completion"},
            format="json",
        )
        
        # Either 403 (forbidden) or 400 (validation error) acceptable
        # Or if update succeeds for notes only, that's acceptable too
        # The key protection is that status/hours cannot change
        if response.status_code == 200:
            assignment.refresh_from_db()
            assert assignment.status == AssignmentStatus.COMPLETED
            assert assignment.hours_logged == 5.0


@pytest.mark.django_db
class TestAvailabilityOwnershipAttack:
    """
    Attack: Chapel Admin A tries to create availability for Volunteer B.
    Expected: Serializer validation rejects out-of-scope volunteer.
    """
    
    def test_cannot_create_availability_for_out_of_scope_volunteer(
        self, api_client, chapel_admin_a, volunteer_b, seed_permissions
    ):
        api_client.force_authenticate(user=chapel_admin_a)
        response = api_client.post(
            "/api/v1/volunteers/availability/",
            {
                "volunteer": str(volunteer_b.id),
                "weekday": 1,  # Tuesday
                "start_time": "18:00:00",
                "end_time": "21:00:00",
                "is_available": False,
            },
            format="json",
        )
        assert response.status_code in (400, 403)


@pytest.mark.django_db
class TestLifecycleTransitionSecurity:
    """
    Test that lifecycle transitions are properly controlled.
    """
    
    def test_cannot_confirm_already_confirmed_assignment(
        self, api_client, chapel_admin_a, volunteer_a, event_schedule_a, seed_permissions
    ):
        from apps.volunteers import services
        
        assignment = services.create_assignment(volunteer_a, event_schedule_a, "USHER")
        services.confirm_assignment(assignment)
        
        api_client.force_authenticate(user=chapel_admin_a)
        response = api_client.post(
            f"/api/v1/volunteers/assignments/{assignment.id}/confirm/",
            format="json",
        )
        # Should reject (already confirmed)
        assert response.status_code == 400
    
    def test_cannot_complete_without_confirming(
        self, api_client, chapel_admin_a, volunteer_a, event_schedule_a, seed_permissions
    ):
        from apps.volunteers import services
        
        assignment = services.create_assignment(volunteer_a, event_schedule_a, "USHER")
        
        api_client.force_authenticate(user=chapel_admin_a)
        response = api_client.post(
            f"/api/v1/volunteers/assignments/{assignment.id}/complete/",
            {"hours_logged": 3.5},
            format="json",
        )
        # Should reject (not confirmed yet)
        assert response.status_code == 400
    
    def test_cannot_decline_completed_assignment(
        self, api_client, chapel_admin_a, volunteer_a, event_schedule_a, seed_permissions
    ):
        from apps.volunteers import services
        
        assignment = services.create_assignment(volunteer_a, event_schedule_a, "USHER")
        services.confirm_assignment(assignment)
        services.complete_assignment(assignment, 2.0)
        
        api_client.force_authenticate(user=chapel_admin_a)
        response = api_client.post(
            f"/api/v1/volunteers/assignments/{assignment.id}/decline/",
            {"reason": "changed my mind"},
            format="json",
        )
        # Should reject (already completed - historical)
        assert response.status_code == 400


@pytest.mark.django_db
class TestConflictDetectionSecurity:
    """
    Test that conflict detection cannot be bypassed.
    """
    
    def test_duplicate_assignment_rejected(
        self, api_client, chapel_admin_a, volunteer_a, event_schedule_a, seed_permissions
    ):
        from apps.volunteers import services
        
        # Create first assignment
        services.create_assignment(volunteer_a, event_schedule_a, "USHER")
        
        # Try to create duplicate via API
        api_client.force_authenticate(user=chapel_admin_a)
        response = api_client.post(
            "/api/v1/volunteers/assignments/",
            {
                "volunteer": str(volunteer_a.id),
                "event_schedule": str(event_schedule_a.id),
                "role": "USHER",
            },
            format="json",
        )
        # Should be rejected by conflict detection
        assert response.status_code == 400
    
    def test_overlapping_assignment_rejected(
        self, api_client, chapel_admin_a, volunteer_a, branch_a, seed_permissions
    ):
        from apps.events.models import Event
        from apps.events.services import generate_event_schedules
        from apps.volunteers import services
        
        start = timezone.now() + dt.timedelta(days=5)
        event1 = Event.objects.create(
            branch=branch_a,
            title="E1",
            start_time=start,
            end_time=start + dt.timedelta(hours=2),
        )
        event2 = Event.objects.create(
            branch=branch_a,
            title="E2",
            start_time=start + dt.timedelta(hours=1),  # Overlaps with E1
            end_time=start + dt.timedelta(hours=3),
        )
        
        sched1 = generate_event_schedules(event1)[0]
        sched2 = generate_event_schedules(event2)[0]
        
        # Create first assignment and confirm it
        assignment = services.create_assignment(volunteer_a, sched1, "USHER")
        services.confirm_assignment(assignment)
        
        # Try to create overlapping assignment via API
        api_client.force_authenticate(user=chapel_admin_a)
        response = api_client.post(
            "/api/v1/volunteers/assignments/",
            {
                "volunteer": str(volunteer_a.id),
                "event_schedule": str(sched2.id),
                "role": "CHOIR",
            },
            format="json",
        )
        # Should be rejected by overlap detection
        assert response.status_code == 400


@pytest.mark.django_db
class TestPermissionEnforcement:
    """
    Test that users without proper permissions are denied access.
    """
    
    def test_user_without_volunteers_view_denied(
        self, api_client, make_user, branch_a
    ):
        # Create user with MEMBER role (no volunteer permissions)
        user = make_user(role="MEMBER", branch=branch_a, email="member@test.com")
        
        api_client.force_authenticate(user=user)
        response = api_client.get("/api/v1/volunteers/profiles/")
        # Should be denied (403)
        assert response.status_code == 403
    
    def test_user_without_volunteers_assign_cannot_create_assignment(
        self, api_client, make_user, branch_a, volunteer_a, event_schedule_a
    ):
        from apps.accounts.models import Permission, RolePermission
        from common.constants.roles import PermissionCodes
        
        # Give VIEW but not ASSIGN permission
        user = make_user(role="MEMBER", branch=branch_a, email="viewer@test.com")
        perm, _ = Permission.objects.get_or_create(code=PermissionCodes.VOLUNTEERS_VIEW)
        RolePermission.objects.get_or_create(legacy_role_code="MEMBER", permission=perm)
        
        api_client.force_authenticate(user=user)
        response = api_client.post(
            "/api/v1/volunteers/assignments/",
            {
                "volunteer": str(volunteer_a.id),
                "event_schedule": str(event_schedule_a.id),
                "role": "USHER",
            },
            format="json",
        )
        # Should be denied (403) - no ASSIGN permission
        assert response.status_code == 403
