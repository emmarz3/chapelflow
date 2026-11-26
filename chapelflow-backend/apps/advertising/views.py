import uuid
import json
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError
from urllib.parse import quote

from django.conf import settings
from django.core.cache import cache
from django.db import transaction
from django.db.models import F
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from rest_framework import serializers, status
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.audit.services import write_audit_log
from apps.finance.services import PaymentProviderError
from apps.members.models import CommunityClassification, Member
from common.permissions.rbac import IsSuperAdmin
from apps.uploads.storage import get_storage_service, generate_storage_filename
from .models import AdDecision, AdSubscriptionProgram, AdvertisingSettings, Campaign
from .serializers import CampaignSerializer, SubscriptionProgramSerializer, CONSENT
from .services import (
    FOUNDING_FIRST_MONTH_KOBO, FOUNDING_OFFER_LIMIT, PRICES,
    activate_payment, ads_paystack_request, campaign_monthly_price_kobo, notify_advertiser_of_review,
    notify_super_admins_about_campaign, plan_code, process_ad_webhook,
)


def _ads_settings():
    return AdvertisingSettings.objects.get_or_create(pk=1)[0]


def _ads_display_allowed():
    if not getattr(settings, 'ADS_POLICY_APPROVED', False):
        return False
    return not AdvertisingSettings.objects.filter(pk=1, emergency_paused=True).exists()


class PlansView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request):
        config = AdvertisingSettings.objects.filter(pk=1).first()
        awarded = Campaign.objects.filter(founding_offer_awarded=True).count()
        enabled = config.founding_offer_enabled if config else False
        remaining = max(0, FOUNDING_OFFER_LIMIT - awarded) if enabled else 0
        approved = bool(getattr(settings, 'ADS_POLICY_APPROVED', False))
        checkout = bool(settings.ADS_PAYSTACK_SECRET_KEY and approved and not (config and config.emergency_paused))
        programs = AdSubscriptionProgram.objects.filter(is_active=True).order_by('sort_order', 'name')
        return Response({
            'plans': [{
                'id': str(program.pk), 'code': program.code, 'name': program.name,
                'description': program.description, 'price_ngn': program.monthly_price_ngn, 'audience': program.audience,
                'base_plan': program.base_plan, 'placements': program.placements, 'interval': 'monthly',
            } for program in programs],
            'consent_text': CONSENT, 'checkout_available': checkout,
            'checkout_reason': '' if checkout else 'Checkout opens after Super Admin advertising policy approval and Super Admin Paystack configuration.',
            'founding_offer': {'enabled': bool(remaining), 'remaining': remaining, 'limit': FOUNDING_OFFER_LIMIT,
                'first_month_price_ngn': FOUNDING_FIRST_MONTH_KOBO // 100,
                'renewal_note': 'First month ₦2,000, then the selected program renews at its regular monthly price.'},
        })

class MyCampaignsView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_scope = 'ads_application'

    def get(self, request):
        campaigns = Campaign.objects.filter(owner=request.user).select_related('program').prefetch_related('payments')
        return Response(CampaignSerializer(campaigns, many=True).data)

    def post(self, request):
        serializer = CampaignSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        campaign = serializer.save()
        write_audit_log('CREATE', 'AdCampaign', campaign.id, user=request.user)
        notify_super_admins_about_campaign(
            Campaign.objects.select_related('owner', 'program').get(pk=campaign.pk)
        )
        return Response(CampaignSerializer(campaign).data, status=201)


class MyCampaignDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request, pk):
        campaign = get_object_or_404(Campaign, pk=pk, owner=request.user)
        if campaign.status != Campaign.Status.CHANGES:
            raise serializers.ValidationError('Changes can only be submitted when requested by the reviewer.')
        serializer = CampaignSerializer(campaign, data=request.data, partial=True, context={'request': request})
        serializer.is_valid(raise_exception=True)
        campaign = serializer.save(
            status=Campaign.Status.PENDING,
            review_note='',
            submission_revision=campaign.submission_revision + 1,
        )
        write_audit_log('UPDATE', 'AdCampaign', campaign.id, {'decision': 'resubmitted'}, user=request.user)
        notify_super_admins_about_campaign(
            Campaign.objects.select_related('owner', 'program').get(pk=campaign.pk)
        )
        return Response(CampaignSerializer(campaign).data)


