from django.conf import settings
from django.core.exceptions import ValidationError


MEDIA_CONTENT_ALLOWED_EXTENSIONS = frozenset({
    "jpg", "jpeg", "png", "gif", "webp",
    "mp4", "mov", "webm",
    "mp3", "m4a", "pdf",
})


def validate_upload(file_obj, *, max_size_mb=None, allowed_extensions=None):
    max_size_mb = max_size_mb or getattr(settings, "MAX_UPLOAD_SIZE_MB", 10)
    max_bytes = max_size_mb * 1024 * 1024
    if file_obj.size > max_bytes:
        raise ValidationError(f"File exceeds the maximum allowed size of {max_size_mb}MB.")

    ext = file_obj.name.rsplit(".", 1)[-1].lower() if "." in file_obj.name else ""
    allowed = set(allowed_extensions) if allowed_extensions is not None else set(
        getattr(settings, "ALLOWED_UPLOAD_EXTENSIONS", [])
    )
    if ext not in allowed:
        raise ValidationError(
            f"File type '.{ext}' is not permitted. Allowed types: {', '.join(sorted(allowed))}."
        )

    return ext


def validate_social_media(file_obj):
    """Match browser MIME, extension and file signature before publishing media."""
    ext = file_obj.name.rsplit(".", 1)[-1].lower() if "." in file_obj.name else ""
    content_type = (file_obj.content_type or "").lower()
    allowed = {
        "jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png",
        "gif": "image/gif", "webp": "image/webp", "mp4": "video/mp4",
        "mov": "video/quicktime", "webm": "video/webm",
    }
    if allowed.get(ext) != content_type:
        raise ValidationError("The media file type does not match its filename.")
    position = file_obj.tell()
    header = file_obj.read(16)
    file_obj.seek(position)
    signature_matches = {
        "jpg": header.startswith(b"\xff\xd8\xff"),
        "jpeg": header.startswith(b"\xff\xd8\xff"),
        "png": header.startswith(b"\x89PNG\r\n\x1a\n"),
        "gif": header.startswith((b"GIF87a", b"GIF89a")),
        "webp": header.startswith(b"RIFF") and header[8:12] == b"WEBP",
        "mp4": header[4:8] == b"ftyp",
        "mov": header[4:8] == b"ftyp",
        "webm": header.startswith(b"\x1a\x45\xdf\xa3"),
    }
    if not signature_matches.get(ext, False):
        raise ValidationError("The media file contents do not match its declared type.")


def validate_public_media(file_obj):
    """Validate images, video, audio and PDF files used by the public media library."""
    ext = file_obj.name.rsplit(".", 1)[-1].lower() if "." in file_obj.name else ""
    allowed_mimes = {
        "jpg": {"image/jpeg", "image/pjpeg"}, "jpeg": {"image/jpeg", "image/pjpeg"},
        "png": {"image/png"}, "gif": {"image/gif"}, "webp": {"image/webp"},
        "mp4": {"video/mp4"}, "mov": {"video/quicktime", "video/mp4"}, "webm": {"video/webm"},
        "mp3": {"audio/mpeg", "audio/mp3", "audio/x-mpeg-3"},
        "m4a": {"audio/mp4", "audio/x-m4a", "video/mp4"},
        "pdf": {"application/pdf"},
    }
    if ext not in allowed_mimes:
        raise ValidationError(
            "Unsupported media format. Use JPG, PNG, GIF, WebP, MP4, MOV, WebM, MP3, M4A, or PDF."
        )

    declared_type = (file_obj.content_type or "").split(";", 1)[0].strip().lower()
    if declared_type and declared_type != "application/octet-stream" and declared_type not in allowed_mimes[ext]:
        raise ValidationError("The media file type does not match its filename.")

    position = file_obj.tell()
    header = file_obj.read(32)
    file_obj.seek(position)
    signatures = {
        "jpg": header.startswith(b"\\xff\\xd8\\xff"),
        "jpeg": header.startswith(b"\\xff\\xd8\\xff"),
        "png": header.startswith(b"\\x89PNG\\r\\n\\x1a\\n"),
        "gif": header.startswith((b"GIF87a", b"GIF89a")),
        "webp": header.startswith(b"RIFF") and header[8:12] == b"WEBP",
        "mp4": header[4:8] == b"ftyp",
        "mov": header[4:8] == b"ftyp",
        "webm": header.startswith(b"\\x1a\\x45\\xdf\\xa3"),
        "mp3": header.startswith(b"ID3") or (
            len(header) > 1 and header[0] == 0xff and header[1] & 0xe0 == 0xe0
        ),
        "m4a": header[4:8] == b"ftyp",
        "pdf": header.startswith(b"%PDF-"),
    }
    if not signatures.get(ext, False):
        raise ValidationError("The file contents do not match the declared media type.")


def validate_category_content(file_obj, category):
    """Reject mismatched media and document bytes before sending them to storage."""
    from zipfile import BadZipFile, ZipFile

    from .models import UploadCategory

    ext = file_obj.name.rsplit(".", 1)[-1].lower() if "." in file_obj.name else ""
    image_categories = {UploadCategory.MEMBER_PHOTO, UploadCategory.BRANCH_LOGO, UploadCategory.EVENT_IMAGE}
    if category in image_categories and ext not in {"jpg", "jpeg", "png", "gif", "webp"}:
        raise ValidationError("This category accepts images only.")
    if category == UploadCategory.MEDIA_CONTENT:
        validate_public_media(file_obj)
        return
    if category in image_categories | {UploadCategory.SOCIAL_POST}:
        validate_social_media(file_obj)
        return
    if ext in {"jpg", "jpeg", "png", "gif", "webp", "mp4", "mov", "webm"}:
        validate_social_media(file_obj)
        return
    if category == UploadCategory.DOCUMENT and ext not in {"pdf", "docx"}:
        raise ValidationError("This category accepts PDF and DOCX documents only.")
    if category == UploadCategory.SERMON_AUDIO and ext not in {"mp3", "m4a"}:
        raise ValidationError("This category accepts MP3 and M4A audio only.")
    if ext in {"pdf", "docx", "mp3", "m4a"}:
        position = file_obj.tell()
        header = file_obj.read(16)
        file_obj.seek(position)
        signatures = {
            "pdf": header.startswith(b"%PDF-"),
            "docx": header.startswith(b"PK\x03\x04"),
            "mp3": header.startswith(b"ID3") or (len(header) > 1 and header[0] == 0xff and header[1] & 0xe0 == 0xe0),
            "m4a": header[4:8] == b"ftyp",
        }
        if not signatures[ext]:
            raise ValidationError("The file contents do not match its declared type.")
        if ext == "docx":
            try:
                with ZipFile(file_obj) as archive:
                    if "[Content_Types].xml" not in archive.namelist() or "word/document.xml" not in archive.namelist():
                        raise ValidationError("The DOCX document is invalid.")
            except BadZipFile as exc:
                raise ValidationError("The DOCX document is invalid.") from exc
            finally:
                file_obj.seek(position)
