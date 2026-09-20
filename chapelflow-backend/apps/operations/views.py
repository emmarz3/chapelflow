import json

from django.core.serializers.json import DjangoJSONEncoder
from django.db import transaction
from django.db.models import Count, F, Max, Q
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from apps.attendance.models import AttendanceRecord
from apps.audit.models import AuditAction, AuditLog
from apps.audit.services import write_audit_log
from apps.communications.models import Announcement, AnnouncementStatus, AudienceType
from apps.communications.services import authorize_audience
from apps.communications.tasks import dispatch_announcement
from apps.members.models import Member, MembershipStatus
from apps.ministries.models import Group
from apps.notifications.models import NotificationChannel
from apps.organizations.models import Branch
from common.constants.roles import PermissionCodes, Roles
from common.permissions.rbac import user_has_completed_required_mfa
from common.permissions.inventory import user_has_inventory_access
from common.permissions.media import is_media_unit_leader, user_has_media_management_access
from common.permissions.scoping import get_accessible_branch_ids
from common.utils.responses import success_response

from .models import (
    Asset, AssetCategory, AssetLocation, AssetMaintenance, AssetMaintenanceStatus,
    AssetMovement, AssetMovementType, AssetStatus, AssetTrackingMode,
    ContentEntry, ContentRevision, ContentStatus, ContentType,
    DutyRoster, FinanceTransaction, MediaItem, PrivacyRequest, WorkerLeaveRequest,
)
from .serializers import (
    AssetCategorySerializer, AssetLocationSerializer, AssetMaintenanceSerializer,
    AssetMovementSerializer, AssetSerializer, ContentEntrySerializer, ContentRevisionSerializer, DutyRosterSerializer,
    FinanceTransactionSerializer, MediaItemSerializer, PrivacyRequestSerializer,
    WorkerLeaveRequestSerializer,
)


ADMIN_ROLES = {Roles.SUPER_ADMIN, Roles.CHAPEL_ADMIN}


def _role(user):
    return user.get_role_code() if hasattr(user, "get_role_code") else user.role


def _require_permission(user, code, *, admin_only=False):
    if not user_has_completed_required_mfa(user):
        raise PermissionDenied("Complete required MFA before using this feature.")
    role = _role(user)
    if role == Roles.SUPER_ADMIN:
        return
    if admin_only:
        if role not in ADMIN_ROLES:
            raise PermissionDenied("You do not have permission to manage this module.")
        return
    if not user.has_perm_code(code):
        raise PermissionDenied("You do not have permission to manage this module.")


def _branch_for_create(user):
    if user.branch_id:
        return user.branch
    raise ValidationError({"branch": "Assign this account to a branch before creating records."})


MEDIA_CONTENT_TYPES = {
    ContentType.SERMON, ContentType.SERMON_SERIES, ContentType.GALLERY,
    ContentType.GALLERY_IMAGE, ContentType.GALLERY_VIDEO, ContentType.LIVESTREAM, ContentType.MEDIA,
}


def _require_content_access(user):
    if not user_has_completed_required_mfa(user):
        raise PermissionDenied("Complete required MFA before managing public content.")
    if _role(user) not in {Roles.SUPER_ADMIN, Roles.CHAPEL_ADMIN, Roles.CHAPLAIN}:
        raise PermissionDenied("You do not have permission to manage public content.")


def _require_media_access(user):
    if not user_has_completed_required_mfa(user):
        raise PermissionDenied("Complete required MFA before managing public media.")
    if not user_has_media_management_access(user):
        raise PermissionDenied("Only the Chaplain, Media Unit Leader, or Social Media Unit Leader can manage public media.")


def _require_entry_content_access(user, entry):
    if entry.content_type in MEDIA_CONTENT_TYPES:
        _require_media_access(user)
        if is_media_unit_leader(user) and entry.created_by_id != user.id:
            raise PermissionDenied("Media unit leaders can manage only media they created.")
        return
    _require_content_access(user)


def _require_inventory_access(user):
    if not user_has_completed_required_mfa(user):
        raise PermissionDenied("Complete required MFA before managing inventory.")
    if not user_has_inventory_access(user):
        raise PermissionDenied(
            "Inventory is restricted to the Chaplain, Student Chaplain, and Chapel Protocol Unit Leader."
        )


def _scope(queryset, user):
    return queryset.filter(branch_id__in=get_accessible_branch_ids(user))


def _rows(queryset, mapper):
    return [mapper(item) for item in queryset[:200]]


