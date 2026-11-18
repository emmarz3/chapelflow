import pytest

from apps.ministries.models import Group, GroupType


@pytest.fixture
def fellowship_a(db, branch_a):
    return Group.objects.create(branch=branch_a, name="Fellowship A", group_type=GroupType.FELLOWSHIP)


@pytest.fixture
def fellowship_b(db, branch_b):
    return Group.objects.create(branch=branch_b, name="Fellowship B", group_type=GroupType.FELLOWSHIP)


def _fellowship_leader(branch, *, member_kwargs=None):
    from apps.accounts.models import User, Permission, RolePermission
    from apps.members.models import Member, MemberQRCode
    from common.constants.roles import Roles, PermissionCodes

    perm, _ = Permission.objects.get_or_create(code=PermissionCodes.MEMBERS_UPDATE)
    RolePermission.objects.get_or_create(legacy_role_code=Roles.FELLOWSHIP_LEADER, permission=perm)
    perm2, _ = Permission.objects.get_or_create(code=PermissionCodes.MEMBERS_CREATE)
    RolePermission.objects.get_or_create(legacy_role_code=Roles.FELLOWSHIP_LEADER, permission=perm2)

    user = User.objects.create_user(
        email=f"leader-{branch.id}@test.com", password="Pass12345!", role=Roles.FELLOWSHIP_LEADER, branch=branch,
    )
    member = Member.objects.create(branch=branch, user=user, first_name="Leader", last_name=str(branch.id)[:8], **(member_kwargs or {}))
    MemberQRCode.objects.get_or_create(member=member)
    return user, member


@pytest.mark.django_db
class TestGroupMembershipScopeEscalation:
    """
    Regression tests for a confirmed IDOR/privilege-escalation bug:
    GroupMembership is the canonical leadership source, and its `group`
    / `member` FKs were completely unvalidated against the caller's
    branch/leadership scope.
    """

    def test_cannot_self_promote_to_leader_of_a_group_in_another_branch(
        self, api_client, branch_a, fellowship_b
    ):
        leader_user, leader_member = _fellowship_leader(branch_a)
        api_client.force_authenticate(user=leader_user)
        response = api_client.post("/api/v1/group-memberships/", {
            "member": str(leader_member.id), "group": str(fellowship_b.id), "role": "LEADER",
        }, format="json")
        assert response.status_code == 400

    def test_cannot_add_out_of_branch_member_to_own_led_group(
        self, api_client, branch_a, branch_b, fellowship_a
    ):
        from apps.groups.models import GroupMembership, GroupRole
        from apps.members.models import Member, MemberQRCode

        leader_user, leader_member = _fellowship_leader(branch_a)
        GroupMembership.objects.create(group=fellowship_a, member=leader_member, role=GroupRole.LEADER, is_active=True)

        outsider = Member.objects.create(branch=branch_b, first_name="Out", last_name="Sider")
        MemberQRCode.objects.get_or_create(member=outsider)

        api_client.force_authenticate(user=leader_user)
        response = api_client.post("/api/v1/group-memberships/", {
            "member": str(outsider.id), "group": str(fellowship_a.id), "role": "MEMBER",
        }, format="json")
        assert response.status_code == 400

    def test_legitimate_membership_creation_within_own_led_group_still_works(
        self, api_client, branch_a, fellowship_a
    ):
        from apps.groups.models import GroupMembership, GroupRole
        from apps.members.models import Member, MemberQRCode

        leader_user, leader_member = _fellowship_leader(branch_a)
        GroupMembership.objects.create(group=fellowship_a, member=leader_member, role=GroupRole.LEADER, is_active=True)

        new_member = Member.objects.create(branch=branch_a, first_name="New", last_name="Member")
        MemberQRCode.objects.get_or_create(member=new_member)

        api_client.force_authenticate(user=leader_user)
        response = api_client.post("/api/v1/group-memberships/", {
            "member": str(new_member.id), "group": str(fellowship_a.id), "role": "MEMBER",
        }, format="json")
        assert response.status_code == 201


