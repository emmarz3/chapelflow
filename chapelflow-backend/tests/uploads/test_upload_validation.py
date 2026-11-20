import pytest


@pytest.mark.django_db
def test_media_upload_rejects_mismatched_file_bytes(api_client, make_user, branch_a):
    from django.core.files.uploadedfile import SimpleUploadedFile
    from common.constants.roles import Roles

    api_client.force_authenticate(make_user(email="publisher@chapelflow.test", branch=branch_a, role=Roles.SUPER_ADMIN))
    response = api_client.post("/api/v1/uploads/upload/", {
        "file": SimpleUploadedFile("fake.jpg", b"<script>alert(1)</script>", "image/jpeg"),
        "category": "MEDIA_CONTENT",
    }, format="multipart")
    assert response.status_code == 400


@pytest.mark.django_db
def test_member_cannot_list_another_members_uploads(api_client, make_user, branch_a):
    from apps.uploads.models import Upload
    from common.constants.roles import Roles

    owner = make_user(email="owner@chapelflow.test", branch=branch_a, role=Roles.MEMBER)
    viewer = make_user(email="viewer@chapelflow.test", branch=branch_a, role=Roles.MEMBER)
    Upload.objects.create(branch=branch_a, uploaded_by=owner, category="DOCUMENT", original_filename="private.pdf",
                          file_url="https://files.example/private.pdf", content_type="application/pdf", size_bytes=7)
    api_client.force_authenticate(viewer)
    response = api_client.get("/api/v1/uploads/")
    assert response.status_code == 200
    assert "private.pdf" not in str(response.data)