class ModuleCollectionView(APIView):
    permission_classes = [IsAuthenticated]

    definitions = {
        "workers": (DutyRoster, DutyRosterSerializer, PermissionCodes.VOLUNTEERS_VIEW, PermissionCodes.VOLUNTEERS_ASSIGN),
        "finance": (FinanceTransaction, FinanceTransactionSerializer, PermissionCodes.FINANCE_VIEW, PermissionCodes.FINANCE_CREATE),
    }

    def get_definition(self, module):
        try:
            return self.definitions[module]
        except KeyError as exc:
            raise ValidationError({"module": "Unknown operations module."}) from exc

    def get(self, request, module):
        model, _, view_code, _ = self.get_definition(module)
        _require_permission(request.user, view_code, admin_only=view_code is None)
        search = request.query_params.get("search", "").strip()
        status = request.query_params.get("status", "").strip().upper()
        queryset = _scope(model.objects.all(), request.user)
        title_field = "description" if module == "finance" else "title"
        if search:
            queryset = queryset.filter(**{f"{title_field}__icontains": search})
        if status and status not in {"ATTENTION", "RECENT"}:
            queryset = queryset.filter(status=status)

        def mapper(item):
            if module == "finance":
                return {
                    "id": str(item.id), "primary": item.description,
                    "secondary": item.category,
                    "detail": f"{item.amount} NGN", "status": item.status,
                }
            primary = item.title
            detail = item.details
            return {
                "id": str(item.id), "primary": primary,
                "secondary": item.branch.name, "detail": detail,
                "status": item.status,
            }

        rows = _rows(queryset, mapper)
        return success_response(rows)

    def post(self, request, module):
        _, serializer_class, _, create_code = self.get_definition(module)
        _require_permission(request.user, create_code, admin_only=create_code is None)
        payload = request.data.copy()
        if module == "workers":
            payload["details"] = payload.get("detail", "")
        elif module == "finance":
            payload["description"] = payload.get("title", "")
            payload["transaction_type"] = "EXPENSE" if str(payload.get("category", "")).upper() == "EXPENSE" else "INCOME"
        else:
            payload["details"] = payload.get("detail", "")
        serializer = serializer_class(data=payload)
        serializer.is_valid(raise_exception=True)
        instance = serializer.save(branch=_branch_for_create(request.user), created_by=request.user)
        write_audit_log(
            AuditAction.CREATE, f"operations.{module}", instance.id,
            metadata={"title": payload.get("title", "")}, user=request.user,
        )
        return success_response(serializer_class(instance).data, message="Record created.", status=201)


def _asset_row(asset):
    low_stock = (
        asset.tracking_mode == AssetTrackingMode.STOCK
        and asset.quantity_on_hand <= asset.reorder_level
    )
    return {
        "id": str(asset.id),
        "primary": asset.name,
        "secondary": asset.category.name if asset.category else "Uncategorised",
        "detail": asset.details,
        "status": "LOW_STOCK" if low_stock else asset.status,
        "category": str(asset.category_id or ""),
        "category_name": asset.category.name if asset.category else "",
        "location": str(asset.location_id or ""),
        "location_name": asset.location.name if asset.location else "",
        "asset_tag": asset.asset_tag,
        "serial_number": asset.serial_number,
        "tracking_mode": asset.tracking_mode,
        "quantity_on_hand": asset.quantity_on_hand,
        "reorder_level": asset.reorder_level,
        "unit_of_measure": asset.unit_of_measure,
        "condition": asset.condition,
        "custodian_name": asset.custodian.full_name if asset.custodian else asset.custodian_name,
        "next_maintenance_at": asset.next_maintenance_at,
        "low_stock": low_stock,
    }


def _assert_inventory_references(branch, category=None, location=None):
    if category and category.branch_id != branch.id:
        raise ValidationError({"category": "Choose a category from this chapel branch."})
    if location and location.branch_id != branch.id:
        raise ValidationError({"location": "Choose a location from this chapel branch."})


def _resolve_inventory_reference(request, branch, payload, field, model):
    """Accept an existing id or create a branch-local category/location from its display name."""
    name = str(payload.pop(f"{field}_name", "") or "").strip()
    if payload.get(field) or not name:
        return None
    instance, _ = model.objects.get_or_create(branch=branch, name=name, defaults={"created_by": request.user})
    payload[field] = str(instance.id)
    return instance


