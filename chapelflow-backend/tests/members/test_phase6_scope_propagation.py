import pytest

from apps.ministries.models import Group, GroupType


def _grant(role, *codes):
    from apps.accounts.models import Permission, RolePermission
    for code in codes:
        perm, _ = Permission.objects.get_or_create(code=code)
        RolePermission.objects.get_or_create(legacy_role_code=role, permission=perm)


@pytest.mark.django_db
class TestFellowshipLeaderMemberScope:
    """
    CRITICAL Phase 6 regression: a Fellowship Leader must only ever see
    members of their OWN Fellowship, never every member in the branch.
    Confirmed as a real bug (PoC) before this fix landed.
    """

    def _setup(self, branch_a):
        from apps.accounts.models import User
        from apps.groups.models import GroupMembership, GroupRole
        from apps.members.models import Member, MemberQRCode
        from common.constants.roles import Roles

        _grant(Roles.FELLOWSHIP_LEADER, "members.view")

        fellowship_a = Group.objects.create(branch=branch_a, name="Fellowship A", group_type=GroupType.FELLOWSHIP)
        fellowship_x = Group.objects.create(branch=branch_a, name="Fellowship X", group_type=GroupType.FELLOWSHIP)

        leader_user = User.objects.create_user(email="fl@test.com", password="Pass12345!", role=Roles.FELLOWSHIP_LEADER, branch=branch_a)
        leader_member = Member.objects.create(user=leader_user, branch=branch_a, first_name="L", last_name="A", fellowship=fellowship_a)
        MemberQRCode.objects.get_or_create(member=leader_member)
        GroupMembership.objects.create(group=fellowship_a, member=leader_member, role=GroupRole.LEADER, is_active=True)

        own = Member.objects.create(branch=branch_a, first_name="Own", last_name="Fellow", fellowship=fellowship_a)
        MemberQRCode.objects.get_or_create(member=own)
        other = Member.objects.create(branch=branch_a, first_name="Other", last_name="Fellow", fellowship=fellowship_x)
        MemberQRCode.objects.get_or_create(member=other)
        unaffiliated = Member.objects.create(branch=branch_a, first_name="No", last_name="Fellowship")
        MemberQRCode.objects.get_or_create(member=unaffiliated)

        return leader_user, own, other, unaffiliated

    def test_fellowship_leader_list_excludes_other_fellowship_members(self, api_client, branch_a):
        leader_user, own, other, unaffiliated = self._setup(branch_a)
        api_client.force_authenticate(user=leader_user)
        response = api_client.get("/api/v1/members/")
        seen_ids = {m["id"] for m in response.data["data"]}
        assert str(own.id) in seen_ids
        assert str(other.id) not in seen_ids
        assert str(unaffiliated.id) not in seen_ids

    def test_fellowship_leader_direct_id_access_to_other_fellowship_member_is_404(self, api_client, branch_a):
        leader_user, own, other, unaffiliated = self._setup(branch_a)
        api_client.force_authenticate(user=leader_user)
        response = api_client.get(f"/api/v1/members/{other.id}/")
        assert response.status_code == 404

    def test_fellowship_leader_can_still_retrieve_own_fellowship_member(self, api_client, branch_a):
        leader_user, own, other, unaffiliated = self._setup(branch_a)
        api_client.force_authenticate(user=leader_user)
        response = api_client.get(f"/api/v1/members/{own.id}/")
        assert response.status_code == 200

    def test_chapel_admin_unaffected_still_sees_whole_branch(self, api_client, branch_a, chapel_admin_a, seed_member_permissions):
        leader_user, own, other, unaffiliated = self._setup(branch_a)
        api_client.force_authenticate(user=chapel_admin_a)
        response = api_client.get("/api/v1/members/")
        seen_ids = {m["id"] for m in response.data["data"]}
        assert {str(own.id), str(other.id), str(unaffiliated.id)} <= seen_ids


