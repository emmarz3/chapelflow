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
from apps.advertising.models import AdSubscriptionProgram, AdvertisingSettings, Campaign, AdPayment
from apps.notifications.models import Notification, NotificationChannel, NotificationStatus
from apps.advertising.services import FOUNDING_FIRST_MONTH_KOBO, PRICES, activate_payment
from apps.members.models import Member
from apps.organizations.models import Organization, Branch
from apps.finance.services import PaymentProviderError


@pytest.fixture
def users(db):
    owner = User.objects.create_user(email='brand@example.com', password='passphrase-very-long')
    other = User.objects.create_user(email='other@example.com', password='passphrase-very-long')
    admin = User.objects.create_superuser(email='admin@example.com', password='passphrase-very-long')
    organization = Organization.objects.create(name='Test chapel', slug='test-chapel-ads')
    branch = Branch.objects.create(organization=organization, name='Test branch')
    Member.objects.create(user=owner, branch=branch, community='STUDENT', first_name='Brand', last_name='Owner')
    Member.objects.create(user=other, branch=branch, community='GUEST', first_name='Outside', last_name='Owner')
    return owner, other, admin


@pytest.mark.django_db
def test_new_advertisers_pay_their_verified_audience_rate(users):
    student, outsider, _ = users
    programs = {program.audience: program for program in AdSubscriptionProgram.objects.filter(code__in=['campus-brand', 'featured-brand'])}
    assert programs['STUDENT'].monthly_price_ngn == 3500
    assert programs['OUTSIDER'].monthly_price_ngn == 5000
    client = APIClient()
    payload = {
        'brand_name': 'Brand', 'description': 'Campus service', 'ad_category': 'Retail',
        'image_url': 'https://example.com/ad.png', 'destination_url': 'https://example.com',
        'contact_email': 'brand@example.com',
    }
    for owner, allowed, denied, expected in (
        (student, programs['STUDENT'], programs['OUTSIDER'], 3500),
        (outsider, programs['OUTSIDER'], programs['STUDENT'], 5000),
    ):
        client.force_authenticate(owner)
        assert client.post('/api/v1/ads/mine/', {**payload, 'program': str(denied.pk)}, format='json').status_code == 400
        response = client.post('/api/v1/ads/mine/', {**payload, 'program': str(allowed.pk)}, format='json')
        assert response.status_code == 201, response.data
        assert response.data['monthly_price_ngn'] == expected
        assert Campaign.objects.get(pk=response.data['id']).monthly_price_kobo == expected * 100
    assert not AdvertisingSettings.objects.get_or_create(pk=1)[0].founding_offer_enabled


