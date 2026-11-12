from django.conf import settings
from django.core.exceptions import ValidationError


def validate_upload(file_obj, *, max_size_mb=None):
    max_size_mb = max_size_mb or getattr(settings, "MAX_UPLOAD_SIZE_MB", 10)
    max_bytes = max_size_mb * 1024 * 1024
    if file_obj.size > max_bytes:
        raise ValidationError(f"File exceeds the maximum allowed size of {max_size_mb}MB.")

    ext = file_obj.name.rsplit(".", 1)[-1].lower() if "." in file_obj.name else ""
    allowed = getattr(settings, "ALLOWED_UPLOAD_EXTENSIONS", [])
    if ext not in allowed:
        raise ValidationError(f"File type '.{ext}' is not permitted. Allowed types: {', '.join(allowed)}.")

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
