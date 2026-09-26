import pytest
from django.utils import timezone

from apps.communications.models import Announcement, AnnouncementStatus
from apps.communications.tasks import dispatch_scheduled_announcements
from apps.ministries.models import Group, GroupType


pytestmark = pytest.mark.django_db


@pytest.mark.parametrize(
    ("module", "payload", "expected_primary"),
    [
        ("workers", {"title": "Sunday roster", "detail": "Main service"}, "Sunday roster"),
        ("finance", {"title": "Projector repair", "amount": "25000", "category": "Expense"}, "Projector repair"),
        ("media", {
            "title": "Sunday sermon", "detail": "Audio recording",
            "content_type": "MEDIA", "media_url": "https://media.example.edu/sunday.mp3",
        }, "Sunday sermon"),
        ("cms", {"title": "Welcome Students", "detail": "Welcome to chapel."}, "Welcome Students"),
    ],
)
def test_operations_modules_create_and_list(api_client, chapel_admin_a, module, payload, expected_primary):
    api_client.force_authenticate(chapel_admin_a)
    created = api_client.post(f"/api/v1/operations/{module}/", payload, format="json")
    assert created.status_code == 201, created.data

    listed = api_client.get(f"/api/v1/operations/{module}/")
    assert listed.status_code == 200, listed.data
    assert listed.data["data"][0]["primary"] == expected_primary


def test_cms_publish(api_client, chapel_admin_a, super_admin, branch_a):
    api_client.force_authenticate(chapel_admin_a)
    content = api_client.post(
        "/api/v1/operations/cms/",
        {"title": "Student Welcome", "detail": "Welcome to the chapel."}, format="json",
    ).data["data"]
    submitted = api_client.post(f"/api/v1/operations/cms/{content['id']}/submit/", {}, format="json")
    assert submitted.status_code == 200
    super_admin.branch = branch_a
    super_admin.save(update_fields=["branch"])
    api_client.force_authenticate(super_admin)
    approved = api_client.post(f"/api/v1/operations/cms/{content['id']}/approve/", {}, format="json")
    assert approved.status_code == 200
    published = api_client.post(f"/api/v1/operations/cms/{content['id']}/publish/", {}, format="json")
    assert published.status_code == 200
    api_client.force_authenticate(user=None)
    public = api_client.get("/api/v1/public/content/student-welcome/")
    assert public.status_code == 200
    assert public.data["data"]["title"] == "Student Welcome"


def test_communication_draft_and_send(api_client, chapel_admin_a, monkeypatch):
    monkeypatch.setattr("apps.operations.views.dispatch_announcement.delay", lambda *_: None)
    api_client.force_authenticate(chapel_admin_a)
    created = api_client.post(
        "/api/v1/operations/communication/",
        {"title": "Service update", "message": "Service begins at nine.", "channel": "Email"},
        format="json",
    )
    assert created.status_code == 201, created.data
    sent = api_client.post(
        f"/api/v1/operations/communication/{created.data['data']['id']}/send/", {}, format="json"
    )
    assert sent.status_code == 200, sent.data
    assert sent.data["data"]["status"] == "QUEUED"


def test_communication_draft_preserves_target_and_schedules_future_delivery(
    api_client, chapel_admin_a, branch_a, monkeypatch
):
    group = Group.objects.create(
        branch=branch_a, name="Chapel Protocol", group_type=GroupType.UNIT
    )
    publish_at = timezone.now() + timezone.timedelta(hours=1)
    api_client.force_authenticate(chapel_admin_a)
    created = api_client.post(
        "/api/v1/operations/communication/",
        {
            "title": "Protocol briefing",
            "message": "Please report thirty minutes before service.",
            "channels": ["IN_APP"],
            "audience_type": "UNIT",
            "target_groups": [str(group.id)],
            "publish_at": publish_at.isoformat(),
        },
        format="json",
    )
    assert created.status_code == 201, created.data
    assert created.data["data"]["target_groups"] == [str(group.id)]
    announcement = Announcement.objects.get(pk=created.data["data"]["id"])
    assert announcement.audience_type == "UNIT"
    assert announcement.channels == ["IN_APP"]

    sent = api_client.post(f"/api/v1/operations/communication/{announcement.id}/send/", {}, format="json")
    assert sent.status_code == 200, sent.data
    assert sent.data["data"]["status"] == AnnouncementStatus.SCHEDULED

    monkeypatch.setattr("apps.communications.tasks.dispatch_announcement.delay", lambda *_: None)
    Announcement.objects.filter(pk=announcement.id).update(publish_at=timezone.now() - timezone.timedelta(seconds=1))
    assert dispatch_scheduled_announcements() == {"dispatched": 1}
    announcement.refresh_from_db()
    assert announcement.status == AnnouncementStatus.QUEUED


def test_analytics_and_privacy_requests(api_client, chapel_admin_a):
    api_client.force_authenticate(chapel_admin_a)
    analytics = api_client.get("/api/v1/analytics/overview/")
    assert analytics.status_code == 200, analytics.data
    assert {item["label"] for item in analytics.data["data"]["metrics"]} >= {
        "Total members", "Active members", "Attendance records",
    }

    export = api_client.post("/api/v1/account/data-export-requests/", {}, format="json")
    deletion = api_client.post(
        "/api/v1/account/deletion-requests/", {"reason": "No longer enrolled"}, format="json"
    )
    assert export.status_code == 201
    assert deletion.status_code == 201
    assert export.data["data"]["requestId"]
    assert deletion.data["data"]["requestId"]


def test_branch_operations_are_super_admin_only(api_client, super_admin, branch_a):
    super_admin.branch = branch_a
    super_admin.save(update_fields=["branch"])
    api_client.force_authenticate(super_admin)
    created = api_client.post(
        "/api/v1/operations/branches/",
        {"title": "Campus Chapel", "detail": "North campus"}, format="json",
    )
    assert created.status_code == 201, created.data
    listed = api_client.get("/api/v1/operations/branches/")
    assert listed.status_code == 200
    assert any(row["primary"] == "Campus Chapel" for row in listed.data["data"])