class AdminCampaignsView(APIView):
    permission_classes = [IsSuperAdmin]
    def get(self, request):
        campaigns = Campaign.objects.select_related('owner', 'reviewed_by', 'program').prefetch_related('payments', 'decisions__actor').all()[:200]
        results = []
        for campaign in campaigns:
            history = [{'action': d.action, 'note': d.note, 'actor_email': d.actor.email if d.actor else '', 'created_at': d.created_at}
                for d in campaign.decisions.all().order_by('-created_at')[:30]]
            results.append(dict(CampaignSerializer(campaign).data, owner_email=campaign.owner.email or '',
                reviewed_by_email=campaign.reviewed_by.email if campaign.reviewed_by else '',
                decision_history=history, placements=campaign.placements_snapshot or (campaign.program.placements if campaign.program_id else ['home', 'events'])))
        return Response(results)


def _disable_paystack_subscription(campaign):
    """Stop future billing using Paystack's server-side subscription code and email token."""
    if not campaign.subscription_code:
        return campaign.subscription_email_token
    token = campaign.subscription_email_token
    if not token:
        subscription = ads_paystack_request(f"/subscription/{quote(campaign.subscription_code, safe='')}")
        token = subscription.get('email_token') or ''
    if not token:
        raise PaymentProviderError('Paystack did not provide the subscription cancellation token.')

    request_body = json.dumps({'code': campaign.subscription_code, 'token': token}).encode()
    provider_request = Request(
        'https://api.paystack.co/subscription/disable',
        data=request_body,
        headers={
            'Authorization': f'Bearer {settings.ADS_PAYSTACK_SECRET_KEY}',
            'Content-Type': 'application/json',
            'Accept': 'application/json',
        },
        method='POST',
    )
    try:
        with urlopen(provider_request, timeout=15) as provider_response:
            payload = json.loads(provider_response.read())
            if not payload.get('status'):
                raise ValueError('Paystack did not confirm cancellation.')
    except (HTTPError, URLError, TimeoutError, ValueError) as exc:
        raise PaymentProviderError('Could not cancel future Paystack renewals. Try again shortly.') from exc
    return token


