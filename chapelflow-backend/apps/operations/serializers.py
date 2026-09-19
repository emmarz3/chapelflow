from django.utils.text import slugify
from rest_framework import serializers

from .models import (
    Asset, AssetCategory, AssetLocation, AssetMaintenance, AssetMovement,
    ContentEntry, ContentRevision, ContentType, DutyRoster, FinanceTransaction, MediaItem,
    PrivacyRequest, WorkerLeaveRequest,
)


class DutyRosterSerializer(serializers.ModelSerializer):
    class Meta:
        model = DutyRoster
        fields = ["id", "branch", "title", "details", "status", "created_at"]
        read_only_fields = ["id", "branch", "status", "created_at"]


class WorkerLeaveRequestSerializer(serializers.ModelSerializer):
    class Meta:
        model = WorkerLeaveRequest
        fields = ["id", "branch", "reason", "status", "created_at"]
        read_only_fields = ["id", "branch", "status", "created_at"]


class FinanceTransactionSerializer(serializers.ModelSerializer):
    class Meta:
        model = FinanceTransaction
        fields = [
            "id", "branch", "description", "amount", "category",
            "transaction_type", "status", "created_at",
        ]
        read_only_fields = ["id", "branch", "status", "created_at"]

    def validate_amount(self, value):
        if value <= 0:
            raise serializers.ValidationError("Amount must be greater than zero.")
        return value


class AssetSerializer(serializers.ModelSerializer):
    asset_tag = serializers.CharField(required=False, allow_blank=True)
    category_name = serializers.CharField(source="category.name", read_only=True)
    location_name = serializers.CharField(source="location.name", read_only=True)
    custodian_display = serializers.SerializerMethodField()
    low_stock = serializers.SerializerMethodField()

    def get_custodian_display(self, asset):
        if asset.custodian:
            return asset.custodian.full_name or asset.custodian.email
        return asset.custodian_name

    def get_low_stock(self, asset):
        return (
            asset.tracking_mode == "STOCK"
            and asset.quantity_on_hand <= asset.reorder_level
        )

    class Meta:
        model = Asset
        fields = [
            "id", "branch", "name", "details", "category", "category_name", "location", "location_name",
            "asset_tag", "serial_number", "tracking_mode", "quantity_on_hand", "reorder_level",
            "unit_of_measure", "condition", "custodian_name", "custodian", "custodian_display",
            "status", "next_maintenance_at", "last_maintenance_at", "low_stock", "created_at", "updated_at",
        ]
        read_only_fields = ["id", "branch", "status", "last_maintenance_at", "low_stock", "created_at", "updated_at"]

    def validate(self, attrs):
        tracking_mode = attrs.get("tracking_mode", getattr(self.instance, "tracking_mode", "SERIALIZED"))
        quantity = attrs.get("quantity_on_hand", getattr(self.instance, "quantity_on_hand", 1))
        asset_tag = attrs.get("asset_tag", getattr(self.instance, "asset_tag", ""))
        if tracking_mode == "SERIALIZED" and quantity not in {0, 1}:
            raise serializers.ValidationError({"quantity_on_hand": ["Individual assets can only have a quantity of 0 or 1."]})
        if tracking_mode == "SERIALIZED" and not asset_tag:
            raise serializers.ValidationError({"asset_tag": ["An asset tag is required for an individual asset."]})
        return attrs


class AssetCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = AssetCategory
        fields = ["id", "branch", "name", "description", "created_at", "updated_at"]
        read_only_fields = ["id", "branch", "created_at", "updated_at"]


class AssetLocationSerializer(serializers.ModelSerializer):
    class Meta:
        model = AssetLocation
        fields = ["id", "branch", "name", "description", "is_active", "created_at", "updated_at"]
        read_only_fields = ["id", "branch", "created_at", "updated_at"]


class AssetMovementSerializer(serializers.ModelSerializer):
    recorded_by_name = serializers.CharField(source="recorded_by.full_name", read_only=True)

    class Meta:
        model = AssetMovement
        fields = [
            "id", "asset", "movement_type", "quantity_change", "quantity_after", "from_location",
            "to_location", "custodian_name", "custodian", "reason", "recorded_by", "recorded_by_name", "created_at",
        ]
        read_only_fields = ["id", "asset", "quantity_change", "quantity_after", "recorded_by", "recorded_by_name", "created_at"]


class AssetMaintenanceSerializer(serializers.ModelSerializer):
    class Meta:
        model = AssetMaintenance
        fields = [
            "id", "asset", "title", "details", "due_at", "status", "completed_at", "completion_notes",
            "created_by", "completed_by", "created_at", "updated_at",
        ]
        read_only_fields = ["id", "asset", "status", "completed_at", "created_by", "completed_by", "created_at", "updated_at"]


class MediaItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = MediaItem
        fields = ["id", "branch", "title", "details", "status", "created_at", "updated_at"]
        read_only_fields = ["id", "branch", "status", "created_at", "updated_at"]


class ContentEntrySerializer(serializers.ModelSerializer):
    slug = serializers.SlugField(required=False)

    class Meta:
        model = ContentEntry
        fields = [
            "id", "branch", "parent", "content_type", "title", "slug",
            "summary", "details", "cover_image_url", "media_url",
            "author_name", "metadata", "sort_order", "status", "publish_at",
            "published_at", "submitted_at", "reviewed_at", "reviewed_by",
            "rejection_reason", "created_at", "updated_at",
        ]
        read_only_fields = [
            "id", "branch", "status", "published_at", "submitted_at",
            "reviewed_at", "reviewed_by", "rejection_reason", "created_at", "updated_at",
        ]

    def validate(self, attrs):
        title = attrs.get("title", getattr(self.instance, "title", ""))
        attrs["slug"] = attrs.get("slug") or slugify(title)
        content_type = attrs.get(
            "content_type", getattr(self.instance, "content_type", ContentType.PAGE)
        )
        media_url = attrs.get("media_url", getattr(self.instance, "media_url", ""))
        author_name = attrs.get("author_name", getattr(self.instance, "author_name", ""))
        if content_type in {
            ContentType.SERMON, ContentType.MEDIA,
            ContentType.GALLERY_IMAGE, ContentType.LIVESTREAM,
        } and not media_url:
            raise serializers.ValidationError({"media_url": ["A media or stream URL is required for this content type."]})
        if content_type == ContentType.SERMON and not author_name:
            raise serializers.ValidationError({"author_name": ["A speaker name is required for a sermon."]})
        parent = attrs.get("parent", getattr(self.instance, "parent", None))
        if content_type == ContentType.GALLERY_IMAGE and (
            parent is None or parent.content_type != ContentType.GALLERY
        ):
            raise serializers.ValidationError({"parent": ["Gallery images must belong to a gallery album."]})
        return attrs


class ContentRevisionSerializer(serializers.ModelSerializer):
    class Meta:
        model = ContentRevision
        fields = ["id", "version", "snapshot", "created_by", "created_at"]
        read_only_fields = fields


class PrivacyRequestSerializer(serializers.ModelSerializer):
    class Meta:
        model = PrivacyRequest
        fields = ["id", "request_type", "reason", "status", "created_at", "completed_at"]
        read_only_fields = ["id", "status", "created_at", "completed_at"]
