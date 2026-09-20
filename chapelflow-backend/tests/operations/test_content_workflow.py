from datetime import timedelta

import pytest
from django.utils import timezone

from apps.operations.models import ContentEntry, ContentRevision, ContentStatus
from apps.operations.tasks import publish_scheduled_content


pytestmark = pytest.mark.django_db


def _create_draft(api_client, user, **overrides):
    api_client.force_authenticate(user)
    payload = {
        "title": "Steady faith",
        "slug": "steady-faith",
        "content_type": "SERMON",
        "summary": "A message for changing seasons.",
        "details": "Hold fast to hope through every season.",
        "author_name": "Chaplain Daniel",
        "media_url": "https://media.example.edu/steady-faith.mp3",
        **overrides,
    }
    return api_client.post("/api/v1/operations/media/", payload, format="json")


def test_content_requires_review_before_publication(
    api_client, chapel_admin_a, super_admin, branch_a
):
    created = _create_draft(api_client, chapel_admin_a)
    assert created.status_code == 201, created.data
    content_id = created.data["data"]["id"]
    api_client.force_authenticate(user=None)
    assert api_client.get("/api/v1/public/sermons/steady-faith/").status_code == 404

    api_client.force_authenticate(chapel_admin_a)
    assert api_client.post(f"/api/v1/operations/cms/{content_id}/submit/", {}).status_code == 200
    assert api_client.post(f"/api/v1/operations/cms/{content_id}/approve/", {}).status_code == 403

    super_admin.branch = branch_a
    super_admin.save(update_fields=["branch"])
    api_client.force_authenticate(super_admin)
    approved = api_client.post(f"/api/v1/operations/cms/{content_id}/approve/", {})
    assert approved.status_code == 200
    assert approved.data["data"]["status"] == "APPROVED"
    assert api_client.post(f"/api/v1/operations/cms/{content_id}/publish/", {}).status_code == 200

    api_client.force_authenticate(user=None)
    public = api_client.get("/api/v1/public/sermons/steady-faith/")
    assert public.status_code == 200
    assert public.data["data"]["title"] == "Steady faith"
    assert public.data["data"]["sections"][0]["action"]["href"].endswith("steady-faith.mp3")
    assert ContentRevision.objects.filter(content_id=content_id).count() == 4


def test_scheduled_content_is_not_public_until_worker_releases_it(
    api_client, chapel_admin_a, super_admin, branch_a
):
    publish_at = timezone.now() + timedelta(hours=1)
    created = _create_draft(
        api_client, chapel_admin_a, slug="scheduled-message", publish_at=publish_at.isoformat()
    )
    content_id = created.data["data"]["id"]
    api_client.post(f"/api/v1/operations/cms/{content_id}/submit/", {})
    super_admin.branch = branch_a
    super_admin.save(update_fields=["branch"])
    api_client.force_authenticate(super_admin)
    approved = api_client.post(f"/api/v1/operations/cms/{content_id}/approve/", {})
    assert approved.data["data"]["status"] == "SCHEDULED"

    api_client.force_authenticate(user=None)
    assert api_client.get("/api/v1/public/sermons/scheduled-message/").status_code == 404
    ContentEntry.objects.filter(pk=content_id).update(publish_at=timezone.now() - timedelta(seconds=1))
    assert publish_scheduled_content() == {"published": 1}
    assert api_client.get("/api/v1/public/sermons/scheduled-message/").status_code == 200


def test_rejection_requires_reason_and_preserves_revisions(
    api_client, chapel_admin_a, super_admin, branch_a
):
    created = _create_draft(api_client, chapel_admin_a, slug="review-me")
    content_id = created.data["data"]["id"]
    api_client.post(f"/api/v1/operations/cms/{content_id}/submit/", {})
    super_admin.branch = branch_a
    super_admin.save(update_fields=["branch"])
    api_client.force_authenticate(super_admin)
    assert api_client.post(f"/api/v1/operations/cms/{content_id}/reject/", {}).status_code == 400
    rejected = api_client.post(
        f"/api/v1/operations/cms/{content_id}/reject/",
        {"reason": "Add an accessible transcript."}, format="json",
    )
    assert rejected.status_code == 200
    entry = ContentEntry.objects.get(pk=content_id)
    assert entry.status == ContentStatus.REJECTED
    assert entry.rejection_reason == "Add an accessible transcript."
    assert list(entry.revisions.values_list("version", flat=True)) == [3, 2, 1]


def test_media_content_validates_required_fields(api_client, chapel_admin_a):
    api_client.force_authenticate(chapel_admin_a)
    invalid = api_client.post(
        "/api/v1/operations/media/",
        {"title": "No recording", "content_type": "SERMON", "details": "Notes only"},
        format="json",
    )
    assert invalid.status_code == 400
    assert "media_url" in invalid.data["errors"]

    page = api_client.post(
        "/api/v1/operations/cms/",
        {
            "title": "Welcome page",
            "content_type": "PAGE",
            "details": "Welcome to the chapel.",
            "parent": "",
            "publish_at": "",
        },
        format="json",
    )
    assert page.status_code == 201, page.data


def test_published_gallery_exposes_only_published_images(
    api_client, chapel_admin_a, super_admin, branch_a
):
    api_client.force_authenticate(chapel_admin_a)
    album = api_client.post(
        "/api/v1/operations/media/",
        {
            "title": "Welcome service",
            "slug": "welcome-service",
            "content_type": "GALLERY",
            "summary": "Photographs from the welcome service.",
            "details": "Our chapel community welcomed new students.",
        },
        format="json",
    )
    assert album.status_code == 201, album.data
    album_id = album.data["data"]["id"]
    image = api_client.post(
        "/api/v1/operations/media/",
        {
            "title": "Opening worship",
            "slug": "opening-worship",
            "content_type": "GALLERY_IMAGE",
            "details": "Students gathered for worship.",
            "media_url": "https://media.example.edu/opening-worship.jpg",
            "parent": album_id,
        },
        format="json",
    )
    assert image.status_code == 201, image.data
    image_id = image.data["data"]["id"]

    for content_id in (album_id, image_id):
        assert api_client.post(f"/api/v1/operations/cms/{content_id}/submit/", {}).status_code == 200
    super_admin.branch = branch_a
    super_admin.save(update_fields=["branch"])
    api_client.force_authenticate(super_admin)
    for content_id in (album_id, image_id):
        assert api_client.post(f"/api/v1/operations/cms/{content_id}/approve/", {}).status_code == 200
        assert api_client.post(f"/api/v1/operations/cms/{content_id}/publish/", {}).status_code == 200

    api_client.force_authenticate(user=None)
    public = api_client.get("/api/v1/public/gallery/welcome-service/")
    assert public.status_code == 200
    assert public.data["data"]["sections"] == [{
        "id": image_id,
        "heading": "Opening worship",
        "body": "Students gathered for worship.",
        "imageUrl": "https://media.example.edu/opening-worship.jpg",
        "imageAlt": "Opening worship",
        "mediaType": "image",
    }]
