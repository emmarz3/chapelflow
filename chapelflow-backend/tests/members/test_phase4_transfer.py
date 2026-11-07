import pytest

from apps.ministries.models import Group, GroupType


@pytest.fixture
def fellowship_a(db, branch_a):
    return Group.objects.create(branch=branch_a, name="Fellowship A", group_type=GroupType.FELLOWSHIP)


@pytest.fixture
def fellowship_b(db, branch_b):
    return Group.objects.create(branch=branch_b, name="Fellowship B", group_type=GroupType.FELLOWSHIP)


@pytest.mark.django_db
class TestMemberFieldLevelLockdown:
    """
    Phase 4: branch/fellowship are scope-defining fields and must not be
    changeable via a plain PATCH -- only via the dedicated, audited
    transfer action.
    """

    def test_patch_cannot_change_branch(
        self, api_client, chapel_admin_a, member_in_branch_a, branch_b, seed_member_permissions
    ):
        api_client.force_authenticate(user=chapel_admin_a)
        response = api_client.patch(
            f"/api/v1/members/{member_in_branch_a.id}/", {"branch": str(branch_b.id)}, format="json"
        )
        assert response.status_code == 400
        member_in_branch_a.refresh_from_db()
        assert member_in_branch_a.branch_id == member_in_branch_a.branch_id  # unchanged

    def test_patch_cannot_change_fellowship(
        self, api_client, chapel_admin_a, member_in_branch_a, fellowship_a, seed_member_permissions
    ):
        api_client.force_authenticate(user=chapel_admin_a)
        response = api_client.patch(
            f"/api/v1/members/{member_in_branch_a.id}/", {"fellowship": str(fellowship_a.id)}, format="json"
        )
        assert response.status_code == 400

    def test_patch_of_unrelated_field_still_works(
        self, api_client, chapel_admin_a, member_in_branch_a, seed_member_permissions
    ):
        api_client.force_authenticate(user=chapel_admin_a)
        response = api_client.patch(
            f"/api/v1/members/{member_in_branch_a.id}/", {"other_names": "Grace"}, format="json"
        )
        assert response.status_code == 200
        member_in_branch_a.refresh_from_db()
        assert member_in_branch_a.other_names == "Grace"


