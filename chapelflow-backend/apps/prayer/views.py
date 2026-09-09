from rest_framework import viewsets
from common.viewsets import StandardModelViewSet
from rest_framework.permissions import IsAuthenticated

from common.constants.roles import Roles, PermissionCodes
from apps.audit.services import write_audit_log
from apps.audit.models import AuditAction
from .models import PrayerNote, PrayerRequest
from .serializers import PrayerNoteSerializer, PrayerRequestSerializer
from .notifications import (
    notify_prayer_request_assigned,
    notify_prayer_request_answered,
    notify_prayer_request_created_to_team,
    notify_prayer_request_closed,
)


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
    permission_classes = [IsAuthenticated]
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

        # Ordinary members/leaders: own requests, or public (non-private) requests
        # in their branch, or requests explicitly assigned to them.
        from django.db.models import Q
        own_member_filter = Q(member__user=user)
        return qs.filter(
            Q(branch_id=user.branch_id) & (own_member_filter | Q(is_private=False) | Q(assigned_to=user))
        )

    def perform_create(self, serializer):
        """
        Phase 13: Auto-set member, branch, created_by, log creation, send notifications.
        """
        member = getattr(self.request.user, "member_profile", None)
        instance = serializer.save(
            member=member, 
            branch=member.branch if member else self.request.data.get("branch"),
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
    permission_classes = [IsAuthenticated]
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
