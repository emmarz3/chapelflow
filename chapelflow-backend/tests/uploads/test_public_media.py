import pytest


@pytest.mark.django_db
def test_gallery_upload_uses_stable_public_url_for_private_bucket(
    api_client, make_user, branch_a, settings, monkeypatch,
):
    from django.core.files.uploadedfile import SimpleUploadedFile
    from apps.operations.models import ContentEntry, ContentStatus, ContentType
    from apps.uploads.models import Upload
    from apps.uploads.storage import S3StorageService
    from common.constants.roles import Roles

    settings.STORAGE_PROVIDER = "s3"
    settings.AWS_S3_ENDPOINT_URL = "https://t3.storageapi.dev"
    settings.AWS_S3_ADDRESSING_STYLE = "virtual"
    settings.AWS_STORAGE_BUCKET_NAME = "chapelflow-media-test"
    settings.AWS_S3_REGION_NAME = "auto"
    settings.PUBLIC_BACKEND_URL = "https://chapelflow-api.example"
    data = b"\x00\x00\x00\x18ftypmp42" + b"video bytes"

    class BucketClient:
        def upload_fileobj(self, fileobj, bucket, key, ExtraArgs):
            assert fileobj.read() == data
            assert bucket == "chapelflow-media-test"
            assert key.startswith("media_content/")
            assert ExtraArgs["ContentType"] == "video/mp4"

        def generate_presigned_url(self, operation, Params, ExpiresIn):
            assert operation == "get_object"
            assert Params["Key"].startswith("media_content/")
            return "https://chapelflow-media-test.t3.storageapi.dev/signed-video"

    monkeypatch.setattr(S3StorageService, "_client", lambda self: BucketClient())
    user = make_user(email="media-publisher@chapelflow.test", branch=branch_a, role=Roles.SUPER_ADMIN)
    api_client.force_authenticate(user=user)
    response = api_client.post("/api/v1/uploads/upload/", {
        "file": SimpleUploadedFile("chapel.mp4", data, "video/mp4"),
        "category": "MEDIA_CONTENT",
    }, format="multipart")
    assert response.status_code == 201
    upload = Upload.objects.get(pk=response.data["data"]["id"])
    assert upload.file_url.startswith("https://chapelflow-media-test.t3.storageapi.dev/media_content/")
    public_url = response.data["data"]["file_url"]
    assert public_url == f"https://chapelflow-api.example/api/v1/uploads/public/{upload.id}/"

    api_client.force_authenticate(user=None)
    assert api_client.get(f"/api/v1/uploads/public/{upload.id}/").status_code == 404
    gallery = ContentEntry.objects.create(
        branch=branch_a, created_by=user, title="Chapel moments", slug="chapel-moments",
        summary="Video from worship", details="Video from worship",
        content_type=ContentType.GALLERY, status=ContentStatus.PUBLISHED,
        cover_image_url=public_url,
    )
    playback = api_client.get(f"/api/v1/uploads/public/{upload.id}/")
    assert playback.status_code == 302
    assert playback["Location"] == "https://chapelflow-media-test.t3.storageapi.dev/signed-video"

    gallery.status = ContentStatus.ARCHIVED
    gallery.save(update_fields=["status"])
    assert api_client.get(f"/api/v1/uploads/public/{upload.id}/").status_code == 404