@pytest.mark.django_db
class TestUnitHeadMemberScope:
    """Unit Head scope is via GroupMembership M2M, not a direct FK -- a structurally different code path from Fellowship, so tested separately."""

    def _setup(self, branch_a):
        from apps.accounts.models import User
        from apps.groups.models import GroupMembership, GroupRole
        from apps.members.models import Member, MemberQRCode
        from common.constants.roles import Roles

        _grant(Roles.UNIT_HEAD, "members.view")

        unit_a = Group.objects.create(branch=branch_a, name="Unit A", group_type=GroupType.UNIT)
        unit_b = Group.objects.create(branch=branch_a, name="Unit B", group_type=GroupType.UNIT)

        head_user = User.objects.create_user(email="uh@test.com", password="Pass12345!", role=Roles.UNIT_HEAD, branch=branch_a)
        head_member = Member.objects.create(user=head_user, branch=branch_a, first_name="Head", last_name="A")
        MemberQRCode.objects.get_or_create(member=head_member)
        GroupMembership.objects.create(group=unit_a, member=head_member, role=GroupRole.LEADER, is_active=True)

        own_unit_member = Member.objects.create(branch=branch_a, first_name="Unit", last_name="AMember")
        MemberQRCode.objects.get_or_create(member=own_unit_member)
        GroupMembership.objects.create(group=unit_a, member=own_unit_member, role=GroupRole.MEMBER, is_active=True)

        other_unit_member = Member.objects.create(branch=branch_a, first_name="Unit", last_name="BMember")
        MemberQRCode.objects.get_or_create(member=other_unit_member)
        GroupMembership.objects.create(group=unit_b, member=other_unit_member, role=GroupRole.MEMBER, is_active=True)

        return head_user, own_unit_member, other_unit_member

    def test_unit_head_sees_only_own_unit_members(self, api_client, branch_a):
        head_user, own_unit_member, other_unit_member = self._setup(branch_a)
        api_client.force_authenticate(user=head_user)
        response = api_client.get("/api/v1/members/")
        seen_ids = {m["id"] for m in response.data["data"]}
        assert str(own_unit_member.id) in seen_ids
        assert str(other_unit_member.id) not in seen_ids

    def test_unit_head_direct_id_access_to_other_unit_member_is_404(self, api_client, branch_a):
        head_user, own_unit_member, other_unit_member = self._setup(branch_a)
        api_client.force_authenticate(user=head_user)
        response = api_client.get(f"/api/v1/members/{other_unit_member.id}/")
        assert response.status_code == 404

    def test_inactive_membership_does_not_grant_visibility(self, api_client, branch_a):
        from apps.groups.models import GroupMembership, GroupRole
        from apps.members.models import Member, MemberQRCode

        head_user, own_unit_member, other_unit_member = self._setup(branch_a)
        unit_a = Group.objects.get(name="Unit A")
        left_member = Member.objects.create(branch=branch_a, first_name="Left", last_name="Unit")
        MemberQRCode.objects.get_or_create(member=left_member)
        GroupMembership.objects.create(group=unit_a, member=left_member, role=GroupRole.MEMBER, is_active=False)

        api_client.force_authenticate(user=head_user)
        response = api_client.get("/api/v1/members/")
        seen_ids = {m["id"] for m in response.data["data"]}
        assert str(left_member.id) not in seen_ids


@pytest.mark.django_db
class TestGroupsCatalogSubtreeScope:
    """
    Confirms current behavior of the groups-catalog endpoint for a
    Fellowship Leader: they see the Fellowship node they lead, but child
    Units/Ministries require their own GroupMembership(role=LEADER) row --
    documented here as a deliberate, tested boundary (not a silent gap).
    """

    def test_fellowship_leader_does_not_automatically_see_child_units_in_groups_catalog(self, api_client, branch_a):
        from apps.accounts.models import User
        from apps.groups.models import GroupMembership, GroupRole
        from apps.members.models import Member, MemberQRCode
        from common.constants.roles import Roles

        _grant(Roles.FELLOWSHIP_LEADER, "members.view")

        fellowship_a = Group.objects.create(branch=branch_a, name="Fellowship A", group_type=GroupType.FELLOWSHIP)
        child_unit = Group.objects.create(branch=branch_a, parent=fellowship_a, name="Child Unit", group_type=GroupType.UNIT)

        leader_user = User.objects.create_user(email="fl2@test.com", password="Pass12345!", role=Roles.FELLOWSHIP_LEADER, branch=branch_a)
        leader_member = Member.objects.create(user=leader_user, branch=branch_a, first_name="L", last_name="B")
        MemberQRCode.objects.get_or_create(member=leader_member)
        GroupMembership.objects.create(group=fellowship_a, member=leader_member, role=GroupRole.LEADER, is_active=True)

        api_client.force_authenticate(user=leader_user)
        response = api_client.get("/api/v1/groups-catalog/")
        seen_ids = {g["id"] for g in response.data["data"]}
        assert str(fellowship_a.id) in seen_ids
        assert str(child_unit.id) not in seen_ids
