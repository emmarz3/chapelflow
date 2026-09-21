from django.db.models import Q
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from common.constants.roles import PermissionCodes
from common.permissions.rbac import HasRolePermission
from common.permissions.scoping import BranchScopedQuerysetMixin
from common.utils.responses import error_response, success_response
from common.viewsets import StandardModelViewSet

from . import services
from .models import Announcement, AnnouncementStatus, CommunicationPreference
from .serializers import (
    AnnouncementCancelSerializer,
    AnnouncementPublishSerializer,
    AnnouncementSerializer,
    CommunicationPreferenceSerializer,
)
from .tasks import dispatch_announcement, get_announcement_delivery_summary


class MyCommunicationPreferenceView(APIView):
    """Self-service preference endpoint that never exposes another member's data."""
    permission_classes = [IsAuthenticated]

    def _preference(self, request):
        member = getattr(request.user, "member_profile", None)
        if member is None:
            return None
        preference, _ = CommunicationPreference.objects.get_or_create(member=member)
        return preference

    def get(self, request):
        preference = self._preference(request)
        if preference is None:
            return error_response("No member profile associated with this account.", status=403)
        return success_response(CommunicationPreferenceSerializer(preference).data)

    def patch(self, request):
        preference = self._preference(request)
        if preference is None:
            return error_response("No member profile associated with this account.", status=403)
        serializer = CommunicationPreferenceSerializer(preference, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        # save() returns the model instance (no .data); respond with the serializer's data.
        serializer.save()
        return success_response(serializer.data)


class StudentAnnouncementFeedView(APIView):
    """Published chapel announcements for a signed-in member account."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if request.user.get_role_code() != "MEMBER":
            return error_response("This feed is available only to member accounts.", status=403)
        member = getattr(request.user, "member_profile", None)
        if member is None:
            return error_response("No member profile associated with this account.", status=403)
        now = timezone.now()
        feed = Announcement.objects.filter(
            branch=member.branch,
            status=AnnouncementStatus.COMPLETED,
            publish_at__lte=now,
        ).filter(Q(expires_at__isnull=True) | Q(expires_at__gt=now))
        if member.community in {"STAFF", "GUEST"}:
            # Staff and guests receive chapel-wide news only. Group-targeted
            # messages remain exclusive to the student community platform.
            feed = feed.filter(
                Q(audience_type="EVERYONE")
                | Q(audience_type="CUSTOM", target_groups__isnull=True, target_community="")
            )
        else:
            feed = feed.filter(
                Q(target_groups__isnull=True)
                | Q(target_groups__memberships__member=member, target_groups__memberships__is_active=True)
            )
        feed = feed.distinct().order_by("-publish_at")[:50]
        return success_response([
            {"id": str(item.id), "title": item.title, "body": item.body, "published_at": item.completed_at or item.publish_at}
            for item in feed
        ])


class AnnouncementViewSet(BranchScopedQuerysetMixin, StandardModelViewSet):
    """
    Phase 10: Announcement management with lifecycle control.
    
    Endpoints:
    - GET /announcements/ - list announcements in scope
    - POST /announcements/ - create announcement (DRAFT status)
    - GET /announcements/{id}/ - retrieve announcement
    - PATCH /announcements/{id}/ - update announcement (DRAFT only)
    - DELETE /announcements/{id}/ - delete announcement
    - POST /announcements/{id}/publish/ - publish DRAFT announcement
    - POST /announcements/{id}/cancel/ - cancel announcement
    - GET /announcements/{id}/delivery-status/ - view delivery statistics
    
    Security:
    - Uses COMMUNICATIONS_* permission codes (fixed from EVENTS_*)
    - Branch-scoped queryset filtering
    - Authorization in perform_create via services.py
    - Lifecycle actions validate state transitions
    - Only DRAFT announcements can be edited/published
    """
    serializer_class = AnnouncementSerializer
    permission_classes = [HasRolePermission]
    filterset_fields = ["branch", "status"]
    permission_action_map = {
        "list": PermissionCodes.COMMUNICATIONS_VIEW,
        "retrieve": PermissionCodes.COMMUNICATIONS_VIEW,
        "create": PermissionCodes.COMMUNICATIONS_CREATE,
        "update": PermissionCodes.COMMUNICATIONS_UPDATE,
        "partial_update": PermissionCodes.COMMUNICATIONS_UPDATE,
        "destroy": PermissionCodes.COMMUNICATIONS_DELETE,
        "publish": PermissionCodes.COMMUNICATIONS_SEND,
        "cancel": PermissionCodes.COMMUNICATIONS_DELETE,
        "delivery_status": PermissionCodes.COMMUNICATIONS_VIEW,
    }

    def get_base_queryset(self):
        return (
            Announcement.objects.select_related("branch")
            .prefetch_related("target_groups")
            .order_by("-created_at", "-id")
        )

    def perform_create(self, serializer):
        """
        Phase 10: Create announcement with authorization checks.
        
        Security:
        - Validates user can access branch (via serializer)
        - Validates user can target audience (via services.authorize_audience)
        - Sets created_by from authenticated user
        - Initial status is DRAFT (not auto-dispatched)
        """
        announcement = serializer.save(
            created_by=self.request.user,
            status=AnnouncementStatus.DRAFT
        )
        
        # Authorize audience targeting
        services.authorize_audience(
            user=self.request.user,
            branch=announcement.branch,
            audience_type=announcement.audience_type,
            target_groups=announcement.target_groups.all(),
            target_community=announcement.target_community,
        )
    
    def perform_update(self, serializer):
        """
        Only DRAFT announcements can be updated.
        Once published/queued/sending, announcement is immutable.
        """
        announcement = self.get_object()
        if announcement.status != AnnouncementStatus.DRAFT:
            from rest_framework.exceptions import ValidationError
            raise ValidationError({
                "detail": f"Cannot update announcement in status {announcement.status}. Only DRAFT announcements can be edited."
            })
        
        serializer.save()
    
    @action(detail=True, methods=["post"], url_path="publish")
    def publish(self, request, pk=None):
        """
        Publish a DRAFT announcement (DRAFT -> QUEUED -> dispatch).
        
        Transitions:
        - DRAFT -> QUEUED: Announcement queued for dispatch
        - Then asynchronously dispatches to recipients
        
        Security:
        - Requires COMMUNICATIONS_SEND permission
        - Re-validates authorization at publish time
        - Respects branch scoping
        - Cannot re-publish already sent announcements
        """
        announcement = self.get_object()
        serializer = AnnouncementPublishSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        # Validate state
        if announcement.status != AnnouncementStatus.DRAFT:
            return Response(
                {"detail": f"Cannot publish announcement in status {announcement.status}. Only DRAFT can be published."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Re-authorize at publish time (groups/permissions may have changed since creation)
        try:
            services.authorize_audience(
                user=request.user,
                branch=announcement.branch,
                audience_type=announcement.audience_type,
                target_groups=announcement.target_groups.all(),
                target_community=announcement.target_community,
            )
        except Exception as e:
            return Response(
                {"detail": str(e)},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Future campaigns stay SCHEDULED until the beat task releases them.
        # This avoids a Celery worker delivering a future-dated campaign early.
        if announcement.publish_at > timezone.now():
            announcement.status = AnnouncementStatus.SCHEDULED
            announcement.save(update_fields=["status"])
            response_serializer = self.get_serializer(announcement)
            return Response({"data": response_serializer.data, "message": "Announcement scheduled for delivery."})

        # Transition to QUEUED
        announcement.status = AnnouncementStatus.QUEUED
        announcement.save(update_fields=["status"])
        
        # Queue dispatch task
        dispatch_announcement.delay(str(announcement.id))
        
        response_serializer = self.get_serializer(announcement)
        return Response({"data": response_serializer.data})
    
    @action(detail=True, methods=["post"], url_path="cancel")
    def cancel(self, request, pk=None):
        """
        Cancel an announcement (any status except COMPLETED -> CANCELLED status).
        
        Note: This sets status to a cancelled/failed state but does not
        recall already-sent notifications (that's not possible).
        
        Security:
        - Requires COMMUNICATIONS_DELETE permission
        - Respects branch scoping
        - Cannot cancel COMPLETED announcements (historical protection)
        """
        announcement = self.get_object()
        serializer = AnnouncementCancelSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        # Validate state
        if announcement.status == AnnouncementStatus.COMPLETED:
            return Response(
                {"detail": "Cannot cancel a COMPLETED announcement. It has already been fully sent."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Set failure status with reason
        reason = serializer.validated_data.get("reason", "")
        announcement.status = AnnouncementStatus.FAILED
        announcement.failure_reason = f"Cancelled by user: {reason}" if reason else "Cancelled by user"
        announcement.save(update_fields=["status", "failure_reason"])
        
        response_serializer = self.get_serializer(announcement)
        return Response({"data": response_serializer.data})

    @action(detail=True, methods=["get"], url_path="delivery-status")
    def delivery_status(self, request, pk=None):
        """
        GET /api/v1/communications/announcements/{id}/delivery-status/ —
        Returns delivery statistics for this announcement (pending/sent/delivered/failed counts).
        
        Security:
        - Requires COMMUNICATIONS_VIEW permission
        - Respects branch scoping (get_object enforces it)
        - Only shows data for accessible announcements
        """
        announcement = self.get_object()
        summary = get_announcement_delivery_summary(announcement.id)
        return success_response(summary)


class CommunicationPreferenceViewSet(StandardModelViewSet):
    """
    Phase 10: Communication preference management for self-service.
    
    Endpoints:
    - GET /preferences/ - list preferences (own only for members, all in scope for staff)
    - GET /preferences/{id}/ - retrieve preference
    - PATCH /preferences/{id}/ - update preference
    
    Note: Preferences are created automatically on first access if they don't exist.
    
    Security:
    - Members can only view/update own preferences
    - Staff can view preferences in scope but cannot override them
    - Member field is immutable after creation
    """
    serializer_class = CommunicationPreferenceSerializer
    permission_classes = [HasRolePermission]
    permission_action_map = {
        "list": PermissionCodes.MEMBERS_VIEW,
        "retrieve": PermissionCodes.MEMBERS_VIEW,
        "update": PermissionCodes.MEMBERS_UPDATE,
        "partial_update": PermissionCodes.MEMBERS_UPDATE,
    }
    
    def get_queryset(self):
        """
        Filter preferences based on user role.
        
        - Members: only their own preference
        - Staff: preferences for members in accessible scope
        """
        user = self.request.user
        
        # If user has a member profile, check if viewing own
        if hasattr(user, 'member_profile') and user.member_profile:
            # Members see only their own
            return CommunicationPreference.objects.filter(
                member=user.member_profile
            )
        
        # Staff see all in scope (via member's branch)
        from common.permissions.scoping import get_accessible_branch_ids
        accessible_branches = get_accessible_branch_ids(user)
        
        return CommunicationPreference.objects.filter(
            member__branch_id__in=accessible_branches
        ).select_related("member")
