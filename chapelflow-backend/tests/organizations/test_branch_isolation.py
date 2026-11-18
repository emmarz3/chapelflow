import pytest


@pytest.mark.django_db
class TestBranchViewSetScoping:
    """
    Phase 1 fix regression tests: BranchViewSet used to hand-roll its own
    scoping and, in doing so, never gave ORG_WIDE_SCOPE_ROLES (Chaplain)
    org-wide visibility -- a Chaplain fell through to a branch-only
    filter and could only see their own single branch. Also exercises
    the new "id" self-lookup path added to BranchScopedQuerysetMixin,
    since Branch is the model being scoped (not something pointing at
    one).
    """

    def test_chapel_admin_sees_only_own_branch(self, api_client, chapel_admin_a, branch_a, branch_b):
        api_client.force_authenticate(user=chapel_admin_a)
        response = api_client.get("/api/v1/branches/")
        assert response.status_code == 200
        ids = {row["id"] for row in response.data["data"]}
        assert ids == {str(branch_a.id)}

    def test_chaplain_sees_every_branch_in_own_org_but_not_other_orgs(
        self, api_client, make_user, branch_a, branch_b, branch_org2
    ):
        chaplain = make_user(role="CHAPLAIN", branch=branch_a, email="chaplain@test.com")
        api_client.force_authenticate(user=chaplain)
        response = api_client.get("/api/v1/branches/")
        assert response.status_code == 200
        ids = {row["id"] for row in response.data["data"]}
        assert ids == {str(branch_a.id), str(branch_b.id)}
        assert str(branch_org2.id) not in ids

    def test_super_admin_sees_every_branch_across_every_org(
        self, api_client, super_admin, branch_a, branch_b, branch_org2
    ):
        api_client.force_authenticate(user=super_admin)
        response = api_client.get("/api/v1/branches/")
        assert response.status_code == 200
        ids = {row["id"] for row in response.data["data"]}
        assert ids == {str(branch_a.id), str(branch_b.id), str(branch_org2.id)}

    def test_chapel_admin_cannot_fetch_another_orgs_branch_by_id(self, api_client, chapel_admin_a, branch_org2):
        api_client.force_authenticate(user=chapel_admin_a)
        response = api_client.get(f"/api/v1/branches/{branch_org2.id}/")
        assert response.status_code == 404
