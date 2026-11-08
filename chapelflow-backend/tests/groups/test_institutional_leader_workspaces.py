"""Regression tests for institutional unit/fellowship leadership workspaces."""
import pytest
from django.urls import reverse


@pytest.mark.django_db
@pytest.mark.parametrize(("role", "kind"), [
    ("UNIT_HEAD", "UNIT"),
    ("FELLOWSHIP_LEADER", "FELLOWSHIP"),
])
def test_assigned_leader_can_access_own_workspace_and_approve_requests(
    api_client, branch_a, role, kind
):
    from apps.accounts.models import User
    from apps.members.models import Member
    from apps.ministries.models import Group
    from apps.groups.models import GroupJoinRequest, GroupMembership, JoinRequestStatus

    group = Group.objects.create(branch=branch_a, name="Own " + kind, group_type=kind)
    other = Group.objects.create(branch=branch_a, name="Other " + kind, group_type=kind)
    leader = User.objects.create_user(
        email=f"leader-{kind.lower()}@example.edu.ng", password="Secure123!Password",
        role=role, first_name="Assigned", last_name="Leader",
        branch=branch_a, institutional_group=group,
    )
    student = User.objects.create_user(
        email=f"student-{kind.lower()}@example.edu.ng", password="Secure123!Password",
        role="MEMBER", first_name="Student", last_name="Applicant", branch=branch_a,
    )
    member = Member.objects.create(
        user=student, branch=branch_a, first_name="Student", last_name="Applicant",
        community="STUDENT",
    )
    request = GroupJoinRequest.objects.create(group=group, member=member)
    api_client.force_authenticate(user=leader)
    root = "/api/v1/community-memberships/"

    mine = api_client.get(root)
    assert mine.status_code == 200
    assert [item["id"] for item in mine.data["data"]] == [str(group.id)]
    assert mine.data["data"][0]["is_leader"] is True

    detail = api_client.get(f"{root}{group.id}/")
    assert detail.status_code == 200
    assert detail.data["data"]["access"]["canManage"] is True
    assert api_client.get(f"{root}{other.id}/").status_code == 404
    assert api_client.get(f"{root}{other.id}/members/").status_code == 404
    assert api_client.get(f"{root}{other.id}/messages/").status_code == 404

    pending = api_client.get(f"{root}{group.id}/members/?status=pending")
    assert pending.status_code == 200
    assert len(pending.data["data"]) == 1

    approved = api_client.patch(
        f"{root}{group.id}/members/{request.id}/",
        {"status": "active"}, format="json",
    )
    assert approved.status_code == 200
    request.refresh_from_db()
    assert request.status == JoinRequestStatus.APPROVED
    assert GroupMembership.objects.filter(group=group, member=member, is_active=True).exists()

    api_client.force_authenticate(user=student)
    message = api_client.post(
        f"{root}{group.id}/messages/", {"body": "Hello team!"}, format="json"
    )
    assert message.status_code == 201
    assert api_client.get(f"{root}{group.id}/messages/").status_code == 200
    assert api_client.get(f"{root}{other.id}/messages/").status_code == 404


@pytest.mark.django_db
def test_leader_can_reject_join_request_without_granting_access(api_client, branch_a):
    from apps.accounts.models import User
    from apps.members.models import Member
    from apps.ministries.models import Group
    from apps.groups.models import GroupJoinRequest, GroupMembership, JoinRequestStatus

    group = Group.objects.create(branch=branch_a, name="Welcomers", group_type="UNIT")
    leader = User.objects.create_user(
        email="welcomer@example.edu.ng", password="Secure123!Password",
        role="UNIT_HEAD", branch=branch_a, institutional_group=group,
    )
    student = User.objects.create_user(
        email="applicant@example.edu.ng", password="Secure123!Password",
        role="MEMBER", branch=branch_a,
    )
    member = Member.objects.create(
        user=student, branch=branch_a, first_name="Pending", last_name="Student",
        community="STUDENT",
    )
    join_request = GroupJoinRequest.objects.create(group=group, member=member)
    api_client.force_authenticate(user=leader)
    response = api_client.patch(
        f"/api/v1/community-memberships/{group.id}/members/{join_request.id}/",
        {"status": "rejected"}, format="json",
    )
    assert response.status_code == 200
    join_request.refresh_from_db()
    assert join_request.status == JoinRequestStatus.REJECTED
    assert not GroupMembership.objects.filter(group=group, member=member).exists()
