import pytest
from unittest.mock import patch

from apps.accounts.models import User
from apps.communications.models import LeadershipDelivery, LeadershipNotice
from apps.groups.models import GroupMembership, GroupMessage, GroupRole
from apps.members.models import Member
from apps.ministries.models import Group


@pytest.mark.django_db
@patch("apps.communications.leadership.queue_notification")
def test_leader_only_notice_and_private_reply(mock_notify, api_client, branch_a):
    unit = Group.objects.create(branch=branch_a, name="Worship Unit", group_type="UNIT")
    other = Group.objects.create(branch=branch_a, name="Music Fellowship", group_type="FELLOWSHIP")
    chaplain = User.objects.create_user(email="chaplain-notice@example.com", password="StrongPass123!", role="STUDENT_CHAPLAIN", branch=branch_a)
    unit_head = User.objects.create_user(email="unit-notice@example.com", password="StrongPass123!", role="UNIT_HEAD", branch=branch_a, institutional_group=unit)
    fellowship_head = User.objects.create_user(email="fellowship-notice@example.com", password="StrongPass123!", role="FELLOWSHIP_LEADER", branch=branch_a, institutional_group=other)
    student = User.objects.create_user(email="student-notice@example.com", password="StrongPass123!", role="MEMBER", branch=branch_a)
    Member.objects.create(user=student, branch=branch_a, first_name="Student", last_name="One", community="STUDENT")
    api_client.force_authenticate(user=chaplain)
    response = api_client.post("/api/v1/communications/leadership/notices/", {
        "branch_id": str(branch_a.id), "title": "Leaders meeting", "body": "Meet privately",
        "audience": "UNIT",
    }, format="json")
    assert response.status_code == 201
    notice_id = response.data["data"]["id"]
    assert LeadershipNotice.objects.count() == 1
    assert list(LeadershipDelivery.objects.values_list("recipient_id", flat=True)) == [unit_head.id]
    assert mock_notify.called

    api_client.force_authenticate(user=student)
    assert api_client.get("/api/v1/communications/leadership/notices/").data["data"] == []
    assert api_client.get(f"/api/v1/communications/leadership/notices/{notice_id}/").status_code == 404
    assert api_client.get("/api/v1/communications/announcements/me/").data["data"] == []
    api_client.force_authenticate(user=fellowship_head)
    assert api_client.get(f"/api/v1/communications/leadership/notices/{notice_id}/").status_code == 404

    api_client.force_authenticate(user=unit_head)
    detail = api_client.get(f"/api/v1/communications/leadership/notices/{notice_id}/")
    assert detail.status_code == 200
    assert detail.data["data"]["read_at"] is not None
    assert api_client.post(f"/api/v1/communications/leadership/notices/{notice_id}/", {}, format="json").status_code == 200
    assert api_client.post(f"/api/v1/communications/leadership/notices/{notice_id}/replies/", {"body": "Understood"}, format="json").status_code == 201
    api_client.force_authenticate(user=chaplain)
    sent = api_client.get(f"/api/v1/communications/leadership/notices/{notice_id}/")
    assert sent.data["data"]["deliveries"][0]["replies"][0]["body"] == "Understood"


@pytest.mark.django_db
def test_oversight_is_branch_scoped_and_read_only(api_client, branch_a, branch_b):
    unit_a = Group.objects.create(branch=branch_a, name="Unit A", group_type="UNIT")
    unit_b = Group.objects.create(branch=branch_b, name="Unit B", group_type="UNIT")
    chaplain = User.objects.create_user(email="student-chaplain-scope@example.com", password="StrongPass123!", role="STUDENT_CHAPLAIN", branch=branch_a)
    member = User.objects.create_user(email="ordinary-student-scope@example.com", password="StrongPass123!", role="MEMBER", branch=branch_a)
    GroupMessage.objects.create(group=unit_a, author=member, body="Rehearsal tomorrow")
    api_client.force_authenticate(user=chaplain)
    response = api_client.get("/api/v1/communications/community-oversight/")
    assert response.status_code == 200
    assert [item["id"] for item in response.data["data"]] == [str(unit_a.id)]
    detail = api_client.get(f"/api/v1/communications/community-oversight/{unit_a.id}/")
    assert detail.data["data"]["messages"][0]["body"] == "Rehearsal tomorrow"
    assert api_client.get(f"/api/v1/communications/community-oversight/{unit_b.id}/").status_code == 404
    assert api_client.post(f"/api/v1/communications/community-oversight/{unit_a.id}/", {}, format="json").status_code == 405
    api_client.force_authenticate(user=member)
    assert api_client.get("/api/v1/communications/community-oversight/").data["data"] == []
    assert api_client.get(f"/api/v1/communications/community-oversight/{unit_a.id}/").status_code == 404


@pytest.mark.django_db
def test_selected_notice_rejects_other_branch(api_client, branch_a, branch_b):
    foreign = Group.objects.create(branch=branch_b, name="Foreign", group_type="UNIT")
    local = Group.objects.create(branch=branch_a, name="Local", group_type="UNIT")
    chaplain = User.objects.create_user(email="student-chaplain-target@example.com", password="StrongPass123!", role="STUDENT_CHAPLAIN", branch=branch_a)
    api_client.force_authenticate(user=chaplain)
    result = api_client.post("/api/v1/communications/leadership/notices/", {
        "branch_id": str(branch_a.id), "title": "Private", "body": "Only us",
        "audience": "SELECTED", "target_group_ids": [str(local.id), str(foreign.id)],
    }, format="json")
    assert result.status_code == 403
    assert LeadershipNotice.objects.count() == 0
