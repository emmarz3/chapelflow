import uuid

import pytest


@pytest.mark.django_db
@pytest.mark.parametrize("community", ["STAFF", "GUEST"])
def test_staff_and_guest_accounts_are_denied_the_student_community_platform(
    api_client, branch_a, community
):
    from apps.accounts.models import User
    from apps.members.models import Member
    from common.constants.roles import Roles

    user = User.objects.create_user(
        email=f"{community.lower()}-community@example.edu.ng",
        password="StrongPass123!",
        first_name=community.title(),
        last_name="Community",
        branch=branch_a,
        role=Roles.MEMBER,
    )
    Member.objects.create(
        user=user,
        branch=branch_a,
        first_name=community.title(),
        last_name="Community",
        community=community,
    )
    api_client.force_authenticate(user=user)

    assert api_client.get("/api/v1/community-memberships/").status_code == 403
    group_id = uuid.uuid4()
    assert api_client.get(f"/api/v1/community-memberships/{group_id}/messages/").status_code == 403
    assert api_client.get("/api/v1/group-join-requests/me/").status_code == 403
    assert api_client.get("/api/v1/dashboard/member/").status_code == 403


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("role", "group_type"),
    [("UNIT_HEAD", "UNIT"), ("FELLOWSHIP_LEADER", "FELLOWSHIP")],
)
def test_institutional_group_leader_can_chat_only_in_their_assigned_group(
    api_client, branch_a, role, group_type
):
    from apps.accounts.models import User
    from apps.ministries.models import Group

    assigned_group = Group.objects.create(
        branch=branch_a, name=f"Assigned {group_type}", group_type=group_type
    )
    other_group = Group.objects.create(
        branch=branch_a, name=f"Other {group_type}", group_type=group_type
    )
    user = User.objects.create_user(
        email=f"{role.lower()}-chat@example.edu.ng",
        password="StrongPass123!",
        first_name="Group",
        last_name="Leader",
        branch=branch_a,
        role=role,
        institutional_group=assigned_group,
    )
    api_client.force_authenticate(user=user)

    response = api_client.post(
        f"/api/v1/community-memberships/{assigned_group.id}/messages/",
        {"body": "Hello, group."},
        format="json",
    )
    assert response.status_code == 201
    assert response.data["data"]["body"] == "Hello, group."

    messages = api_client.get(
        f"/api/v1/community-memberships/{assigned_group.id}/messages/"
    )
    assert messages.status_code == 200
    assert [item["body"] for item in messages.data["data"]] == ["Hello, group."]

    assert api_client.get(
        f"/api/v1/community-memberships/{other_group.id}/messages/"
    ).status_code == 404
    assert api_client.post(
        f"/api/v1/community-memberships/{other_group.id}/messages/",
        {"body": "Should not be sent."},
        format="json",
    ).status_code == 404
