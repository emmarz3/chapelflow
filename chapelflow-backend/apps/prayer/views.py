from django.utils import timezone
from rest_framework import viewsets
from common.viewsets import StandardModelViewSet
from rest_framework.permissions import BasePermission, IsAuthenticated, SAFE_METHODS
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response

from common.constants.roles import Roles, PermissionCodes
from apps.audit.services import write_audit_log
from apps.audit.models import AuditAction
from .models import PrayerNote, PrayerRequest, Testimony, TestimonyStatus
from .serializers import PrayerNoteSerializer, PrayerRequestSerializer, TestimonySerializer
from .notifications import (
    notify_prayer_request_assigned,
    notify_prayer_request_answered,
    notify_prayer_request_created_to_team,
    notify_prayer_request_closed,
)


class PrayerRequestAccess(BasePermission):
    """Protect private care records even when a request is visible to others."""

    def has_permission(self, request, view):
        user = request.user
        if not (user and user.is_authenticated and user.is_active):
            return False
        role = user.get_role_code() if hasattr(user, "get_role_code") else user.role
        if role in Roles.PASTORAL_ACCESS_ROLES:
            from common.permissions.rbac import user_has_completed_required_mfa
            return user_has_completed_required_mfa(user)
        return True

    def has_object_permission(self, request, view, obj):
        user = request.user
        role = user.get_role_code() if hasattr(user, "get_role_code") else user.role
        from common.permissions.rbac import user_has_completed_required_mfa

        if role in Roles.PASTORAL_ACCESS_ROLES:
            return user_has_completed_required_mfa(user)
        is_owner = bool(obj.member_id and getattr(obj.member, "user_id", None) == user.id)
        if request.method in SAFE_METHODS:
            return is_owner or (
                obj.privacy_level == "PUBLIC"
                and obj.branch_id == user.branch_id
                and not obj.is_private
            )
        return is_owner and obj.status == "NEW"


class PastoralStaffOnly(BasePermission):
    """Follow-up notes are never available to a member, including their owner."""

    def has_permission(self, request, view):
        user = request.user
        if not (user and user.is_authenticated and user.is_active):
            return False
        role = user.get_role_code() if hasattr(user, "get_role_code") else user.role
        if role not in Roles.PASTORAL_ACCESS_ROLES:
            return False
        from common.permissions.rbac import user_has_completed_required_mfa
        return user_has_completed_required_mfa(user)