@pytest.mark.django_db
@override_settings(ADS_POLICY_APPROVED=True)
def test_approval_payment_and_placement(users):
    owner, other, admin = users
    program = AdSubscriptionProgram.objects.get(code='campus-brand')
    client = APIClient()
    client.force_authenticate(owner)
    response = client.post('/api/v1/ads/mine/', {
        'brand_name': 'Campus Studio', 'description': 'Portrait sessions',
        'image_url': 'https://example.com/ad.png', 'destination_url': 'https://example.com',
        'contact_email': 'brand@example.com', 'program': str(program.pk), 'ad_category': 'Retail', 'scendey_opt_in': True,
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
    with patch('apps.advertising.views.ads_paystack_request', return_value={
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
@override_settings(ADS_PAYSTACK_SECRET_KEY='test-secret')
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
    with patch('apps.advertising.services.ads_paystack_request', return_value={
        'reference': 'ad-first', 'amount': 1, 'currency': 'NGN', 'status': 'success',
        'subscription': {'subscription_code': 'SUB_test'},
    }):
        assert client.post('/api/v1/ads/paystack/webhook/', data=body, content_type='application/json', HTTP_X_PAYSTACK_SIGNATURE=signature).status_code == 400
    campaign.refresh_from_db()
    assert campaign.status == Campaign.Status.APPROVED


@pytest.mark.django_db
@override_settings(ADS_PAYSTACK_SECRET_KEY='test-secret')
def test_failed_renewal_pauses_ad_even_before_paid_until(users):
    owner, _, _ = users
    campaign = Campaign.objects.create(owner=owner, brand_name='Studio', description='Pictures',
        image_url='https://example.com/ad.jpg', destination_url='https://example.com',
        contact_email=owner.email, plan='CAMPUS', status=Campaign.Status.ACTIVE,
        subscription_code='SUB_test', paid_until=timezone.now() + timedelta(days=20))
    body = json.dumps({'event': 'invoice.payment_failed', 'data': {'subscription': {'subscription_code': 'SUB_test'}}}).encode()
    signature = hmac.new(b'test-secret', body, hashlib.sha512).hexdigest()
    response = APIClient().post('/api/v1/ads/paystack/webhook/', data=body,
        content_type='application/json', HTTP_X_PAYSTACK_SIGNATURE=signature)
    assert response.status_code == 200, response.data
    campaign.refresh_from_db()
    assert campaign.status == Campaign.Status.PAUSED
    assert APIClient().get('/api/v1/ads/placement/events/').data['ad'] is None


@pytest.mark.django_db
@override_settings(ADS_PAYSTACK_SECRET_KEY='test-secret', ADS_POLICY_APPROVED=True)
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
        'apps.advertising.services.ads_paystack_request',
        return_value={'subscription_code':'SUB_founding','email_token':'email-token'},
    ) as paystack:
        activated = activate_payment(campaign, verified)
    assert activated.status == Campaign.Status.ACTIVE
    assert activated.subscription_code == 'SUB_founding'
    assert AdPayment.objects.get(campaign=campaign).amount_kobo == FOUNDING_FIRST_MONTH_KOBO
    assert paystack.call_args.args[0] == '/subscription'
    assert paystack.call_args.kwargs['payload']['plan'] == 'PLN_CAMPUS'


@pytest.mark.django_db
@override_settings(
    ADS_PAYSTACK_SECRET_KEY='test-api-key',
    ADS_PAYSTACK_WEBHOOK_SECRET='whsec_test_signing_secret',
)
def test_webhook_accepts_current_paystack_signature(users):
    owner, _, _ = users
    campaign = Campaign.objects.create(
        owner=owner, brand_name='Signed Studio', description='Pictures',
        image_url='https://example.com/ad.jpg', destination_url='https://example.com',
        contact_email=owner.email, plan='CAMPUS', status=Campaign.Status.ACTIVE,
        subscription_code='SUB_signed', paid_until=timezone.now() + timedelta(days=20),
    )
    body = json.dumps({
        'event': 'invoice.payment_failed',
        'data': {'subscription': {'subscription_code': 'SUB_signed'}},
    }).encode()
    timestamp = int(timezone.now().timestamp())
    digest = hmac.new(
        b'whsec_test_signing_secret',
        str(timestamp).encode('ascii') + b'.' + body,
        hashlib.sha512,
    ).hexdigest()
    header = f't={timestamp},v1=whk_test:{digest}'
    response = APIClient().post(
        '/api/v1/ads/paystack/webhook/', data=body,
        content_type='application/json', HTTP_PAYSTACK_SIGNATURE=header,
    )
    assert response.status_code == 200, response.data
    campaign.refresh_from_db()
    assert campaign.status == Campaign.Status.PAUSED


@pytest.mark.django_db
@override_settings(ADS_POLICY_APPROVED=True)
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
    AdvertisingSettings.objects.create(pk=1, founding_offer_enabled=True)
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


@pytest.mark.django_db
def test_super_admin_can_create_and_manage_subscription_programs(users):
    _, _, admin = users
    client = APIClient()
    client.force_authenticate(admin)
    response = client.post('/api/v1/ads/admin/programs/', {
        'code': 'student-spotlight',
        'name': 'Student Spotlight',
        'description': 'A dedicated student brand placement.',
        'monthly_price_ngn': 5200,
        'base_plan': 'FEATURED',
        'placements': ['home'],
        'is_active': True,
        'sort_order': 5,
    }, format='json')
    assert response.status_code == 201, response.data
    program_id = response.data['id']
    assert response.data['monthly_price_ngn'] == 5200
    assert response.data['placements'] == ['home']

    public_programs = APIClient().get('/api/v1/ads/plans/')
    assert public_programs.status_code == 200
    assert any(item['id'] == program_id for item in public_programs.data['plans'])

    updated = client.patch(f'/api/v1/ads/admin/programs/{program_id}/', {
        'monthly_price_ngn': 6500,
        'placements': ['home', 'events'],
    }, format='json')
    assert updated.status_code == 200, updated.data
    assert updated.data['monthly_price_ngn'] == 6500

    deactivated = client.patch(f'/api/v1/ads/admin/programs/{program_id}/', {
        'is_active': False,
    }, format='json')
    assert deactivated.status_code == 200
    assert deactivated.data['is_active'] is False
    assert all(item['id'] != program_id for item in APIClient().get('/api/v1/ads/plans/').data['plans'])


@pytest.mark.django_db
@override_settings(ADS_PAYSTACK_SECRET_KEY='test-secret', ADS_POLICY_APPROVED=True)
def test_program_price_is_snapshotted_for_existing_campaigns(users):
    owner, _, admin = users
    program = AdSubscriptionProgram.objects.create(
        code='campus-plus', name='Campus Plus', description='Campus placement',
        monthly_price_ngn=4200, base_plan='CAMPUS', placements=['home', 'events'],
    )
    client = APIClient()
    client.force_authenticate(owner)
    first = client.post('/api/v1/ads/mine/', {
        'brand_name': 'First Brand', 'description': 'First campaign',
        'image_url': 'https://example.com/first.png', 'destination_url': 'https://example.com/first',
        'contact_email': owner.email, 'ad_category': 'Retail', 'program': str(program.pk),
    }, format='json')
    assert first.status_code == 201, first.data
    first_campaign = Campaign.objects.get(pk=first.data['id'])
    assert first_campaign.monthly_price_kobo == 420000

    client.force_authenticate(admin)
    changed = client.patch(f'/api/v1/ads/admin/programs/{program.pk}/', {
        'monthly_price_ngn': 6100,
    }, format='json')
    assert changed.status_code == 200, changed.data
    first_campaign.refresh_from_db()
    assert first_campaign.monthly_price_kobo == 420000

    client.force_authenticate(owner)
    second = client.post('/api/v1/ads/mine/', {
        'brand_name': 'Second Brand', 'description': 'Second campaign',
        'image_url': 'https://example.com/second.png', 'destination_url': 'https://example.com/second',
        'contact_email': owner.email, 'ad_category': 'Retail', 'program': str(program.pk),
    }, format='json')
    assert second.status_code == 201, second.data
    second_campaign = Campaign.objects.get(pk=second.data['id'])
    assert second_campaign.monthly_price_kobo == 610000
    assert first_campaign.monthly_price_kobo != second_campaign.monthly_price_kobo


@pytest.mark.django_db
@override_settings(ADS_PAYSTACK_SECRET_KEY='test-secret', ADS_POLICY_APPROVED=True)
def test_ad_application_notifies_super_admin_and_checkout_waits_for_approval(users):
    owner, _, admin = users
    from apps.communications.models import CommunicationPreference

    preference, _ = CommunicationPreference.objects.get_or_create(user=admin)
    preference.master_enabled = False
    preference.in_app_enabled = False
    preference.admin_alerts_enabled = False
    preference.save(update_fields=['master_enabled', 'in_app_enabled', 'admin_alerts_enabled'])
    program = AdSubscriptionProgram.objects.create(
        code='featured-campus', name='Featured Campus', description='Featured campus rotation',
        monthly_price_ngn=5800, base_plan='FEATURED', placements=['home', 'events'],
    )
    client = APIClient()
    client.force_authenticate(owner)
    submitted = client.post('/api/v1/ads/mine/', {
        'brand_name': 'Campus Creator', 'description': 'Student creative work',
        'image_url': 'https://example.com/creative.png', 'destination_url': 'https://example.com/creator',
        'contact_email': owner.email, 'ad_category': 'Creative services', 'program': str(program.pk),
    }, format='json')
    assert submitted.status_code == 201, submitted.data
    campaign = Campaign.objects.get(pk=submitted.data['id'])
    assert campaign.status == Campaign.Status.PENDING
    assert campaign.monthly_price_kobo == 580000

    admin_notice = Notification.objects.get(
        recipient=admin,
        channel=NotificationChannel.IN_APP,
        idempotency_key=f'ads:review:{campaign.pk}:1:{admin.pk}',
    )
    assert admin_notice.status != NotificationStatus.SKIPPED
    assert admin_notice.read_at is None
    assert admin_notice.href == f'/app/admin/advertising?campaign={campaign.pk}'

    # A pending creative cannot initialize Paystack or record a reference.
    with patch('apps.advertising.views.ads_paystack_request') as paystack:
        blocked = client.post(f'/api/v1/ads/{campaign.pk}/checkout/')
    assert blocked.status_code == 400
    paystack.assert_not_called()
    campaign.refresh_from_db()
    assert campaign.reference is None

    client.force_authenticate(admin)
    approved = client.post(
        f'/api/v1/ads/admin/{campaign.pk}/review/',
        {'action': 'approve'},
        format='json',
    )
    assert approved.status_code == 200, approved.data
    assert Notification.objects.filter(
        recipient=owner, channel=NotificationChannel.IN_APP,
        title='Your advertisement was approved',
    ).exists()

    client.force_authenticate(owner)
    def initialize_checkout(*args, **kwargs):
        reference = kwargs['payload']['reference']
        return {
            'reference': reference,
            'authorization_url': f'https://checkout.paystack.com/{reference}',
        }

    with patch('apps.advertising.views.plan_code', return_value='PLN_FEATURED_CUSTOM') as create_plan, patch(
        'apps.advertising.views.ads_paystack_request',
        side_effect=initialize_checkout,
    ) as paystack:
        checkout = client.post(f'/api/v1/ads/{campaign.pk}/checkout/')
    assert checkout.status_code == 200, checkout.data
    assert checkout.data['renewal_amount_ngn'] == 5800
    create_plan.assert_called_once()
    assert create_plan.call_args.kwargs['program'].pk == program.pk
    assert create_plan.call_args.kwargs['amount_kobo'] == 580000
    checkout_payload = paystack.call_args.kwargs['payload']
    # New approvals pay the stated monthly rate; existing awarded offers retain their discount.
    assert checkout_payload['amount'] == 580000
    assert checkout_payload['metadata']['renewal_amount_kobo'] == 580000
    assert checkout_payload['metadata']['billing_mode'] == 'MONTHLY_SUBSCRIPTION'
    assert checkout_payload['plan'] == 'PLN_FEATURED_CUSTOM'
