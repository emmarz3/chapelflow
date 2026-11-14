import pytest


@pytest.mark.django_db
class TestUpperRoom:
    def test_railway_bucket_video_upload_and_playback_redirect(
        self, api_client, make_user, branch_a, settings, monkeypatch,
    ):
        from django.core.files.uploadedfile import SimpleUploadedFile
        from apps.uploads.storage import S3StorageService

        settings.UPPER_ROOM_STORAGE_PROVIDER = "s3"
        settings.AWS_S3_ENDPOINT_URL = "https://t3.storageapi.dev"
        settings.AWS_S3_ADDRESSING_STYLE = "virtual"
        settings.AWS_STORAGE_BUCKET_NAME = "chapelflow-media-test"
        settings.AWS_S3_REGION_NAME = "auto"
        data = b"\x00\x00\x00\x18ftypmp42" + b"video bytes"

        class BucketClient:
            def upload_fileobj(self, fileobj, bucket, key, ExtraArgs):
                assert fileobj.read() == data
                assert bucket == "chapelflow-media-test"
                assert key.startswith("upper-room/")
                assert ExtraArgs["ContentType"] == "video/mp4"

            def generate_presigned_url(self, operation, Params, ExpiresIn):
                assert operation == "get_object"
                assert Params["Key"].startswith("upper-room/")
                return "https://chapelflow-media-test.t3.storageapi.dev/signed-video"

        monkeypatch.setattr(S3StorageService, "_client", lambda self: BucketClient())
        api_client.force_authenticate(user=make_user(email="bucket-video@chapelflow.test", branch=branch_a))
        posted = api_client.post("/api/v1/social/posts/", {
            "files": SimpleUploadedFile("worship.mp4", data, "video/mp4"),
        }, format="multipart")
        assert posted.status_code == 201
        path = posted.data["data"]["media"][0]["url"]
        assert path.startswith("/api/v1/social/media/")
        playback = api_client.get(path)
        assert playback.status_code == 302
        assert playback["Location"] == "https://chapelflow-media-test.t3.storageapi.dev/signed-video"

    def test_local_video_streams_from_feed_with_range_and_branch_access(
        self, api_client, make_user, branch_a, branch_b, settings, tmp_path,
    ):
        from django.core.files.uploadedfile import SimpleUploadedFile
        from apps.social.models import SocialPostMedia

        settings.STORAGE_PROVIDER = "local"
        settings.MEDIA_ROOT = tmp_path
        settings.PUBLIC_BACKEND_URL = "https://chapelflow-api.example"
        video = b"\x00\x00\x00\x18ftypmp42" + b"playable video bytes"
        author = make_user(email="video-author@chapelflow.test", branch=branch_a)
        api_client.force_authenticate(user=author)
        posted = api_client.post("/api/v1/social/posts/", {
            "caption": "Worship video",
            "files": SimpleUploadedFile("worship.mp4", video, "video/mp4"),
        }, format="multipart")
        assert posted.status_code == 201
        media = SocialPostMedia.objects.get()
        path = posted.data["data"]["media"][0]["url"]
        assert path == f"/api/v1/social/media/{media.upload_id}/"

        streamed = api_client.get(path, HTTP_RANGE="bytes=0-11")
        assert streamed.status_code == 206
        assert streamed["Content-Type"] == "video/mp4"
        assert streamed["Content-Range"] == f"bytes 0-11/{len(video)}"
        assert b"".join(streamed.streaming_content) == video[:12]

        api_client.force_authenticate(user=make_user(email="video-outsider@chapelflow.test", branch=branch_b))
        assert api_client.get(path).status_code == 404

        api_client.force_authenticate(user=author)
        api_client.delete(f"/api/v1/social/posts/{media.post_id}/")
        assert api_client.get(path).status_code == 404

    @pytest.mark.parametrize("filename,content,content_type", [
        ("worship.png", b"\x89PNG\r\n\x1a\n" + b"image content", "image/png"),
        ("worship.mp4", b"\x00\x00\x00\x18ftypmp42" + b"video content", "video/mp4"),
    ])
    def test_media_post_passes_django_credentials_and_binary_stream_to_cloudinary(
        self, api_client, make_user, branch_a, settings, monkeypatch,
        filename, content, content_type,
    ):
        import cloudinary.uploader
        from django.core.files.uploadedfile import SimpleUploadedFile
        from apps.social.models import SocialPostMedia

        settings.STORAGE_PROVIDER = "cloudinary"
        settings.CLOUDINARY_CLOUD_NAME = "test-cloud"
        settings.CLOUDINARY_API_KEY = "test-key"
        settings.CLOUDINARY_API_SECRET = "test-secret"
        url = "https://res.cloudinary.com/test-cloud/upload/worship"

        def upload(file_obj, **options):
            assert file_obj.read() == content
            assert options["cloud_name"] == "test-cloud"
            assert options["api_key"] == "test-key"
            assert options["api_secret"] == "test-secret"
            assert options["resource_type"] == "auto"
            return {"secure_url": url}

        monkeypatch.setattr(cloudinary.uploader, "upload", upload)
        api_client.force_authenticate(user=make_user(email="media@chapelflow.test", branch=branch_a))
        response = api_client.post("/api/v1/social/posts/", {
            "caption": "Sunday worship", "files": SimpleUploadedFile(filename, content, content_type),
        }, format="multipart")

        assert response.status_code == 201
        assert SocialPostMedia.objects.get().upload.file_url == url
        feed = api_client.get("/api/v1/social/posts/")
        assert feed.status_code == 200
        assert feed.data["data"]["items"][0]["caption"] == "Sunday worship"

    def test_posts_are_visible_only_to_their_chapel_branch(self, api_client, make_user, branch_a, branch_b):
        from apps.social.models import SocialPost

        author = make_user(email="author@chapelflow.test", branch=branch_a)
        other_branch_member = make_user(email="other@chapelflow.test", branch=branch_b)
        SocialPost.objects.create(branch=branch_a, author=author, caption="Sunday worship was beautiful.")

        api_client.force_authenticate(user=other_branch_member)
        response = api_client.get("/api/v1/social/posts/")

        assert response.status_code == 200
        assert response.data["data"]["items"] == []

    def test_a_like_toggles_without_duplicate_reactions(self, api_client, make_user, branch_a):
        from apps.social.models import SocialPost, SocialReaction

        user = make_user(email="member@chapelflow.test", branch=branch_a)
        post = SocialPost.objects.create(branch=branch_a, author=user, caption="A good word today.")
        api_client.force_authenticate(user=user)

        first = api_client.post(f"/api/v1/social/posts/{post.id}/like/")
        second = api_client.post(f"/api/v1/social/posts/{post.id}/like/")

        assert first.status_code == 200
        assert first.data["data"] == {"liked": True, "like_count": 1}
        assert second.status_code == 200
        assert second.data["data"] == {"liked": False, "like_count": 0}
        assert SocialReaction.objects.filter(post=post, user=user).count() == 0

    def test_comments_require_content_and_return_the_author(self, api_client, make_user, branch_a):
        from apps.social.models import SocialPost

        user = make_user(email="commenter@chapelflow.test", branch=branch_a, first_name="Ada", last_name="Grace")
        post = SocialPost.objects.create(branch=branch_a, author=user, caption="Welcome to The Upper Room.")
        api_client.force_authenticate(user=user)

        empty = api_client.post(f"/api/v1/social/posts/{post.id}/comments/", {"body": ""}, format="json")
        created = api_client.post(f"/api/v1/social/posts/{post.id}/comments/", {"body": "Amen to this."}, format="json")

        assert empty.status_code == 400
        assert created.status_code == 201
        assert created.data["data"]["author_name"] == "Ada Grace"
        assert created.data["data"]["body"] == "Amen to this."