class AssetCollectionView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        _require_inventory_access(request.user)
        queryset = _scope(
            Asset.objects.select_related("branch", "category", "location", "custodian"), request.user
        )
        search = request.query_params.get("search", "").strip()
        status = request.query_params.get("status", "").strip().upper()
        if search:
            queryset = queryset.filter(
                Q(name__icontains=search)
                | Q(asset_tag__icontains=search)
                | Q(serial_number__icontains=search)
                | Q(custodian_name__icontains=search)
            )
        if status == "LOW_STOCK":
            queryset = queryset.filter(
                tracking_mode=AssetTrackingMode.STOCK,
                quantity_on_hand__lte=F("reorder_level"),
            )
        elif status and status not in {"ATTENTION", "RECENT"}:
            queryset = queryset.filter(status=status)
        return success_response(_rows(queryset.order_by("name"), _asset_row))

    def post(self, request):
        _require_inventory_access(request.user)
        branch = _branch_for_create(request.user)
        payload = request.data.copy()
        payload["name"] = payload.get("name") or payload.get("title") or ""
        payload["details"] = payload.get("details") or payload.get("detail") or ""
        _resolve_inventory_reference(request, branch, payload, "category", AssetCategory)
        _resolve_inventory_reference(request, branch, payload, "location", AssetLocation)
        serializer = AssetSerializer(data=payload)
        serializer.is_valid(raise_exception=True)
        _assert_inventory_references(
            branch,
            serializer.validated_data.get("category"),
            serializer.validated_data.get("location"),
        )
        with transaction.atomic():
            asset = serializer.save(branch=branch, created_by=request.user)
            AssetMovement.objects.create(
                asset=asset,
                movement_type=AssetMovementType.ADJUSTMENT,
                quantity_change=asset.quantity_on_hand,
                quantity_after=asset.quantity_on_hand,
                to_location=asset.location,
                custodian_name=asset.custodian_name,
                custodian=asset.custodian,
                reason="Opening inventory balance",
                recorded_by=request.user,
            )
        write_audit_log(
            AuditAction.CREATE, "operations.asset", asset.id,
            metadata={"asset_tag": asset.asset_tag, "quantity_on_hand": asset.quantity_on_hand}, user=request.user,
        )
        return success_response(_asset_row(asset), message="Asset added to the inventory register.", status=201)


class AssetMovementView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        _require_inventory_access(request.user)
        action = str(request.data.get("action", "issue")).strip().lower()
        action_types = {
            "issue": AssetMovementType.ISSUE,
            "return": AssetMovementType.RETURN,
            "transfer": AssetMovementType.TRANSFER,
            "adjust": AssetMovementType.ADJUSTMENT,
            "maintenance_start": AssetMovementType.MAINTENANCE_START,
            "maintenance_complete": AssetMovementType.MAINTENANCE_COMPLETE,
        }
        if action not in action_types:
            raise ValidationError({"action": "Choose issue, return, transfer, adjust, maintenance_start, or maintenance_complete."})
        try:
            quantity = int(request.data.get("quantity", 1))
        except (TypeError, ValueError) as exc:
            raise ValidationError({"quantity": "Enter a whole number."}) from exc
        if action != "adjust" and quantity <= 0:
            raise ValidationError({"quantity": "Quantity must be greater than zero."})
        if action == "adjust" and quantity == 0:
            raise ValidationError({"quantity": "Adjustment cannot be zero."})

        with transaction.atomic():
            asset = _scope(
                Asset.objects.select_for_update().select_related("location", "custodian"), request.user
            ).filter(pk=pk).first()
            if not asset:
                raise PermissionDenied("Asset not found in your branch scope.")
            location_id = request.data.get("location") or request.data.get("to_location")
            target_location = None
            if location_id:
                target_location = AssetLocation.objects.filter(pk=location_id, branch=asset.branch, is_active=True).first()
                if not target_location:
                    raise ValidationError({"location": "Choose an active location from this chapel branch."})
            quantity_change = 0
            prior_location = asset.location
            if action == "issue":
                if asset.status != AssetStatus.AVAILABLE:
                    raise ValidationError({"status": "Only available assets can be issued."})
                if quantity > asset.quantity_on_hand:
                    raise ValidationError({"quantity": "Cannot issue more items than are in stock."})
                quantity_change = -quantity
                asset.quantity_on_hand -= quantity
                if asset.tracking_mode == AssetTrackingMode.SERIALIZED:
                    if quantity != 1:
                        raise ValidationError({"quantity": "An individual asset is issued one at a time."})
                    asset.status = AssetStatus.ISSUED
                asset.custodian_name = str(request.data.get("custodian_name", "")).strip()
                asset.custodian = None
            elif action == "return":
                if asset.tracking_mode == AssetTrackingMode.SERIALIZED and asset.status != AssetStatus.ISSUED:
                    raise ValidationError({"status": "Only issued individual assets can be returned."})
                quantity_change = quantity
                asset.quantity_on_hand += quantity
                if asset.tracking_mode == AssetTrackingMode.SERIALIZED:
                    if quantity != 1:
                        raise ValidationError({"quantity": "An individual asset is returned one at a time."})
                    asset.status = AssetStatus.AVAILABLE
                asset.custodian_name = ""
                asset.custodian = None
            elif action == "transfer":
                if not target_location:
                    raise ValidationError({"location": "Choose the receiving location."})
                asset.location = target_location
            elif action == "adjust":
                if asset.tracking_mode != AssetTrackingMode.STOCK:
                    raise ValidationError({"tracking_mode": "Only stock items can be adjusted."})
                if asset.quantity_on_hand + quantity < 0:
                    raise ValidationError({"quantity": "Adjustment would reduce stock below zero."})
                quantity_change = quantity
                asset.quantity_on_hand += quantity
            elif action == "maintenance_start":
                if asset.status != AssetStatus.AVAILABLE:
                    raise ValidationError({"status": "Only available assets can be sent for maintenance."})
                asset.status = AssetStatus.MAINTENANCE
            elif action == "maintenance_complete":
                if asset.status != AssetStatus.MAINTENANCE:
                    raise ValidationError({"status": "This asset is not currently in maintenance."})
                asset.status = AssetStatus.AVAILABLE
                asset.last_maintenance_at = timezone.localdate()

            if target_location and action != "transfer":
                asset.location = target_location
            asset.save()
            movement = AssetMovement.objects.create(
                asset=asset,
                movement_type=action_types[action],
                quantity_change=quantity_change,
                quantity_after=asset.quantity_on_hand,
                from_location=prior_location,
                to_location=asset.location,
                custodian_name=asset.custodian_name if action == "issue" else "",
                custodian=asset.custodian,
                reason=str(request.data.get("reason", "")).strip(),
                recorded_by=request.user,
            )
        write_audit_log(
            AuditAction.UPDATE, "operations.asset", asset.id,
            metadata={"movement": movement.movement_type, "quantity_change": movement.quantity_change}, user=request.user,
        )
        return success_response(
            {"asset": _asset_row(asset), "movement": AssetMovementSerializer(movement).data},
            message="Inventory movement recorded.",
        )


