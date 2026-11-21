from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.accounts.serializers import UserPublicSerializer
from apps.uploads.models import Upload
from common.constants.roles import Roles


class ProfilePhotoTests(TestCase):
    url = "/api/v1/auth/profile/photo/"

    def photo(self, content=b"\x89PNG\r\n\x1a\nimage-content", name="avatar.png"):
        return SimpleUploadedFile(name, content, content_type="image/png")

    def account(self, role, suffix=""):
        return User.objects.create_user(
            email=f"{role.lower()}{suffix}@example.com", password="safe-password-123",
            first_name="Photo", last_name="Owner", role=role,
        )

    @patch("apps.uploads.storage.get_storage_service")
    def test_every_role_can_upload_without_a_member_or_branch(self, storage):
        storage.return_value.upload_bytes.return_value = "https://res.cloudinary.com/test/image/upload/avatar.png"
        client = APIClient()
        for role, _ in Roles.CHOICES:
            with self.subTest(role=role):
                user = self.account(role)
                client.force_authenticate(user)
                response = client.post(self.url, {"file": self.photo()}, format="multipart")
                self.assertEqual(response.status_code, 200)
                user.refresh_from_db()
                self.assertEqual(user.photo_url, response.data["data"]["photo_url"])
                self.assertEqual(UserPublicSerializer(user).data["photo_url"], user.photo_url)
                self.assertEqual(Upload.objects.get(uploaded_by=user).file_url, user.photo_url)

    @patch("apps.uploads.storage.get_storage_service")
    def test_upload_updates_only_requesting_account_and_replaces_photo(self, storage):
        storage.return_value.upload_bytes.return_value = "https://example.com/new.png"
        owner, other = self.account(Roles.MEMBER), self.account(Roles.MEMBER, "other")
        owner.photo_url = "https://example.com/old.png"
        owner.save()
        client = APIClient()
        client.force_authenticate(owner)
        response = client.post(self.url, {"file": self.photo(), "user_id": str(other.pk)}, format="multipart")
        self.assertEqual(response.status_code, 200)
        owner.refresh_from_db()
        other.refresh_from_db()
        self.assertEqual(owner.photo_url, "https://example.com/new.png")
        self.assertEqual(other.photo_url, "")

    @patch("apps.uploads.storage.get_storage_service")
    def test_invalid_and_oversized_images_never_reach_storage(self, storage):
        client = APIClient()
        client.force_authenticate(self.account(Roles.MEMBER))
        for photo in [self.photo(b"not an image"), self.photo(name="avatar.svg"), self.photo(b"x" * (10 * 1024 * 1024 + 1))]:
            self.assertEqual(client.post(self.url, {"file": photo}, format="multipart").status_code, 400)
        storage.assert_not_called()
        self.assertEqual(Upload.objects.count(), 0)

    @patch("apps.uploads.storage.get_storage_service")
    def test_storage_failure_preserves_existing_picture(self, storage):
        storage.return_value.upload_bytes.side_effect = RuntimeError("provider unavailable")
        owner = self.account(Roles.MEMBER)
        owner.photo_url = "https://example.com/old.png"
        owner.save()
        client = APIClient()
        client.force_authenticate(owner)
        self.assertEqual(client.post(self.url, {"file": self.photo()}, format="multipart").status_code, 503)
        owner.refresh_from_db()
        self.assertEqual(owner.photo_url, "https://example.com/old.png")
        self.assertFalse(Upload.objects.exists())

    def test_anonymous_upload_is_rejected(self):
        self.assertIn(APIClient().post(self.url, {"file": self.photo()}, format="multipart").status_code, (401, 403))
