import pytest


@pytest.mark.django_db
class TestBranchIsolation:
    """
    Regression tests for the branch-scoping bug: a viewset that overrides
    get_queryset() directly (instead of get_base_queryset()) silently
    bypasses BranchScopedQuerysetMixin's filtering. These tests exercise
    the real HTTP layer end-to-end so a future regression of this kind
    fails loudly here rather than shipping.
    """

    def test_admin_cannot_list_another_branchs_members(
        self, api_client, chapel_admin_b, member_in_branch_a, seed_member_permissions
    ):
        api_client.force_authenticate(user=chapel_admin_b)
        response = api_client.get("/api/v1/members/")
        assert response.status_code == 200
        assert response.data["data"] == []

    def test_admin_cannot_fetch_another_branchs_member_by_id(
        self, api_client, chapel_admin_b, member_in_branch_a, seed_member_permissions
    ):
        api_client.force_authenticate(user=chapel_admin_b)
        response = api_client.get(f"/api/v1/members/{member_in_branch_a.id}/")
        # Must be 404, not 403 -- a 403 would confirm the record exists in another branch.
        assert response.status_code == 404

    def test_admin_can_see_own_branchs_members(
        self, api_client, chapel_admin_a, member_in_branch_a, seed_member_permissions
    ):
        api_client.force_authenticate(user=chapel_admin_a)
        response = api_client.get("/api/v1/members/")
        assert response.status_code == 200
        assert len(response.data["data"]) == 1
        assert response.data["data"][0]["id"] == str(member_in_branch_a.id)

    def test_super_admin_sees_all_branches(
        self, api_client, super_admin, member_in_branch_a, seed_member_permissions
    ):
        api_client.force_authenticate(user=super_admin)
        response = api_client.get("/api/v1/members/")
        assert response.status_code == 200
        assert len(response.data["data"]) == 1

    def test_leader_with_no_branch_assigned_sees_nothing(
        self, api_client, member_in_branch_a, seed_member_permissions
    ):
        from apps.accounts.models import User

        homeless_admin = User.objects.create_user(
            email="noassign@test.com", password="Pass12345!", role="CHAPEL_ADMIN", branch=None
        )
        api_client.force_authenticate(user=homeless_admin)
        response = api_client.get("/api/v1/members/")
        assert response.status_code == 200
        assert response.data["data"] == []

    def test_unauthorized_role_cannot_create_member(self, api_client, branch_a):
        from apps.accounts.models import User

        visitor = User.objects.create_user(email="visitor@test.com", password="Pass12345!", role="VISITOR")
        api_client.force_authenticate(user=visitor)
        response = api_client.post(
            "/api/v1/members/",
            {"branch": str(branch_a.id), "first_name": "New", "last_name": "Person"},
            format="json",
        )
        assert response.status_code == 403
