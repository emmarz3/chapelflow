from rest_framework import serializers

from common.serializers.validators import ScopedFKValidationMixin
from .models import Event, EventRegistration, EventSchedule, EventType, Location


class LocationSerializer(ScopedFKValidationMixin, serializers.ModelSerializer):
    class Meta:
        model = Location
        fields = ["id", "branch", "name", "address", "capacity"]
    
    def validate_branch(self, branch):
        """Phase 3: Validate user can access this branch."""
        return self.validate_branch_fk(branch)


class EventTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = EventType
        fields = ["id", "name", "description"]


class EventScheduleSerializer(serializers.ModelSerializer):
    class Meta:
        model = EventSchedule
        fields = ["id", "event", "occurrence_start", "occurrence_end", "is_cancelled"]
        read_only_fields = ["id"]


class EventSerializer(ScopedFKValidationMixin, serializers.ModelSerializer):
    schedules = EventScheduleSerializer(many=True, read_only=True)

    class Meta:
        model = Event
        fields = [
            "id", "branch", "event_type", "location", "title", "description",
            "start_time", "end_time", "frequency", "recurrence_end_date",
            "is_public", "requires_registration", "capacity", "registration_deadline",
            "schedules", "created_at", "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]
    
    def validate_branch(self, branch):
        """Phase 3: Validate user can access this branch."""
        return self.validate_branch_fk(branch)
    
    def validate_location(self, location):
        """Phase 3: Validate location belongs to accessible branch."""
        return self.validate_related_branch_fk(location, 'location')

    def validate(self, attrs):
        start = attrs.get("start_time", getattr(self.instance, "start_time", None))
        end = attrs.get("end_time", getattr(self.instance, "end_time", None))
        if start and end and end <= start:
            raise serializers.ValidationError({"end_time": "End time must be after start time."})
        frequency = attrs.get("frequency", getattr(self.instance, "frequency", "NONE"))
        recurrence_end = attrs.get("recurrence_end_date", getattr(self.instance, "recurrence_end_date", None))
        if frequency != "NONE" and not recurrence_end:
            raise serializers.ValidationError(
                {"recurrence_end_date": "Required when the event repeats."}
            )
        deadline = attrs.get("registration_deadline", getattr(self.instance, "registration_deadline", None))
        if deadline and start and deadline > start:
            raise serializers.ValidationError(
                {"registration_deadline": "Registration deadline must be before the event starts."}
            )
        return attrs


class EventRegistrationSerializer(ScopedFKValidationMixin, serializers.ModelSerializer):
    class Meta:
        model = EventRegistration
        fields = ["id", "schedule", "member", "status", "registered_at", "cancelled_at", "attended"]
        read_only_fields = ["id", "status", "registered_at", "cancelled_at"]
        # `status` is deliberately read-only here: it's computed by
        # services.register_for_event (capacity/waitlist) and
        # services.cancel_registration (cancel + waitlist promotion),
        # never set directly by a client -- see EventRegistrationViewSet.
    
    def validate_schedule(self, schedule):
        """Phase 3: Validate schedule belongs to accessible event."""
        return self.validate_related_branch_fk(schedule, 'schedule')
    
    def validate_member(self, member):
        """Phase 3: Validate member belongs to accessible branch."""
        return self.validate_member_fk(member)
