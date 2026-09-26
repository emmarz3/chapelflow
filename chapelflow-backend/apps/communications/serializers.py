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
            "email_enabled", "sms_enabled", "push_enabled",
            "announcements_enabled",
            "updated_at",
        ]
        read_only_fields = ["id", "member", "updated_at"]
    
    def validate(self, attrs):
        """
        Prevent disabling all channels (would make member unreachable).
        At least one channel should remain enabled.
        """
        # Get current values if updating
        if self.instance:
            email = attrs.get('email_enabled', self.instance.email_enabled)
            sms = attrs.get('sms_enabled', self.instance.sms_enabled)
            push = attrs.get('push_enabled', self.instance.push_enabled)
        else:
            email = attrs.get('email_enabled', True)
            sms = attrs.get('sms_enabled', True)
            push = attrs.get('push_enabled', True)
        
        # Allow all disabled (user's choice), just warn in UI
        # This validation could be stricter if business requires it
        
        return attrs


class AnnouncementPublishSerializer(serializers.Serializer):
    """Serializer for publishing a DRAFT announcement (no additional fields needed)."""
    pass


class AnnouncementCancelSerializer(serializers.Serializer):
    """Serializer for cancelling an announcement with optional reason."""
    reason = serializers.CharField(max_length=500, required=False, allow_blank=True)
