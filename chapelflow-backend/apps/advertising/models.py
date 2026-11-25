import uuid
from django.conf import settings
from django.db import models


class Campaign(models.Model):
    class Status(models.TextChoices):
        PENDING = 'PENDING', 'Pending review'
        CHANGES = 'CHANGES', 'Changes requested'
        APPROVED = 'APPROVED', 'Approved, awaiting payment'
        REJECTED = 'REJECTED', 'Rejected'
        ACTIVE = 'ACTIVE', 'Active'
        PAUSED = 'PAUSED', 'Paused'
        CANCELLED = 'CANCELLED', 'Cancelled'

    class Plan(models.TextChoices):
        CAMPUS = 'CAMPUS', 'Campus Brand'
        FEATURED = 'FEATURED', 'Featured Brand'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='ad_campaigns')
    brand_name = models.CharField(max_length=120)
    description = models.CharField(max_length=300)
    image_url = models.URLField(max_length=1000)
    destination_url = models.URLField(max_length=1000)
    contact_email = models.EmailField()
    plan = models.CharField(max_length=12, choices=Plan.choices)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.PENDING)
    review_note = models.TextField(blank=True)
    reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name='+')
    reviewed_at = models.DateTimeField(null=True, blank=True)
    # Separate consent; never a condition of chapel advertising.
    scendey_opt_in = models.BooleanField(default=False)
    scendey_consented_at = models.DateTimeField(null=True, blank=True)
    scendey_consent_text = models.CharField(max_length=300, blank=True)
    scendey_synced_at = models.DateTimeField(null=True, blank=True)
    reference = models.CharField(max_length=90, unique=True, null=True, blank=True)
    subscription_code = models.CharField(max_length=120, unique=True, null=True, blank=True)
    subscription_email_token = models.CharField(max_length=180, blank=True)
    paid_until = models.DateTimeField(null=True, blank=True)
    cancel_at_period_end = models.BooleanField(default=False)
    impressions = models.PositiveIntegerField(default=0)
    clicks = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [models.Index(fields=['status', 'paid_until'])]


class AdPayment(models.Model):
    reference = models.CharField(max_length=100, primary_key=True)
    campaign = models.ForeignKey(Campaign, on_delete=models.CASCADE, related_name='payments')
    amount_kobo = models.PositiveIntegerField()
    paid_at = models.DateTimeField()
    provider_payload = models.JSONField(default=dict, blank=True)


class PaystackPlan(models.Model):
    plan = models.CharField(max_length=12, unique=True, choices=Campaign.Plan.choices)
    code = models.CharField(max_length=120)
    amount_kobo = models.PositiveIntegerField()


class AdDecision(models.Model):
    campaign = models.ForeignKey(Campaign, on_delete=models.CASCADE, related_name='decisions')
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    action = models.CharField(max_length=24)
    note = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
