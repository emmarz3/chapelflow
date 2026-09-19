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
