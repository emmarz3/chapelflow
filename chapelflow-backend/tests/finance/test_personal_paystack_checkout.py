from unittest.mock import patch

import pytest


@pytest.mark.django_db
class TestPersonalPaystackCheckout:
    @pytest.fixture
    def authenticated_member(self, api_client, member_in_branch_a):
        user = member_in_branch_a.user
        user.email = "giver@chapelflow.test"
        user.save(update_fields=["email"])
        api_client.force_authenticate(user=user)
        return api_client, user, member_in_branch_a

    @patch("apps.finance.views.initialize_paystack_checkout")
    def test_starts_a_server_owned_checkout_without_recording_giving_yet(
        self, initialize_checkout, authenticated_member
    ):
        from apps.finance.models import Giving, Payment, PaymentStatus

        api_client, user, member = authenticated_member
        initialize_checkout.return_value = "https://checkout.paystack.test/authorization-token"

        response = api_client.post(
            "/api/v1/giving/checkout/",
            {"giving_type": "TITHE", "amount": "2500.00", "note": "September", "terms_accepted": True},
            format="json",
        )

        assert response.status_code == 201
        assert response.data["data"]["authorization_url"] == initialize_checkout.return_value
        payment = Payment.objects.get(provider_reference=response.data["data"]["reference"])
        assert payment.member == member
        assert payment.initiated_by == user
        assert payment.giving_category.name == "Tithe"
        assert payment.giving_note == "September"
        assert payment.status == PaymentStatus.PENDING
        assert Giving.objects.filter(payment=payment).count() == 0

    def test_requires_the_checkout_warning_acknowledgement(self, authenticated_member):
        from apps.finance.models import Payment

        api_client, _, _ = authenticated_member
        response = api_client.post(
            "/api/v1/giving/checkout/",
            {"giving_type": "OFFERING", "amount": "500.00", "terms_accepted": False},
            format="json",
        )

        assert response.status_code == 400
        assert "terms_accepted" in response.data["errors"]
        assert Payment.objects.count() == 0

    def test_cannot_verify_another_accounts_payment(self, api_client, branch_a, authenticated_member):
        from apps.accounts.models import User
        from apps.finance.models import Payment

        _, owner, _ = authenticated_member
        other = User.objects.create_user(
            email="other-giver@chapelflow.test",
            password="Pass12345!",
            role="MEMBER",
            branch=branch_a,
        )
        Payment.objects.create(
            branch=branch_a,
            initiated_by=owner,
            provider="PAYSTACK",
            provider_reference="CF-private-reference",
            amount="1000.00",
        )
        api_client.force_authenticate(user=other)

        response = api_client.post(
            "/api/v1/giving/checkout/verify/",
            {"reference": "CF-private-reference"},
            format="json",
        )

        assert response.status_code == 404