class AssetMaintenanceCollectionView(APIView):
    permission_classes = [IsAuthenticated]

    def get_asset(self, user, pk):
        asset = _scope(Asset.objects.all(), user).filter(pk=pk).first()
        if not asset:
            raise PermissionDenied("Asset not found in your branch scope.")
        return asset

    def get(self, request, pk):
        _require_inventory_access(request.user)
        asset = self.get_asset(request.user, pk)
        return success_response(AssetMaintenanceSerializer(asset.maintenance_records.all(), many=True).data)

    def post(self, request, pk):
        _require_inventory_access(request.user)
        asset = self.get_asset(request.user, pk)
        serializer = AssetMaintenanceSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        maintenance = serializer.save(asset=asset, created_by=request.user)
        if asset.next_maintenance_at is None or maintenance.due_at < asset.next_maintenance_at:
            asset.next_maintenance_at = maintenance.due_at
            asset.save(update_fields=["next_maintenance_at", "updated_at"])
        write_audit_log(
            AuditAction.CREATE, "operations.asset_maintenance", maintenance.id,
            metadata={"asset_id": str(asset.id), "due_at": maintenance.due_at.isoformat()}, user=request.user,
        )
        return success_response(AssetMaintenanceSerializer(maintenance).data, message="Maintenance scheduled.", status=201)


class AssetMaintenanceActionView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk, maintenance_pk, action):
        _require_inventory_access(request.user)
        asset = _scope(Asset.objects.all(), request.user).filter(pk=pk).first()
        maintenance = AssetMaintenance.objects.filter(pk=maintenance_pk, asset=asset).first() if asset else None
        if not maintenance:
            raise PermissionDenied("Maintenance record not found in your branch scope.")
        if maintenance.status != AssetMaintenanceStatus.SCHEDULED:
            raise ValidationError({"status": "Only scheduled maintenance can be changed."})
        if action == "complete":
            maintenance.status = AssetMaintenanceStatus.COMPLETED
            maintenance.completed_at = timezone.localdate()
            maintenance.completed_by = request.user
            maintenance.completion_notes = str(request.data.get("completion_notes", "")).strip()
            maintenance.save()
            asset.last_maintenance_at = maintenance.completed_at
            asset.next_maintenance_at = (
                asset.maintenance_records.filter(status=AssetMaintenanceStatus.SCHEDULED)
                .order_by("due_at").values_list("due_at", flat=True).first()
            )
            asset.save(update_fields=["last_maintenance_at", "next_maintenance_at", "updated_at"])
        elif action == "cancel":
            maintenance.status = AssetMaintenanceStatus.CANCELLED
        else:
            raise ValidationError({"action": "Choose complete or cancel."})
        if action == "cancel":
            maintenance.save()
        write_audit_log(
            AuditAction.UPDATE, "operations.asset_maintenance", maintenance.id,
            metadata={"asset_id": str(asset.id), "action": action}, user=request.user,
        )
        return success_response(
            AssetMaintenanceSerializer(maintenance).data,
            message="Maintenance completed." if action == "complete" else "Maintenance cancelled.",
        )


class AssetHistoryView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        _require_inventory_access(request.user)
        asset = _scope(
            Asset.objects.select_related("category", "location", "custodian"), request.user
        ).filter(pk=pk).first()
        if not asset:
            raise PermissionDenied("Asset not found in your branch scope.")
        audit_entries = AuditLog.objects.filter(
            resource_type="operations.asset", resource_id=str(asset.id)
        ).values("id", "action", "metadata", "created_at")[:100]
        return success_response({
            "asset": AssetSerializer(asset).data,
            "movements": AssetMovementSerializer(asset.movements.select_related("recorded_by"), many=True).data,
            "maintenance": AssetMaintenanceSerializer(asset.maintenance_records.all(), many=True).data,
            "audit": list(audit_entries),
        })


