from urllib.parse import urlparse
from rest_framework import serializers
from django.utils import timezone
from common.constants.roles import Roles
from apps.members.models import CommunityClassification, Member
from .models import Campaign

CONSENT = 'Send me Scendey waitlist updates about onboarding when Scendey launches.'


class CampaignSerializer(serializers.ModelSerializer):
    monthly_price_ngn = serializers.SerializerMethodField()
    payment_history = serializers.SerializerMethodField()

    def get_monthly_price_ngn(self, campaign):
        from .services import PRICES
        return PRICES[campaign.plan] // 100

    def get_payment_history(self, campaign):
        payments = sorted(campaign.payments.all(), key=lambda payment: payment.paid_at, reverse=True)
        return [{'reference': p.reference, 'amount_ngn': p.amount_kobo // 100, 'paid_at': p.paid_at} for p in payments]

    class Meta:
        model = Campaign
        fields = ('id', 'brand_name', 'description', 'image_url', 'destination_url', 'contact_email',
                  'plan', 'ad_category', 'applicant_community', 'founding_offer_awarded', 'status', 'review_note',
                  'reviewed_at', 'scendey_opt_in', 'created_at', 'paid_until', 'cancel_at_period_end', 'impressions', 'clicks',
                  'monthly_price_ngn', 'payment_history')
        read_only_fields = ('id', 'applicant_community', 'founding_offer_awarded', 'status', 'review_note', 'reviewed_at',
                            'created_at', 'paid_until', 'cancel_at_period_end', 'impressions', 'clicks',
                            'monthly_price_ngn', 'payment_history')

    def validate(self, attrs):
        if self.instance is None:
            user = self.context['request'].user
            if user.get_role_code() != Roles.MEMBER:
                raise serializers.ValidationError('Only student and staff community members can advertise.')
            community = Member.objects.filter(user=user).values_list('community', flat=True).first() or CommunityClassification.STUDENT
            if community not in {CommunityClassification.STUDENT, CommunityClassification.STAFF}:
                raise serializers.ValidationError('Advertising is available to student and staff community members only.')
            self.applicant_community = community
            if not attrs.get('ad_category', '').strip():
                raise serializers.ValidationError({'ad_category': 'Describe the proposed advertisement category.'})
        for key in ('image_url', 'destination_url'):
            url = urlparse(attrs.get(key) or getattr(self.instance, key, ''))
            if url.scheme != 'https' or not url.hostname or url.username or url.password:
                raise serializers.ValidationError({key: 'Use a public HTTPS URL.'})
        if (attrs.get('plan') or getattr(self.instance, 'plan', None)) not in Campaign.Plan.values:
            raise serializers.ValidationError({'plan': 'Choose an available monthly plan.'})
        return attrs

    def create(self, validated_data):
        consent = validated_data.get('scendey_opt_in', False)
        validated_data['applicant_community'] = getattr(self, 'applicant_community', CommunityClassification.STUDENT)
        return Campaign.objects.create(
            **validated_data, owner=self.context['request'].user,
            scendey_consented_at=timezone.now() if consent else None,
            scendey_consent_text=CONSENT if consent else '',
        )
