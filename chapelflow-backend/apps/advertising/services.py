import hashlib
import hmac
import json
import logging
from urllib.parse import quote

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import F
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from apps.finance.services import PaymentProviderError, _paystack_request
from apps.notifications.models import Notification, NotificationCategory, NotificationChannel, NotificationStatus
from common.constants.roles import Roles
from .models import AdPayment, AdSubscriptionProgram, Campaign, PaystackPlan

PRICES = {'CAMPUS': 300000, 'FEATURED': 750000}
FOUNDING_FIRST_MONTH_KOBO = 200000
FOUNDING_OFFER_LIMIT = 10
logger = logging.getLogger(__name__)


def campaign_monthly_price_kobo(campaign):
    """Return the price snapshot agreed when the campaign application was made."""
    if campaign.monthly_price_kobo:
        return campaign.monthly_price_kobo
    if campaign.program_id:
        return campaign.program.monthly_price_ngn * 100
    return PRICES[campaign.plan]


def notify_in_app(*, recipient, title, body, href, idempotency_key):
    """Persist a high-priority in-app notice without an external provider dependency."""
    now = timezone.now()
    notification, created = Notification.objects.get_or_create(
        idempotency_key=idempotency_key,
        defaults={
            'recipient': recipient,
            'channel': NotificationChannel.IN_APP,
            'category': NotificationCategory.ADMIN_ALERT,
            'title': title[:255],
            'body': body,
            'href': href,
            'status': NotificationStatus.DELIVERED,
            'provider_response': {'status': 'delivered', 'provider': 'in_app'},
            'sent_at': now,
        },
    )
    return notification, created


def notify_super_admins_about_campaign(campaign):
    """Notify every active Super Admin when an ad awaits review, including resubmissions."""
    User = get_user_model()
    program_name = campaign.program.name if campaign.program_id else campaign.get_plan_display()
    community = 'staff' if campaign.applicant_community == 'STAFF' else 'student'
    title = 'Advertisement awaiting review'
    body = (
        f'{campaign.brand_name} submitted a {community} advertisement and selected '
        f'{program_name}. Review its category, creative and destination before payment is enabled.'
    )
    recipients = User.objects.filter(role=Roles.SUPER_ADMIN, is_active=True)
    created = 0
    for admin in recipients.iterator():
        _, was_created = notify_in_app(
            recipient=admin,
            title=title,
            body=body,
            href=f'/app/admin/advertising?campaign={campaign.pk}',
            idempotency_key=f'ads:review:{campaign.pk}:{campaign.submission_revision}:{admin.pk}',
        )
        created += int(was_created)
    return created


def notify_advertiser_of_review(campaign):
    decision = campaign.decisions.order_by('-created_at').first()
    action = decision.action if decision else 'updated'
    title_by_action = {
        'approve': 'Your advertisement was approved',
        'reject': 'Your advertisement was not approved',
        'changes': 'Changes requested for your advertisement',
    }
    body_by_action = {
        'approve': 'Your advertisement is approved. Return to Ads & subscriptions to continue to secure payment.',
        'reject': campaign.review_note or 'Your advertisement was not approved by the Chapel.',
        'changes': campaign.review_note or 'Please update your advertisement and resubmit it for review.',
    }
    notify_in_app(
        recipient=campaign.owner,
        title=title_by_action.get(action, 'Your advertising application was updated'),
        body=body_by_action.get(action, 'Your advertising application status has changed.'),
        href='/app/advertise',
        idempotency_key=f'ads:decision:{campaign.pk}:{campaign.reviewed_at.isoformat() if campaign.reviewed_at else campaign.updated_at.isoformat()}',
    )


def queue_scendey_sync(campaign_id):
    from .tasks import sync_scendey_waitlist
    try:
        sync_scendey_waitlist.delay(str(campaign_id))
    except Exception:
        logger.exception('scendey_sync_queue_unavailable')


