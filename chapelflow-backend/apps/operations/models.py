import uuid

from django.conf import settings
from django.db import models


class BranchRecord(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    branch = models.ForeignKey(
        "organizations.Branch", on_delete=models.PROTECT,
        related_name="%(app_label)s_%(class)s_records",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class DutyRoster(BranchRecord):
    title = models.CharField(max_length=255)
    details = models.TextField()
    status = models.CharField(max_length=20, default="DRAFT")

    class Meta:
        db_table = "operations_duty_roster"
        ordering = ["-created_at"]


class WorkerLeaveRequest(BranchRecord):
    reason = models.TextField()
    status = models.CharField(max_length=20, default="PENDING")

    class Meta:
        db_table = "operations_worker_leave_request"
        ordering = ["-created_at"]


class FinanceTransaction(BranchRecord):
    description = models.CharField(max_length=255)
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    category = models.CharField(max_length=100)
    transaction_type = models.CharField(
        max_length=10,
        choices=[("INCOME", "Income"), ("EXPENSE", "Expense")],
        default="INCOME",
    )
    status = models.CharField(max_length=20, default="RECORDED")

    class Meta:
        db_table = "operations_finance_transaction"
        ordering = ["-created_at"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(amount__gt=0),
                name="operations_finance_amount_positive",
            )
        ]


class AssetStatus(models.TextChoices):
    AVAILABLE = "AVAILABLE", "Available"
    ISSUED = "ISSUED", "Issued"
    MAINTENANCE = "MAINTENANCE", "In maintenance"
    RETIRED = "RETIRED", "Retired"
    LOST = "LOST", "Lost"


class AssetTrackingMode(models.TextChoices):
    SERIALIZED = "SERIALIZED", "Individual asset"
    STOCK = "STOCK", "Stock item"


class AssetCondition(models.TextChoices):
    EXCELLENT = "EXCELLENT", "Excellent"
    GOOD = "GOOD", "Good"
    FAIR = "FAIR", "Fair"
    POOR = "POOR", "Poor"


class AssetCategory(BranchRecord):
    name = models.CharField(max_length=120)
    description = models.TextField(blank=True)

    class Meta:
        db_table = "operations_asset_category"
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(fields=["branch", "name"], name="unique_asset_category_per_branch"),
        ]


class AssetLocation(BranchRecord):
    name = models.CharField(max_length=120)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "operations_asset_location"
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(fields=["branch", "name"], name="unique_asset_location_per_branch"),
        ]


class Asset(BranchRecord):
    name = models.CharField(max_length=255)
    details = models.TextField()
    category = models.ForeignKey(
        AssetCategory, null=True, blank=True, on_delete=models.SET_NULL, related_name="assets"
    )
    location = models.ForeignKey(
        AssetLocation, null=True, blank=True, on_delete=models.SET_NULL, related_name="assets"
    )
    asset_tag = models.CharField(max_length=80, blank=True)
    serial_number = models.CharField(max_length=120, blank=True)
    tracking_mode = models.CharField(
        max_length=12, choices=AssetTrackingMode.choices, default=AssetTrackingMode.SERIALIZED
    )
    quantity_on_hand = models.PositiveIntegerField(default=1)
    reorder_level = models.PositiveIntegerField(default=0)
    unit_of_measure = models.CharField(max_length=30, default="item")
    condition = models.CharField(
        max_length=12, choices=AssetCondition.choices, default=AssetCondition.GOOD
    )
    custodian_name = models.CharField(max_length=180, blank=True)
    custodian = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="custodied_assets",
    )
    status = models.CharField(max_length=20, choices=AssetStatus.choices, default=AssetStatus.AVAILABLE)
    next_maintenance_at = models.DateField(null=True, blank=True)
    last_maintenance_at = models.DateField(null=True, blank=True)

    class Meta:
        db_table = "operations_asset"
        ordering = ["name"]
        indexes = [
            models.Index(fields=["branch", "status"]),
            models.Index(fields=["branch", "tracking_mode", "quantity_on_hand"]),
            models.Index(fields=["next_maintenance_at"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["branch", "asset_tag"],
                condition=~models.Q(asset_tag=""),
                name="unique_asset_tag_per_branch",
            ),
        ]


class AssetMovementType(models.TextChoices):
    ISSUE = "ISSUE", "Issue"
    RETURN = "RETURN", "Return"
    TRANSFER = "TRANSFER", "Transfer"
    ADJUSTMENT = "ADJUSTMENT", "Stock adjustment"
    MAINTENANCE_START = "MAINTENANCE_START", "Send to maintenance"
    MAINTENANCE_COMPLETE = "MAINTENANCE_COMPLETE", "Complete maintenance"


class AssetMovement(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    asset = models.ForeignKey(Asset, on_delete=models.PROTECT, related_name="movements")
    movement_type = models.CharField(max_length=24, choices=AssetMovementType.choices)
    quantity_change = models.IntegerField(default=0)
    quantity_after = models.PositiveIntegerField()
    from_location = models.ForeignKey(
        AssetLocation, null=True, blank=True, on_delete=models.SET_NULL, related_name="outgoing_movements"
    )
    to_location = models.ForeignKey(
        AssetLocation, null=True, blank=True, on_delete=models.SET_NULL, related_name="incoming_movements"
    )
    custodian_name = models.CharField(max_length=180, blank=True)
    custodian = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="asset_movements_received",
    )
    reason = models.CharField(max_length=500, blank=True)
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="recorded_asset_movements"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "operations_asset_movement"
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["asset", "-created_at"])]


class AssetMaintenanceStatus(models.TextChoices):
    SCHEDULED = "SCHEDULED", "Scheduled"
    COMPLETED = "COMPLETED", "Completed"
    CANCELLED = "CANCELLED", "Cancelled"