class ReviewView(APIView):
    permission_classes = [IsSuperAdmin]
    def post(self, request, pk):
        decision = request.data.get('action')
        note = str(request.data.get('note') or '').strip()[:2000]
        transitions = {
            'approve': ({Campaign.Status.PENDING, Campaign.Status.CHANGES}, Campaign.Status.APPROVED),
            'reject': ({Campaign.Status.PENDING, Campaign.Status.CHANGES}, Campaign.Status.REJECTED),
            'changes': ({Campaign.Status.PENDING}, Campaign.Status.CHANGES),
            'pause': ({Campaign.Status.ACTIVE}, Campaign.Status.PAUSED),
            'resume': ({Campaign.Status.PAUSED}, Campaign.Status.ACTIVE),
            'revoke': ({Campaign.Status.APPROVED, Campaign.Status.ACTIVE, Campaign.Status.PAUSED}, Campaign.Status.REVOKED),
        }
        if decision not in transitions:
            raise serializers.ValidationError('Choose a valid advertising decision.')
        if decision in {'reject', 'changes', 'pause', 'revoke'} and not note:
            raise serializers.ValidationError('Include a reason for this decision.')

        # Revoke must stop future billing as well as hide the creative. Cancel
        # with Paystack before changing the campaign state so a provider error
        # never leaves the advertiser paying for an already-revoked campaign.
        current = get_object_or_404(Campaign, pk=pk)
        cancellation_token = None
        if decision == 'revoke' and current.status in transitions['revoke'][0] and current.subscription_code and not current.cancel_at_period_end:
            try:
                cancellation_token = _disable_paystack_subscription(current)
            except PaymentProviderError as exc:
                return Response({'message': str(exc)}, status=502)

        with transaction.atomic():
            campaign = get_object_or_404(Campaign.objects.select_for_update(), pk=pk)
            allowed, next_status = transitions[decision]
            if campaign.status not in allowed:
                raise serializers.ValidationError('This review action is unavailable for the current campaign.')
            if decision == 'resume' and (not campaign.paid_until or campaign.paid_until <= timezone.now() or campaign.cancel_at_period_end):
                raise serializers.ValidationError('A current subscription is required before resuming this ad.')
            if decision == 'approve' and campaign.applicant_community == 'STUDENT' and not campaign.founding_offer_awarded:
                config = _ads_settings()
                config = AdvertisingSettings.objects.select_for_update().get(pk=config.pk)
                if config.founding_offer_enabled and Campaign.objects.filter(founding_offer_awarded=True).count() < FOUNDING_OFFER_LIMIT:
                    campaign.founding_offer_awarded = True
            campaign.status = next_status
            if decision == 'revoke' and campaign.subscription_code:
                campaign.cancel_at_period_end = True
                if cancellation_token:
                    campaign.subscription_email_token = cancellation_token
            campaign.review_note = note
            campaign.reviewed_by = request.user
            campaign.reviewed_at = timezone.now()
            campaign.save()
            AdDecision.objects.create(campaign=campaign, actor=request.user, action=decision, note=note)
            write_audit_log('UPDATE', 'AdCampaign', campaign.id, {'decision': decision, 'note': note}, user=request.user)
        if decision in {'approve', 'reject', 'changes'}:
            notify_advertiser_of_review(
                Campaign.objects.select_related('owner').prefetch_related('decisions').get(pk=campaign.pk)
            )
        return Response(CampaignSerializer(campaign).data)


class AdminProgramsView(APIView):
    permission_classes = [IsSuperAdmin]

    def get(self, request):
        programs = AdSubscriptionProgram.objects.all().order_by('sort_order', 'name')
        return Response(SubscriptionProgramSerializer(programs, many=True).data)

    def post(self, request):
        serializer = SubscriptionProgramSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        program = serializer.save(created_by=request.user, updated_by=request.user)
        write_audit_log('CREATE', 'AdSubscriptionProgram', program.id, {'code': program.code}, user=request.user)
        return Response(SubscriptionProgramSerializer(program).data, status=201)


class AdminProgramDetailView(APIView):
    permission_classes = [IsSuperAdmin]

    def patch(self, request, pk):
        program = get_object_or_404(AdSubscriptionProgram, pk=pk)
        serializer = SubscriptionProgramSerializer(
            program, data=request.data, partial=True, context={'request': request},
        )
        serializer.is_valid(raise_exception=True)
        program = serializer.save(updated_by=request.user)
        write_audit_log(
            'UPDATE', 'AdSubscriptionProgram', program.id,
            {'is_active': program.is_active, 'monthly_price_ngn': program.monthly_price_ngn},
            user=request.user,
        )
        return Response(SubscriptionProgramSerializer(program).data)

    def delete(self, request, pk):
        # Programs are soft-deactivated so campaigns and payment history keep
        # their foreign-key references and existing subscribers are untouched.
        program = get_object_or_404(AdSubscriptionProgram, pk=pk)
        program.is_active = False
        program.updated_by = request.user
        program.save(update_fields=['is_active', 'updated_by', 'updated_at'])
        write_audit_log('UPDATE', 'AdSubscriptionProgram', program.id, {'is_active': False}, user=request.user)
        return Response(status=204)


