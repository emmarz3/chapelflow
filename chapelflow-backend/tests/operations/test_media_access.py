import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from apps.ministries.models import Group, GroupType
from common.constants.roles import Roles


pytestmark = pytest.mark.django_db


@pytest.fixture
def media_author(make_user, branch_a):
    return make_user(role=Roles.STUDENT_CHAPLAIN, branch=branch_a, email="media-access-author@test.edu")


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



@pytest.mark.parametrize(
    ("filename", "content_type", "payload"),
    [
        ("service.mp3", "audio/mpeg", b"ID3" + b"\x00" * 20),
        ("service.m4a", "audio/mp4", b"\x00\x00\x00\x18ftypM4A " + b"\x00" * 20),
        ("programme.pdf", "application/pdf", b"%PDF-1.4\nChapel programme"),
        ("worship.webm", "video/webm", b"\x1a\x45\xdf\xa3" + b"\x00" * 20),
    ],
)
def test_media_upload_accepts_supported_sermon_and_gallery_file_formats(
    api_client, media_author, monkeypatch, filename, content_type, payload
):
    class FakeStorage:
        def upload_fileobj(self, file_obj, storage_name, content_type=""):
            assert file_obj.read()
            file_obj.seek(0)
            return f"https://files.example.edu/{storage_name}"

    monkeypatch.setattr("apps.uploads.views.get_storage_service", lambda: FakeStorage())
    api_client.force_authenticate(media_author)
    response = api_client.post(
        "/api/v1/uploads/upload/",
        {
            "file": SimpleUploadedFile(filename, payload, content_type=content_type),
            "category": "MEDIA_CONTENT",
        },
        format="multipart",
    )
    assert response.status_code == 201, response.data
    assert response.data["data"]["original_filename"] == filename
    assert response.data["data"]["content_type"] == content_type


def test_media_upload_rejects_mismatched_file_signature(api_client, media_author, monkeypatch):
    class FakeStorage:
        def upload_fileobj(self, file_obj, storage_name, content_type=""):
            raise AssertionError("Invalid file must be rejected before storage is called")

    monkeypatch.setattr("apps.uploads.views.get_storage_service", lambda: FakeStorage())
    api_client.force_authenticate(media_author)
    response = api_client.post(
        "/api/v1/uploads/upload/",
        {
            "file": SimpleUploadedFile("sermon.mp3", b"not-an-mp3-file", content_type="audio/mpeg"),
            "category": "MEDIA_CONTENT",
        },
        format="multipart",
    )
    assert response.status_code == 400
    assert "file contents" in str(response.data).lower() or "file type" in str(response.data).lower()





def test_media_leader_and_super_admin_can_upload_gallery_files(
    api_client, make_user, branch_a, super_admin, monkeypatch
):
    media_unit = Group.objects.create(
        branch=branch_a,
        name="Media",
        group_type=GroupType.UNIT,
    )
    media_leader = make_user(
        email="media-upload-leader@test.edu",
        branch=branch_a,
        role=Roles.UNIT_HEAD,
        institutional_group=media_unit,
    )

    class FakeStorage:
        def upload_fileobj(self, file_obj, storage_name, content_type=""):
            assert file_obj.read()
            file_obj.seek(0)
            return f"https://files.example.edu/{storage_name}"

    monkeypatch.setattr("apps.uploads.views.get_storage_service", lambda: FakeStorage())

    for user in (media_leader, super_admin):
        api_client.force_authenticate(user)
        response = api_client.post(
            "/api/v1/uploads/upload/",
            {
                "file": SimpleUploadedFile(
                    "sunday-gallery.jpg",
                    b"\xff\xd8\xff" + b"\x00" * 24,
                    content_type="image/jpeg",
                ),
                "category": "MEDIA_CONTENT",
            },
            format="multipart",
        )
        assert response.status_code == 201, response.data
        assert response.data["data"]["original_filename"] == "sunday-gallery.jpg"