class InventoryReferenceCollectionView(APIView):
    permission_classes = [IsAuthenticated]
    model = None
    serializer_class = None

    def get(self, request):
        _require_inventory_access(request.user)
        queryset = _scope(self.model.objects.all(), request.user)
        return success_response(self.serializer_class(queryset, many=True).data)

    def post(self, request):
        _require_inventory_access(request.user)
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        instance = serializer.save(branch=_branch_for_create(request.user), created_by=request.user)
        write_audit_log(AuditAction.CREATE, f"operations.{self.model._meta.model_name}", instance.id, user=request.user)
        return success_response(self.serializer_class(instance).data, message="Inventory reference created.", status=201)


class AssetCategoryCollectionView(InventoryReferenceCollectionView):
    model = AssetCategory
    serializer_class = AssetCategorySerializer


class AssetLocationCollectionView(InventoryReferenceCollectionView):
    model = AssetLocation
    serializer_class = AssetLocationSerializer


class InventoryAlertView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        _require_inventory_access(request.user)
        asset_queryset = _scope(Asset.objects.select_related("category", "location"), request.user)
        low_stock = asset_queryset.filter(
            tracking_mode=AssetTrackingMode.STOCK,
            quantity_on_hand__lte=F("reorder_level"),
        )
        due_maintenance = AssetMaintenance.objects.filter(
            asset__in=asset_queryset,
            status=AssetMaintenanceStatus.SCHEDULED,
            due_at__lte=timezone.localdate(),
        ).select_related("asset")
        return success_response({
            "low_stock": _rows(low_stock, _asset_row),
            "maintenance_due": AssetMaintenanceSerializer(due_maintenance, many=True).data,
        })


class RosterAcknowledgeView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        _require_permission(request.user, PermissionCodes.VOLUNTEERS_UPDATE)
        roster = _scope(DutyRoster.objects.all(), request.user).filter(pk=pk).first()
        if not roster:
            raise PermissionDenied("Roster not found in your branch scope.")
        roster.status = "ACKNOWLEDGED"
        roster.save(update_fields=["status", "updated_at"])
        return success_response(DutyRosterSerializer(roster).data, message="Roster acknowledged.")


class CommunicationOperationsView(APIView):
    permission_classes = [IsAuthenticated]

    @staticmethod
    def _row(item):
        groups = list(item.target_groups.all())
        target = item.get_audience_type_display()
        if groups:
            target = ", ".join(group.name for group in groups)
        return {
            "id": str(item.id), "primary": item.title,
            "secondary": ", ".join(item.channels or [NotificationChannel.EMAIL]),
            "detail": item.body, "status": item.status,
            "audience_type": item.audience_type,
            "target_groups": [str(group.id) for group in groups],
            "target_label": target,
            "publish_at": item.publish_at,
        }

    @staticmethod
    def _channels(value):
        values = value if isinstance(value, list) else str(value or "EMAIL").split(",")
        channels = [str(channel).strip().upper().replace("-", "_") for channel in values]
        channels = list(dict.fromkeys(channel for channel in channels if channel))
        valid = set(NotificationChannel.values)
        if not channels or any(channel not in valid for channel in channels):
            raise ValidationError({"channels": "Select one or more supported delivery channels."})
        return channels

    @staticmethod
    def _publish_at(value):
        if not value:
            return timezone.now()
        publish_at = parse_datetime(str(value))
        if publish_at is None:
            raise ValidationError({"publish_at": "Enter a valid date and time."})
        return timezone.make_aware(publish_at) if timezone.is_naive(publish_at) else publish_at

    def get(self, request):
        _require_permission(request.user, PermissionCodes.COMMUNICATIONS_VIEW)
        queryset = _scope(
            Announcement.objects.select_related("branch").prefetch_related("target_groups").order_by("-created_at"),
            request.user,
        )
        search = request.query_params.get("search", "").strip()
        if search:
            queryset = queryset.filter(title__icontains=search)
        return success_response(_rows(queryset, self._row))

    def post(self, request):
        _require_permission(request.user, PermissionCodes.COMMUNICATIONS_CREATE)
        branch = _branch_for_create(request.user)
        title = str(request.data.get("title", "")).strip()
        body = str(request.data.get("message", "")).strip()
        if not title or not body:
            raise ValidationError({"title": "A title and message are required."})
        channels = self._channels(request.data.get("channels", request.data.get("channel")))
        audience_type = str(request.data.get("audience_type", AudienceType.EVERYONE)).upper()
        if audience_type not in AudienceType.values:
            raise ValidationError({"audience_type": "Select a valid broadcast audience."})
        group_ids = request.data.get("target_groups", [])
        if isinstance(group_ids, str):
            group_ids = [group_id.strip() for group_id in group_ids.split(",") if group_id.strip()]
        if not isinstance(group_ids, list):
            raise ValidationError({"target_groups": "Select valid chapel groups."})
        groups = list(Group.objects.filter(id__in=group_ids, branch=branch, is_active=True))
        if len(groups) != len(set(map(str, group_ids))):
            raise ValidationError({"target_groups": "Choose active groups from this chapel branch."})
        if audience_type in {AudienceType.CUSTOM, AudienceType.FELLOWSHIP, AudienceType.UNIT, AudienceType.MINISTRY} and not groups:
            raise ValidationError({"target_groups": "Choose at least one chapel group for this broadcast."})
        target_community = str(request.data.get("target_community", "")).strip().upper()
        publish_at = self._publish_at(request.data.get("publish_at"))
        authorize_audience(
            user=request.user, branch=branch, audience_type=audience_type,
            target_groups=groups, target_community=target_community,
        )
        announcement = Announcement.objects.create(
            branch=branch, title=title, body=body, audience_type=audience_type,
            channels=channels, target_community=target_community, publish_at=publish_at,
            created_by=request.user, status=AnnouncementStatus.DRAFT,
        )
        if groups:
            announcement.target_groups.set(groups)
        write_audit_log(
            AuditAction.COMMUNICATION_ACTION, "communications.announcement", announcement.id,
            metadata={"status": "DRAFT", "audience_type": audience_type, "channels": channels}, user=request.user,
        )
        announcement = Announcement.objects.prefetch_related("target_groups").get(pk=announcement.pk)
        return success_response(self._row(announcement), message="Broadcast draft created.", status=201)


