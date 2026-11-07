"""
StorageService abstraction. Nothing else in the codebase should import
cloudinary/boto3 directly — swap STORAGE_PROVIDER in settings and every
caller of get_storage_service() gets the new backend for free.
"""
import mimetypes
import time
import uuid
from urllib.parse import urlparse

from django.conf import settings


class StorageService:
    def upload_bytes(self, content: bytes, filename: str, content_type: str = "") -> str:
        raise NotImplementedError

    def upload_fileobj(self, fileobj, filename: str, content_type: str = "", *, private: bool = False) -> str:
        raise NotImplementedError

    def get_download_url(self, file_url: str, *, expires_in: int = 300) -> str:
        raise NotImplementedError("This storage provider does not support private downloads.")

    def delete(self, file_url: str) -> None:
        raise NotImplementedError


class LocalStorageService(StorageService):
    """Dev/test fallback — writes to MEDIA_ROOT. Not for production use."""

    def upload_bytes(self, content: bytes, filename: str, content_type: str = "") -> str:
        from pathlib import Path
        path = Path(settings.MEDIA_ROOT) / filename
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        media_url = settings.MEDIA_URL.rstrip("/")
        if media_url.startswith(("http://", "https://")):
            return f"{media_url}/{filename}"
        return f"{settings.PUBLIC_BACKEND_URL.rstrip('/')}/{media_url.lstrip('/')}/{filename}"

    def upload_fileobj(self, fileobj, filename: str, content_type: str = "", *, private: bool = False) -> str:
        if private and not (
            settings.DEBUG or getattr(settings, "PRIVATE_REPORTS_LOCAL_STORAGE", False)
        ):
            raise RuntimeError("Local storage cannot provide private report downloads in production.")
        from pathlib import Path
        import shutil
        path = Path(settings.MEDIA_ROOT) / filename
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("wb") as destination:
            shutil.copyfileobj(fileobj, destination, length=1024 * 1024)
        media_url = settings.MEDIA_URL.rstrip("/")
        if media_url.startswith(("http://", "https://")):
            return f"{media_url}/{filename}"
        return f"{settings.PUBLIC_BACKEND_URL.rstrip('/')}/{media_url.lstrip('/')}/{filename}"

    def get_download_url(self, file_url: str, *, expires_in: int = 300) -> str:
        return file_url if (
            settings.DEBUG or getattr(settings, "PRIVATE_REPORTS_LOCAL_STORAGE", False)
        ) else ""

    def delete(self, file_url: str) -> None:
        from pathlib import Path
        relative = file_url.replace(settings.MEDIA_URL, "", 1)
        path = Path(settings.MEDIA_ROOT) / relative
        if path.exists():
            path.unlink()


class CloudinaryStorageService(StorageService):
    def upload_bytes(self, content: bytes, filename: str, content_type: str = "") -> str:
        import cloudinary.uploader
        result = cloudinary.uploader.upload(
            content, public_id=filename, resource_type="auto",
        )
        return result["secure_url"]

    def upload_fileobj(self, fileobj, filename: str, content_type: str = "", *, private: bool = False) -> str:
        import cloudinary.uploader
        resource_type = "raw" if private else "auto"
        options = {"type": "private"} if private else {}
        result = cloudinary.uploader.upload(
            fileobj, public_id=filename, resource_type=resource_type, **options,
        )
        return result["secure_url"]

    def get_download_url(self, file_url: str, *, expires_in: int = 300) -> str:
        parsed = urlparse(file_url)
        marker = "/raw/private/"
        if marker not in parsed.path:
            # Older report objects were uploaded with public delivery. Never
            # return those URLs from the authenticated report API.
            return ""
        public_id = parsed.path.split(marker, 1)[1]
        parts = public_id.split("/")
        if parts and parts[0].startswith("v") and parts[0][1:].isdigit():
            parts = parts[1:]
        public_id = "/".join(parts)
        if "." not in public_id:
            return ""
        public_id, file_format = public_id.rsplit(".", 1)
        import cloudinary.utils
        return cloudinary.utils.private_download_url(
            public_id,
            file_format,
            resource_type="raw",
            type="private",
            expires_at=int(time.time()) + max(60, min(expires_in, 900)),
            attachment=True,
        )

    def delete(self, file_url: str) -> None:
        import cloudinary.uploader
        public_id = file_url.rsplit("/", 1)[-1].rsplit(".", 1)[0]
        cloudinary.uploader.destroy(public_id)


