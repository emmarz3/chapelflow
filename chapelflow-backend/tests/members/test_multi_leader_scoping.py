import pytest


@pytest.mark.django_db
class TestMultiLeaderGroupScoping:
    """
    Spec section 6/7: Fellowship Leader / Unit Head / Ministry-Group Leader
    are scoped to the Group(s) they actively lead via GroupMembership
    (role=LEADER) — not Group.leader (a single FK kept only for backward
    compatibility) — and a Group can have more than one active leader.
    """

    @pytest.fixture
    def fellowship_setup(self, branch_a):
        from apps.groups.models import GroupMembership, GroupRole
        from apps.members.models import Member
        from apps.ministries.models import Group, GroupType

        fellowship_led = Group.objects.create(branch=branch_a, name="Led Fellowship", group_type=GroupType.FELLOWSHIP)
        fellowship_not_led = Group.objects.create(branch=branch_a, name="Other Fellowship", group_type=GroupType.FELLOWSHIP)
        unit = Group.objects.create(branch=branch_a, name="Some Unit", group_type=GroupType.UNIT)

        leader_member = Member.objects.create(branch=branch_a, first_name="Leader", last_name="One")
        second_leader_member = Member.objects.create(branch=branch_a, first_name="Leader", last_name="Two")

        GroupMembership.objects.create(member=leader_member, group=fellowship_led, role=GroupRole.LEADER)
        # A second, independent leader of the SAME group — proves multi-leader support.
        GroupMembership.objects.create(member=second_leader_member, group=fellowship_led, role=GroupRole.LEADER)

        return {
            "fellowship_led": fellowship_led,
            "fellowship_not_led": fellowship_not_led,
            "unit": unit,
            "leader_member": leader_member,
            "second_leader_member": second_leader_member,
        }

    def test_fellowship_leader_sees_only_led_fellowship(self, api_client, branch_a, fellowship_setup, make_user):
        from apps.accounts.models import Permission, RolePermission
        from common.constants.roles import PermissionCodes, Roles

        perm, _ = Permission.objects.get_or_create(code=PermissionCodes.MEMBERS_VIEW)
        RolePermission.objects.get_or_create(legacy_role_code=Roles.FELLOWSHIP_LEADER, permission=perm)

        user = make_user(role="FELLOWSHIP_LEADER", branch=branch_a, email="fl@test.com")
        member = fellowship_setup["leader_member"]
        member.user = user
        member.save(update_fields=["user"])

        api_client.force_authenticate(user=user)
        response = api_client.get("/api/v1/groups-catalog/")
        assert response.status_code == 200

        names = {g["name"] for g in response.data["data"]}
        assert "Led Fellowship" in names
        assert "Other Fellowship" not in names
        assert "Some Unit" not in names  # different group_type, not led anyway

    def test_second_leader_of_same_group_also_sees_it(self, api_client, branch_a, fellowship_setup, make_user):
        from apps.accounts.models import Permission, RolePermission
        from common.constants.roles import PermissionCodes, Roles

        perm, _ = Permission.objects.get_or_create(code=PermissionCodes.MEMBERS_VIEW)
        RolePermission.objects.get_or_create(legacy_role_code=Roles.FELLOWSHIP_LEADER, permission=perm)

        user = make_user(role="FELLOWSHIP_LEADER", branch=branch_a, email="fl2@test.com")
        member = fellowship_setup["second_leader_member"]
        member.user = user
        member.save(update_fields=["user"])

        api_client.force_authenticate(user=user)
        response = api_client.get("/api/v1/groups-catalog/")
        names = {g["name"] for g in response.data["data"]}
        assert "Led Fellowship" in names

    def test_group_membership_list_scoped_to_led_group_only(self, api_client, branch_a, fellowship_setup, make_user):
        from apps.accounts.models import Permission, RolePermission
        from apps.groups.models import GroupMembership, GroupRole
        from apps.members.models import Member
        from common.constants.roles import PermissionCodes, Roles

        perm, _ = Permission.objects.get_or_create(code=PermissionCodes.MEMBERS_VIEW)
        RolePermission.objects.get_or_create(legacy_role_code=Roles.FELLOWSHIP_LEADER, permission=perm)

        rando = Member.objects.create(branch=branch_a, first_name="Rando", last_name="Member")
        GroupMembership.objects.create(member=rando, group=fellowship_setup["fellowship_not_led"], role=GroupRole.MEMBER)

        user = make_user(role="FELLOWSHIP_LEADER", branch=branch_a, email="fl3@test.com")
        member = fellowship_setup["leader_member"]
        member.user = user
        member.save(update_fields=["user"])

        api_client.force_authenticate(user=user)
        response = api_client.get("/api/v1/group-memberships/")
        assert response.status_code == 200
        group_ids = {row["group"] for row in response.data["data"]}
        assert str(fellowship_setup["fellowship_not_led"].id) not in group_ids

    def test_unit_head_not_scoped_to_fellowships_they_do_not_lead(self, api_client, branch_a, fellowship_setup, make_user):
        """A role's group-type restriction is enforced, not just group identity."""
        from apps.accounts.models import Permission, RolePermission
        from common.constants.roles import PermissionCodes, Roles

        perm, _ = Permission.objects.get_or_create(code=PermissionCodes.MEMBERS_VIEW)
        RolePermission.objects.get_or_create(legacy_role_code=Roles.UNIT_HEAD, permission=perm)

        user = make_user(role="UNIT_HEAD", branch=branch_a, email="uh@test.com")
        member = fellowship_setup["leader_member"]
        member.user = user
        member.save(update_fields=["user"])
        # This member leads a FELLOWSHIP, but the account role is UNIT_HEAD —
        # scoping keys off role-required group_type (UNIT), so this leadership
        # of a Fellowship must not leak through.

        api_client.force_authenticate(user=user)
        response = api_client.get("/api/v1/groups-catalog/")
        names = {g["name"] for g in response.data["data"]}
        assert "Led Fellowship" not in names

    def test_chapel_admin_unaffected_by_leader_scoping(self, api_client, branch_a, fellowship_setup, chapel_admin_a, seed_member_permissions):
        """Non-assignment-scoped roles still see everything in their branch, unchanged."""
        api_client.force_authenticate(user=chapel_admin_a)
        response = api_client.get("/api/v1/groups-catalog/")
        names = {g["name"] for g in response.data["data"]}
        assert {"Led Fellowship", "Other Fellowship", "Some Unit"}.issubset(names)