class AdminSettingsView(APIView):
    permission_classes = [IsSuperAdmin]
    def get(self, request):
        config = _ads_settings()
        awarded = Campaign.objects.filter(founding_offer_awarded=True).count()
        return Response({'emergency_paused': config.emergency_paused, 'emergency_pause_reason': config.emergency_pause_reason,
            'founding_offer_enabled': config.founding_offer_enabled, 'founding_offer_awarded': awarded,
            'founding_offer_remaining': max(0, FOUNDING_OFFER_LIMIT - awarded) if config.founding_offer_enabled else 0,
            'policy_approved': bool(getattr(settings, 'ADS_POLICY_APPROVED', False)),
            'checkout_configured': bool(settings.ADS_PAYSTACK_SECRET_KEY)})
    def post(self, request):
        action = str(request.data.get('action') or '')
        note = str(request.data.get('note') or '').strip()[:2000]
        if action not in {'pause_all', 'resume_all', 'enable_founding_offer', 'disable_founding_offer'}:
            raise serializers.ValidationError('Choose a valid advertising setting.')
        if action == 'pause_all' and not note:
            raise serializers.ValidationError('A reason is required for the emergency pause.')
        with transaction.atomic():
            config = _ads_settings()
            config = AdvertisingSettings.objects.select_for_update().get(pk=config.pk)
            if action == 'pause_all':
                config.emergency_paused, config.emergency_pause_reason = True, note
                config.emergency_paused_by, config.emergency_paused_at = request.user, timezone.now()
            elif action == 'resume_all':
                config.emergency_paused, config.emergency_pause_reason = False, ''
                config.emergency_paused_by, config.emergency_paused_at = None, None
            elif action == 'enable_founding_offer':
                config.founding_offer_enabled = True
            elif action == 'disable_founding_offer':
                config.founding_offer_enabled = False
            config.save()
            write_audit_log('UPDATE', 'AdvertisingSettings', config.pk, {'action': action, 'note': note}, user=request.user)
        return self.get(request)

class ImageView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]
    throttle_scope = 'ads_image'

    def post(self, request):
        community = Member.objects.filter(user=request.user).values_list('community', flat=True).first()
        if request.user.get_role_code() != 'MEMBER' or community not in {CommunityClassification.STUDENT, CommunityClassification.STAFF, CommunityClassification.GUEST}:
            return Response({'detail': 'Complete your member profile before uploading an advertising creative.'}, status=403)
        file = request.FILES.get('file')
        if not file or file.size > 2 * 1024 * 1024 or file.content_type not in {'image/png', 'image/jpeg', 'image/webp'}:
            raise serializers.ValidationError('Upload a PNG, JPEG or WebP image under 2 MB.')
        if getattr(settings, 'STORAGE_PROVIDER', '').lower() != 'cloudinary':
            raise serializers.ValidationError('Public advertising images require Cloudinary storage.')
        signature = file.read(16)
        if not (signature.startswith(b'\x89PNG\r\n\x1a\n') or signature.startswith(b'\xff\xd8\xff') or signature.startswith(b'RIFF') and signature[8:12] == b'WEBP'):
            raise serializers.ValidationError('This file is not a valid image.')
        file.seek(0)
        from PIL import Image, UnidentifiedImageError
        try:
            with Image.open(file) as image:
                image.verify()
        except (UnidentifiedImageError, OSError):
            raise serializers.ValidationError('This image could not be decoded.')
        file.seek(0)
        url = get_storage_service().upload_fileobj(file, generate_storage_filename(file.name, prefix='advertising'), content_type=file.content_type)
        return Response({'image_url': url}, status=201)


