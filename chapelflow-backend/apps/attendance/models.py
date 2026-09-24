import uuid

from django.conf import settings
from django.db import models


class AttendanceMethod(models.TextChoices):
    QR_CODE = "QR_CODE", "QR Code"
    MANUAL = "MANUAL", "Manual"
    KIOSK = "KIOSK", "Kiosk"
    SELF_CHECK_IN = "SELF_CHECK_IN", "Self Check-In"


class AttendanceStatus(models.TextChoices):
    """
    Server-determined attendance status. Late is computed based on event
    start time + grace period. Absent is generated when session closes
    for registered members who didn't check in. Excused requires
    administrative approval.
    """
    PRESENT = "PRESENT", "Present"
    LATE = "LATE", "Late"
    ABSENT = "ABSENT", "Absent"
    EXCUSED = "EXCUSED", "Excused"


class AttendanceSessionState(models.TextChoices):
    OPEN = "OPEN", "Open"
    PAUSED = "PAUSED", "Paused"
    CLOSED = "CLOSED", "Closed"


class CheckInDevice(models.Model):
    """
    A registered kiosk/scanner device, so records can be traced to
    hardware. `secret_hash` is the device's own credential (spec Phase 8:
    "do not rely on a permanent shared secret alone") -- distinct from
    whatever staff user is logged into the kiosk browser, so a device can
    be individually revoked/rotated without touching any user account,
    and stolen/cloned hardware can be cut off immediately via is_active.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    branch = models.ForeignKey("organizations.Branch", on_delete=models.CASCADE, related_name="devices")
    name = models.CharField(max_length=150)
    device_identifier = models.CharField(max_length=150, unique=True)
    secret_hash = models.CharField(
        max_length=255, blank=True,
        help_text="Hashed (never plaintext) per-device credential, set via "
                   "CheckInDeviceViewSet.rotate_secret. Required for kiosk check-in "
                   "(see KioskCheckInView) -- a device with no secret set cannot check anyone in.",
    )
    is_active = models.BooleanField(default=True)
    last_seen_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "attendance_device"

    def __str__(self):
        return self.name

    def set_secret(self, raw_secret: str) -> None:
        from django.contrib.auth.hashers import make_password
        self.secret_hash = make_password(raw_secret)

    def verify_secret(self, raw_secret: str) -> bool:
        from django.contrib.auth.hashers import check_password
        if not self.secret_hash or not raw_secret:
            return False
        return check_password(raw_secret, self.secret_hash)


class AttendanceSession(models.Model):
    """
    An attendance-taking window tied to a specific event occurrence.
    Created (or fetched) automatically the first time a check-in happens
    for an EventSchedule, or manually opened by staff for ad-hoc sessions.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    branch = models.ForeignKey("organizations.Branch", on_delete=models.CASCADE, related_name="attendance_sessions")
    event_schedule = models.ForeignKey(
        "events.EventSchedule", null=True, blank=True, on_delete=models.SET_NULL, related_name="attendance_sessions"
    )
    label = models.CharField(max_length=255, blank=True)
    venue = models.CharField(max_length=120, blank=True)
    opened_at = models.DateTimeField(auto_now_add=True)
    closed_at = models.DateTimeField(null=True, blank=True)
    is_open = models.BooleanField(default=True)
    state = models.CharField(max_length=12, choices=AttendanceSessionState.choices, default=AttendanceSessionState.OPEN)
    window_opens_at = models.DateTimeField(null=True, blank=True)
    window_closes_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "attendance_session"
        indexes = [models.Index(fields=["branch", "is_open"])]

    def __str__(self):
        return self.label or f"Session {self.id}"


class AttendanceCheckpoint(models.Model):
    """One private, server-authorized usher checkpoint for a service."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    session = models.ForeignKey(AttendanceSession, on_delete=models.CASCADE, related_name="checkpoints")
    usher = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="attendance_checkpoints")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "attendance_checkpoint"
        constraints = [models.UniqueConstraint(fields=["session", "usher"], name="unique_usher_checkpoint_per_session")]
        indexes = [models.Index(fields=["session", "usher"])]


class AttendanceScanAttempt(models.Model):
    """Safe, token-redacted audit trail for each live-QR scan attempt."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    session = models.ForeignKey(AttendanceSession, null=True, blank=True, on_delete=models.SET_NULL, related_name="scan_attempts")
    checkpoint = models.ForeignKey(AttendanceCheckpoint, null=True, blank=True, on_delete=models.SET_NULL, related_name="scan_attempts")
    student = models.ForeignKey("members.Member", null=True, blank=True, on_delete=models.SET_NULL, related_name="attendance_scan_attempts")
    token_reference = models.CharField(max_length=64, blank=True)
    result = models.CharField(max_length=40)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "attendance_scan_attempt"
        indexes = [models.Index(fields=["session", "-created_at"]), models.Index(fields=["student", "-created_at"])]