class S3StorageService(StorageService):
    def _client(self):
        import boto3
        from botocore.config import Config
        credentials = {}
        if not settings.AWS_USE_IAM_ROLE:
            credentials = {
                "aws_access_key_id": settings.AWS_ACCESS_KEY_ID,
                "aws_secret_access_key": settings.AWS_SECRET_ACCESS_KEY,
            }
        return boto3.client(
            "s3",
            **credentials,
            region_name=settings.AWS_S3_REGION_NAME,
            config=Config(connect_timeout=5, read_timeout=60, retries={"max_attempts": 3, "mode": "standard"}),
        )

    def upload_bytes(self, content: bytes, filename: str, content_type: str = "") -> str:
        client = self._client()
        content_type = content_type or mimetypes.guess_type(filename)[0] or "application/octet-stream"
        client.put_object(
            Bucket=settings.AWS_STORAGE_BUCKET_NAME, Key=filename, Body=content, ContentType=content_type,
        )
        return f"https://{settings.AWS_STORAGE_BUCKET_NAME}.s3.{settings.AWS_S3_REGION_NAME}.amazonaws.com/{filename}"

    def upload_fileobj(self, fileobj, filename: str, content_type: str = "", *, private: bool = False) -> str:
        client = self._client()
        content_type = content_type or mimetypes.guess_type(filename)[0] or "application/octet-stream"
        client.upload_fileobj(fileobj, settings.AWS_STORAGE_BUCKET_NAME, filename, ExtraArgs={"ContentType": content_type})
        return f"https://{settings.AWS_STORAGE_BUCKET_NAME}.s3.{settings.AWS_S3_REGION_NAME}.amazonaws.com/{filename}"

    def get_download_url(self, file_url: str, *, expires_in: int = 300) -> str:
        parsed = urlparse(file_url)
        expected_host = f"{settings.AWS_STORAGE_BUCKET_NAME}.s3.{settings.AWS_S3_REGION_NAME}.amazonaws.com"
        if parsed.hostname != expected_host:
            return ""
        return self._client().generate_presigned_url(
            "get_object",
            Params={"Bucket": settings.AWS_STORAGE_BUCKET_NAME, "Key": parsed.path.lstrip("/")},
            ExpiresIn=max(60, min(expires_in, 900)),
        )

    def delete(self, file_url: str) -> None:
        key = file_url.split(".amazonaws.com/", 1)[-1]
        self._client().delete_object(Bucket=settings.AWS_STORAGE_BUCKET_NAME, Key=key)


class SupabaseStorageService(StorageService):
    """Uses the Supabase Storage REST API directly (not boto3's S3
    compatibility layer) so we're not fighting AWS-specific assumptions
    about the endpoint/host. Auth is via the service_role key — this
    bypasses Row Level Security, so it must only ever run server-side.
    """

    def _base_url(self) -> str:
        return settings.SUPABASE_URL.rstrip("/")

    def _headers(self, content_type: str = "") -> dict:
        headers = {
            "Authorization": f"Bearer {settings.SUPABASE_SECRET_KEY}",
            "apikey": settings.SUPABASE_SECRET_KEY,
        }
        if content_type:
            headers["Content-Type"] = content_type
        return headers

    def upload_bytes(self, content: bytes, filename: str, content_type: str = "") -> str:
        import requests

        content_type = content_type or mimetypes.guess_type(filename)[0] or "application/octet-stream"
        bucket = settings.SUPABASE_STORAGE_BUCKET
        url = f"{self._base_url()}/storage/v1/object/{bucket}/{filename}"
        response = requests.post(
            url,
            headers={**self._headers(content_type), "x-upsert": "true"},
            data=content,
            timeout=30,
        )
        response.raise_for_status()
        return f"{self._base_url()}/storage/v1/object/public/{bucket}/{filename}"

    def upload_fileobj(self, fileobj, filename: str, content_type: str = "", *, private: bool = False) -> str:
        if private:
            raise RuntimeError("Supabase report downloads require a private storage bucket; configure one before enabling exports.")
        import requests
        content_type = content_type or mimetypes.guess_type(filename)[0] or "application/octet-stream"
        bucket = settings.SUPABASE_STORAGE_BUCKET
        url = f"{self._base_url()}/storage/v1/object/{bucket}/{filename}"
        response = requests.post(
            url, headers={**self._headers(content_type), "x-upsert": "true"},
            data=fileobj, timeout=(5, 60),
        )
        response.raise_for_status()
        return f"{self._base_url()}/storage/v1/object/public/{bucket}/{filename}"

    def delete(self, file_url: str) -> None:
        import requests

        bucket = settings.SUPABASE_STORAGE_BUCKET
        marker = f"/storage/v1/object/public/{bucket}/"
        key = file_url.split(marker, 1)[-1] if marker in file_url else file_url.rsplit("/", 1)[-1]
        url = f"{self._base_url()}/storage/v1/object/{bucket}/{key}"
        response = requests.delete(url, headers=self._headers(), timeout=30)
        if response.status_code not in (200, 204, 404):
            response.raise_for_status()


def get_storage_service() -> StorageService:
    provider = getattr(settings, "STORAGE_PROVIDER", "local")
    return {
        "local": LocalStorageService,
        "cloudinary": CloudinaryStorageService,
        "s3": S3StorageService,
        "supabase": SupabaseStorageService,
    }.get(provider, LocalStorageService)()


def generate_storage_filename(original_name: str, prefix: str = "uploads") -> str:
    ext = original_name.rsplit(".", 1)[-1].lower() if "." in original_name else ""
    unique = uuid.uuid4().hex
    return f"{prefix}/{unique}.{ext}" if ext else f"{prefix}/{unique}"