class PrayerRequestViewSet(StandardModelViewSet):
    """
    Privacy model: a member always sees their own requests. Private
    requests from OTHER members are visible only to pastoral-access roles
    or the staff member assigned to the request.
    
    Phase 13 enhancements:
    - Auto-set created_by
    - Comprehensive audit logging
    """
    serializer_class = PrayerRequestSerializer
    permission_classes = [PrayerRequestAccess]
    filterset_fields = ["branch", "status", "category", "assigned_to"]
    permission_action_map = {
        "list": PermissionCodes.PRAYER_VIEW,
        "retrieve": PermissionCodes.PRAYER_VIEW,
        "create": PermissionCodes.PRAYER_CREATE,
        "update": PermissionCodes.PRAYER_UPDATE,
        "partial_update": PermissionCodes.PRAYER_UPDATE,
        "destroy": PermissionCodes.PRAYER_DELETE,
    }

    def get_queryset(self):
        qs = PrayerRequest.objects.select_related("branch", "member", "assigned_to", "created_by").prefetch_related("notes")
        user = self.request.user

        if user.role in Roles.GLOBAL_SCOPE_ROLES or user.role in Roles.PASTORAL_ACCESS_ROLES:
            if user.role in Roles.GLOBAL_SCOPE_ROLES:
                return qs
            return qs.filter(branch_id=user.branch_id) if user.branch_id else qs.none()

        # Ordinary users can see their own requests and moderated public
        # requests in their branch. Fellowship and pastoral visibility is not
        # inferred from a branch alone.
        from django.db.models import Q
        own_member_filter = Q(member__user=user)
        return qs.filter(
            Q(branch_id=user.branch_id)
            & (own_member_filter | Q(privacy_level="PUBLIC", is_private=False))
        )

    def perform_create(self, serializer):
        """
        Phase 13: Auto-set member, branch, created_by, log creation, send notifications.
        """
        member = getattr(self.request.user, "member_profile", None)
        role = self.request.user.get_role_code() if hasattr(self.request.user, "get_role_code") else self.request.user.role
        if role not in Roles.PASTORAL_ACCESS_ROLES and member is None:
            from rest_framework.exceptions import ValidationError

            raise ValidationError({"member": "A student profile is required to submit a prayer request."})
        branch = member.branch if member else serializer.validated_data.get("branch") or self.request.user.branch
        if branch is None:
            from rest_framework.exceptions import ValidationError

            raise ValidationError({"branch": "Choose a chapel branch for this request."})
        instance = serializer.save(
            member=member, 
            branch=branch,
            created_by=self.request.user
        )
        
        # Audit log
        write_audit_log(
            action=AuditAction.PRAYER_REQUEST_CREATE,
            resource_type="PrayerRequest",
            resource_id=instance.id,
            metadata={
                "member_id": str(instance.member.id) if instance.member else None,
                "category": instance.category,
                "privacy_level": instance.privacy_level,
                "branch_id": str(instance.branch.id) if instance.branch else None,
                "is_anonymous": bool(instance.submitted_by_name and not instance.member),
            },
            user=self.request.user
        )
        
        # Phase 13: Notifications
        # Notify pastoral team for PASTORAL-level requests
        if instance.privacy_level == 'PASTORAL':
            notify_prayer_request_created_to_team(instance, self.request.user)
        
        # Notify if already assigned
        if instance.assigned_to:
            notify_prayer_request_assigned(instance, instance.assigned_to)
    
    def perform_update(self, serializer):
        """
        Phase 13: Track status changes, assignments, closures, send notifications.
        """
        instance = serializer.instance
        old_status = instance.status
        old_assigned = instance.assigned_to
        
        updated_instance = serializer.save()
        
        # Track assignment changes
        if updated_instance.assigned_to != old_assigned:
            write_audit_log(
                action=AuditAction.PRAYER_REQUEST_ASSIGN,
                resource_type="PrayerRequest",
                resource_id=updated_instance.id,
                metadata={
                    "old_assigned_to": str(old_assigned.id) if old_assigned else None,
                    "new_assigned_to": str(updated_instance.assigned_to.id) if updated_instance.assigned_to else None,
                },
                user=self.request.user
            )
            
            # Phase 13: Notify newly assigned staff
            if updated_instance.assigned_to:
                notify_prayer_request_assigned(updated_instance, updated_instance.assigned_to)
        
        # Track status changes
        if updated_instance.status != old_status:
            write_audit_log(
                action=AuditAction.PRAYER_REQUEST_STATUS_CHANGE,
                resource_type="PrayerRequest",
                resource_id=updated_instance.id,
                metadata={
                    "old_status": old_status,
                    "new_status": updated_instance.status,
                },
                user=self.request.user
            )
            
            # Phase 13: Notify on answered status
            if updated_instance.status == 'ANSWERED' and old_status != 'ANSWERED':
                notify_prayer_request_answered(updated_instance, self.request.user)
        
        # Track closures
        if updated_instance.status in ['ANSWERED', 'CLOSED', 'CANCELLED'] and old_status not in ['ANSWERED', 'CLOSED', 'CANCELLED']:
            write_audit_log(
                action=AuditAction.PRAYER_REQUEST_CLOSE,
                resource_type="PrayerRequest",
                resource_id=updated_instance.id,
                metadata={
                    "final_status": updated_instance.status,
                    "closure_reason": updated_instance.closure_reason or "",
                },
                user=self.request.user
            )
            
            # Phase 13: Notify on closure
            notify_prayer_request_closed(updated_instance, self.request.user)
    
    def retrieve(self, request, *args, **kwargs):
        """
        Phase 13: Log sensitive record access for private prayers.
        """
        response = super().retrieve(request, *args, **kwargs)
        instance = self.get_object()
        
        # Only log access to private/pastoral prayer requests
        if instance.privacy_level in ['PRIVATE', 'PASTORAL']:
            write_audit_log(
                action=AuditAction.PRAYER_REQUEST_ACCESS,
                resource_type="PrayerRequest",
                resource_id=instance.id,
                metadata={
                    "member_id": str(instance.member.id) if instance.member else None,
                    "privacy_level": instance.privacy_level,
                    "category": instance.category,
                },
                user=request.user
            )
        
        return response