class CommunicationSendView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        _require_permission(request.user, PermissionCodes.COMMUNICATIONS_SEND)
        announcement = _scope(Announcement.objects.all(), request.user).filter(pk=pk).first()
        if not announcement:
            raise PermissionDenied("Broadcast not found in your branch scope.")
        if announcement.status != AnnouncementStatus.DRAFT:
            raise ValidationError({"status": "Only draft broadcasts can be sent."})
        authorize_audience(
            user=request.user, branch=announcement.branch,
            audience_type=announcement.audience_type,
            target_groups=announcement.target_groups.all(),
            target_community=announcement.target_community,
        )
        if announcement.publish_at > timezone.now():
            announcement.status = AnnouncementStatus.SCHEDULED
            announcement.save(update_fields=["status"])
            return success_response(
                {"id": str(announcement.id), "status": announcement.status},
                message="Broadcast scheduled for delivery.",
            )
        announcement.status = AnnouncementStatus.QUEUED
        announcement.save(update_fields=["status"])
        dispatch_announcement.delay(str(announcement.id))
        return success_response({"id": str(announcement.id), "status": announcement.status}, message="Broadcast queued.")


class BranchOperationsView(APIView):
    permission_classes = [IsAuthenticated]

    def _authorize(self, user):
        if _role(user) != Roles.SUPER_ADMIN:
            raise PermissionDenied("Only the Super Admin can manage branches.")
        if not user_has_completed_required_mfa(user):
            raise PermissionDenied("Complete required MFA before managing branches.")

    def get(self, request):
        self._authorize(request.user)
        queryset = Branch.objects.select_related("organization").order_by("name")
        search = request.query_params.get("search", "").strip()
        if search:
            queryset = queryset.filter(name__icontains=search)
        return success_response(_rows(queryset, lambda item: {
            "id": str(item.id), "primary": item.name,
            "secondary": item.organization.name,
            "detail": item.address or item.city or item.branch_type,
            "status": "ACTIVE" if item.is_active else "INACTIVE",
        }))

    def post(self, request):
        self._authorize(request.user)
        organization = request.user.branch.organization if request.user.branch_id else None
        if organization is None:
            raise ValidationError({"organization": "Assign the Super Admin to an organization before creating branches."})
        name = str(request.data.get("title", "")).strip()
        if not name:
            raise ValidationError({"title": "Branch name is required."})
        branch = Branch.objects.create(
            organization=organization,
            name=name,
            address=request.data.get("detail", ""),
        )
        write_audit_log(AuditAction.CREATE, "organizations.branch", branch.id, metadata={"name": branch.name}, user=request.user)
        return success_response({
            "id": str(branch.id), "primary": branch.name,
            "secondary": organization.name, "detail": branch.address,
            "status": "ACTIVE",
        }, message="Branch created.", status=201)


def _content_snapshot(entry):
    return json.loads(json.dumps(ContentEntrySerializer(entry).data, cls=DjangoJSONEncoder))


def _create_content_revision(entry, user):
    latest = entry.revisions.aggregate(value=Max("version"))["value"] or 0
    return ContentRevision.objects.create(
        content=entry,
        version=latest + 1,
        snapshot=_content_snapshot(entry),
        created_by=user,
    )


def _content_row(entry):
    return {
        "id": str(entry.id),
        "primary": entry.title,
        "secondary": entry.get_content_type_display(),
        "detail": entry.summary or entry.details[:180],
        "status": entry.status,
        "content_type": entry.content_type,
        "slug": entry.slug,
        "media_url": entry.media_url,
        "cover_image_url": entry.cover_image_url,
        "author_name": entry.author_name,
        "publish_at": entry.publish_at,
        "published_at": entry.published_at,
        "rejection_reason": entry.rejection_reason,
    }


