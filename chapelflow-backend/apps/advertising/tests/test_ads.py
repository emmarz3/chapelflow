import hashlib
import hmac
import json
from datetime import timedelta
from unittest.mock import patch

import pytest
from django.test import override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.advertising.models import Campaign, AdPayment
from apps.advertising.services import PRICES


@pytest.fixture
def users(db):
    owner = User.objects.create_user(email='brand@example.com', password='passphrase-very-long')
    other = User.objects.create_user(email='other@example.com', password='passphrase-very-long')
    admin = User.objects.create_superuser(email='admin@example.com', password='passphrase-very-long')
    return owner, other, admin


@pytest.mark.django_db
def test_approval_payment_and_placement(users):
    owner, other, admin = users
    client = APIClient()
    client.force_authenticate(owner)
    response = client.post('/api/v1/ads/mine/', {
        'brand_name': 'Campus Studio', 'description': 'Portrait sessions',
        'image_url': 'https://example.com/ad.png', 'destination_url': 'https://example.com',
        'contact_email': 'brand@example.com', 'plan': 'CAMPUS', 'scendey_opt_in': True,
    }, format='json')
    assert response.status_code == 201, response.data
    campaign = Campaign.objects.get(pk=response.data['id'])
    assert campaign.scendey_consented_at
    assert client.post(f'/api/v1/ads/{campaign.pk}/checkout/').status_code == 400
    client.force_authenticate(other)
    assert client.post(f'/api/v1/ads/{campaign.pk}/verify/').status_code == 404
    client.force_authenticate(admin)
    assert client.post(f'/api/v1/ads/admin/{campaign.pk}/review/', {'action': 'approve'}).status_code == 200
    campaign.refresh_from_db()
    campaign.reference = 'ad-first'
    campaign.save()
    client.force_authenticate(owner)
    with patch('apps.advertising.views._paystack_request', return_value={
        'reference': 'ad-first', 'amount': PRICES['CAMPUS'], 'currency': 'NGN',
        'status': 'success', 'subscription': {'subscription_code': 'SUB_test', 'email_token': 'token'},
    }):
        response = client.post(f'/api/v1/ads/{campaign.pk}/verify/')
        assert response.status_code == 200, response.data
        client.post(f'/api/v1/ads/{campaign.pk}/verify/')
    assert AdPayment.objects.filter(campaign=campaign).count() == 1
    client.force_authenticate(user=None)
    assert client.get('/api/v1/ads/placement/home/').data['ad']['brand_name'] == 'Campus Studio'
    client.force_authenticate(admin)
    assert client.post(f'/api/v1/ads/admin/{campaign.pk}/review/', {'action': 'pause', 'note': 'Review'}).status_code == 200
    client.force_authenticate(user=None)
    assert client.get('/api/v1/ads/placement/home/').data['ad'] is None


@pytest.mark.django_db
@override_settings(PAYSTACK_SECRET_KEY='test-secret')
def test_webhook_rejects_unsigned_or_mismatched_payment(users):
    owner, _, admin = users
    campaign = Campaign.objects.create(owner=owner, brand_name='Studio', description='Pictures',
        image_url='https://example.com/ad.jpg', destination_url='https://example.com',
        contact_email=owner.email, plan='CAMPUS', status=Campaign.Status.APPROVED, reference='ad-first')
    client = APIClient()
    data = {'event': 'charge.success', 'data': {'reference': 'ad-first'}}
    body = json.dumps(data).encode()
    assert client.post('/api/v1/ads/paystack/webhook/', data=body, content_type='application/json').status_code == 400
    signature = hmac.new(b'test-secret', body, hashlib.sha512).hexdigest()
    with patch('apps.advertising.services._paystack_request', return_value={
        'reference': 'ad-first', 'amount': 1, 'currency': 'NGN', 'status': 'success',
        'subscription': {'subscription_code': 'SUB_test'},
    }):
        assert client.post('/api/v1/ads/paystack/webhook/', data=body, content_type='application/json', HTTP_X_PAYSTACK_SIGNATURE=signature).status_code == 400
    campaign.refresh_from_db()
    assert campaign.status == Campaign.Status.APPROVED


@pytest.mark.django_db
@override_settings(PAYSTACK_SECRET_KEY='test-secret')
def test_failed_renewal_pauses_ad_even_before_paid_until(users):
    owner, _, _ = users
    campaign = Campaign.objects.create(owner=owner, brand_name='Studio', description='Pictures',
        image_url='https://example.com/ad.jpg', destination_url='https://example.com',
        contact_email=owner.email, plan='CAMPUS', status=Campaign.Status.ACTIVE,
        subscription_code='SUB_test', paid_until=timezone.now() + timedelta(days=20))
    body = json.dumps({'event': 'invoice.payment_failed', 'data': {'subscription': {'subscription_code': 'SUB_test'}}}).encode()
    signature = hmac.new(b'test-secret', body, hashlib.sha512).hexdigest()
    response = APIClient().post('/api/v1/payments/webhook/paystack/', data=body,
        content_type='application/json', HTTP_X_PAYSTACK_SIGNATURE=signature)
    assert response.status_code == 200, response.data
    campaign.refresh_from_db()
    assert campaign.status == Campaign.Status.PAUSED
    assert APIClient().get('/api/v1/ads/placement/events/').data['ad'] is None
