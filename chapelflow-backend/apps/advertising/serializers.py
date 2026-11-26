from urllib.parse import urlparse

from django.utils import timezone
from rest_framework import serializers

from common.constants.roles import Roles
from apps.members.models import CommunityClassification, Member
from .models import AdSubscriptionProgram, Campaign
from .services import PRICES, campaign_monthly_price_kobo

CONSENT = 'Send me Scendey waitlist updates about onboarding when Scendey launches.'


class CampaignSerializer(serializers.ModelSerializer):
    program = serializers.PrimaryKeyRelatedField(
        queryset=AdSubscriptionProgram.objects.filter(is_active=True),
        required=False,
    )
    program_name = serializers.SerializerMethodField()
    program_code = serializers.SerializerMethodField()
    monthly_price_ngn = serializers.SerializerMethodField()
    payment_history = serializers.SerializerMethodField()

    def get_program_name(self, campaign):
        return campaign.program_name_snapshot or (campaign.program.name if campaign.program_id else campaign.get_plan_display())

    def get_program_code(self, campaign):
        return campaign.program.code if campaign.program_id else campaign.plan.lower()

    def get_monthly_price_ngn(self, campaign):
        return campaign_monthly_price_kobo(campaign) // 100

    def get_payment_history(self, campaign):
        payments = sorted(campaign.payments.all(), key=lambda payment: payment.paid_at, reverse=True)
        return [{'reference': p.reference, 'amount_ngn': p.amount_kobo // 100, 'paid_at': p.paid_at} for p in payments]

    class Meta:
        model = Campaign
        fields = (
            'id', 'brand_name', 'description', 'image_url', 'destination_url', 'contact_email',
            'plan', 'program', 'program_name', 'program_code', 'ad_category', 'applicant_community',
            'founding_offer_awarded', 'submission_revision', 'status', 'review_note', 'reviewed_at',
            'scendey_opt_in', 'created_at', 'paid_until', 'cancel_at_period_end', 'impressions', 'clicks',
            'monthly_price_ngn', 'payment_history',
        )
        read_only_fields = (
            'id', 'program_name', 'program_code', 'applicant_community', 'founding_offer_awarded',
            'submission_revision', 'status', 'review_note', 'reviewed_at', 'created_at', 'paid_until',
            'cancel_at_period_end', 'impressions', 'clicks', 'monthly_price_ngn', 'payment_history',
        )
        extra_kwargs = {'plan': {'required': False}}

    def validate(self, attrs):
        program = attrs.get('program') or (self.instance.program if self.instance else None)
        if self.instance and 'program' in attrs and attrs['program'].pk != self.instance.program_id:
            raise serializers.ValidationError({'program': 'The subscription program cannot be changed after an application is submitted.'})

        if self.instance is None:
            user = self.context['request'].user
            if user.get_role_code() != Roles.MEMBER:
                raise serializers.ValidationError('Only community members can advertise.')
            community = Member.objects.filter(user=user).values_list('community', flat=True).first()
            if community not in {CommunityClassification.STUDENT, CommunityClassification.STAFF, CommunityClassification.GUEST}:
                raise serializers.ValidationError('Complete your member profile before applying to advertise.')
            self.applicant_community = community
            if not attrs.get('ad_category', '').strip():
                raise serializers.ValidationError({'ad_category': 'Describe the proposed advertisement category.'})

        for key in ('image_url', 'destination_url'):
            url = urlparse(attrs.get(key) or getattr(self.instance, key, ''))
            if url.scheme != 'https' or not url.hostname or url.username or url.password:
                raise serializers.ValidationError({key: 'Use a public HTTPS URL.'})

        if program:
            if self.instance is None and program.audience != ('STUDENT' if self.applicant_community == CommunityClassification.STUDENT else 'OUTSIDER'):
                raise serializers.ValidationError({'program': 'Choose the subscription program for your student or outside advertiser status.'})
            if not program.is_active and (self.instance is None or self.instance.program_id != program.pk):
                raise serializers.ValidationError({'program': 'This subscription program is no longer available.'})
            attrs['plan'] = program.base_plan
            if self.instance is None:
                attrs['monthly_price_kobo'] = program.monthly_price_ngn * 100
        else:
            if self.instance is None:
                raise serializers.ValidationError({'program': 'Choose an available monthly subscription program.'})
            plan = attrs.get('plan') or getattr(self.instance, 'plan', None)
            if plan not in Campaign.Plan.values:
                raise serializers.ValidationError({'program': 'Choose an available monthly subscription program.'})
            if self.instance is None:
                attrs['monthly_price_kobo'] = PRICES[plan]
        return attrs

    def create(self, validated_data):
        consent = validated_data.get('scendey_opt_in', False)
        program = validated_data.get('program')
        validated_data['applicant_community'] = getattr(self, 'applicant_community', CommunityClassification.STUDENT)
        if program:
            validated_data['program_name_snapshot'] = program.name
            validated_data['placements_snapshot'] = list(program.placements)
        return Campaign.objects.create(
            **validated_data, owner=self.context['request'].user,
            scendey_consented_at=timezone.now() if consent else None,
            scendey_consent_text=CONSENT if consent else '',
        )


class SubscriptionProgramSerializer(serializers.ModelSerializer):
    placements = serializers.ListField(
        child=serializers.ChoiceField(choices=['home', 'events']),
        allow_empty=False,
    )
    campaign_count = serializers.SerializerMethodField()

    class Meta:
        model = AdSubscriptionProgram
        fields = (
            'id', 'code', 'name', 'description', 'monthly_price_ngn', 'audience', 'base_plan',
            'placements', 'is_active', 'sort_order', 'campaign_count', 'created_at', 'updated_at',
        )
        read_only_fields = ('id', 'campaign_count', 'created_at', 'updated_at')

    def get_campaign_count(self, program):
        return program.campaigns.count()

    def validate_monthly_price_ngn(self, value):
        if value < 100 or value > 1000000:
            raise serializers.ValidationError('Monthly price must be between ₦100 and ₦1,000,000.')
        return value

    def validate_code(self, value):
        value = value.lower()
        queryset = AdSubscriptionProgram.objects.exclude(pk=self.instance.pk) if self.instance else AdSubscriptionProgram.objects.all()
        if queryset.filter(code=value).exists():
            raise serializers.ValidationError('A subscription program with this code already exists.')
        return value

    def validate(self, attrs):
        placements = attrs.get('placements', self.instance.placements if self.instance else [])
        if not placements:
            raise serializers.ValidationError({'placements': 'Select at least one placement.'})
        return attrs
