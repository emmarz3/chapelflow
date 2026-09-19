from datetime import timedelta

import pytest
from django.utils import timezone

from apps.accounts.models import User
from apps.ministries.models import Group, GroupType
from common.constants.roles import Roles


pytestmark = pytest.mark.django_db


def _inventory_users(branch):
    protocol = Group.objects.create(
        branch=branch,
        name="Chapel Protocol",
        group_type=GroupType.UNIT,
    )
    chaplain = User.objects.create_user(
        email="chaplain.inventory@test.com",
        password="Pass12345!",
        role=Roles.CHAPLAIN,
        branch=branch,
    )
    student_chaplain = User.objects.create_user(
        email="student.chaplain.inventory@test.com",
        password="Pass12345!",
        role=Roles.STUDENT_CHAPLAIN,
        branch=branch,
    )
    protocol_leader = User.objects.create_user(
        email="protocol.inventory@test.com",
        password="Pass12345!",
        role=Roles.UNIT_HEAD,
        branch=branch,
        institutional_group=protocol,
    )
    other_unit = Group.objects.create(branch=branch, name="Media", group_type=GroupType.UNIT)
    other_leader = User.objects.create_user(
        email="media.inventory@test.com",
        password="Pass12345!",
        role=Roles.UNIT_HEAD,
        branch=branch,
        institutional_group=other_unit,
    )
    return chaplain, student_chaplain, protocol_leader, other_leader


def test_inventory_is_restricted_to_chaplain_student_chaplain_and_protocol_leader(
    api_client, branch_a, chapel_admin_a, super_admin
):
    chaplain, student_chaplain, protocol_leader, other_leader = _inventory_users(branch_a)

    api_client.force_authenticate(chapel_admin_a)
    assert api_client.get("/api/v1/operations/assets/").status_code == 403

    api_client.force_authenticate(super_admin)
    assert api_client.get("/api/v1/operations/assets/").status_code == 403

    api_client.force_authenticate(other_leader)
    assert api_client.get("/api/v1/operations/assets/").status_code == 403

    for user in (chaplain, student_chaplain, protocol_leader):
        api_client.force_authenticate(user)
        assert api_client.get("/api/v1/operations/assets/").status_code == 200


def test_protocol_inventory_tracks_stock_custody_maintenance_and_history(api_client, branch_a):
    _, _, protocol_leader, _ = _inventory_users(branch_a)
    api_client.force_authenticate(protocol_leader)
    created = api_client.post(
        "/api/v1/operations/assets/",
        {
            "title": "Communion cups",
            "detail": "Reusable service cups",
            "tracking_mode": "STOCK",
            "quantity_on_hand": 20,
            "reorder_level": 5,
            "category_name": "Communion supplies",
            "location_name": "Protocol store",
        },
        format="json",
    )
    assert created.status_code == 201, created.data
    asset = created.data["data"]
    assert asset["quantity_on_hand"] == 20
    assert asset["category_name"] == "Communion supplies"
    assert asset["location_name"] == "Protocol store"

    issued = api_client.post(
        f"/api/v1/operations/assets/{asset['id']}/movement/",
        {"action": "issue", "quantity": 16, "custodian_name": "Service team"},
        format="json",
    )
    assert issued.status_code == 200, issued.data
    assert issued.data["data"]["asset"]["quantity_on_hand"] == 4
    assert issued.data["data"]["asset"]["status"] == "LOW_STOCK"

    alerts = api_client.get("/api/v1/operations/assets/alerts/")
    assert alerts.status_code == 200, alerts.data
    assert [item["id"] for item in alerts.data["data"]["low_stock"]] == [asset["id"]]

    returned = api_client.post(
        f"/api/v1/operations/assets/{asset['id']}/movement/",
        {"action": "return", "quantity": 3},
        format="json",
    )
    assert returned.status_code == 200, returned.data
    assert returned.data["data"]["asset"]["quantity_on_hand"] == 7

    maintenance = api_client.post(
        f"/api/v1/operations/assets/{asset['id']}/maintenance/",
        {
            "title": "Quarterly stock review",
            "details": "Count and inspect all cups.",
            "due_at": (timezone.localdate() + timedelta(days=7)).isoformat(),
        },
        format="json",
    )
    assert maintenance.status_code == 201, maintenance.data
    completed = api_client.post(
        f"/api/v1/operations/assets/{asset['id']}/maintenance/{maintenance.data['data']['id']}/complete/",
        {"completion_notes": "Count verified."},
        format="json",
    )
    assert completed.status_code == 200, completed.data
    assert completed.data["data"]["status"] == "COMPLETED"

    history = api_client.get(f"/api/v1/operations/assets/{asset['id']}/history/")
    assert history.status_code == 200, history.data
    assert [item["movement_type"] for item in history.data["data"]["movements"]] == [
        "RETURN", "ISSUE", "ADJUSTMENT"
    ]
    assert history.data["data"]["maintenance"][0]["status"] == "COMPLETED"


def test_individual_asset_requires_tag_and_has_issue_return_lifecycle(api_client, branch_a):
    _, _, protocol_leader, _ = _inventory_users(branch_a)
    api_client.force_authenticate(protocol_leader)
    invalid = api_client.post(
        "/api/v1/operations/assets/",
        {"title": "Projector", "detail": "Main auditorium"},
        format="json",
    )
    assert invalid.status_code == 400
    assert "asset_tag" in invalid.data["errors"]

    created = api_client.post(
        "/api/v1/operations/assets/",
        {"title": "Projector", "detail": "Main auditorium", "asset_tag": "CUC-PROJ-001"},
        format="json",
    )
    assert created.status_code == 201, created.data
    asset_id = created.data["data"]["id"]
    assert api_client.post(
        f"/api/v1/operations/assets/{asset_id}/movement/",
        {"action": "issue", "custodian_name": "Protocol team"}, format="json",
    ).data["data"]["asset"]["status"] == "ISSUED"
    assert api_client.post(
        f"/api/v1/operations/assets/{asset_id}/movement/",
        {"action": "return"}, format="json",
    ).data["data"]["asset"]["status"] == "AVAILABLE"
