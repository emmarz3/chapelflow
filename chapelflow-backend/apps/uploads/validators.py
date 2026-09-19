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