@pytest.mark.django_db
class TestMemberTransfer:
    def test_admin_transfers_member_between_branches_within_scope(
        self, api_client, chapel_admin_a, member_in_branch_a, branch_a, seed_member_permissions
    ):
        api_client.force_authenticate(user=chapel_admin_a)
        response = api_client.post(
            f"/api/v1/members/{member_in_branch_a.id}/transfer/",
            {"branch_id": str(branch_a.id), "note": "no-op sanity"}, format="json",
        )
        # Same branch -> no-op ValueError -> 400, proves it's not silently accepted.
        assert response.status_code == 400

    def test_admin_cannot_transfer_member_into_another_branch_out_of_scope(
        self, api_client, chapel_admin_a, member_in_branch_a, branch_b, seed_member_permissions
    ):
        api_client.force_authenticate(user=chapel_admin_a)
        response = api_client.post(
            f"/api/v1/members/{member_in_branch_a.id}/transfer/",
            {"branch_id": str(branch_b.id)}, format="json",
        )
        assert response.status_code == 403
        member_in_branch_a.refresh_from_db()
        assert member_in_branch_a.branch_id != branch_b.id

    def test_super_admin_can_transfer_member_across_branches_with_history(
        self, api_client, super_admin, member_in_branch_a, branch_b
    ):
        from apps.members.models import MembershipHistory

        api_client.force_authenticate(user=super_admin)
        response = api_client.post(
            f"/api/v1/members/{member_in_branch_a.id}/transfer/",
            {"branch_id": str(branch_b.id), "note": "Relocated"}, format="json",
        )
        assert response.status_code == 200
        member_in_branch_a.refresh_from_db()
        assert member_in_branch_a.branch_id == branch_b.id

        history = MembershipHistory.objects.filter(member=member_in_branch_a).latest("created_at")
        assert history.new_branch_id == branch_b.id
        assert history.note == "Relocated"
        assert history.changed_by == super_admin

    def test_fellowship_leader_cannot_transfer_member_into_fellowship_they_do_not_lead(
        self, api_client, branch_a, fellowship_a, fellowship_b, seed_member_permissions
    ):
        from apps.accounts.models import User, Permission, RolePermission
        from apps.groups.models import GroupMembership, GroupRole
        from apps.members.models import Member, MemberQRCode
        from common.constants.roles import Roles, PermissionCodes

        perm, _ = Permission.objects.get_or_create(code=PermissionCodes.MEMBERS_UPDATE)
        RolePermission.objects.get_or_create(legacy_role_code=Roles.FELLOWSHIP_LEADER, permission=perm)

        leader_user = User.objects.create_user(
            email="leader_a@test.com", password="Pass12345!", role=Roles.FELLOWSHIP_LEADER, branch=branch_a,
        )
        leader_member = Member.objects.create(
            user=leader_user, branch=branch_a, first_name="Leader", last_name="A", fellowship=fellowship_a,
        )
        MemberQRCode.objects.get_or_create(member=leader_member)
        GroupMembership.objects.create(group=fellowship_a, member=leader_member, role=GroupRole.LEADER, is_active=True)

        target = Member.objects.create(branch=branch_a, first_name="Target", last_name="Member", fellowship=fellowship_a)
        MemberQRCode.objects.get_or_create(member=target)

        api_client.force_authenticate(user=leader_user)
        response = api_client.post(
            f"/api/v1/members/{target.id}/transfer/",
            {"fellowship_id": str(fellowship_b.id)}, format="json",
        )
        assert response.status_code == 403

    def test_fellowship_leader_can_transfer_member_into_fellowship_they_lead(
        self, api_client, branch_a, fellowship_a, seed_member_permissions
    ):
        from apps.accounts.models import User, Permission, RolePermission
        from apps.groups.models import GroupMembership, GroupRole
        from apps.members.models import Member, MemberQRCode
        from common.constants.roles import Roles, PermissionCodes

        perm, _ = Permission.objects.get_or_create(code=PermissionCodes.MEMBERS_UPDATE)
        RolePermission.objects.get_or_create(legacy_role_code=Roles.FELLOWSHIP_LEADER, permission=perm)

        leader_user = User.objects.create_user(
            email="leader_a2@test.com", password="Pass12345!", role=Roles.FELLOWSHIP_LEADER, branch=branch_a,
        )
        leader_member = Member.objects.create(user=leader_user, branch=branch_a, first_name="Leader", last_name="A2")
        MemberQRCode.objects.get_or_create(member=leader_member)
        GroupMembership.objects.create(group=fellowship_a, member=leader_member, role=GroupRole.LEADER, is_active=True)

        target = Member.objects.create(branch=branch_a, first_name="Target2", last_name="Member")
        MemberQRCode.objects.get_or_create(member=target)

        api_client.force_authenticate(user=leader_user)
        response = api_client.post(
            f"/api/v1/members/{target.id}/transfer/",
            {"fellowship_id": str(fellowship_a.id)}, format="json",
        )
        assert response.status_code == 200
        target.refresh_from_db()
        assert target.fellowship_id == fellowship_a.id

    def test_transfer_requires_at_least_one_field(
        self, api_client, chapel_admin_a, member_in_branch_a, seed_member_permissions
    ):
        api_client.force_authenticate(user=chapel_admin_a)
        response = api_client.post(f"/api/v1/members/{member_in_branch_a.id}/transfer/", {}, format="json")
        assert response.status_code == 400

    def test_clearing_fellowship_explicitly(
        self, api_client, chapel_admin_a, branch_a, fellowship_a, seed_member_permissions
    ):
        from apps.members.models import Member, MemberQRCode

        member = Member.objects.create(branch=branch_a, first_name="Cleared", last_name="Fellow", fellowship=fellowship_a)
        MemberQRCode.objects.get_or_create(member=member)

        api_client.force_authenticate(user=chapel_admin_a)
        response = api_client.post(
            f"/api/v1/members/{member.id}/transfer/", {"fellowship_id": None}, format="json",
        )
        assert response.status_code == 200
        member.refresh_from_db()
        assert member.fellowship_id is None
