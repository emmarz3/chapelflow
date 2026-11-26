from unittest.mock import patch

import pytest
from django.core import signing
from django.test import override_settings


@pytest.mark.django_db
def test_email_verification_activates_once(api_client, make_user):
    user = make_user(email="verify-me@chapelflow.test")
    user.is_active = False
    user.save(update_fields=["is_active"])
    token = signing.dumps({"id": str(user.pk), "email": user.email}, salt="chapelflow-email-verification")
    response = api_client.post("/api/v1/auth/verify-email/", {"token": token}, format="json")
    assert response.status_code == 200
    user.refresh_from_db()
    assert user.is_active
    assert api_client.post("/api/v1/auth/verify-email/", {"token": token}, format="json").status_code == 400


@pytest.mark.django_db
@override_settings(EMAIL_VERIFICATION_REQUIRED=True, EMAIL_HOST="", FRONTEND_URL="")
def test_registration_fails_closed_when_email_delivery_is_not_configured(api_client, branch_a):
    response = api_client.post("/api/v1/auth/register/", {"email": "new@chapelflow.test", "password": "StrongPass123!", "first_name": "Chidi", "last_name": "Okafor", "branch": str(branch_a.id), "community": "STAFF"}, format="json")
    assert response.status_code == 503


@pytest.mark.django_db
def test_resend_does_not_reveal_account_existence(api_client):
    missing = api_client.post("/api/v1/auth/resend-verification/", {"email": "missing@chapelflow.test"}, format="json")
    assert missing.status_code == 200
    assert "pending registration" in missing.data["message"]


@pytest.mark.django_db(transaction=True)
@override_settings(EMAIL_VERIFICATION_REQUIRED=True, EMAIL_HOST="smtp.example.com", EMAIL_HOST_USER="verified@example.com", EMAIL_HOST_PASSWORD="test", FRONTEND_URL="https://chapelflow.example")
def test_registration_requires_email_before_sign_in(api_client, branch_a):
    with patch("apps.accounts.tasks.send_registration_verification_email.delay") as send:
        response = api_client.post("/api/v1/auth/register/", {"email": "student@chapelflow.test", "matric_no": "swe/2025/018", "password": "StrongPass123!", "first_name": "Chidi", "last_name": "Okafor", "branch": str(branch_a.id), "community": "STUDENT", "academic_level": "100"}, format="json")
    assert response.status_code == 201
    assert response.data["data"]["verification_required"] is True
    assert "chapelflow_access" not in response.cookies
    from apps.accounts.models import User
    user = User.objects.get(email="student@chapelflow.test")
    assert not user.is_active
    assert send.called
    assert api_client.post("/api/v1/auth/login/", {"email": user.email, "password": "StrongPass123!"}, format="json").status_code != 200
