import pytest
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError


def test_password_policy_accepts_eight_characters_and_rejects_shorter():
    validate_password("Zp9!kQ2x")
    with pytest.raises(ValidationError):
        validate_password("Zp9!kQ2")


def test_password_policy_still_rejects_common_passwords():
    with pytest.raises(ValidationError):
        validate_password("password")