class CheckoutView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_scope = 'ads_checkout'
    def post(self, request, pk):
        campaign = get_object_or_404(Campaign, pk=pk, owner=request.user)
        if campaign.status != Campaign.Status.APPROVED or campaign.subscription_code:
            raise serializers.ValidationError('This ad needs approval and must not already have a subscription.')
        if not getattr(settings, 'ADS_POLICY_APPROVED', False):
            raise serializers.ValidationError('Advertising checkout is closed until the Super Admin confirms revenue ownership, refund/dispute handling, and permitted ad categories.')
        config = AdvertisingSettings.objects.filter(pk=1).first()
        if config and config.emergency_paused:
            raise serializers.ValidationError('Advertising checkout is temporarily paused by the Super Admin.')
        if not settings.ADS_PAYSTACK_SECRET_KEY:
            raise serializers.ValidationError('Advertising checkout is not configured yet.')
        if not campaign.owner.email:
            raise serializers.ValidationError('Add an email address to your account before subscribing.')
        try:
            recurring_amount = campaign_monthly_price_kobo(campaign)
            recurring_plan = plan_code(
                campaign.plan, program=campaign.program, amount_kobo=recurring_amount,
            )
            founding = campaign.founding_offer_awarded and not campaign.payments.exists()
            amount = FOUNDING_FIRST_MONTH_KOBO if founding else recurring_amount
            reference = campaign.reference or f'ad-{uuid.uuid4().hex}'
            payload = {'email': campaign.owner.email, 'amount': amount, 'currency': 'NGN', 'reference': reference,
                'channels': ['card'] if founding else ['card', 'direct_debit'],
                'metadata': {'ad_campaign_id': str(campaign.id), 'program_id': str(campaign.program_id or ''),
                    'billing_mode': 'FOUNDING_FIRST_MONTH' if founding else 'MONTHLY_SUBSCRIPTION',
                    'renewal_amount_kobo': recurring_amount}}
            if settings.FRONTEND_URL:
                payload['callback_url'] = f"{settings.FRONTEND_URL.rstrip('/')}/app/advertise?campaign={campaign.id}"
            if not founding:
                payload['plan'] = recurring_plan
            data = ads_paystack_request('/transaction/initialize', method='POST', payload=payload)
        except PaymentProviderError as exc:
            return Response({'message': str(exc)}, status=502)
        if data.get('reference') != reference or not data.get('authorization_url'):
            return Response({'message': 'Paystack did not return a valid checkout.'}, status=502)
        campaign.reference = reference
        campaign.save(update_fields=['reference'])
        return Response({'checkout_url': data['authorization_url'], 'founding_offer': bool(founding),
            'first_month_amount_ngn': amount // 100, 'renewal_amount_ngn': recurring_amount // 100})

class VerifyView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        campaign = get_object_or_404(Campaign, pk=pk, owner=request.user)
        if not campaign.reference:
            raise serializers.ValidationError('Start checkout first.')
        try:
            data = ads_paystack_request(f"/transaction/verify/{quote(campaign.reference, safe='')}")
            if data.get('status') == 'success':
                activate_payment(campaign, data)
        except PaymentProviderError as exc:
            return Response({'message': str(exc)}, status=502)
        campaign.refresh_from_db()
        return Response(CampaignSerializer(campaign).data)


class CancelView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        campaign = get_object_or_404(Campaign, pk=pk, owner=request.user)
        if not campaign.subscription_code:
            raise serializers.ValidationError('No monthly subscription is attached to this ad.')
        if campaign.cancel_at_period_end:
            return Response(CampaignSerializer(campaign).data)
        try:
            campaign.subscription_email_token = _disable_paystack_subscription(campaign) or campaign.subscription_email_token
        except PaymentProviderError as exc:
            return Response({'message': str(exc)}, status=502)
        campaign.cancel_at_period_end = True
        campaign.save(update_fields=['cancel_at_period_end', 'subscription_email_token'])
        write_audit_log('UPDATE', 'AdCampaign', campaign.id, {'decision': 'cancel_renewal'}, user=request.user)
        return Response(CampaignSerializer(campaign).data)


@method_decorator(csrf_exempt, name='dispatch')
class WebhookView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        try:
            handled = process_ad_webhook(request)
        except (PaymentProviderError, ValueError) as exc:
            return Response({'message': str(exc)}, status=400)
        return Response({'handled': handled})


class PlacementView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_scope = 'ads_public'

    def get(self, request, placement):
        if not _ads_display_allowed():
            return Response({'ad': None})
        if placement not in {'home', 'events'}:
            return Response(status=404)
        campaigns = list(Campaign.objects.filter(
            status=Campaign.Status.ACTIVE, paid_until__gt=timezone.now(),
        ).select_related('program').order_by('id'))
        campaigns = [
            campaign for campaign in campaigns
            if placement in (campaign.placements_snapshot or (campaign.program.placements if campaign.program_id else ['home', 'events']))
        ]
        if not campaigns:
            return Response({'ad': None})
        # Stable per anonymous session / day, with the existing Featured tier
        # receiving twice the placement weight.
        import hashlib
        choices = [campaign for campaign in campaigns for _ in range(2 if campaign.plan == Campaign.Plan.FEATURED else 1)]
        key = f"{request.META.get('REMOTE_ADDR', '')}:{request.headers.get('User-Agent', '')[:60]}:{timezone.localdate()}"
        selected = choices[int(hashlib.sha256(f'{key}:{placement}'.encode()).hexdigest(), 16) % len(choices)]
        viewer_key = f"ad:view:{selected.pk}:{hashlib.sha256(key.encode()).hexdigest()[:24]}"
        if cache.add(viewer_key, 1, timeout=60 * 60 * 12):
            Campaign.objects.filter(pk=selected.pk).update(impressions=F('impressions') + 1)
        return Response({'ad': {'id': selected.id, 'brand_name': selected.brand_name, 'description': selected.description, 'image_url': selected.image_url, 'plan': selected.plan}})


class DashboardPlacementView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_scope = 'ads_public'

    def get(self, request):
        if not _ads_display_allowed():
            return Response({'ad': None})
        campaigns = list(Campaign.objects.filter(
            status=Campaign.Status.ACTIVE, paid_until__gt=timezone.now(),
        ).select_related('program').order_by('id'))
        campaigns = [campaign for campaign in campaigns if 'dashboard' in (
            campaign.placements_snapshot or (campaign.program.placements if campaign.program_id else [])
        )]
        if not campaigns:
            return Response({'ad': None})
        import hashlib
        choices = [campaign for campaign in campaigns for _ in range(2 if campaign.plan == Campaign.Plan.FEATURED else 1)]
        key = f'{request.user.pk}:{timezone.localdate().isoformat()}'
        selected = choices[int(hashlib.sha256(f'{key}:dashboard'.encode()).hexdigest(), 16) % len(choices)]
        if cache.add(f'ad:dashboard:view:{selected.pk}:{key}', 1, timeout=60 * 60 * 24):
            Campaign.objects.filter(pk=selected.pk).update(impressions=F('impressions') + 1)
        return Response({'ad': {
            'id': selected.id, 'brand_name': selected.brand_name, 'description': selected.description,
            'image_url': selected.image_url, 'plan': selected.plan,
        }})


class AdDirectoryView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_scope = 'ads_public'

    def get(self, request):
        if not _ads_display_allowed():
            return Response({'items': [], 'total': 0})
        search = request.query_params.get('q', '').strip()[:80]
        try:
            page = max(1, min(int(request.query_params.get('page', '1')), 1000))
        except (TypeError, ValueError):
            page = 1
        campaigns = Campaign.objects.filter(
            status=Campaign.Status.ACTIVE, paid_until__gt=timezone.now(),
        )
        if search:
            campaigns = campaigns.filter(Q(brand_name__icontains=search) | Q(description__icontains=search) | Q(ad_category__icontains=search))
        total = campaigns.count()
        items = campaigns.order_by('brand_name', 'id')[(page - 1) * 24:page * 24]
        return Response({'items': [{
            'id': campaign.id, 'brand_name': campaign.brand_name,
            'description': campaign.description, 'ad_category': campaign.ad_category,
            'image_url': campaign.image_url,
        } for campaign in items], 'total': total, 'page': page, 'page_size': 24})


class ClickView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_scope = 'ads_public'

    def post(self, request, pk):
        if not _ads_display_allowed():
            return Response({'message': 'Advertising is temporarily unavailable.'}, status=404)
        campaign = get_object_or_404(Campaign, pk=pk, status=Campaign.Status.ACTIVE, paid_until__gt=timezone.now())
        import hashlib
        key = f"{request.META.get('REMOTE_ADDR', '')}:{request.headers.get('User-Agent', '')[:60]}:{pk}"
        if cache.add(f"ad:click:{hashlib.sha256(key.encode()).hexdigest()}", 1, timeout=60 * 30):
            Campaign.objects.filter(pk=pk).update(clicks=F('clicks') + 1)
        return Response({'url': campaign.destination_url})
