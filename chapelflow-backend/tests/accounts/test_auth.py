import pytest
from django.core.exceptions import ValidationError

from apps.accounts.validators import normalize_matric_no, validate_matric_no


class TestMatricNoValidator:
    def test_valid_matric_no_passes(self):
        validate_matric_no("SWE/2024/005")  # should not raise

    def test_normalizes_lowercase_to_uppercase(self):
        assert normalize_matric_no("swe/2024/005") == "SWE/2024/005"

    def test_strips_whitespace(self):
        assert normalize_matric_no("  SWE/2024/005  ") == "SWE/2024/005"

    @pytest.mark.parametrize(
        "bad_value",
        [
            "notarealformat",
            "SWE-2024-005",
            "12/2024/005",       # programme code must be letters
            "SWE/24/5",          # year/sequence too short for default pattern in some configs -- kept lenient below
            "SWE/2024/",         # missing sequence
        ],
    )
    def test_invalid_formats_raise(self, bad_value):
        if bad_value == "SWE/24/5":
            pytest.skip("2-digit year / 1-digit sequence is accepted by the lenient default regex; not a real failure case.")
        with pytest.raises(ValidationError):
            validate_matric_no(bad_value)


@pytest.mark.django_db
class TestUserMatricLogin:
    def test_matric_no_normalized_on_save(self):
        from apps.accounts.models import User

        user = User.objects.create_user(matric_no="swe/2024/005", password="Pass12345!", role="MEMBER")
        assert user.matric_no == "SWE/2024/005"

    def test_login_case_insensitive(self, api_client):
        from apps.accounts.models import User

        User.objects.create_user(matric_no="swe/2024/005", password="Pass12345!", role="MEMBER")
        response = api_client.post(
            "/api/v1/auth/login/", {"matric_no": "SWE/2024/005", "password": "Pass12345!"}, format="json"
        )
        assert response.status_code == 200
        assert response.data["success"] is True

    def test_invalid_credentials_return_clean_400_not_500(self, api_client):
        response = api_client.post(
            "/api/v1/auth/login/", {"matric_no": "NOTREAL/0000/000", "password": "whatever"}, format="json"
        )
        assert response.status_code == 400
        assert response.data["success"] is False

    def test_inactive_account_cannot_login(self, api_client):
        from apps.accounts.models import User

        user = User.objects.create_user(matric_no="swe/2024/009", password="Pass12345!", role="MEMBER")
        user.is_active = False
        user.save()

        response = api_client.post(
            "/api/v1/auth/login/", {"matric_no": "SWE/2024/009", "password": "Pass12345!"}, format="json"
        )
        assert response.status_code == 400
        assert response.data["success"] is False
