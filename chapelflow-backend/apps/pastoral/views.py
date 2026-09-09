from rest_framework import viewsets
from common.viewsets import StandardModelViewSet

from common.constants.roles import Roles, PermissionCodes
from common.permissions.rbac import IsPastoralAuthorized
from apps.audit.services import write_audit_log
from apps.audit.models import AuditAction
from .models import PastoralCase, PastoralNote
from .serializers import PastoralCaseSerializer, PastoralNoteSerializer
from .notifications import (
    notify_case_assigned,
    notify_case_escalated,
    notify_case_closed,
    notify_urgent_case_created,
)


class PastoralCaseViewSet(StandardModelViewSet):
    """
    Strict access: queryset is pre-filtered to cases the user is allowed
    to know exist at all, AND has_object_permission re-checks on every
    single-object action (retrieve/update/destroy) as defense in depth.
    
    Phase 13 enhancements:
    - Auto-set created_by and updated_by
    - Enhanced filtering with priority
    - Comprehensive audit logging
    """
    serializer_class = PastoralCaseSerializer
    permission_classes = [IsPastoralAuthorized]
    filterset_fields = ["branch", "status", "assigned_to", "priority"]
    permission_action_map = {
        "list": PermissionCodes.PASTORAL_VIEW,
        "retrieve": PermissionCodes.PASTORAL_VIEW,
        "create": PermissionCodes.PASTORAL_CREATE,
        "update": PermissionCodes.PASTORAL_UPDATE,
        "partial_update": PermissionCodes.PASTORAL_UPDATE,
        "destroy": PermissionCodes.PASTORAL_DELETE,
    }

    def get_queryset(self):
        qs = PastoralCase.objects.select_related("branch", "member", "assigned_to", "created_by", "updated_by").prefetch_related("notes")
        user = self.request.user

        if user.role in Roles.GLOBAL_SCOPE_ROLES:
            return qs
        if user.role in Roles.PASTORAL_ACCESS_ROLES:
            return qs.filter(branch_id=user.branch_id) if user.branch_id else qs.none()

        # Any other role: only cases assigned to them, or about themselves.
        from django.db.models import Q
        return qs.filter(Q(assigned_to=user) | Q(member__user=user))
    
    def perform_create(self, serializer):
        """
        Phase 13: Auto-set created_by and updated_by, log creation, send notifications.
        """
        instance = serializer.save(created_by=self.request.user, updated_by=self.request.user)
        
        # Audit log
        write_audit_log(
            action=AuditAction.PASTORAL_CASE_CREATE,
            resource_type="PastoralCase",
            resource_id=instance.id,
            metadata={
                "member_id": str(instance.member.id) if instance.member else None,
                "category": instance.category,
                "priority": instance.priority,
                "branch_id": str(instance.branch.id) if instance.branch else None,
            },
            user=self.request.user
        )
        
        # Phase 13: Notifications
        # Notify if URGENT priority
        if instance.priority == 'URGENT':
            notify_urgent_case_created(instance, self.request.user)
        
        # Notify if already assigned
        if instance.assigned_to:
            notify_case_assigned(instance, instance.assigned_to)
    
    def perform_update(self, serializer):
        """
        Phase 13: Track status changes, assignments, escalations, closures, send notifications.
        """
        instance = serializer.instance
        old_status = instance.status
        old_assigned = instance.assigned_to
        old_escalated = instance.escalated_at
        
        updated_instance = serializer.save(updated_by=self.request.user)
        
        # Track assignment changes
        if updated_instance.assigned_to != old_assigned:
            write_audit_log(
                action=AuditAction.PASTORAL_CASE_ASSIGN,
                resource_type="PastoralCase",
                resource_id=updated_instance.id,
                metadata={
                    "old_assigned_to": str(old_assigned.id) if old_assigned else None,
                    "new_assigned_to": str(updated_instance.assigned_to.id) if updated_instance.assigned_to else None,
                },
                user=self.request.user
            )
            
            # Phase 13: Notify newly assigned staff
            if updated_instance.assigned_to:
                notify_case_assigned(updated_instance, updated_instance.assigned_to)
        
        # Track status changes
        if updated_instance.status != old_status:
            write_audit_log(
                action=AuditAction.PASTORAL_CASE_STATUS_CHANGE,
                resource_type="PastoralCase",
                resource_id=updated_instance.id,
                metadata={
                    "old_status": old_status,
                    "new_status": updated_instance.status,
                },
                user=self.request.user
            )
        
        # Track escalations
        if updated_instance.escalated_at and not old_escalated:
            write_audit_log(
                action=AuditAction.PASTORAL_CASE_ESCALATE,
                resource_type="PastoralCase",
                resource_id=updated_instance.id,
                metadata={
                    "escalation_reason": updated_instance.escalation_reason or "",
                    "escalated_by": str(updated_instance.escalated_by.id) if updated_instance.escalated_by else None,
                },
                user=self.request.user
            )
            
            # Phase 13: Notify senior pastoral staff of escalation
            notify_case_escalated(updated_instance, self.request.user)
        
        # Track closures
        if updated_instance.status == 'CLOSED' and old_status != 'CLOSED':
            write_audit_log(
                action=AuditAction.PASTORAL_CASE_CLOSE,
                resource_type="PastoralCase",
                resource_id=updated_instance.id,
                metadata={
                    "closure_reason": updated_instance.closure_reason or "",
                },
                user=self.request.user
            )
            
            # Phase 13: Notify relevant parties of closure
            notify_case_closed(updated_instance, self.request.user)
    
    def retrieve(self, request, *args, **kwargs):
        """
        Phase 13: Log sensitive record access.
        """
        response = super().retrieve(request, *args, **kwargs)
        instance = self.get_object()
        
        write_audit_log(
            action=AuditAction.PASTORAL_CASE_ACCESS,
            resource_type="PastoralCase",
            resource_id=instance.id,
            metadata={
                "member_id": str(instance.member.id) if instance.member else None,
                "category": instance.category,
            },
            user=request.user
        )
        
        return response


class PastoralNoteViewSet(StandardModelViewSet):
    """
    Phase 13: Pastoral notes with audit logging.
    """
    serializer_class = PastoralNoteSerializer
    permission_classes = [IsPastoralAuthorized]
    filterset_fields = ["case"]
    permission_action_map = {
        "list": PermissionCodes.PASTORAL_VIEW,
        "retrieve": PermissionCodes.PASTORAL_VIEW,
        "create": PermissionCodes.PASTORAL_CREATE,
        "update": PermissionCodes.PASTORAL_UPDATE,
        "partial_update": PermissionCodes.PASTORAL_UPDATE,
        "destroy": PermissionCodes.PASTORAL_DELETE,
    }

    def get_queryset(self):
        user = self.request.user
        qs = PastoralNote.objects.select_related("case", "author")
        if user.role in Roles.GLOBAL_SCOPE_ROLES:
            return qs
        if user.role in Roles.PASTORAL_ACCESS_ROLES:
            return qs.filter(case__branch_id=user.branch_id)
        from django.db.models import Q
        return qs.filter(Q(case__assigned_to=user) | Q(case__member__user=user))

    def perform_create(self, serializer):
        """
        Phase 13: Auto-set author and log note creation.
        """
        instance = serializer.save(author=self.request.user)
        
        # Audit log
        write_audit_log(
            action=AuditAction.PASTORAL_NOTE_CREATE,
            resource_type="PastoralNote",
            resource_id=instance.id,
            metadata={
                "case_id": str(instance.case.id),
                "member_id": str(instance.case.member.id) if instance.case.member else None,
            },
            user=self.request.user
        )
