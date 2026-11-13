import pytest

from apps.ministries.models import Group, GroupType
from common.constants.roles import Roles


pytestmark = pytest.mark.django_db


def _media_payload():
    return {
        "title": "Welcome service photos",
        "content_type": "MEDIA",
        "summary": "A short media update.",
        "details": "A short media update for the chapel.",
        "media_url": "https://media.example.edu/welcome.mp4",
    }


def test_only_media_and_social_media_unit_leaders_can_create_media(api_client, make_user, branch_a):
    media_unit = Group.objects.create(branch=branch_a, name="Media", group_type=GroupType.UNIT)
    social_media_unit = Group.objects.create(branch=branch_a, name="Social Media", group_type=GroupType.UNIT)
    protocol_unit = Group.objects.create(branch=branch_a, name="Chapel Protocol", group_type=GroupType.UNIT)
    media_leader = make_user(
        email="media-leader@test.edu",
        branch=branch_a,
        role=Roles.UNIT_HEAD,
        institutional_group=media_unit,
    )
    protocol_leader = make_user(
        email="protocol-leader@test.edu",
        branch=branch_a,
        role=Roles.UNIT_HEAD,
        institutional_group=protocol_unit,
    )
    social_media_leader = make_user(
        email="social-media-leader@test.edu",
        branch=branch_a,
        role=Roles.UNIT_HEAD,
        institutional_group=social_media_unit,
    )

    api_client.force_authenticate(media_leader)
    created = api_client.post("/api/v1/operations/media/", _media_payload(), format="json")
    assert created.status_code == 201, created.data

    api_client.force_authenticate(social_media_leader)
    gallery = api_client.post("/api/v1/operations/media/", {
        "title": "Social Media Sunday gallery",
        "content_type": "GALLERY",
        "summary": "Photos from Sunday service.",
        "details": "Shared by the Social Media unit.",
    }, format="json")
    assert gallery.status_code == 201, gallery.data
    assert gallery.data["data"]["status"] == "PUBLISHED"

    api_client.force_authenticate(protocol_leader)
    denied = api_client.post("/api/v1/operations/media/", _media_payload(), format="json")
    assert denied.status_code == 403
