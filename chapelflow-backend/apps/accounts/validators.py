import re

from django.conf import settings
from django.core.exceptions import ValidationError


def normalize_matric_no(value: str) -> str:
    """Uppercase and strip whitespace so 'swe/2024/005' == 'SWE/2024/005'."""
    if value is None:
        return value
    return value.strip().upper()


def validate_matric_no(value: str) -> None:
    """
    Validates against a configurable pattern (settings.MATRIC_NUMBER_REGEX)
    rather than hardcoding one department/institution's format.

    Default pattern: PROGRAMME/YEAR/SEQUENCE, e.g. SWE/2024/005
    """
    if not value:
        return
    normalized = normalize_matric_no(value)
    pattern = getattr(settings, "MATRIC_NUMBER_REGEX", r"^[A-Z]{2,6}/[0-9]{2,4}/[0-9]{3,6}$")
    if not re.match(pattern, normalized):
        raise ValidationError(
            "Enter a valid matriculation number, e.g. SWE/2024/005.",
            code="invalid_matric_no",
        )