def plan_code(plan, *, program=None, amount_kobo=None):
    """Get or create the Paystack monthly plan for a legacy plan or a price version."""
    if program is not None:
        amount = amount_kobo or program.monthly_price_ngn * 100
        with transaction.atomic():
            locked_program = AdSubscriptionProgram.objects.select_for_update().get(pk=program.pk)
            saved = PaystackPlan.objects.select_for_update().filter(
                program=locked_program, amount_kobo=amount,
            ).first()
            if saved:
                return saved.code
            data = _paystack_request('/plan', method='POST', payload={
                'name': f'ChapelFlow {locked_program.name} - NGN {amount // 100}',
                'amount': amount,
                'interval': 'monthly',
                'currency': 'NGN',
            })
            code = data.get('plan_code')
            if not code:
                raise PaymentProviderError('Paystack could not create the monthly plan.')
            PaystackPlan.objects.create(program=locked_program, code=code, amount_kobo=amount)
            return code

    amount = PRICES[plan]
    with transaction.atomic():
        saved = PaystackPlan.objects.select_for_update().filter(plan=plan, program__isnull=True).first()
        if saved and saved.amount_kobo == amount:
            return saved.code
        if saved:
            raise PaymentProviderError('The advertising plan needs administrator review before checkout.')
        data = _paystack_request('/plan', method='POST', payload={
            'name': f'ChapelFlow {Campaign.Plan(plan).label}', 'amount': amount,
            'interval': 'monthly', 'currency': 'NGN',
        })
        code = data.get('plan_code')
        if not code:
            raise PaymentProviderError('Paystack could not create the monthly plan.')
        PaystackPlan.objects.create(plan=plan, code=code, amount_kobo=amount)
        return code


def activate_payment(campaign, data):
    reference = str(data.get('reference') or '')
    subscription = data.get('subscription') or {}
    if not isinstance(subscription, dict):
        subscription = {}
    code = data.get('subscription_code') or subscription.get('subscription_code') or campaign.subscription_code
    amount = data.get('amount')
    if not reference or data.get('currency') != 'NGN' or data.get('status') != 'success':
        raise PaymentProviderError('Payment details did not match the advertising plan.')
    with transaction.atomic():
        campaign = Campaign.objects.select_for_update(of=('self',)).select_related('program', 'owner').get(pk=campaign.pk)
        if AdPayment.objects.filter(reference=reference).exists():
            return campaign
        if campaign.status not in {Campaign.Status.APPROVED, Campaign.Status.ACTIVE, Campaign.Status.PAUSED}:
            raise PaymentProviderError('This advertisement is not approved for payment.')
        founding_first_payment = bool(campaign.founding_offer_awarded and not AdPayment.objects.filter(campaign=campaign).exists())
        recurring_amount = campaign_monthly_price_kobo(campaign)
        expected_amount = FOUNDING_FIRST_MONTH_KOBO if founding_first_payment else recurring_amount
        if amount != expected_amount:
            raise PaymentProviderError('The verified amount does not match the approved advertising offer.')
        if campaign.reference != reference and campaign.subscription_code != code:
            raise PaymentProviderError('Payment does not belong to this campaign.')
        paid_at = parse_datetime(str(data.get('paid_at') or '')) or timezone.now()
        if timezone.is_naive(paid_at):
            paid_at = timezone.make_aware(paid_at)
        if founding_first_payment and not code:
            customer, authorization = data.get('customer') or {}, data.get('authorization') or {}
            customer_code = customer.get('customer_code') if isinstance(customer, dict) else None
            authorization_code = authorization.get('authorization_code') if isinstance(authorization, dict) else None
            reusable = authorization.get('reusable') if isinstance(authorization, dict) else False
            if not customer_code or not authorization_code or not reusable:
                raise PaymentProviderError('Founding payment verified, but no reusable card authorization was returned. Contact the chapel office before another payment attempt.')
            recurring_code = plan_code(
                campaign.plan, program=campaign.program, amount_kobo=recurring_amount,
            )
            from dateutil.relativedelta import relativedelta
            subscription_data = _paystack_request('/subscription', method='POST', payload={
                'customer': customer_code, 'plan': recurring_code, 'authorization': authorization_code,
                'start_date': (paid_at + relativedelta(months=1)).isoformat(),
            })
            code = subscription_data.get('subscription_code')
            if not code:
                raise PaymentProviderError('Paystack did not confirm the regular monthly renewal subscription.')
            subscription = subscription_data
        if not code:
            raise PaymentProviderError('Paystack has not confirmed the monthly subscription yet. Try verification again shortly.')
        if campaign.subscription_code and code != campaign.subscription_code:
            raise PaymentProviderError('Subscription does not match this campaign.')
        AdPayment.objects.create(reference=reference, campaign=campaign, amount_kobo=amount, paid_at=paid_at)
        from dateutil.relativedelta import relativedelta
        campaign.paid_until = max(campaign.paid_until or paid_at, paid_at) + relativedelta(months=1)
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
    elif event == 'invoice.payment_failed':
        campaign.status = Campaign.Status.PAUSED
        campaign.save(update_fields=['status'])
    elif event in {'subscription.disable', 'subscription.not_renew'}:
        campaign.cancel_at_period_end = True
        if not campaign.paid_until or campaign.paid_until <= timezone.now():
            campaign.status = Campaign.Status.PAUSED
        campaign.save(update_fields=['status', 'cancel_at_period_end'])
    return True
