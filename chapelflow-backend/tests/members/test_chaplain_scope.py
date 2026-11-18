import pytest


@pytest.mark.django_db
class TestChaplainOrgWideScope:
    """
    Spec section 6/9: Chaplain sees every branch in their own Organization
    (not just their assigned branch, unlike Chapel Admin) but is NOT
    global like Super Admin — never another organization's data, and
    never technical/system-config access.
    """

    def test_chaplain_sees_members_across_branches_in_same_org(
        self, api_client, branch_a, branch_b, make_user, member_in_branch_a
    ):
        from apps.members.models import Member
        from apps.accounts.models import Permission, RolePermission
        from common.constants.roles import PermissionCodes, Roles

        perm, _ = Permission.objects.get_or_create(code=PermissionCodes.MEMBERS_VIEW)
        RolePermission.objects.get_or_create(legacy_role_code=Roles.CHAPLAIN, permission=perm)

        member_b = Member.objects.create(branch=branch_b, first_name="Branch", last_name="B")
        chaplain = make_user(role="CHAPLAIN", branch=branch_a, email="chaplain@test.com")

        api_client.force_authenticate(user=chaplain)
        response = api_client.get("/api/v1/members/")
        assert response.status_code == 200
        ids = {m["id"] for m in response.data["data"]}
        assert str(member_in_branch_a.id) in ids
        assert str(member_b.id) in ids

    def test_chapel_admin_still_scoped_to_own_branch_only(
        self, api_client, branch_a, branch_b, chapel_admin_a, member_in_branch_a, seed_member_permissions
    ):
        from apps.members.models import Member

        member_b = Member.objects.create(branch=branch_b, first_name="Branch", last_name="B")
        api_client.force_authenticate(user=chapel_admin_a)
        response = api_client.get("/api/v1/members/")
        ids = {m["id"] for m in response.data["data"]}
        assert str(member_in_branch_a.id) in ids
        assert str(member_b.id) not in ids
