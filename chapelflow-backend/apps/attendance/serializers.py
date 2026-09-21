from rest_framework import serializers

from common.serializers.validators import ScopedFKValidationMixin
from .models import AttendanceRecord, AttendanceSession, AttendanceStatus, CheckInDevice, VisitorAttendance


class CheckInDeviceSerializer(ScopedFKValidationMixin, serializers.ModelSerializer):
    class Meta:
        model = CheckInDevice
        fields = ["id", "branch", "name", "device_identifier", "is_active", "last_seen_at", "created_at"]
        read_only_fields = ["id", "created_at"]
    
    def validate_branch(self, branch):
        """Phase 3: Validate user can access this branch."""
        return self.validate_branch_fk(branch)


class AttendanceSessionSerializer(ScopedFKValidationMixin, serializers.ModelSerializer):
    record_count = serializers.IntegerField(source="records.count", read_only=True)

    class Meta:
        model = AttendanceSession
        fields = [
            "id", "branch", "event_schedule", "label", "opened_at",
            "closed_at", "is_open", "state", "window_opens_at", "window_closes_at", "record_count",
        ]
        read_only_fields = ["id", "opened_at"]
    
    def validate_branch(self, branch):
        """Phase 3: Validate user can access this branch."""
        return self.validate_branch_fk(branch)
    
    def validate_event_schedule(self, event_schedule):
        """Phase 3: Validate event schedule belongs to accessible event."""
        return self.validate_related_branch_fk(event_schedule, 'event_schedule')


class AttendanceRecordSerializer(ScopedFKValidationMixin, serializers.ModelSerializer):
    class Meta:
        model = AttendanceRecord
        fields = [
            "id", "session", "member", "visitor", "method", "status", "device",
            "checked_in_by", "checkpoint", "checked_in_at", "checked_out_at", "synced_at", 
            "client_record_id", "created_at",
        ]
        read_only_fields = ["id", "created_at", "checked_in_by", "status"]
    
    def validate_session(self, session):
        """Phase 3: Validate session belongs to accessible branch."""
        return self.validate_related_branch_fk(session, 'session')
    
    def validate_member(self, member):
        """Phase 3: Validate member belongs to accessible branch."""
        if member:
            return self.validate_member_fk(member)
        return member
    
    def validate_device(self, device):
        """Phase 3: Validate device belongs to accessible branch."""
        if device:
            return self.validate_related_branch_fk(device, 'device')
        return device
    
    def validate_checked_out_at(self, checked_out_at):
        """Validate check-out time is after check-in time."""
        if checked_out_at and self.instance:
            if checked_out_at < self.instance.checked_in_at:
                raise serializers.ValidationError("Check-out time cannot be before check-in time.")
        return checked_out_at


class VisitorAttendanceSerializer(ScopedFKValidationMixin, serializers.ModelSerializer):
    class Meta:
        model = VisitorAttendance
        fields = [
            "id", "session", "full_name", "phone_number", "email",
            "how_heard", "invited_by", "checked_in_at", "follow_up_status",
            "visitor_record",
        ]
        read_only_fields = ["id"]
    
    def validate_session(self, session):
        """Phase 3: Validate session belongs to accessible branch."""
        return self.validate_related_branch_fk(session, 'session')
    
    def validate_invited_by(self, invited_by):
        """Phase 3: Validate invited_by member belongs to accessible branch."""
        if invited_by:
            return self.validate_member_fk(invited_by)
        return invited_by


class QRCheckInSerializer(serializers.Serializer):
    token = serializers.CharField()
    session_id = serializers.UUIDField()
    device_id = serializers.UUIDField(required=False)


class KioskCheckInSerializer(serializers.Serializer):
    token = serializers.CharField()
    session_id = serializers.UUIDField()
    device_id = serializers.UUIDField()
    device_secret = serializers.CharField(write_only=True)


class ManualCheckInSerializer(serializers.Serializer):
    member_id = serializers.UUIDField()
    session_id = serializers.UUIDField()


class OfflineSyncRecordSerializer(serializers.Serializer):
    client_record_id = serializers.CharField(max_length=64)
    member_id = serializers.UUIDField()
    session_id = serializers.UUIDField()
    checked_in_at = serializers.DateTimeField()
    method = serializers.ChoiceField(
        choices=["QR_CODE", "MANUAL", "KIOSK", "SELF_CHECK_IN"], default="SELF_CHECK_IN"
    )


class OfflineSyncRequestSerializer(serializers.Serializer):
    records = OfflineSyncRecordSerializer(many=True)


class SelfCheckInSerializer(serializers.Serializer):
    """
    Phase 7 security enhancement: Self-check-in serializer that does NOT
    accept member_id or token. Member is derived from authenticated user.
    """
    session_id = serializers.UUIDField()


class StudentUsherScanSerializer(serializers.Serializer):
    token = serializers.CharField(max_length=2048, trim_whitespace=True)


class AttendanceCorrectionSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=AttendanceStatus.choices)
    reason = serializers.CharField(max_length=500, trim_whitespace=True)
