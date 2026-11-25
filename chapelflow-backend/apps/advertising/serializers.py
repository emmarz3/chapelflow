from urllib.parse import urlparse
from rest_framework import serializers
from django.utils import timezone
from .models import Campaign

CONSENT = 'Send me Scendey waitlist updates about onboarding when Scendey launches.'


class CampaignSerializer(serializers.ModelSerializer):
    class Meta:
        model = Campaign
        fields = ('id', 'brand_name', 'description', 'image_url', 'destination_url', 'contact_email',
                  'plan', 'status', 'review_note', 'scendey_opt_in', 'created_at', 'paid_until',
                  'cancel_at_period_end', 'impressions', 'clicks')
        read_only_fields = ('id', 'status', 'review_note', 'created_at', 'paid_until',
                            'cancel_at_period_end', 'impressions', 'clicks')

    def validate(self, attrs):
        for key in ('image_url', 'destination_url'):
            url = urlparse(attrs.get(key) or getattr(self.instance, key, ''))
            if url.scheme != 'https' or not url.hostname or url.username or url.password:
                raise serializers.ValidationError({key: 'Use a public HTTPS URL.'})
        if (attrs.get('plan') or getattr(self.instance, 'plan', None)) not in Campaign.Plan.values:
            raise serializers.ValidationError({'plan': 'Choose an available monthly plan.'})
        return attrs

    def create(self, validated_data):
        consent = validated_data.get('scendey_opt_in', False)
        return Campaign.objects.create(
            **validated_data, owner=self.context['request'].user,
            scendey_consented_at=timezone.now() if consent else None,
            scendey_consent_text=CONSENT if consent else '',
        )
