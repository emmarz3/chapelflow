"""
StorageService abstraction. Nothing else in the codebase should import
cloudinary/boto3 directly — swap STORAGE_PROVIDER in settings and every
caller of get_storage_service() gets the new backend for free.
"""
import mimetypes
import uuid

from django.conf import settings


class StorageService:
    def upload_bytes(self, content: bytes, filename: str, content_type: str = "") -> str:
        raise NotImplementedError

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

    def delete(self, file_url: str) -> None:
        import cloudinary.uploader
        public_id = file_url.rsplit("/", 1)[-1].rsplit(".", 1)[0]
        cloudinary.uploader.destroy(public_id)


class S3StorageService(StorageService):
    def _client(self):
        import boto3
        return boto3.client(
            "s3",
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            region_name=settings.AWS_S3_REGION_NAME,
        )

    def upload_bytes(self, content: bytes, filename: str, content_type: str = "") -> str:
        client = self._client()
        content_type = content_type or mimetypes.guess_type(filename)[0] or "application/octet-stream"
        client.put_object(
            Bucket=settings.AWS_STORAGE_BUCKET_NAME, Key=filename, Body=content, ContentType=content_type,
        )
        return f"https://{settings.AWS_STORAGE_BUCKET_NAME}.s3.{settings.AWS_S3_REGION_NAME}.amazonaws.com/{filename}"

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