@pytest.mark.django_db
class TestGroupLeadershipHistory:
    def test_assigning_leader_writes_audit_log(self, api_client, branch_a, fellowship_a, seed_member_permissions, chapel_admin_a):
        from apps.members.models import Member, MemberQRCode
        from apps.audit.models import AuditLog, AuditAction

        target = Member.objects.create(branch=branch_a, first_name="New", last_name="Leader")
        MemberQRCode.objects.get_or_create(member=target)

        api_client.force_authenticate(user=chapel_admin_a)
        response = api_client.post("/api/v1/group-memberships/", {
            "member": str(target.id), "group": str(fellowship_a.id), "role": "LEADER",
        }, format="json")
        assert response.status_code == 201
        assert AuditLog.objects.filter(action=AuditAction.GROUP_LEADERSHIP_CHANGE, resource_id=response.data["data"]["id"]).exists()

    def test_removing_leader_writes_audit_log(self, api_client, branch_a, fellowship_a, seed_member_permissions, chapel_admin_a):
        from apps.groups.models import GroupMembership, GroupRole
        from apps.members.models import Member, MemberQRCode
        from apps.audit.models import AuditLog, AuditAction

        target = Member.objects.create(branch=branch_a, first_name="Outgoing", last_name="Leader")
        MemberQRCode.objects.get_or_create(member=target)
        membership = GroupMembership.objects.create(group=fellowship_a, member=target, role=GroupRole.LEADER, is_active=True)

        api_client.force_authenticate(user=chapel_admin_a)
        response = api_client.delete(f"/api/v1/group-memberships/{membership.id}/")
        assert response.status_code in (200, 204)
        assert AuditLog.objects.filter(action=AuditAction.GROUP_LEADERSHIP_CHANGE, resource_id=str(membership.id)).exists()

    def test_ordinary_member_role_changes_are_not_logged_as_leadership_changes(
        self, api_client, branch_a, fellowship_a, seed_member_permissions, chapel_admin_a
    ):
        from apps.members.models import Member, MemberQRCode
        from apps.audit.models import AuditLog, AuditAction

        target = Member.objects.create(branch=branch_a, first_name="Plain", last_name="Member")
        MemberQRCode.objects.get_or_create(member=target)

        api_client.force_authenticate(user=chapel_admin_a)
        response = api_client.post("/api/v1/group-memberships/", {
            "member": str(target.id), "group": str(fellowship_a.id), "role": "MEMBER",
        }, format="json")
        assert response.status_code == 201
        assert not AuditLog.objects.filter(action=AuditAction.GROUP_LEADERSHIP_CHANGE, resource_id=response.data["data"]["id"]).exists()
    """Regression tests for the matching bug on Group.branch/parent/leader."""

    def test_cannot_create_group_in_another_branch(self, api_client, branch_a, branch_b):
        leader_user, _ = _fellowship_leader(branch_a)
        api_client.force_authenticate(user=leader_user)
        response = api_client.post("/api/v1/groups-catalog/", {
            "branch": str(branch_b.id), "name": "Hostile Fellowship", "group_type": "FELLOWSHIP",
        }, format="json")
        assert response.status_code == 400

    def test_cannot_reparent_group_to_a_different_branch_parent(self, api_client, branch_a, fellowship_a, fellowship_b):
        leader_user, _ = _fellowship_leader(branch_a)
        api_client.force_authenticate(user=leader_user)
        response = api_client.patch(f"/api/v1/groups-catalog/{fellowship_a.id}/", {
            "parent": str(fellowship_b.id),
        }, format="json")
        assert response.status_code in (400, 403, 404)

    def test_legitimate_group_creation_in_own_branch_still_works(self, api_client, branch_a):
        leader_user, _ = _fellowship_leader(branch_a)
        api_client.force_authenticate(user=leader_user)
        response = api_client.post("/api/v1/groups-catalog/", {
            "branch": str(branch_a.id), "name": "New Unit", "group_type": "UNIT",
        }, format="json")
        assert response.status_code == 201
