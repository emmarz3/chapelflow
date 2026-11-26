import uuid
from django.conf import settings
from django.db import models


AD_PLACEMENT_CHOICES = (("home", "Homepage"), ("events", "Events page"))
AD_BASE_PLAN_CHOICES = (("CAMPUS", "Campus Brand"), ("FEATURED", "Featured Brand"))


class AdSubscriptionProgram(models.Model):
    """A reusable, admin-managed advertising offer.

    Campaigns keep a price snapshot and a versioned Paystack plan, so editing
    this catalogue never silently changes an existing advertiser's renewal.
    Programs are deactivated rather than deleted once they have been used.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.SlugField(max_length=48, unique=True)
    name = models.CharField(max_length=120)
    description = models.CharField(max_length=500, blank=True)
    monthly_price_ngn = models.PositiveIntegerField()
    base_plan = models.CharField(max_length=12, choices=AD_BASE_PLAN_CHOICES, default="CAMPUS")
    placements = models.JSONField(default=list)
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveSmallIntegerField(default=0)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="created_ad_programs",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="updated_ad_programs",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["sort_order", "name"]
        indexes = [models.Index(fields=["is_active", "sort_order"], name="advertising_is_acti_2bcff2_idx")]

    def __str__(self):
        return f"{self.name} (₦{self.monthly_price_ngn:,}/month)"


class Campaign(models.Model):
    class Status(models.TextChoices):
        PENDING = 'PENDING', 'Pending review'
        CHANGES = 'CHANGES', 'Changes requested'
        APPROVED = 'APPROVED', 'Approved, awaiting payment'
        REJECTED = 'REJECTED', 'Rejected'
        REVOKED = 'REVOKED', 'Revoked'
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
    program = models.ForeignKey(
        AdSubscriptionProgram, null=True, blank=True, on_delete=models.PROTECT,
        related_name="campaigns",
    )
    # Snapshot of the monthly price agreed when the advertiser applies.
    # Existing and active subscriptions are not repriced when a program changes.
    monthly_price_kobo = models.PositiveIntegerField(null=True, blank=True)
    ad_category = models.CharField(max_length=80, blank=True, default='')
    applicant_community = models.CharField(max_length=10, choices=[('STUDENT', 'Student'), ('STAFF', 'Staff')], default='STUDENT')
    founding_offer_awarded = models.BooleanField(default=False)
    submission_revision = models.PositiveSmallIntegerField(default=1)
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
    campaign = models.ForeignKey(Campaign, on_delete=models.PROTECT, related_name='payments')
    amount_kobo = models.PositiveIntegerField()
    paid_at = models.DateTimeField()
    provider_payload = models.JSONField(default=dict, blank=True)


class PaystackPlan(models.Model):
    # Legacy plans keep plan populated. New program prices are versioned by
    # (program, amount_kobo), allowing future pricing without repricing users.
    plan = models.CharField(max_length=12, blank=True, null=True, choices=Campaign.Plan.choices)
    program = models.ForeignKey(
        AdSubscriptionProgram, null=True, blank=True, on_delete=models.PROTECT,
        related_name="paystack_plans",
    )
    code = models.CharField(max_length=120)
    amount_kobo = models.PositiveIntegerField()

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["plan"],
                condition=models.Q(program__isnull=True, plan__isnull=False),
                name="ad_paystack_legacy_plan_unique",
            ),
            models.UniqueConstraint(
                fields=["program", "amount_kobo"],
                condition=models.Q(program__isnull=False),
                name="ad_paystack_program_amount_unique",
            ),
        ]


class AdDecision(models.Model):
    campaign = models.ForeignKey(Campaign, on_delete=models.CASCADE, related_name='decisions')
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    action = models.CharField(max_length=24)
    note = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)


class AdvertisingSettings(models.Model):
    """Singleton controls for emergency display pause and founding-offer availability."""
    id = models.PositiveSmallIntegerField(primary_key=True, default=1, editable=False)
    emergency_paused = models.BooleanField(default=False)
    emergency_pause_reason = models.TextField(blank=True)
    emergency_paused_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='advertising_pause_actions')
    emergency_paused_at = models.DateTimeField(null=True, blank=True)
    founding_offer_enabled = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Advertising settings'
        verbose_name_plural = 'Advertising settings'

    def __str__(self):
        return 'ChapelFlow advertising settings'