class AssetMaintenance(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    asset = models.ForeignKey(Asset, on_delete=models.PROTECT, related_name="maintenance_records")
    title = models.CharField(max_length=180)
    details = models.TextField(blank=True)
    due_at = models.DateField()
    status = models.CharField(
        max_length=12, choices=AssetMaintenanceStatus.choices, default=AssetMaintenanceStatus.SCHEDULED
    )
    completed_at = models.DateField(null=True, blank=True)
    completion_notes = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="created_asset_maintenance"
    )
    completed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="completed_asset_maintenance",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "operations_asset_maintenance"
        ordering = ["status", "due_at"]
        indexes = [models.Index(fields=["asset", "status", "due_at"])]


class MediaItem(BranchRecord):
    title = models.CharField(max_length=255)
    details = models.TextField()
    status = models.CharField(max_length=20, default="DRAFT")

    class Meta:
        db_table = "operations_media_item"
        ordering = ["-created_at"]


class ContentType(models.TextChoices):
    PAGE = "PAGE", "Website page"
    NEWS = "NEWS", "News article"
    SERMON = "SERMON", "Sermon"
    SERMON_SERIES = "SERMON_SERIES", "Sermon series"
    GALLERY = "GALLERY", "Gallery album"
    GALLERY_IMAGE = "GALLERY_IMAGE", "Gallery image"
    GALLERY_VIDEO = "GALLERY_VIDEO", "Gallery video"
    LIVESTREAM = "LIVESTREAM", "Livestream"
    MEDIA = "MEDIA", "Media resource"


class ContentStatus(models.TextChoices):
    DRAFT = "DRAFT", "Draft"
    IN_REVIEW = "IN_REVIEW", "In review"
    APPROVED = "APPROVED", "Approved"
    SCHEDULED = "SCHEDULED", "Scheduled"
    PUBLISHED = "PUBLISHED", "Published"
    REJECTED = "REJECTED", "Changes requested"
    ARCHIVED = "ARCHIVED", "Archived"


class ContentEntry(BranchRecord):
    parent = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.SET_NULL, related_name="children"
    )
    content_type = models.CharField(
        max_length=20, choices=ContentType.choices, default=ContentType.PAGE
    )
    title = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255)
    summary = models.CharField(max_length=500, blank=True)
    details = models.TextField()
    cover_image_url = models.URLField(blank=True)
    media_url = models.URLField(blank=True)
    author_name = models.CharField(max_length=180, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    sort_order = models.PositiveIntegerField(default=0)
    status = models.CharField(
        max_length=20, choices=ContentStatus.choices, default=ContentStatus.DRAFT
    )
    publish_at = models.DateTimeField(null=True, blank=True)
    published_at = models.DateTimeField(null=True, blank=True)
    submitted_at = models.DateTimeField(null=True, blank=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="reviewed_content_entries",
    )
    rejection_reason = models.CharField(max_length=500, blank=True)

    class Meta:
        db_table = "operations_content_entry"
        ordering = ["-updated_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["branch", "slug"], name="unique_content_slug_per_branch"
            )
        ]
        indexes = [
            models.Index(fields=["branch", "content_type", "status"]),
            models.Index(fields=["status", "publish_at"]),
        ]


class ContentRevision(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    content = models.ForeignKey(ContentEntry, on_delete=models.CASCADE, related_name="revisions")
    version = models.PositiveIntegerField()
    snapshot = models.JSONField(default=dict)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "operations_content_revision"
        ordering = ["-version"]
        constraints = [
            models.UniqueConstraint(fields=["content", "version"], name="unique_content_revision_version")
        ]


class PrivacyRequest(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="privacy_requests"
    )
    request_type = models.CharField(
        max_length=10,
        choices=[("EXPORT", "Data export"), ("DELETION", "Account deletion")],
    )
    reason = models.TextField(blank=True)
    status = models.CharField(max_length=20, default="PENDING")
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "operations_privacy_request"
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "request_type"],
                condition=models.Q(status="PENDING"),
                name="one_pending_privacy_request_per_type",
            )
        ]


class HomepageContent(models.Model):
    """Singleton holding the super-admin-managed public homepage document.

    ``content`` stays empty until a Super Admin first saves; the React client
    then falls back to its built-in defaults. ``version`` supports optimistic
    concurrency so two editors cannot silently overwrite each other.
    """

    key = models.CharField(max_length=40, unique=True, default="homepage")
    content = models.JSONField(default=dict, blank=True)
    version = models.PositiveIntegerField(default=0)
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="+",
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "operations_homepage_content"

    def __str__(self):
        return f"Homepage content v{self.version}"


class HomepageRequestKind(models.TextChoices):
    EVENT = "EVENT", "Event registration / RSVP"
    UNIT = "UNIT", "Unit join request"


class HomepageRequestStatus(models.TextChoices):
    NEW = "NEW", "New"
    CONTACTED = "CONTACTED", "Contacted"
    CLOSED = "CLOSED", "Closed"


class HomepageRequest(models.Model):
    """A public visitor's event registration or unit-join request."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    kind = models.CharField(max_length=10, choices=HomepageRequestKind.choices)
    item_id = models.CharField(max_length=64)
    item_title = models.CharField(max_length=180, blank=True)
    name = models.CharField(max_length=120)
    email = models.EmailField()
    matric_no = models.CharField(max_length=40, blank=True)
    consent = models.BooleanField(default=False)
    status = models.CharField(
        max_length=12, choices=HomepageRequestStatus.choices, default=HomepageRequestStatus.NEW
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "operations_homepage_request"
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["kind", "item_id", "email"], name="unique_homepage_request_per_email"
            )
        ]
        indexes = [models.Index(fields=["kind", "item_id"])]
