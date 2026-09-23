from decimal import Decimal

from rest_framework import serializers

from common.serializers.validators import ScopedFKValidationMixin
from .models import AssignmentStatus, VolunteerAssignment, VolunteerAvailability, VolunteerProfile


class VolunteerProfileSerializer(ScopedFKValidationMixin, serializers.ModelSerializer):
    """
    Phase 9: Volunteer profile serializer with full lifecycle support.
    
    Security:
    - member: validated against user's scope (cannot create profile for out-of-scope member)
    - status: writable to allow staff to manage lifecycle (PENDING -> ACTIVE transitions)
    - created_at: read-only (server-controlled)
    """
    member_name = serializers.CharField(source="member.full_name", read_only=True)

    class Meta:
        model = VolunteerProfile
        fields = ["id", "member", "member_name", "skills", "availability_notes", "is_active", "status", "created_at"]
        read_only_fields = ["id", "created_at"]
    
    def validate_member(self, member):
        """Phase 3: Validate member belongs to accessible branch."""
        return self.validate_member_fk(member)


class VolunteerAvailabilitySerializer(ScopedFKValidationMixin, serializers.ModelSerializer):
    """
    Phase 9: Volunteer availability window serializer.
    
    Security:
    - volunteer: validated against user's scope
    - For self-service, views should derive volunteer from authenticated user
    - weekday: 0-6 (Monday-Sunday)
    - times: validated to ensure end_time > start_time
    """
    class Meta:
        model = VolunteerAvailability
        fields = ["id", "volunteer", "weekday", "start_time", "end_time", "is_available", "created_at"]
        read_only_fields = ["id", "created_at"]
    
    def validate_volunteer(self, volunteer):
        """Phase 3: Validate volunteer profile belongs to accessible branch."""
        return self.validate_related_branch_fk(volunteer, 'volunteer')
    
    def validate(self, attrs):
        """Validate time range consistency."""
        start_time = attrs.get('start_time')
        end_time = attrs.get('end_time')
        
        if start_time and end_time and start_time >= end_time:
            raise serializers.ValidationError({
                "end_time": "End time must be after start time."
            })
        
        return attrs


class VolunteerAssignmentSerializer(ScopedFKValidationMixin, serializers.ModelSerializer):
    """
    Phase 9: Volunteer assignment serializer with lifecycle and service-hour tracking.
    
    Security (READ-ONLY fields - server-controlled):
    - status: controlled via lifecycle actions (confirm/decline/complete), NOT directly writable
    - confirmed: synced with status automatically, kept for backward compatibility
    - hours_logged: only set via complete action with authorization checks
    - responded_at: timestamp set when volunteer confirms/declines
    - completed_at: timestamp set when assignment marked complete
    - reminder_sent_at: timestamp set by background task
    - created_at: server timestamp
    
    Writable fields:
    - volunteer: validated against scope (cannot assign out-of-scope volunteer)
    - event_schedule: validated against scope (cannot assign to out-of-scope event)
    - group: validated against scope (cannot assign to out-of-scope group)
    - role: validated against VolunteerRole choices
    - notes: free text for assignment context
    """
    volunteer_name = serializers.CharField(source="volunteer.member.full_name", read_only=True)
    event_title = serializers.CharField(source="event_schedule.event.title", read_only=True)
    group_name = serializers.CharField(source="group.name", read_only=True)

    class Meta:
        model = VolunteerAssignment
        fields = [
            "id", "volunteer", "volunteer_name", "event_schedule", "event_title", "group", "group_name", "role", "status", "confirmed",
            "notes", "hours_logged", "responded_at", "completed_at", "reminder_sent_at", "created_at"
        ]
        read_only_fields = [
            "id", "status", "confirmed", "hours_logged", "responded_at", 
            "completed_at", "reminder_sent_at", "created_at"
        ]
    
    def validate_volunteer(self, volunteer):
        """Phase 3: Validate volunteer profile belongs to accessible branch."""
        return self.validate_related_branch_fk(volunteer, 'volunteer')
    
    def validate_event_schedule(self, event_schedule):
        """Phase 3: Validate event schedule belongs to accessible branch."""
        if event_schedule is None:
            return event_schedule
        return self.validate_related_branch_fk(event_schedule, 'event_schedule')
    
    def validate_group(self, group):
        """Phase 3: Validate group belongs to accessible branch."""
        if group is None:
            return group
        return self.validate_related_branch_fk(group, 'group')


class AssignmentConfirmSerializer(serializers.Serializer):
    """Serializer for confirming an assignment (no additional fields needed)."""
    pass


class AssignmentDeclineSerializer(serializers.Serializer):
    """Serializer for declining an assignment with optional reason."""
    reason = serializers.CharField(max_length=255, required=False, allow_blank=True)


class AssignmentCompleteSerializer(serializers.Serializer):
    """
    Serializer for completing an assignment with service hours.
    
    Security:
    - hours_logged: validated as non-negative decimal
    - Only CONFIRMED assignments can be completed
    - Completion is irreversible (historical data protection)
    """
    hours_logged = serializers.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        min_value=Decimal("0.00"),
        required=True,
        help_text="Number of service hours logged (0.00 - 999.99)"
    )
