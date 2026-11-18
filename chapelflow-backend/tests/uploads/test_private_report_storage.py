from io import BytesIO
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from django.test import override_settings

from apps.uploads.storage import (
    CloudinaryStorageService,
    LocalStorageService,
    S3StorageService,
    SupabaseStorageService,
)
from apps.reports.serializers import ReportJobSerializer


def test_cloudinary_report_upload_uses_private_raw_delivery(monkeypatch):
    import cloudinary.uploader

    upload = Mock(return_value={"secure_url": "https://res.cloudinary.com/demo/raw/private/v123/reports/export.csv"})
    monkeypatch.setattr(cloudinary.uploader, "upload", upload)

    result = CloudinaryStorageService().upload_fileobj(
        BytesIO(b"sensitive"), "reports/export.csv", "text/csv", private=True,
    )

    assert result.endswith("/raw/private/v123/reports/export.csv")
    assert upload.call_args.kwargs["resource_type"] == "raw"
    assert upload.call_args.kwargs["type"] == "private"


def test_cloudinary_report_download_is_time_limited_and_legacy_public_urls_are_hidden(monkeypatch):
    import cloudinary.utils

    download = Mock(return_value="https://api.cloudinary.com/temporary-signed-download")
    monkeypatch.setattr(cloudinary.utils, "private_download_url", download)
    service = CloudinaryStorageService()

    result = service.get_download_url(
        "https://res.cloudinary.com/demo/raw/private/v123/reports/export.csv",
    )

    assert result == "https://api.cloudinary.com/temporary-signed-download"
    assert download.call_args.args == ("reports/export", "csv")
    assert download.call_args.kwargs["resource_type"] == "raw"
    assert download.call_args.kwargs["type"] == "private"
    assert download.call_args.kwargs["attachment"] is True
    assert service.get_download_url("https://res.cloudinary.com/demo/raw/upload/reports/old.csv") == ""


@override_settings(AWS_STORAGE_BUCKET_NAME="private-reports", AWS_S3_REGION_NAME="eu-west-2")
def test_s3_report_download_is_presigned_and_rejects_foreign_hosts(monkeypatch):
    client = Mock()
    client.generate_presigned_url.return_value = "https://signed.example/download"
    service = S3StorageService()
    monkeypatch.setattr(service, "_client", lambda: client)

    result = service.get_download_url(
        "https://private-reports.s3.eu-west-2.amazonaws.com/reports/export.csv",
    )

    assert result == "https://signed.example/download"
    assert client.generate_presigned_url.call_args.kwargs["ExpiresIn"] == 300
    assert service.get_download_url("https://attacker.example/reports/export.csv") == ""


@override_settings(AWS_USE_IAM_ROLE=True, AWS_S3_REGION_NAME="eu-west-2", AWS_ACCESS_KEY_ID="", AWS_SECRET_ACCESS_KEY="")
def test_s3_uses_task_role_credentials(monkeypatch):
    import boto3

    client_factory = Mock()
    monkeypatch.setattr(boto3, "client", client_factory)
    S3StorageService()._client()

    assert client_factory.call_args.args == ("s3",)
    assert "aws_access_key_id" not in client_factory.call_args.kwargs
    assert "aws_secret_access_key" not in client_factory.call_args.kwargs


def test_supabase_private_report_upload_fails_closed():
    with pytest.raises(RuntimeError, match="private storage bucket"):
        SupabaseStorageService().upload_fileobj(
            BytesIO(b"sensitive"), "reports/export.csv", "text/csv", private=True,
        )


@override_settings(DEBUG=False, PRIVATE_REPORTS_LOCAL_STORAGE=False)
def test_local_storage_refuses_private_production_reports():
    with pytest.raises(RuntimeError, match="cannot provide private report downloads"):
        LocalStorageService().upload_fileobj(
            BytesIO(b"sensitive"), "reports/export.csv", "text/csv", private=True,
        )


def test_report_serializer_returns_only_provider_generated_download_url(monkeypatch):
    storage = Mock()
    storage.get_download_url.return_value = "https://signed.example/download"
    monkeypatch.setattr("apps.uploads.storage.get_storage_service", lambda: storage)
    serializer = ReportJobSerializer()

    completed = SimpleNamespace(status="COMPLETE", file_url="https://storage/private-object")
    queued = SimpleNamespace(status="QUEUED", file_url="")

    assert serializer.get_file_url(completed) == "https://signed.example/download"
    assert serializer.get_file_url(queued) == ""
    assert storage.get_download_url.call_count == 1