class ContentCollectionView(APIView):
    permission_classes = [IsAuthenticated]
    allowed_types = set(ContentType.values)
    default_type = ContentType.PAGE

    def authorize(self, user):
        _require_content_access(user)

    def restrict_queryset(self, queryset, user):
        return queryset

    def get(self, request):
        self.authorize(request.user)
        queryset = _scope(
            ContentEntry.objects.select_related("branch", "parent", "reviewed_by"), request.user
        ).filter(content_type__in=self.allowed_types)
        queryset = self.restrict_queryset(queryset, request.user)
        search = request.query_params.get("search", "").strip()
        status = request.query_params.get("status", "").strip().upper()
        content_type = request.query_params.get("content_type", "").strip().upper()
        if search:
            queryset = queryset.filter(
                Q(title__icontains=search) | Q(summary__icontains=search) | Q(details__icontains=search)
            )
        if status and status not in {"ATTENTION", "RECENT"}:
            queryset = queryset.filter(status=status)
        if content_type:
            if content_type not in self.allowed_types:
                raise ValidationError({"content_type": "Select a valid content type."})
            queryset = queryset.filter(content_type=content_type)
        return success_response(_rows(queryset.order_by("-updated_at"), _content_row))

    def post(self, request):
        self.authorize(request.user)
        payload = request.data.copy()
        payload["content_type"] = str(payload.get("content_type") or self.default_type).upper()
        payload["details"] = payload.get("details") or payload.get("detail") or ""
        payload["summary"] = payload.get("summary") or payload["details"][:500]
        if "downloadable" in payload:
            metadata = payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {}
            metadata["downloadable"] = str(payload.pop("downloadable")).lower() in {"1", "true", "on", "yes"}
            payload["metadata"] = metadata
        for optional_field in ("parent", "publish_at"):
            if not payload.get(optional_field):
                payload.pop(optional_field, None)
        if payload["content_type"] not in self.allowed_types:
            raise ValidationError({"content_type": "Select a valid content type."})
        serializer = ContentEntrySerializer(data=payload)
        serializer.is_valid(raise_exception=True)
        parent = serializer.validated_data.get("parent")
        branch = _branch_for_create(request.user)
        if parent and parent.branch_id != branch.id:
            raise ValidationError({"parent": "Parent content must belong to the same branch."})
        with transaction.atomic():
            entry = serializer.save(branch=branch, created_by=request.user)
            _create_content_revision(entry, request.user)
        write_audit_log(
            AuditAction.CREATE, "operations.content", entry.id,
            metadata={"content_type": entry.content_type, "status": entry.status}, user=request.user,
        )
        return success_response(_content_row(entry), message="Content draft created.", status=201)


class MediaCollectionView(ContentCollectionView):
    allowed_types = MEDIA_CONTENT_TYPES
    default_type = ContentType.MEDIA

    def authorize(self, user):
        _require_media_access(user)

    def restrict_queryset(self, queryset, user):
        return queryset.filter(created_by=user) if is_media_unit_leader(user) else queryset


class ContentDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request, pk):
        with transaction.atomic():
            entry = _scope(ContentEntry.objects.select_for_update(), request.user).filter(pk=pk).first()
            if not entry:
                raise PermissionDenied("Content entry not found in your branch scope.")
            _require_entry_content_access(request.user, entry)
            if entry.status in {ContentStatus.PUBLISHED, ContentStatus.ARCHIVED}:
                raise ValidationError({"status": "Published or archived content is immutable; create a new draft revision."})
            serializer = ContentEntrySerializer(entry, data=request.data, partial=True)
            serializer.is_valid(raise_exception=True)
            parent = serializer.validated_data.get("parent", entry.parent)
            if parent and parent.branch_id != entry.branch_id:
                raise ValidationError({"parent": "Parent content must belong to the same branch."})
            entry = serializer.save()
            _create_content_revision(entry, request.user)
        write_audit_log(AuditAction.UPDATE, "operations.content", entry.id, metadata={"revision": True}, user=request.user)
        return success_response(_content_row(entry), message="Draft revision saved.")


class ContentRevisionListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        entry = _scope(ContentEntry.objects.all(), request.user).filter(pk=pk).first()
        if not entry:
            raise PermissionDenied("Content entry not found in your branch scope.")
        _require_entry_content_access(request.user, entry)
        return success_response(ContentRevisionSerializer(entry.revisions.all(), many=True).data)


