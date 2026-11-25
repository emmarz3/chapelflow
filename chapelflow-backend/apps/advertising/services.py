import hashlib
import hmac
import json
import logging
from urllib.parse import quote

from django.conf import settings
from django.db import transaction
from django.db.models import F
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from apps.finance.services import PaymentProviderError, _paystack_request
from .models import AdPayment, Campaign, PaystackPlan

PRICES = {'CAMPUS': 300000, 'FEATURED': 750000}
logger = logging.getLogger(__name__)


def queue_scendey_sync(campaign_id):
    from .tasks import sync_scendey_waitlist
    try:
        sync_scendey_waitlist.delay(str(campaign_id))
    except Exception:
        logger.exception('scendey_sync_queue_unavailable')


def plan_code(plan):
    with transaction.atomic():
        saved = PaystackPlan.objects.select_for_update().filter(plan=plan).first()
        if saved and saved.amount_kobo == PRICES[plan]:
            return saved.code
        if saved:
            raise PaymentProviderError('The advertising plan needs administrator review before checkout.')
        data = _paystack_request('/plan', method='POST', payload={
            'name': f'ChapelFlow {Campaign.Plan(plan).label}', 'amount': PRICES[plan],
            'interval': 'monthly', 'currency': 'NGN',
        })
        code = data.get('plan_code')
        if not code:
            raise PaymentProviderError('Paystack could not create the monthly plan.')
        PaystackPlan.objects.create(plan=plan, code=code, amount_kobo=PRICES[plan])
        return code


def activate_payment(campaign, data):
    reference = str(data.get('reference') or '')
    amount = data.get('amount')
    if not reference or amount != PRICES[campaign.plan] or data.get('currency') != 'NGN' or data.get('status') != 'success':
        raise PaymentProviderError('Payment details did not match the advertising plan.')
    subscription = data.get('subscription') or {}
    code = subscription.get('subscription_code') if isinstance(subscription, dict) else None
    if not code and not campaign.subscription_code:
        raise PaymentProviderError('Paystack has not confirmed the monthly subscription yet. Try verification again shortly.')
    if code and campaign.subscription_code and code != campaign.subscription_code:
        raise PaymentProviderError('Subscription does not match this campaign.')
    with transaction.atomic():
        campaign = Campaign.objects.select_for_update().get(pk=campaign.pk)
        if campaign.reference != reference and campaign.subscription_code != code:
            raise PaymentProviderError('Payment does not belong to this campaign.')
        if AdPayment.objects.filter(reference=reference).exists():
            return campaign
        if campaign.status not in {Campaign.Status.APPROVED, Campaign.Status.ACTIVE, Campaign.Status.PAUSED}:
            raise PaymentProviderError('This advertisement is not approved for payment.')
        paid_at = parse_datetime(str(data.get('paid_at') or '')) or timezone.now()
        if timezone.is_naive(paid_at):
            paid_at = timezone.make_aware(paid_at)
        AdPayment.objects.create(reference=reference, campaign=campaign, amount_kobo=amount, paid_at=paid_at)
        # Use a bounded paid period even if Paystack's next invoice has not arrived yet.
        from dateutil.relativedelta import relativedelta
        campaign.paid_until = max(campaign.paid_until or paid_at, paid_at) + relativedelta(months=1)
        if code:
            campaign.subscription_code = code
            campaign.subscription_email_token = subscription.get('email_token') or campaign.subscription_email_token
        if campaign.status == Campaign.Status.APPROVED:
            campaign.status = Campaign.Status.ACTIVE
        campaign.save()
        if campaign.scendey_opt_in and not campaign.scendey_synced_at:
            transaction.on_commit(lambda: queue_scendey_sync(campaign.id))
    return campaign


def process_ad_webhook(request):
    secret = settings.PAYSTACK_SECRET_KEY
    signature = request.headers.get('X-Paystack-Signature', '')
    if not secret or not hmac.compare_digest(signature, hmac.new(secret.encode(), request.body, hashlib.sha512).hexdigest()):
        raise PaymentProviderError('Invalid Paystack signature.')
    payload = json.loads(request.body)
    event, data = payload.get('event'), payload.get('data') or {}
    if not isinstance(data, dict):
        return False
    subscription = data.get('subscription') or {}
    sub_code = data.get('subscription_code') or (subscription.get('subscription_code') if isinstance(subscription, dict) else None)
    campaign = Campaign.objects.filter(subscription_code=sub_code).first() if sub_code else None
    if not campaign and event == 'charge.success':
        campaign = Campaign.objects.filter(reference=data.get('reference')).first()
    if not campaign:
        if event in {'subscription.create', 'subscription.disable', 'subscription.not_renew', 'invoice.payment_failed', 'invoice.update', 'invoice.create'}:
            return True
        return False
    if event == 'subscription.create':
        campaign.subscription_code = data.get('subscription_code') or campaign.subscription_code
        campaign.subscription_email_token = data.get('email_token') or campaign.subscription_email_token
        campaign.save(update_fields=['subscription_code', 'subscription_email_token'])
    elif event == 'charge.success':
        # Verify independently; never trust an event body to grant advertising time.
        verified = _paystack_request(f"/transaction/verify/{quote(str(data.get('reference')), safe='')}")
        activate_payment(campaign, verified)
    elif event in {'subscription.disable', 'invoice.payment_failed'}:
        campaign.status = Campaign.Status.PAUSED
        campaign.save(update_fields=['status'])
    elif event == 'subscription.not_renew':
        campaign.cancel_at_period_end = True
        campaign.save(update_fields=['cancel_at_period_end'])
    return True
