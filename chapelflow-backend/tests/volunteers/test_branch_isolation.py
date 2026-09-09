import pytest


def _grant_chaplain(codes):
    from apps.accounts.models import Permission, RolePermission
    from common.constants.roles import Roles

    for code in codes:
        perm, _ = Permission.objects.get_or_create(code=code)
        RolePermission.objects.get_or_create(legacy_role_code=Roles.CHAPLAIN, permission=perm)


@pytest.fixture
def volunteer_member_a(db, branch_a):
    from apps.accounts.models import User
    from apps.members.models import Member

    user = User.objects.create_user(matric_no="SWE/2024/010", password="Pass12345!", role="MEMBER", branch=branch_a)
    return Member.objects.create(user=user, branch=branch_a, first_name="Vera", last_name="Onboard")


@pytest.fixture
def volunteer_member_b(db, branch_b):
    from apps.accounts.models import User
    from apps.members.models import Member

    user = User.objects.create_user(matric_no="SWE/2024/011", password="Pass12345!", role="MEMBER", branch=branch_b)
    return Member.objects.create(user=user, branch=branch_b, first_name="Victor", last_name="Onboard")


@pytest.mark.django_db
class TestVolunteerProfileBranchIsolation:
    """
    Phase 1 fix regression tests: both volunteer viewsets used to
    hand-roll branch-only scoping (missing the Chaplain org-wide tier),
    same root cause as the other five Phase 1 scoping fixes.
    """

    def test_chapel_admin_sees_only_own_branch_profiles(
        self, api_client, chapel_admin_a, seed_member_permissions, volunteer_member_a, volunteer_member_b
    ):
        from apps.volunteers.models import VolunteerProfile

        profile_a = VolunteerProfile.objects.create(member=volunteer_member_a)
        profile_b = VolunteerProfile.objects.create(member=volunteer_member_b)

        api_client.force_authenticate(user=chapel_admin_a)
        response = api_client.get("/api/v1/volunteers/profiles/")
        assert response.status_code == 200
        ids = {row["id"] for row in response.data["data"]}
        assert str(profile_a.id) in ids
        assert str(profile_b.id) not in ids

    def test_chaplain_sees_profiles_across_own_org(
        self, api_client, make_user, branch_a, seed_member_permissions, volunteer_member_a, volunteer_member_b
    ):
        from apps.volunteers.models import VolunteerProfile
        from common.constants.roles import PermissionCodes

        _grant_chaplain([PermissionCodes.MEMBERS_VIEW])
        profile_a = VolunteerProfile.objects.create(member=volunteer_member_a)
        profile_b = VolunteerProfile.objects.create(member=volunteer_member_b)

        chaplain = make_user(role="CHAPLAIN", branch=branch_a, email="chaplain@test.com")
        api_client.force_authenticate(user=chaplain)
        response = api_client.get("/api/v1/volunteers/profiles/")
        assert response.status_code == 200
        ids = {row["id"] for row in response.data["data"]}
        assert ids == {str(profile_a.id), str(profile_b.id)}

    def test_chapel_admin_cannot_fetch_another_branchs_profile_by_id(
        self, api_client, chapel_admin_a, seed_member_permissions, volunteer_member_b
    ):
        from apps.volunteers.models import VolunteerProfile

        profile_b = VolunteerProfile.objects.create(member=volunteer_member_b)
        api_client.force_authenticate(user=chapel_admin_a)
        response = api_client.get(f"/api/v1/volunteers/profiles/{profile_b.id}/")
        assert response.status_code == 404


@pytest.mark.django_db
class TestVolunteerAssignmentBranchIsolation:
    def test_chapel_admin_sees_only_own_branch_assignments(
        self, api_client, chapel_admin_a, seed_member_permissions, volunteer_member_a, volunteer_member_b
    ):
        from apps.volunteers.models import VolunteerAssignment, VolunteerProfile

        profile_a = VolunteerProfile.objects.create(member=volunteer_member_a)
        profile_b = VolunteerProfile.objects.create(member=volunteer_member_b)
        assignment_a = VolunteerAssignment.objects.create(volunteer=profile_a, role="USHER")
        VolunteerAssignment.objects.create(volunteer=profile_b, role="CHOIR")

        api_client.force_authenticate(user=chapel_admin_a)
        response = api_client.get("/api/v1/volunteers/assignments/")
        assert response.status_code == 200
        ids = {row["id"] for row in response.data["data"]}
        assert ids == {str(assignment_a.id)}
