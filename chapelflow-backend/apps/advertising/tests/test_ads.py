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
from apps.advertising.models import AdvertisingSettings, Campaign, AdPayment
from apps.advertising.services import FOUNDING_FIRST_MONTH_KOBO, PRICES, activate_payment
from apps.finance.services import PaymentProviderError


@pytest.fixture
def users(db):
    owner = User.objects.create_user(email='brand@example.com', password='passphrase-very-long')
    other = User.objects.create_user(email='other@example.com', password='passphrase-very-long')
    admin = User.objects.create_superuser(email='admin@example.com', password='passphrase-very-long')
    return owner, other, admin


@pytest.mark.django_db
@override_settings(ADVERTISING_POLICY_APPROVED=True)
def test_approval_payment_and_placement(users):
    owner, other, admin = users
    client = APIClient()
    client.force_authenticate(owner)
    response = client.post('/api/v1/ads/mine/', {
        'brand_name': 'Campus Studio', 'description': 'Portrait sessions',
        'image_url': 'https://example.com/ad.png', 'destination_url': 'https://example.com',
        'contact_email': 'brand@example.com', 'plan': 'CAMPUS', 'ad_category': 'Retail', 'scendey_opt_in': True,
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
    campaign.founding_offer_awarded = False
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


@pytest.mark.django_db
@override_settings(PAYSTACK_SECRET_KEY='test-secret', ADVERTISING_POLICY_APPROVED=True)
def test_founding_student_offer_charges_discount_then_schedules_full_price_subscription(users):
    owner, _, _ = users
    campaign = Campaign.objects.create(owner=owner, brand_name='Student Studio', description='Campus portraits',
        ad_category='Retail', image_url='https://example.com/ad.jpg', destination_url='https://example.com',
        contact_email=owner.email, plan='CAMPUS', applicant_community='STUDENT', founding_offer_awarded=True,
        status=Campaign.Status.APPROVED, reference='ad-founding')
    verified = {'reference':'ad-founding','amount':FOUNDING_FIRST_MONTH_KOBO,'currency':'NGN','status':'success',
        'paid_at':timezone.now().isoformat(),'customer':{'customer_code':'CUS_test'},
        'authorization':{'authorization_code':'AUTH_test','reusable':True}}
    with patch('apps.advertising.services.plan_code', return_value='PLN_CAMPUS'), patch(
        'apps.advertising.services._paystack_request',
        return_value={'subscription_code':'SUB_founding','email_token':'email-token'},
    ) as paystack:
        activated = activate_payment(campaign, verified)
    assert activated.status == Campaign.Status.ACTIVE
    assert activated.subscription_code == 'SUB_founding'
    assert AdPayment.objects.get(campaign=campaign).amount_kobo == FOUNDING_FIRST_MONTH_KOBO
    assert paystack.call_args.args[0] == '/subscription'
    assert paystack.call_args.kwargs['payload']['plan'] == 'PLN_CAMPUS'


@pytest.mark.django_db
@override_settings(ADVERTISING_POLICY_APPROVED=True)
def test_emergency_pause_hides_placements_until_resumed(users):
    owner, _, admin = users
    Campaign.objects.create(owner=owner, brand_name='Studio', description='Pictures', ad_category='Services',
        image_url='https://example.com/ad.jpg', destination_url='https://example.com', contact_email=owner.email,
        plan='CAMPUS', status=Campaign.Status.ACTIVE, paid_until=timezone.now()+timedelta(days=10))
    AdvertisingSettings.objects.create(pk=1, emergency_paused=True, emergency_pause_reason='Chapel review')
    client=APIClient()
    assert client.get('/api/v1/ads/placement/home/').data['ad'] is None
    client.force_authenticate(admin)
    response=client.post('/api/v1/ads/admin/settings/', {'action':'resume_all'}, format='json')
    assert response.status_code == 200
    client.force_authenticate(user=None)
    assert client.get('/api/v1/ads/placement/home/').data['ad']['brand_name'] == 'Studio'


@pytest.mark.django_db
def test_first_ten_approved_student_campaigns_receive_founding_offer(users):
    owner, _, admin = users
    client=APIClient(); client.force_authenticate(admin); awarded=[]
    for index in range(11):
        campaign=Campaign.objects.create(owner=owner,brand_name=f'Student brand {index}',description='Campus service',
            ad_category='Retail',image_url='https://example.com/ad.jpg',destination_url='https://example.com',
            contact_email=owner.email,plan='CAMPUS',applicant_community='STUDENT')
        response=client.post(f'/api/v1/ads/admin/{campaign.pk}/review/',{'action':'approve'},format='json')
        assert response.status_code == 200, response.data
        campaign.refresh_from_db(); awarded.append(campaign.founding_offer_awarded)
    assert awarded == [True]*10+[False]


@pytest.mark.django_db
def test_revoke_is_an_admin_decision(users):
    owner, _, admin = users
    campaign=Campaign.objects.create(owner=owner,brand_name='Studio',description='Pictures',ad_category='Services',
        image_url='https://example.com/ad.jpg',destination_url='https://example.com',contact_email=owner.email,
        plan='CAMPUS',status=Campaign.Status.ACTIVE,paid_until=timezone.now()+timedelta(days=15))
    client=APIClient(); client.force_authenticate(admin)
    response=client.post(f'/api/v1/ads/admin/{campaign.pk}/review/',{'action':'revoke','note':'Policy violation'},format='json')
    assert response.status_code == 200
    campaign.refresh_from_db()
    assert campaign.status == Campaign.Status.REVOKED


@pytest.mark.django_db
def test_admin_revoke_cancels_paystack_subscription_before_revoke(users):
    owner, _, admin = users
    campaign = Campaign.objects.create(
        owner=owner, brand_name='Studio', description='Pictures', ad_category='Services',
        image_url='https://example.com/ad.jpg', destination_url='https://example.com',
        contact_email=owner.email, plan='CAMPUS', status=Campaign.Status.ACTIVE,
        subscription_code='SUB_revoke', subscription_email_token='email-token',
        paid_until=timezone.now() + timedelta(days=15),
    )
    client = APIClient()
    client.force_authenticate(admin)
    with patch('apps.advertising.views._disable_paystack_subscription', return_value='email-token') as disable:
        response = client.post(
            f'/api/v1/ads/admin/{campaign.pk}/review/',
            {'action': 'revoke', 'note': 'Policy violation'},
            format='json',
        )
    assert response.status_code == 200, response.data
    disable.assert_called_once()
    campaign.refresh_from_db()
    assert campaign.status == Campaign.Status.REVOKED
    assert campaign.cancel_at_period_end is True


@pytest.mark.django_db
def test_revoke_is_blocked_when_paystack_cancellation_fails(users):
    owner, _, admin = users
    campaign = Campaign.objects.create(
        owner=owner, brand_name='Studio', description='Pictures', ad_category='Services',
        image_url='https://example.com/ad.jpg', destination_url='https://example.com',
        contact_email=owner.email, plan='CAMPUS', status=Campaign.Status.ACTIVE,
        subscription_code='SUB_revoke', subscription_email_token='email-token',
        paid_until=timezone.now() + timedelta(days=15),
    )
    client = APIClient()
    client.force_authenticate(admin)
    with patch('apps.advertising.views._disable_paystack_subscription', side_effect=PaymentProviderError('Paystack offline')):
        response = client.post(
            f'/api/v1/ads/admin/{campaign.pk}/review/',
            {'action': 'revoke', 'note': 'Policy violation'},
            format='json',
        )
    assert response.status_code == 502
    campaign.refresh_from_db()
    assert campaign.status == Campaign.Status.ACTIVE
    assert campaign.cancel_at_period_end is False
