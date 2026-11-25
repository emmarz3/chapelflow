import uuid
import json
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError
from urllib.parse import quote

from django.conf import settings
from django.core.cache import cache
from django.db.models import F
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
from apps.finance.services import PaymentProviderError, _paystack_request
from common.permissions.rbac import IsSuperAdmin
from apps.uploads.storage import get_storage_service, generate_storage_filename
from .models import AdDecision, Campaign
from .serializers import CampaignSerializer, CONSENT
from .services import PRICES, activate_payment, plan_code, process_ad_webhook


class PlansView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request):
        return Response({'plans': [{'code': key, 'name': Campaign.Plan(key).label, 'price_ngn': value // 100, 'interval': 'monthly'} for key, value in PRICES.items()], 'consent_text': CONSENT, 'checkout_available': bool(settings.PAYSTACK_SECRET_KEY)})


class MyCampaignsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(CampaignSerializer(Campaign.objects.filter(owner=request.user), many=True).data)

    def post(self, request):
        serializer = CampaignSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        campaign = serializer.save()
        write_audit_log('CREATE', 'AdCampaign', campaign.id, user=request.user)
        return Response(CampaignSerializer(campaign).data, status=201)


class MyCampaignDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request, pk):
        campaign = get_object_or_404(Campaign, pk=pk, owner=request.user)
        if campaign.status != Campaign.Status.CHANGES:
            raise serializers.ValidationError('Changes can only be submitted when requested by the reviewer.')
        serializer = CampaignSerializer(campaign, data=request.data, partial=True, context={'request': request})
        serializer.is_valid(raise_exception=True)
        serializer.save(status=Campaign.Status.PENDING, review_note='')
        write_audit_log('UPDATE', 'AdCampaign', campaign.id, {'decision': 'resubmitted'}, user=request.user)
        return Response(CampaignSerializer(campaign).data)


class AdminCampaignsView(APIView):
    permission_classes = [IsSuperAdmin]

    def get(self, request):
        campaigns = Campaign.objects.select_related('owner').all()[:200]
        return Response([dict(CampaignSerializer(campaign).data, owner_email=campaign.owner.email or '') for campaign in campaigns])


class ReviewView(APIView):
    permission_classes = [IsSuperAdmin]

    def post(self, request, pk):
        campaign = get_object_or_404(Campaign, pk=pk)
        decision = request.data.get('action')
        note = str(request.data.get('note') or '').strip()[:2000]
        transitions = {
            'approve': ({Campaign.Status.PENDING, Campaign.Status.CHANGES}, Campaign.Status.APPROVED),
            'reject': ({Campaign.Status.PENDING, Campaign.Status.CHANGES}, Campaign.Status.REJECTED),
            'changes': ({Campaign.Status.PENDING}, Campaign.Status.CHANGES),
            'pause': ({Campaign.Status.ACTIVE}, Campaign.Status.PAUSED),
            'resume': ({Campaign.Status.PAUSED}, Campaign.Status.ACTIVE),
        }
        if decision not in transitions or campaign.status not in transitions[decision][0]:
            raise serializers.ValidationError('This review action is unavailable for the current campaign.')
        if decision in {'reject', 'changes', 'pause'} and not note:
            raise serializers.ValidationError('Include a reason for this decision.')
        if decision == 'resume' and (not campaign.paid_until or campaign.paid_until <= timezone.now() or campaign.cancel_at_period_end):
            raise serializers.ValidationError('A current subscription is required before resuming this ad.')
        campaign.status = transitions[decision][1]
        campaign.review_note = note
        campaign.reviewed_by = request.user
        campaign.reviewed_at = timezone.now()
        campaign.save()
        AdDecision.objects.create(campaign=campaign, actor=request.user, action=decision, note=note)
        write_audit_log('UPDATE', 'AdCampaign', campaign.id, {'decision': decision}, user=request.user)
        return Response(CampaignSerializer(campaign).data)


class ImageView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
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

    def post(self, request, pk):
        campaign = get_object_or_404(Campaign, pk=pk, owner=request.user)
        if campaign.status != Campaign.Status.APPROVED or campaign.subscription_code:
            raise serializers.ValidationError('This ad needs approval and must not already have a subscription.')
        if not settings.PAYSTACK_SECRET_KEY:
            raise serializers.ValidationError('Advertising checkout is not configured yet.')
        if not campaign.owner.email:
            raise serializers.ValidationError('Add an email address to your account before subscribing.')
        try:
            code = plan_code(campaign.plan)
            reference = campaign.reference or f'ad-{uuid.uuid4().hex}'
            data = _paystack_request('/transaction/initialize', method='POST', payload={
                'email': campaign.owner.email, 'amount': PRICES[campaign.plan],
                'currency': 'NGN', 'reference': reference, 'plan': code,
                'channels': ['card', 'direct_debit'],
                'metadata': {'ad_campaign_id': str(campaign.id)},
                'callback_url': f"{settings.FRONTEND_URL.rstrip('/')}/app/advertise?campaign={campaign.id}" if getattr(settings, 'FRONTEND_URL', '') else '',
            })
        except PaymentProviderError as exc:
            return Response({'message': str(exc)}, status=502)
        if data.get('reference') != reference or not data.get('authorization_url'):
            return Response({'message': 'Paystack did not return a valid checkout.'}, status=502)
        campaign.reference = reference
        campaign.save(update_fields=['reference'])
        return Response({'checkout_url': data['authorization_url']})


class VerifyView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        campaign = get_object_or_404(Campaign, pk=pk, owner=request.user)
        if not campaign.reference:
            raise serializers.ValidationError('Start checkout first.')
        try:
            data = _paystack_request(f"/transaction/verify/{quote(campaign.reference, safe='')}")
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
        if not campaign.subscription_email_token:
            data = _paystack_request(f"/subscription/{quote(campaign.subscription_code, safe='')}")
            campaign.subscription_email_token = data.get('email_token') or ''
        if not campaign.subscription_email_token:
            return Response({'message': 'Contact the chapel office to cancel this subscription.'}, status=502)
        request_body = json.dumps({'code': campaign.subscription_code, 'token': campaign.subscription_email_token}).encode()
        provider_request = Request('https://api.paystack.co/subscription/disable', data=request_body,
            headers={'Authorization': f'Bearer {settings.PAYSTACK_SECRET_KEY}', 'Content-Type': 'application/json'}, method='POST')
        try:
            with urlopen(provider_request, timeout=15) as provider_response:
                if not json.loads(provider_response.read()).get('status'):
                    raise ValueError('Paystack did not confirm cancellation.')
        except (HTTPError, URLError, TimeoutError, ValueError):
            return Response({'message': 'Could not cancel renewal with Paystack. Try again shortly.'}, status=502)
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
        if placement not in {'home', 'events'}:
            return Response(status=404)
        campaigns = list(Campaign.objects.filter(status=Campaign.Status.ACTIVE, paid_until__gt=timezone.now()).order_by('id'))
        if not campaigns:
            return Response({'ad': None})
        # Stable per anonymous session / day, with twice the weight for Featured.
        import hashlib
        choices = [campaign for campaign in campaigns for _ in range(2 if campaign.plan == Campaign.Plan.FEATURED else 1)]
        key = f"{request.META.get('REMOTE_ADDR', '')}:{request.headers.get('User-Agent', '')[:60]}:{placement}:{timezone.localdate()}"
        selected = choices[int(hashlib.sha256(key.encode()).hexdigest(), 16) % len(choices)]
        viewer_key = f"ad:view:{selected.pk}:{hashlib.sha256(key.encode()).hexdigest()[:24]}"
        if cache.add(viewer_key, 1, timeout=60 * 60 * 12):
            Campaign.objects.filter(pk=selected.pk).update(impressions=F('impressions') + 1)
        return Response({'ad': {'id': selected.id, 'brand_name': selected.brand_name, 'description': selected.description, 'image_url': selected.image_url, 'plan': selected.plan}})


class ClickView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_scope = 'ads_public'

    def post(self, request, pk):
        campaign = get_object_or_404(Campaign, pk=pk, status=Campaign.Status.ACTIVE, paid_until__gt=timezone.now())
        import hashlib
        key = f"{request.META.get('REMOTE_ADDR', '')}:{request.headers.get('User-Agent', '')[:60]}:{pk}"
        if cache.add(f"ad:click:{hashlib.sha256(key.encode()).hexdigest()}", 1, timeout=60 * 30):
            Campaign.objects.filter(pk=pk).update(clicks=F('clicks') + 1)
        return Response({'url': campaign.destination_url})
