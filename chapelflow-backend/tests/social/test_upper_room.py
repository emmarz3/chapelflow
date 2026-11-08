import pytest


@pytest.mark.django_db
class TestUpperRoom:
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
