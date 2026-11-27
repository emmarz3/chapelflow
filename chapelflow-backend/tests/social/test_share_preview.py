import pytest


@pytest.mark.django_db
@pytest.mark.parametrize("media_type,original,expected", [
    ("IMAGE", "image/upload/v1/upper-room/photo.png", "image/upload/w_1000,q_auto,f_jpg/v1/upper-room/photo.jpg"),
    ("VIDEO", "video/upload/v1/upper-room/clip.mp4", "video/upload/so_0,w_1000,q_auto,f_jpg/v1/upper-room/clip.jpg"),
])
def test_share_preview_includes_the_posts_real_media_and_checks_branch(
    api_client, make_user, branch_a, branch_b, settings, monkeypatch, media_type, original, expected,
):
    from apps.social.models import SocialPost, SocialPostMedia
    from apps.uploads.models import Upload, UploadCategory

    settings.CLOUDINARY_CLOUD_NAME = "test-cloud"
    author = make_user(email=f"preview-{media_type.lower()}@chapelflow.test", branch=branch_a)
    post = SocialPost.objects.create(branch=branch_a, author=author, caption="A chapel moment")
    upload = Upload.objects.create(
        branch=branch_a, uploaded_by=author, category=UploadCategory.SOCIAL_POST,
        original_filename="media", file_url=f"https://res.cloudinary.com/test-cloud/{original}",
        content_type="image/png" if media_type == "IMAGE" else "video/mp4", size_bytes=120,
    )
    media = SocialPostMedia.objects.create(post=post, upload=upload, media_type=media_type)
    calls = []

    class Upstream:
        status_code = 200
        headers = {"Content-Type": "image/jpeg"}

        def iter_content(self, chunk_size):
            yield b"preview-jpeg"

        def close(self):
            pass

    def get(url, **kwargs):
        calls.append(url)
        return Upstream()

    monkeypatch.setattr("apps.social.views.requests.get", get)
    path = f"/api/v1/social/media/{media.id}/share-preview/"
    api_client.force_authenticate(user=author)
    response = api_client.get(path)
    assert response.status_code == 200
    assert response.content == b"preview-jpeg"
    assert response["Content-Type"] == "image/jpeg"
    assert response["Cache-Control"] == "private, no-store"
    assert calls == [f"https://res.cloudinary.com/test-cloud/{expected}"]

    api_client.force_authenticate(user=make_user(email=f"outsider-{media_type.lower()}@chapelflow.test", branch=branch_b))
    assert api_client.get(path).status_code == 404
    assert len(calls) == 1


@pytest.mark.django_db
def test_share_preview_rejects_untrusted_cloudinary_host(api_client, make_user, branch_a, settings, monkeypatch):
    from apps.social.models import SocialPost, SocialPostMedia
    from apps.uploads.models import Upload, UploadCategory

    settings.CLOUDINARY_CLOUD_NAME = "test-cloud"
    user = make_user(email="preview-host@chapelflow.test", branch=branch_a)
    post = SocialPost.objects.create(branch=branch_a, author=user)
    upload = Upload.objects.create(
        branch=branch_a, uploaded_by=user, category=UploadCategory.SOCIAL_POST,
        original_filename="photo", file_url="https://evil.example/test-cloud/image/upload/photo.jpg",
        content_type="image/jpeg", size_bytes=120,
    )
    media = SocialPostMedia.objects.create(post=post, upload=upload, media_type="IMAGE")
    monkeypatch.setattr("apps.social.views.requests.get", lambda *args, **kwargs: pytest.fail("Untrusted URL fetched"))
    api_client.force_authenticate(user=user)
    assert api_client.get(f"/api/v1/social/media/{media.id}/share-preview/").status_code == 422


@pytest.mark.django_db
def test_bucket_video_preview_proxies_authorized_bytes(api_client, make_user, branch_a, settings, monkeypatch):
    from apps.social.models import SocialPost, SocialPostMedia
    from apps.uploads.models import Upload, UploadCategory
    from apps.uploads.storage import S3StorageService

    settings.AWS_S3_ENDPOINT_URL = "https://storage.example.test"
    settings.AWS_S3_ADDRESSING_STYLE = "virtual"
    settings.AWS_STORAGE_BUCKET_NAME = "chapelflow-media"
    user = make_user(email="preview-bucket@chapelflow.test", branch=branch_a)
    post = SocialPost.objects.create(branch=branch_a, author=user)
    upload = Upload.objects.create(
        branch=branch_a, uploaded_by=user, category=UploadCategory.SOCIAL_POST,
        original_filename="clip.mp4",
        file_url="https://chapelflow-media.storage.example.test/upper-room/clip.mp4",
        content_type="video/mp4", size_bytes=120,
    )
    media = SocialPostMedia.objects.create(post=post, upload=upload, media_type="VIDEO")
    monkeypatch.setattr(S3StorageService, "get_download_url", lambda *args, **kwargs: "https://chapelflow-media.storage.example.test/upper-room/clip.mp4?signature=test")

    class Upstream:
        status_code = 200
        headers = {"Content-Type": "video/mp4"}

        def iter_content(self, chunk_size):
            yield b"video-bytes"

        def close(self):
            pass

    monkeypatch.setattr("apps.social.views.requests.get", lambda *args, **kwargs: Upstream())
    api_client.force_authenticate(user=user)
    response = api_client.get(f"/api/v1/social/media/{media.id}/share-preview/")
    assert response.status_code == 200
    assert response["Content-Type"] == "video/mp4"
    assert response.content == b"video-bytes"
