import hashlib
import hmac
import json

import pytest


@pytest.mark.django_db
class TestFinanceAccess:
    def test_member_cannot_access_finance_records(self, api_client, branch_a):
        from apps.accounts.models import User

        member_user = User.objects.create_user(email="member@test.com", password="Pass12345!", role="MEMBER", branch=branch_a)
        api_client.force_authenticate(user=member_user)
        response = api_client.get("/api/v1/giving/")
        assert response.status_code == 403

    def test_finance_officer_can_access_finance_records(self, api_client, branch_a):
        from apps.accounts.models import User

        finance_user = User.objects.create_user(email="fin@test.com", password="Pass12345!", role="FINANCE_OFFICER", branch=branch_a)
        api_client.force_authenticate(user=finance_user)
        response = api_client.get("/api/v1/giving/")
        assert response.status_code == 200


@pytest.mark.django_db
class TestPaystackWebhookIdempotency:
    @pytest.fixture(autouse=True)
    def _set_secret(self, settings):
        settings.PAYSTACK_SECRET_KEY = "test-secret"

    def _sign(self, body: bytes, secret: str) -> str:
        return hmac.new(secret.encode(), body, hashlib.sha512).hexdigest()

    def test_invalid_signature_rejected(self, api_client, branch_a):
        from apps.finance.models import Payment

        Payment.objects.create(
            branch=branch_a, provider="PAYSTACK", provider_reference="ref-123", amount=1000, status="PENDING"
        )
        body = json.dumps({"event": "charge.success", "data": {"reference": "ref-123", "amount": 100000}})
        response = api_client.post(
            "/api/v1/payments/webhook/paystack/",
            data=body,
            content_type="application/json",
            HTTP_X_PAYSTACK_SIGNATURE="wrong-signature",
        )
        assert response.status_code == 400

    def test_valid_webhook_confirms_payment(self, api_client, branch_a):
        from apps.finance.models import Payment, PaymentStatus

        payment = Payment.objects.create(
            branch=branch_a, provider="PAYSTACK", provider_reference="ref-456", amount=1000, status=PaymentStatus.PENDING
        )
        body = json.dumps({"event": "charge.success", "data": {"reference": "ref-456", "amount": 100000}}).encode()
        signature = self._sign(body, "test-secret")

        response = api_client.post(
            "/api/v1/payments/webhook/paystack/",
            data=body,
            content_type="application/json",
            HTTP_X_PAYSTACK_SIGNATURE=signature,
        )
        assert response.status_code == 200
        payment.refresh_from_db()
        assert payment.status == PaymentStatus.SUCCESSFUL

    def test_replayed_webhook_is_idempotent_noop(self, api_client, branch_a):
        """Gateways redeliver webhooks; a second delivery of the same event
        must not error or double-process the payment."""
        from apps.finance.models import Payment, PaymentStatus

        payment = Payment.objects.create(
            branch=branch_a, provider="PAYSTACK", provider_reference="ref-789", amount=1000, status=PaymentStatus.PENDING
        )
        body = json.dumps({"event": "charge.success", "data": {"reference": "ref-789", "amount": 100000}}).encode()
        signature = self._sign(body, "test-secret")

        first = api_client.post(
            "/api/v1/payments/webhook/paystack/", data=body, content_type="application/json",
            HTTP_X_PAYSTACK_SIGNATURE=signature,
        )
        second = api_client.post(
            "/api/v1/payments/webhook/paystack/", data=body, content_type="application/json",
            HTTP_X_PAYSTACK_SIGNATURE=signature,
        )

        assert first.status_code == 200
        assert second.status_code == 200
        payment.refresh_from_db()
        assert payment.status == PaymentStatus.SUCCESSFUL

    def test_unknown_reference_rejected(self, api_client):
        body = json.dumps({"event": "charge.success", "data": {"reference": "does-not-exist", "amount": 100000}}).encode()
        signature = self._sign(body, "test-secret")

        response = api_client.post(
            "/api/v1/payments/webhook/paystack/", data=body, content_type="application/json",
            HTTP_X_PAYSTACK_SIGNATURE=signature,
        )
        assert response.status_code == 400
