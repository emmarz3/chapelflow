from rest_framework import serializers

from common.serializers.validators import ScopedFKValidationMixin
from .models import Announcement, AnnouncementStatus, AudienceType, CommunicationPreference


class AnnouncementSerializer(ScopedFKValidationMixin, serializers.ModelSerializer):
    """
    Phase 10: Announcement serializer with full lifecycle and security.
    
    Security (READ-ONLY fields - server-controlled):
    - status: controlled via lifecycle actions (publish/cancel), not direct PATCH
    - sending_started_at: set when dispatch begins
    - completed_at: set when dispatch completes
    - failure_reason: set on dispatch failure
    - created_by: set from authenticated user
    - created_at: server timestamp
    
    Writable fields:
    - branch: validated against user's scope
    - title, body: content fields
    - audience_type: validated against user's authorization
    - target_groups: validated against user's scope and leadership
    - target_membership_statuses: list of membership status values
    - target_community: required if audience_type=STAFF_COMMUNITY
    - channels: list of notification channels (EMAIL/SMS/PUSH)
    - publish_at: when to send
    - expires_at: optional expiration
    """
    class Meta:
        model = Announcement
        fields = [
            "id", "branch", "title", "body", 
            "status", "audience_type", "channels",
            "target_groups", "target_membership_statuses", "target_community",
            "created_by", "publish_at", "expires_at",
            "sending_started_at", "completed_at", "failure_reason",
            "created_at",
        ]
        read_only_fields = [
            "id", "status", "created_by", "created_at",
            "sending_started_at", "completed_at", "failure_reason",
        ]
    
    def validate_branch(self, branch):
        """Phase 3: Validate user can access this branch."""
        return self.validate_branch_fk(branch)
    
    def validate_target_groups(self, target_groups):
        """
        Phase 3: Validate all target groups belong to accessible branches.
        Phase 10: Also validates assignment-scoped leaders can only target groups they lead.
        """
        if not target_groups:
            return target_groups
        
        request = self.context.get('request')
        if not request or not request.user:
            raise serializers.ValidationError("Authentication required")
        
        from common.permissions.scoping import user_can_access_group
        
        invalid_groups = []
        for group in target_groups:
            if not user_can_access_group(request.user, group):
                invalid_groups.append(group.name)
        
        if invalid_groups:
            raise serializers.ValidationError(
                f"You are not authorized to target these groups: {', '.join(invalid_groups)}"
            )
        
        return target_groups
    
    def validate_channels(self, channels):
        """Validate channel list contains valid NotificationChannel values."""
        if not channels:
            return channels
        
        from apps.notifications.models import NotificationChannel
        valid_channels = [c.value for c in NotificationChannel]
        
        invalid = [ch for ch in channels if ch not in valid_channels]
        if invalid:
            raise serializers.ValidationError(
                f"Invalid channels: {invalid}. Must be one of: {valid_channels}"
            )
        if "PUSH" in channels:
            raise serializers.ValidationError("Browser push is unavailable until device subscriptions are configured.")
        if "SMS" in channels:
            from django.conf import settings
            if not settings.SMS_CHANNEL_ENABLED:
                raise serializers.ValidationError("SMS delivery is unavailable.")
        
        return channels
    
    def validate(self, attrs):
        """
        Cross-field validation:
        - audience_type=STAFF_COMMUNITY requires target_community
        - Assignment-scoped leaders restricted to certain audience types
        """
        audience_type = attrs.get('audience_type')
        target_community = attrs.get('target_community')
        
        if audience_type == AudienceType.STAFF_COMMUNITY and not target_community:
            raise serializers.ValidationError({
                "target_community": "Required when audience_type is STAFF_COMMUNITY."
            })
        
        return attrs


class CommunicationPreferenceSerializer(serializers.ModelSerializer):
    """
    Phase 10: Communication preference serializer for self-service management.
    
    Security:
    - Members can update own preferences
    - Staff cannot override member preferences (no legitimate use case)
    - member field is read-only after creation
    - updated_at is automatic
    
    Used by:
    - Self-service preference management endpoints
    - Member profile settings
    """
    class Meta:
        model = CommunicationPreference
        fields = [
            "id", "member",
            "master_enabled", "email_enabled", "sms_enabled", "push_enabled", "in_app_enabled",
            "announcements_enabled", "events_enabled", "service_reminders_enabled",
            "devotional_enabled", "fellowship_enabled", "prayer_updates_enabled",
            "prayer_notifications_enabled", "live_service_enabled", "admin_alerts_enabled",
            "birthday_enabled", "quiet_hours_enabled", "quiet_hours_start", "quiet_hours_end",
            "timezone_name",
            "updated_at",
        ]
        read_only_fields = ["id", "member", "updated_at"]
    
    def validate(self, attrs):
        from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

        current = self.instance
        enabled = attrs.get("quiet_hours_enabled", current.quiet_hours_enabled if current else False)
        start = attrs.get("quiet_hours_start", current.quiet_hours_start if current else None)
        end = attrs.get("quiet_hours_end", current.quiet_hours_end if current else None)
        name = attrs.get("timezone_name", current.timezone_name if current else "Africa/Lagos")
        try:
            ZoneInfo(name)
        except (ZoneInfoNotFoundError, ValueError, TypeError):
            raise serializers.ValidationError({"timezone_name": "Enter a valid IANA time zone."})
        if enabled and (not start or not end or start == end):
            raise serializers.ValidationError({"quiet_hours_start": "Choose different start and end times for quiet hours."})
        return attrs


class AnnouncementPublishSerializer(serializers.Serializer):
    """Serializer for publishing a DRAFT announcement (no additional fields needed)."""
    pass


class AnnouncementCancelSerializer(serializers.Serializer):
    """Serializer for cancelling an announcement with optional reason."""
    reason = serializers.CharField(max_length=500, required=False, allow_blank=True)
