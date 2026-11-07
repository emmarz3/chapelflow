import pytest


@pytest.mark.django_db
class TestGroupLeaderDeprecation:
    """
    Group.leader (single FK) is deprecated but not dropped (Phase 0
    remediation). GroupSerializer must build its leadership listing
    (`leaders`) purely from active GroupMembership rows, never from
    the deprecated `leader` field.
    """

    def test_leader_field_still_present_but_leaders_list_is_the_real_source(self, branch_a, chapel_admin_a, api_client, seed_member_permissions):
        from apps.groups.models import GroupMembership, GroupRole
        from apps.members.models import Member
        from apps.ministries.models import Group, GroupType

        group = Group.objects.create(branch=branch_a, name="Choir", group_type=GroupType.MINISTRY)
        leader_member = Member.objects.create(branch=branch_a, first_name="Choir", last_name="Leader")
        GroupMembership.objects.create(member=leader_member, group=group, role=GroupRole.LEADER)

        api_client.force_authenticate(user=chapel_admin_a)
        response = api_client.get(f"/api/v1/groups-catalog/{group.id}/")
        assert response.status_code == 200

        data = response.data["data"]
        assert data["leader"] is None  # deprecated FK was never set
        assert len(data["leaders"]) == 1
        assert data["leaders"][0]["member_id"] == str(leader_member.id)
        assert data["leaders"][0]["full_name"] == leader_member.full_name

    def test_leaders_list_reflects_multiple_active_leaders_not_deprecated_fk(self, branch_a, chapel_admin_a, api_client, seed_member_permissions):
        from apps.groups.models import GroupMembership, GroupRole
        from apps.members.models import Member
        from apps.ministries.models import Group, GroupType

        group = Group.objects.create(branch=branch_a, name="Ushers", group_type=GroupType.UNIT)
        leader_one = Member.objects.create(branch=branch_a, first_name="Usher", last_name="One")
        leader_two = Member.objects.create(branch=branch_a, first_name="Usher", last_name="Two")
        # Deliberately set the deprecated single FK to a THIRD, unrelated
        # member — proves `leaders` ignores it entirely.
        stale_leader = Member.objects.create(branch=branch_a, first_name="Stale", last_name="Leader")
        group.leader = stale_leader
        group.save(update_fields=["leader"])

        GroupMembership.objects.create(member=leader_one, group=group, role=GroupRole.LEADER)
        GroupMembership.objects.create(member=leader_two, group=group, role=GroupRole.LEADER)

        api_client.force_authenticate(user=chapel_admin_a)
        response = api_client.get(f"/api/v1/groups-catalog/{group.id}/")
        data = response.data["data"]

        ids = {leader["member_id"] for leader in data["leaders"]}
        assert ids == {str(leader_one.id), str(leader_two.id)}
        assert str(stale_leader.id) not in ids
        # The deprecated field is still readable (backward compat) even
        # though `leaders` correctly ignores it.
        assert data["leader"] == stale_leader.id

    def test_inactive_group_membership_leader_excluded_from_listing(self, branch_a, chapel_admin_a, api_client, seed_member_permissions):
        from apps.groups.models import GroupMembership, GroupRole
        from apps.members.models import Member
        from apps.ministries.models import Group, GroupType

        group = Group.objects.create(branch=branch_a, name="Media Team", group_type=GroupType.MINISTRY)
        former_leader = Member.objects.create(branch=branch_a, first_name="Former", last_name="Leader")
        GroupMembership.objects.create(member=former_leader, group=group, role=GroupRole.LEADER, is_active=False)

        api_client.force_authenticate(user=chapel_admin_a)
        response = api_client.get(f"/api/v1/groups-catalog/{group.id}/")
        assert response.data["data"]["leaders"] == []

    def test_active_leader_memberships_helper_matches_serializer_output(self, branch_a):
        """apps.groups.serializers.active_leader_memberships is the shared source of truth."""
        from apps.groups.models import GroupMembership, GroupRole
        from apps.groups.serializers import active_leader_memberships
        from apps.members.models import Member
        from apps.ministries.models import Group, GroupType

        group = Group.objects.create(branch=branch_a, name="Tech Team", group_type=GroupType.UNIT)
        leader = Member.objects.create(branch=branch_a, first_name="Tech", last_name="Head")
        member_only = Member.objects.create(branch=branch_a, first_name="Just", last_name="Member")
        GroupMembership.objects.create(member=leader, group=group, role=GroupRole.LEADER)
        GroupMembership.objects.create(member=member_only, group=group, role=GroupRole.MEMBER)

        result = list(active_leader_memberships(group))
        assert len(result) == 1
        assert result[0].member_id == leader.id
