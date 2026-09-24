from django.db.models import Sum
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from common.constants.roles import PermissionCodes
from common.permissions.rbac import HasRolePermission
from common.permissions.scoping import BranchScopedQuerysetMixin
from common.viewsets import StandardModelViewSet

from . import services
from .models import AssignmentStatus, VolunteerAssignment, VolunteerAvailability, VolunteerProfile
from .serializers import (
    AssignmentCompleteSerializer,
    AssignmentConfirmSerializer,
    AssignmentDeclineSerializer,
    VolunteerAssignmentSerializer,
    VolunteerAvailabilitySerializer,
    VolunteerProfileSerializer,
)


class VolunteerProfileViewSet(BranchScopedQuerysetMixin, StandardModelViewSet):
    """
    Phase 9: Volunteer profile management with proper VOLUNTEERS_* permissions.
    
    Security:
    - Uses VOLUNTEERS_VIEW/CREATE/UPDATE/DELETE permission codes (fixed from MEMBERS_*)
    - Branch-scoped via member__branch relationship
    - Create-time validation ensures member belongs to authorized scope
    
    Endpoints:
    - GET /profiles/ - list profiles in scope
    - POST /profiles/ - create profile (validates member scope)
    - GET /profiles/{id}/ - retrieve profile details
    - PATCH /profiles/{id}/ - update profile
    - DELETE /profiles/{id}/ - delete/deactivate profile
    - GET /profiles/{id}/history/ - retrieve service history with total hours
    """
    serializer_class = VolunteerProfileSerializer
    permission_classes = [HasRolePermission]
    filterset_fields = ["member", "is_active", "status"]
    permission_action_map = {
        "list": PermissionCodes.VOLUNTEERS_VIEW,
        "retrieve": PermissionCodes.VOLUNTEERS_VIEW,
        "create": PermissionCodes.VOLUNTEERS_CREATE,
        "update": PermissionCodes.VOLUNTEERS_UPDATE,
        "partial_update": PermissionCodes.VOLUNTEERS_UPDATE,
        "destroy": PermissionCodes.VOLUNTEERS_DELETE,
        "history": PermissionCodes.VOLUNTEERS_VIEW,
    }
    branch_field_lookup = "member__branch"

    def get_base_queryset(self):
        return VolunteerProfile.objects.select_related("member")

    def perform_create(self, serializer):
        # Approval is a privilege reserved for organization/branch admins.
        # Never trust a submitted status or is_active value for initial approval.
        from common.constants.roles import Roles

        approved = self.request.user.role in {Roles.SUPER_ADMIN, Roles.CHAPEL_ADMIN}
        serializer.save(
            status="ACTIVE" if approved else "PENDING",
            is_active=approved,
        )
    
    @action(detail=True, methods=["get"], url_path="history")
    def history(self, request, pk=None):
        """
        Phase 9: Retrieve volunteer service history with completed assignments and total hours.
        
        Returns:
        - assignments: list of completed assignments with details
        - total_hours: sum of hours_logged across all completed assignments
        
        Security:
        - Respects branch scoping (cannot view out-of-scope volunteer history)
        - Only returns COMPLETED assignments
        """
        volunteer = self.get_object()
        
        completed_assignments = (
            VolunteerAssignment.objects
            .filter(volunteer=volunteer, status=AssignmentStatus.COMPLETED)
            .select_related("event_schedule__event", "group")
            .order_by("-completed_at")
        )
        
        total_hours = completed_assignments.aggregate(
            total=Sum("hours_logged")
        )["total"] or 0
        
        assignment_data = []
        for assignment in completed_assignments:
            assignment_data.append({
                "id": str(assignment.id),
                "role": assignment.role,
                "event": assignment.event_schedule.event.title if assignment.event_schedule else None,
                "group": assignment.group.name if assignment.group else None,
                "hours_logged": str(assignment.hours_logged),
                "completed_at": assignment.completed_at,
            })
        
        return Response({
            "data": {
                "volunteer_id": str(volunteer.id),
                "total_hours": float(total_hours),
                "completed_count": completed_assignments.count(),
                "assignments": assignment_data,
            }
        })


class VolunteerAvailabilityViewSet(BranchScopedQuerysetMixin, StandardModelViewSet):
    """
    Phase 9: Volunteer availability window management.
    
    Security:
    - Uses VOLUNTEERS_VIEW/CREATE/UPDATE/DELETE permission codes
    - Branch-scoped via volunteer__member__branch relationship
    - Create-time validation ensures volunteer belongs to authorized scope
    - Self-service: volunteers should be able to manage their own availability
      (implement via permissions.py if needed)
    
    Endpoints:
    - GET /availability/ - list availability windows in scope
    - POST /availability/ - create availability window (validates volunteer scope)
    - GET /availability/{id}/ - retrieve window details
    - PATCH /availability/{id}/ - update window
    - DELETE /availability/{id}/ - delete window
    """
    serializer_class = VolunteerAvailabilitySerializer
    permission_classes = [HasRolePermission]
    filterset_fields = ["volunteer", "weekday", "is_available"]
    permission_action_map = {
        "list": PermissionCodes.VOLUNTEERS_VIEW,
        "retrieve": PermissionCodes.VOLUNTEERS_VIEW,
        "create": PermissionCodes.VOLUNTEERS_CREATE,
        "update": PermissionCodes.VOLUNTEERS_UPDATE,
        "partial_update": PermissionCodes.VOLUNTEERS_UPDATE,
        "destroy": PermissionCodes.VOLUNTEERS_DELETE,
    }
    branch_field_lookup = "volunteer__member__branch"

    def get_base_queryset(self):
        return VolunteerAvailability.objects.select_related("volunteer__member")


