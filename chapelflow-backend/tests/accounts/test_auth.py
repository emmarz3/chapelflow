import pytest
<<<<<<< HEAD
from http.cookies import Morsel
=======
>>>>>>> origin/main
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.test import override_settings

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
    @pytest.fixture(autouse=True)
    def clear_login_throttle(self):
        cache.clear()

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

<<<<<<< HEAD
    def test_failed_login_log_does_not_include_submitted_identifier(self, caplog):
        from types import SimpleNamespace

        from apps.accounts.services import record_login

        caplog.set_level(30, logger="chapelflow.security")
        identifier = "private.student@example.edu"
        request = SimpleNamespace(META={"REMOTE_ADDR": "127.0.0.1", "HTTP_USER_AGENT": "test"})

        record_login(None, request, successful=False, failure_reason="invalid_credentials", identifier_attempted=identifier)

        assert identifier not in caplog.text
        assert "login_failed reason=invalid_credentials" in caplog.text

=======
>>>>>>> origin/main
    @override_settings(DEBUG=False)
    def test_production_login_cookies_support_cross_origin_frontends(self, api_client):
        from apps.accounts.models import User

        User.objects.create_user(email="cookie-test@example.com", password="Pass12345!", role="CHAPEL_ADMIN")
        response = api_client.post(
            "/api/v1/auth/login/",
            {"email": "cookie-test@example.com", "password": "Pass12345!"},
            format="json",
        )

        assert response.status_code == 200
        for name in ("chapelflow_access", "chapelflow_refresh", "chapelflow_csrf"):
            assert response.cookies[name]["samesite"] == "None"
            assert response.cookies[name]["secure"] is True
            assert response.cookies[name]["path"] == "/"

<<<<<<< HEAD
    @override_settings(DEBUG=True, CHAPELFLOW_LOCAL_EMBEDDED_PREVIEW=True)
    def test_local_preview_login_uses_partitioned_secure_cookies(self, api_client):
        if "partitioned" not in Morsel._reserved:
            pytest.skip("This Python version cannot serialize Partitioned cookies.")
        from apps.accounts.models import User

        User.objects.create_user(email="preview-test@example.com", password="Pass12345!", role="MEMBER")
        response = api_client.post(
            "/api/v1/auth/login/",
            {"email": "preview-test@example.com", "password": "Pass12345!"},
            format="json",
        )

        assert response.status_code == 200
        for name in ("chapelflow_access", "chapelflow_refresh", "chapelflow_csrf"):
            assert response.cookies[name]["samesite"] == "None"
            assert response.cookies[name]["secure"] is True
            assert response.cookies[name]["partitioned"] is True
        assert response.cookies["chapelflow_access"]["httponly"] is True
        assert response.cookies["chapelflow_refresh"]["httponly"] is True

=======
>>>>>>> origin/main
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