class AttendanceRecord(models.Model):
    """
    A single check-in. Duplicate prevention: unique_together on
    (session, member) means a member cannot be double-recorded within
    the same session at the database level, not just in application code.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    session = models.ForeignKey(AttendanceSession, on_delete=models.CASCADE, related_name="records")
    member = models.ForeignKey(
        "members.Member", null=True, blank=True, on_delete=models.SET_NULL, related_name="attendance_records"
    )
    visitor = models.ForeignKey(
        "attendance.VisitorAttendance", null=True, blank=True, on_delete=models.CASCADE, related_name="+"
    )

    method = models.CharField(max_length=20, choices=AttendanceMethod.choices)
    status = models.CharField(
        max_length=10,
        choices=AttendanceStatus.choices,
        default=AttendanceStatus.PRESENT,
        help_text="Server-determined status: PRESENT (on-time), LATE (after grace period), "
                   "ABSENT (didn't check in), EXCUSED (administratively approved absence)",
    )
    device = models.ForeignKey(CheckInDevice, null=True, blank=True, on_delete=models.SET_NULL, related_name="records")
    checked_in_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    checkpoint = models.ForeignKey(
        AttendanceCheckpoint, null=True, blank=True, on_delete=models.SET_NULL, related_name="records"
    )
    checked_out_at = models.DateTimeField(
        null=True, blank=True,
        help_text="Optional check-out time for duration tracking. Must be >= checked_in_at.",
    )

    checked_in_at = models.DateTimeField()  # original event timestamp (preserved across offline sync)
    synced_at = models.DateTimeField(null=True, blank=True)  # when it reached the server, if different

    # Client-generated idempotency key for offline sync. Required for
    # OFFLINE-sourced records; makes re-submission of the same record safe.
    client_record_id = models.CharField(max_length=64, null=True, blank=True, unique=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "attendance_record"
        ordering = ["-checked_in_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["session", "member"],
                condition=models.Q(member__isnull=False),
                name="unique_member_per_session",
            )
        ]
        indexes = [
            models.Index(fields=["session", "member"]),
            models.Index(fields=["checked_in_at"]),
        ]

    def __str__(self):
        return f"{self.member or self.visitor} @ {self.checked_in_at}"


class AttendanceCorrection(models.Model):
    """Append-only explanation for an administrative attendance correction."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    record = models.ForeignKey(AttendanceRecord, on_delete=models.PROTECT, related_name="corrections")
    previous_status = models.CharField(max_length=10, choices=AttendanceStatus.choices)
    new_status = models.CharField(max_length=10, choices=AttendanceStatus.choices)
    reason = models.CharField(max_length=500)
    corrected_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="attendance_corrections")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "attendance_correction"
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["record", "-created_at"])]


class VisitorAttendance(models.Model):
    """Visitors don't have a Member record; captured separately, lightweight."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    session = models.ForeignKey(AttendanceSession, on_delete=models.CASCADE, related_name="visitors")
    visitor_record = models.ForeignKey(
        "visitors.Visitor", null=True, blank=True, on_delete=models.SET_NULL, related_name="attendance_records",
        help_text="Link to the full Visitor/first-timer domain record (apps.visitors), added in Phase 0. "
                   "Nullable so existing rows created before this link existed remain valid.",
    )
    full_name = models.CharField(max_length=255)
    phone_number = models.CharField(max_length=20, blank=True)
    email = models.EmailField(blank=True)
    how_heard = models.CharField(max_length=255, blank=True)
    invited_by = models.ForeignKey(
        "members.Member", null=True, blank=True, on_delete=models.SET_NULL, related_name="invited_visitors"
    )
    checked_in_at = models.DateTimeField()
    follow_up_status = models.CharField(
        max_length=20,
        choices=[("PENDING", "Pending"), ("CONTACTED", "Contacted"), ("CONVERTED", "Converted to Member")],
        default="PENDING",
    )

    class Meta:
        db_table = "attendance_visitor"
        ordering = ["-checked_in_at"]