class VolunteerAssignmentViewSet(BranchScopedQuerysetMixin, StandardModelViewSet):
    """
    Phase 9: Volunteer assignment management with full lifecycle support.
    
    Security:
    - Uses VOLUNTEERS_VIEW/ASSIGN/UPDATE/DELETE permission codes (fixed from EVENTS_*)
    - Branch-scoped via volunteer__member__branch relationship
    - Create-time validation ensures volunteer, event, and group belong to authorized scope
    - Lifecycle transitions controlled via custom actions (not direct PATCH)
    
    Endpoints:
    - GET /assignments/ - list assignments in scope
    - POST /assignments/ - create assignment (validates scope, runs conflict checks)
    - GET /assignments/{id}/ - retrieve assignment details
    - PATCH /assignments/{id}/ - update assignment notes/role only (not status)
    - DELETE /assignments/{id}/ - cancel assignment
    - POST /assignments/{id}/confirm/ - confirm assignment (PENDING -> CONFIRMED)
    - POST /assignments/{id}/decline/ - decline assignment with reason (-> DECLINED)
    - POST /assignments/{id}/complete/ - complete assignment with hours (CONFIRMED -> COMPLETED)
    """
    serializer_class = VolunteerAssignmentSerializer
    permission_classes = [HasRolePermission]
    filterset_fields = ["volunteer", "event_schedule", "group", "role", "status"]
    permission_action_map = {
        "list": PermissionCodes.VOLUNTEERS_VIEW,
        "retrieve": PermissionCodes.VOLUNTEERS_VIEW,
        "create": PermissionCodes.VOLUNTEERS_ASSIGN,
        "update": PermissionCodes.VOLUNTEERS_UPDATE,
        "partial_update": PermissionCodes.VOLUNTEERS_UPDATE,
        "destroy": PermissionCodes.VOLUNTEERS_DELETE,
        "confirm": PermissionCodes.VOLUNTEERS_UPDATE,
        "decline": PermissionCodes.VOLUNTEERS_UPDATE,
        "complete": PermissionCodes.VOLUNTEERS_UPDATE,
    }
    branch_field_lookup = "volunteer__member__branch"

    def get_base_queryset(self):
        return VolunteerAssignment.objects.select_related(
            "volunteer__member", "event_schedule__event", "group"
        )
    
    def perform_create(self, serializer):
        """
        Phase 9: Create assignment with conflict detection via services layer.
        
        Security:
        - All FK scope validation handled by serializer
        - Business rule validation (conflicts, availability) via services.create_assignment
        - Prevents duplicate assignments, overlapping assignments, unavailable windows
        """
        # Services layer handles conflict detection and business rules
        volunteer = serializer.validated_data["volunteer"]
        event_schedule = serializer.validated_data.get("event_schedule")
        role = serializer.validated_data["role"]
        group = serializer.validated_data.get("group")
        notes = serializer.validated_data.get("notes", "")
        
        # Create via services to ensure conflict checks run
        assignment = services.create_assignment(
            volunteer=volunteer,
            event_schedule=event_schedule,
            role=role,
            group=group,
            notes=notes,
        )
        
        # Update serializer instance for proper response
        serializer.instance = assignment
    
    @action(detail=True, methods=["post"], url_path="confirm")
    def confirm(self, request, pk=None):
        """
        Phase 9: Confirm a PENDING assignment.
        
        Transitions: PENDING -> CONFIRMED
        
        Security:
        - Requires VOLUNTEERS_UPDATE permission
        - Respects branch scoping
        - Re-validates conflicts at confirmation time
        - Sets responded_at timestamp
        - Syncs confirmed=True for backward compatibility
        """
        assignment = self.get_object()
        serializer = AssignmentConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        # Use services layer for business logic
        assignment = services.confirm_assignment(assignment)
        
        response_serializer = self.get_serializer(assignment)
        return Response({"data": response_serializer.data})
    
    @action(detail=True, methods=["post"], url_path="decline")
    def decline(self, request, pk=None):
        """
        Phase 9: Decline an assignment with optional reason.
        
        Transitions: PENDING/CONFIRMED -> DECLINED
        
        Security:
        - Requires VOLUNTEERS_UPDATE permission
        - Respects branch scoping
        - Cannot decline COMPLETED or CANCELLED assignments
        - Sets responded_at timestamp
        - Appends reason to notes if provided
        """
        assignment = self.get_object()
        serializer = AssignmentDeclineSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        reason = serializer.validated_data.get("reason", "")
        assignment = services.decline_assignment(assignment, reason=reason)
        
        response_serializer = self.get_serializer(assignment)
        return Response({"data": response_serializer.data})
    
    @action(detail=True, methods=["post"], url_path="complete")
    def complete(self, request, pk=None):
        """
        Phase 9: Complete a CONFIRMED assignment with service hours.
        
        Transitions: CONFIRMED -> COMPLETED
        
        Security:
        - Requires VOLUNTEERS_UPDATE permission
        - Respects branch scoping
        - Only CONFIRMED assignments can be completed
        - Validates hours_logged >= 0
        - Sets completed_at timestamp
        - Completed assignments are historical (protected from further modification)
        """
        assignment = self.get_object()
        serializer = AssignmentCompleteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        hours_logged = serializer.validated_data["hours_logged"]
        assignment = services.complete_assignment(assignment, hours_logged=hours_logged)
        
        response_serializer = self.get_serializer(assignment)
        return Response({"data": response_serializer.data})
