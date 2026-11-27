from unittest.mock import Mock, patch

import pytest
from django.core.cache import cache
from django.test import override_settings
from rest_framework.test import APIClient

ENDPOINT = "/api/v1/public/scendey-waitlist/"
SCENDEY_URL = "https://scendey-waitlist-production.up.railway.app/api/join"


@pytest.fixture(autouse=True)
def clear_throttle_cache():
    cache.clear()
    yield
    cache.clear()


@pytest.mark.parametrize(
    ("audience", "role"),
    [
        ("student", "SHOPPER"),
        ("staff", "SHOPPER"),
        ("other", "SHOPPER"),
        ("business", "BRAND"),
    ],
)
@override_settings(SCENDEY_WAITLIST_URL=SCENDEY_URL)
def test_public_signup_maps_audience_and_forwards_only_optional_marketing_consent(audience, role):
    provider = Mock(ok=True, status_code=201)
    provider.json.return_value = {"ok": True, "existing": False, "delivered": True}
    payload = {
        "name": "Test Visitor",
        "email": "  Visitor@Example.COM ",
        "audienceCategory": audience,
        "marketingConsent": False,
    }
    if audience == "business":
        payload.update({"brandName": "Test Brand", "category": "Fashion"})

    with patch("apps.advertising.scendey.requests.post", return_value=provider) as send:
        response = APIClient().post(ENDPOINT, payload, format="json")

    assert response.status_code == 200, response.data
    assert response.data["data"]["processed"] is True
    forwarded = send.call_args.kwargs["json"]
    assert forwarded["role"] == role
    assert forwarded["audienceCategory"] == audience.upper()
    assert forwarded["name"] == "Test Visitor"
    assert forwarded["email"] == "visitor@example.com"
    assert forwarded["consent"] is False
    assert forwarded["source"] == "ChapelFlow"
    assert send.call_args.kwargs["timeout"] == (3, 12)
    assert "brandName" in forwarded if audience == "business" else "brandName" not in forwarded


@override_settings(SCENDEY_WAITLIST_URL=SCENDEY_URL)
def test_marketing_opt_in_is_forwarded_separately_from_transactional_verification():
    provider = Mock(ok=True, status_code=201)
    provider.json.return_value = {"ok": True, "existing": False, "delivered": True}
    payload = {
        "name": "Brand Owner",
        "email": "owner@example.com",
        "audienceCategory": "business",
        "brandName": "Brand",
        "category": "Retail",
        "marketingConsent": True,
    }

    with patch("apps.advertising.scendey.requests.post", return_value=provider) as send:
        response = APIClient().post(ENDPOINT, payload, format="json")

    assert response.status_code == 200
    assert send.call_args.kwargs["json"]["consent"] is True


def test_honeypot_returns_generic_success_without_calling_scendey():
    with patch("apps.advertising.scendey.requests.post") as send:
        response = APIClient().post(
            ENDPOINT,
            {"website": "https://spam.invalid"},
            format="json",
        )

    assert response.status_code == 200
    assert response.data["data"]["processed"] is True
    send.assert_not_called()


def test_missing_or_insecure_provider_url_fails_closed():
    for endpoint in ("", "http://scendey.invalid/api/join", "https://user:pass@example.com/join"):
        with override_settings(SCENDEY_WAITLIST_URL=endpoint):
            response = APIClient().post(
                ENDPOINT,
                {
                    "name": "Test Visitor",
                    "email": "visitor@example.com",
                    "audienceCategory": "student",
                },
                format="json",
            )
        assert response.status_code == 503


@override_settings(SCENDEY_WAITLIST_URL=SCENDEY_URL)
def test_provider_failure_does_not_claim_registration_success():
    provider = Mock(ok=False, status_code=500)
    provider.json.return_value = {"ok": False}

    with patch("apps.advertising.scendey.requests.post", return_value=provider):
        response = APIClient().post(
            ENDPOINT,
            {
                "name": "Test Visitor",
                "email": "visitor@example.com",
                "audienceCategory": "student",
            },
            format="json",
        )

    assert response.status_code == 502
    assert response.data["message"]


@override_settings(SCENDEY_WAITLIST_URL=SCENDEY_URL)
def test_invalid_business_payload_is_rejected_before_provider_call():
    with patch("apps.advertising.scendey.requests.post") as send:
        response = APIClient().post(
            ENDPOINT,
            {
                "name": "Brand Owner",
                "email": "owner@example.com",
                "audienceCategory": "business",
            },
            format="json",
        )

    assert response.status_code == 400
    send.assert_not_called()


def _advertiser_campaign():
    from types import SimpleNamespace

    return SimpleNamespace(
        pk="campaign-123",
        owner=SimpleNamespace(
            get_full_name=lambda: "Brand Owner",
            email="owner@example.com",
        ),
        brand_name="Test Brand",
        ad_category="Fashion",
        destination_url="https://brand.example",
    )


@override_settings(SCENDEY_WAITLIST_URL=SCENDEY_URL)
def test_advertiser_sync_does_not_mark_an_existing_email_as_synced():
    from apps.advertising.tasks import sync_scendey_waitlist

    campaign = _advertiser_campaign()
    load_query = Mock()
    load_query.select_related.return_value.first.return_value = campaign
    filter_campaign = Mock(return_value=load_query)
    provider = Mock(ok=True, status_code=200)
    provider.json.return_value = {"ok": True, "existing": True, "delivered": False}

    with patch("apps.advertising.tasks.Campaign.objects.filter", filter_campaign), patch(
        "apps.advertising.tasks.requests.post", return_value=provider
    ) as send:
        outcome = sync_scendey_waitlist.run("campaign-123")

    assert outcome == {"status": "already_registered", "campaign_id": "campaign-123"}
    # Only the initial lookup occurs. In particular, scendey_synced_at is not updated.
    assert filter_campaign.call_count == 1
    payload = send.call_args.kwargs["json"]
    assert payload["role"] == "BRAND"
    assert payload["audienceCategory"] == "BUSINESS"
    assert payload["name"] == "Brand Owner"
    assert payload["consent"] is True


@override_settings(SCENDEY_WAITLIST_URL=SCENDEY_URL)
def test_advertiser_sync_marks_only_a_new_scendey_record_as_synced():
    from apps.advertising.tasks import sync_scendey_waitlist

    campaign = _advertiser_campaign()
    load_query = Mock()
    load_query.select_related.return_value.first.return_value = campaign
    update_query = Mock()
    filter_campaign = Mock(side_effect=[load_query, update_query])
    provider = Mock(ok=True, status_code=201)
    provider.json.return_value = {"ok": True, "existing": False, "delivered": True}

    with patch("apps.advertising.tasks.Campaign.objects.filter", filter_campaign), patch(
        "apps.advertising.tasks.requests.post", return_value=provider
    ):
        outcome = sync_scendey_waitlist.run("campaign-123")

    assert outcome == {"status": "synced", "campaign_id": "campaign-123"}
    filter_campaign.assert_any_call(pk=campaign.pk, scendey_synced_at__isnull=True)
    update_query.update.assert_called_once()