class PrayerNoteViewSet(StandardModelViewSet):
    """
    Staff-only follow-up notes; visibility inherits from the parent request's queryset.
    
    Phase 13: Audit logging for note creation.
    """
    serializer_class = PrayerNoteSerializer
    permission_classes = [PastoralStaffOnly]
    filterset_fields = ["prayer_request"]
    permission_action_map = {
        "list": PermissionCodes.PRAYER_VIEW,
        "retrieve": PermissionCodes.PRAYER_VIEW,
        "create": PermissionCodes.PRAYER_CREATE,
        "update": PermissionCodes.PRAYER_UPDATE,
        "partial_update": PermissionCodes.PRAYER_UPDATE,
        "destroy": PermissionCodes.PRAYER_DELETE,
    }

    def get_queryset(self):
        user = self.request.user
        if user.role not in (Roles.GLOBAL_SCOPE_ROLES | Roles.PASTORAL_ACCESS_ROLES):
            return PrayerNote.objects.none()
        qs = PrayerNote.objects.select_related("prayer_request", "author")
        if user.role in Roles.GLOBAL_SCOPE_ROLES:
            return qs
        return qs.filter(prayer_request__branch_id=user.branch_id)

    def perform_create(self, serializer):
        """
        Phase 13: Auto-set author and log note creation.
        """
        instance = serializer.save(author=self.request.user)
        
        # Audit log
        write_audit_log(
            action=AuditAction.PRAYER_NOTE_CREATE,
            resource_type="PrayerNote",
            resource_id=instance.id,
            metadata={
                "prayer_request_id": str(instance.prayer_request.id),
                "member_id": str(instance.prayer_request.member.id) if instance.prayer_request.member else None,
            },
            user=self.request.user
        )


class TestimonyViewSet(viewsets.ModelViewSet):
    """Private submissions and a pastoral moderation queue for testimonies."""

    serializer_class = TestimonySerializer
    permission_classes = [IsAuthenticated]
    http_method_names = ["get", "post", "head", "options"]

    def _is_moderator(self):
        role = self.request.user.get_role_code() if hasattr(self.request.user, "get_role_code") else self.request.user.role
        if role not in Roles.PASTORAL_ACCESS_ROLES:
            return False
        from common.permissions.rbac import user_has_completed_required_mfa
        return user_has_completed_required_mfa(self.request.user)

    def get_queryset(self):
        qs = Testimony.objects.select_related("branch", "member", "reviewed_by")
        user = self.request.user
        if self._is_moderator():
            if user.role in Roles.GLOBAL_SCOPE_ROLES:
                return qs
            return qs.filter(branch_id=user.branch_id) if user.branch_id else qs.none()
        return qs.filter(member__user=user)

    def perform_create(self, serializer):
        member = getattr(self.request.user, "member_profile", None)
        if member is None:
            raise ValidationError({"member": "A student profile is required to submit a testimony."})
        instance = serializer.save(member=member, branch=member.branch)
        write_audit_log(
            action=AuditAction.PRAYER_REQUEST_CREATE,
            resource_type="Testimony",
            resource_id=instance.id,
            metadata={"branch_id": str(member.branch_id), "consent_to_publish": instance.consent_to_publish},
            user=self.request.user,
        )

    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        if not self._is_moderator():
            raise PermissionDenied("Only authorized pastoral staff can approve testimonies.")
        instance = self.get_object()
        if not instance.consent_to_publish:
            raise ValidationError({"consent_to_publish": "The member has not consented to sharing this testimony."})
        instance.status = TestimonyStatus.APPROVED
        instance.rejection_reason = ""
        instance.reviewed_by = request.user
        instance.reviewed_at = timezone.now()
        instance.full_clean()
        instance.save(update_fields=["status", "rejection_reason", "reviewed_by", "reviewed_at", "updated_at"])
        return Response(self.get_serializer(instance).data)

    @action(detail=True, methods=["post"])
    def reject(self, request, pk=None):
        if not self._is_moderator():
            raise PermissionDenied("Only authorized pastoral staff can review testimonies.")
        reason = str(request.data.get("reason", "")).strip()
        if not reason:
            raise ValidationError({"reason": "Provide a reason so the member understands the decision."})
        instance = self.get_object()
        instance.status = TestimonyStatus.REJECTED
        instance.rejection_reason = reason
        instance.reviewed_by = request.user
        instance.reviewed_at = timezone.now()
        instance.full_clean()
        instance.save(update_fields=["status", "rejection_reason", "reviewed_by", "reviewed_at", "updated_at"])
        return Response(self.get_serializer(instance).data)