class ContentWorkflowView(APIView):
    permission_classes = [IsAuthenticated]

    reviewer_roles = {Roles.SUPER_ADMIN, Roles.CHAPLAIN}

    def post(self, request, pk, action):
        now = timezone.now()
        with transaction.atomic():
            entry = _scope(ContentEntry.objects.select_for_update(), request.user).filter(pk=pk).first()
            if not entry:
                raise PermissionDenied("Content entry not found in your branch scope.")
            _require_entry_content_access(request.user, entry)
            previous = entry.status
            if action == "submit":
                if entry.status not in {ContentStatus.DRAFT, ContentStatus.REJECTED}:
                    raise ValidationError({"status": "Only a draft or rejected item can be submitted."})
                entry.status = ContentStatus.IN_REVIEW
                entry.submitted_at = now
                entry.rejection_reason = ""
            elif action in {"approve", "reject"}:
                if _role(request.user) not in self.reviewer_roles:
                    raise PermissionDenied("Only a Super Admin or Chaplain can review public content.")
                if entry.status != ContentStatus.IN_REVIEW:
                    raise ValidationError({"status": "Only content in review can be approved or rejected."})
                entry.reviewed_by = request.user
                entry.reviewed_at = now
                if action == "reject":
                    reason = str(request.data.get("reason", "")).strip()
                    if not reason:
                        raise ValidationError({"reason": "Explain the changes required."})
                    entry.status = ContentStatus.REJECTED
                    entry.rejection_reason = reason
                elif entry.publish_at and entry.publish_at > now:
                    entry.status = ContentStatus.SCHEDULED
                else:
                    entry.status = ContentStatus.APPROVED
            elif action == "publish":
                if entry.status not in {ContentStatus.APPROVED, ContentStatus.SCHEDULED}:
                    raise ValidationError({"status": "Content must be approved before publication."})
                if entry.publish_at and entry.publish_at > now:
                    entry.status = ContentStatus.SCHEDULED
                else:
                    entry.status = ContentStatus.PUBLISHED
                    entry.published_at = now
            elif action == "archive":
                if entry.status != ContentStatus.PUBLISHED:
                    raise ValidationError({"status": "Only published content can be archived."})
                entry.status = ContentStatus.ARCHIVED
            else:
                raise ValidationError({"action": "Unknown content workflow action."})
            entry.save()
            _create_content_revision(entry, request.user)
        write_audit_log(
            AuditAction.UPDATE, "operations.content", entry.id,
            metadata={"previous_status": previous, "status": entry.status, "workflow_action": action},
            user=request.user,
        )
        return success_response(_content_row(entry), message=f"Content {action} completed.")


class ContentPublishView(ContentWorkflowView):
    def post(self, request, pk):
        return super().post(request, pk, "publish")


class WorkerLeaveRequestView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        _require_permission(request.user, PermissionCodes.VOLUNTEERS_UPDATE)
        payload = {"reason": request.data.get("reason") or request.data.get("detail") or "Leave requested"}
        serializer = WorkerLeaveRequestSerializer(data=payload)
        serializer.is_valid(raise_exception=True)
        instance = serializer.save(branch=_branch_for_create(request.user), created_by=request.user)
        return success_response(WorkerLeaveRequestSerializer(instance).data, message="Leave request submitted.", status=201)


class AnalyticsOverviewView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        _require_permission(request.user, PermissionCodes.REPORTS_VIEW)
        branch_ids = get_accessible_branch_ids(request.user)
        members = Member.objects.filter(branch_id__in=branch_ids)
        attendance = AttendanceRecord.objects.filter(session__branch_id__in=branch_ids)
        total = members.count()
        active = members.filter(membership_status=MembershipStatus.ACTIVE).count()
        scans = attendance.count()
        by_level = list(
            members.exclude(academic_level="")
            .values("academic_level").annotate(value=Count("id"))
            .order_by("academic_level")
        )
        return success_response({
            "metrics": [
                {"label": "Total members", "value": str(total), "note": "Current authorized scope"},
                {"label": "Active members", "value": str(active), "note": "Active membership records"},
                {"label": "Attendance records", "value": str(scans), "note": "All recorded sessions"},
            ],
            "attendanceTrend": [],
            "byLevel": [{"name": row["academic_level"], "value": row["value"]} for row in by_level],
        })


class PrivacyRequestCreateView(APIView):
    permission_classes = [IsAuthenticated]
    request_type = None

    def post(self, request):
        existing = PrivacyRequest.objects.filter(
            user=request.user, request_type=self.request_type, status="PENDING"
        ).first()
        if existing:
            return success_response(
                {"requestId": str(existing.id)},
                message="A matching privacy request is already pending.",
            )
        serializer = PrivacyRequestSerializer(data={
            "request_type": self.request_type,
            "reason": request.data.get("reason", ""),
        })
        serializer.is_valid(raise_exception=True)
        instance = serializer.save(user=request.user)
        write_audit_log(AuditAction.CREATE, "privacy_request", instance.id, metadata={"type": self.request_type}, user=request.user)
        return success_response({"requestId": str(instance.id)}, message="Privacy request submitted.", status=201)


class DataExportRequestView(PrivacyRequestCreateView):
    request_type = "EXPORT"


class DeletionRequestView(PrivacyRequestCreateView):
    request_type = "DELETION"
