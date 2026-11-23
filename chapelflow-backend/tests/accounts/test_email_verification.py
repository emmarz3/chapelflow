from urllib.parse import parse_qs, urlparse

import pytest
from django.core import mail
from django.core.cache import cache


@pytest.mark.django_db
class TestEmailVerification:
    def setup_method(self):
        cache.clear()
        mail.outbox.clear()

    def test_signup_sends_confirmation_and_blocks_login_until_verified(self, api_client, branch_a):
        from apps.accounts.models import User

        email = "new.member@example.edu.ng"
        response = api_client.post(
            "/api/v1/auth/register/",
            {
                "email": email,
                "password": "StrongPass123!",
                "first_name": "New",
                "last_name": "Member",
                "branch": str(branch_a.id),
                "community": "GUEST",
            },
            format="json",
        )

        assert response.status_code == 201
        assert response.data["data"]["verification_required"] is True
        assert "chapelflow_access" not in response.cookies
        user = User.objects.get(email=email)
        assert user.email_verified is False
        assert len(mail.outbox) == 1
        assert "Confirm your ChapelFlow email address" == mail.outbox[0].subject

        login_before_verification = api_client.post(
            "/api/v1/auth/login/",
            {"email": email, "password": "StrongPass123!"},
            format="json",
        )
        assert login_before_verification.status_code == 400
        assert "verify your email" in str(login_before_verification.data).lower()

        verification_line = next(
            line.strip()
            for line in mail.outbox[0].body.splitlines()
            if "/verify-email?" in line
        )
        token = parse_qs(urlparse(verification_line).query)["token"][0]
        verified = api_client.post(
            "/api/v1/auth/verify-email/",
            {"token": token},
            format="json",
        )

        assert verified.status_code == 200
        assert verified.data["data"]["verified"] is True
        user.refresh_from_db()
        assert user.email_verified is True

        login_after_verification = api_client.post(
            "/api/v1/auth/login/",
            {"email": email, "password": "StrongPass123!"},
            format="json",
        )
        assert login_after_verification.status_code == 200
        assert "chapelflow_access" in login_after_verification.cookies

    def test_invalid_verification_tokens_are_rejected(self, api_client):
        response = api_client.post(
            "/api/v1/auth/verify-email/",
            {"token": "not-a-valid-signed-token"},
            format="json",
        )
        assert response.status_code == 400

    def test_resend_is_generic_for_registered_and_unknown_addresses(self, api_client):
        from apps.accounts.models import User

        User.objects.create_user(
            email="awaiting.confirmation@example.com",
            password="StrongPass123!",
            first_name="Awaiting",
            last_name="Confirmation",
            email_verified=False,
        )

        known = api_client.post(
            "/api/v1/auth/resend-verification/",
            {"email": "awaiting.confirmation@example.com"},
            format="json",
        )
        unknown = api_client.post(
            "/api/v1/auth/resend-verification/",
            {"email": "not-registered@example.com"},
            format="json",
        )

        assert known.status_code == 200
        assert unknown.status_code == 200
        assert known.data["message"] == unknown.data["message"]
        assert len(mail.outbox) == 1
        assert "verify-email?token=" in mail.outbox[0].body
