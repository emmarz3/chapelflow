import logging
from urllib.parse import urlparse

import requests
from celery import shared_task
from django.conf import settings
from django.utils import timezone

from .models import Campaign

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=5)
def sync_scendey_waitlist(self, campaign_id):
    campaign = Campaign.objects.filter(pk=campaign_id, scendey_opt_in=True, scendey_synced_at__isnull=True,
        payments__isnull=False).select_related('owner').first()
    if not campaign:
        return
    endpoint = getattr(settings, 'SCENDEY_WAITLIST_URL', '')
    parsed = urlparse(endpoint)
    if parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password:
        logger.info('scendey_waitlist_url_not_configured')
        return
    try:
        response = requests.post(endpoint, json={
            'role': 'BRAND', 'audienceCategory': 'BUSINESS',
            'name': (campaign.owner.get_full_name() or campaign.owner.email.split('@', 1)[0])[:100],
            'email': campaign.owner.email,
            'brandName': campaign.brand_name[:100], 'category': (campaign.ad_category or 'Campus brand')[:60],
            'handleOrUrl': campaign.destination_url[:200],
            'consent': True, 'source': 'ChapelFlow advertising',
        }, timeout=10)
        response.raise_for_status()
        result = response.json()
        if not result.get('ok'):
            raise ValueError('Scendey did not accept signup')
        if result.get('existing') is True:
            # Scendey's global email uniqueness means we cannot assume an
            # existing SHOPPER record is the advertiser BRAND entry. Keep the
            # campaign unsynced for an explicit reconciliation instead of
            # falsely recording a successful advertiser opt-in.
            logger.warning(
                'scendey_waitlist_existing_email_requires_reconciliation campaign_id=%s',
                campaign.pk,
            )
            return {'status': 'already_registered', 'campaign_id': str(campaign.pk)}
    except (requests.RequestException, ValueError) as exc:
        raise self.retry(exc=exc, countdown=min(300, 2 ** self.request.retries * 10)) from exc
    Campaign.objects.filter(pk=campaign.pk, scendey_synced_at__isnull=True).update(scendey_synced_at=timezone.now())
    return {'status': 'synced', 'campaign_id': str(campaign.pk)}
