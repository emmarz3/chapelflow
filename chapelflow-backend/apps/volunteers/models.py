import uuid

from django.db import models


class VolunteerStatus(models.TextChoices):
    """Volunteer profile lifecycle status."""
    PENDING = "PENDING", "Pending onboarding"
    ACTIVE = "ACTIVE", "Active"
    INACTIVE = "INACTIVE", "Inactive"


class VolunteerProfile(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    member = models.OneToOneField("members.Member", on_delete=models.CASCADE, related_name="volunteer_profile")
    skills = models.JSONField(default=list, blank=True, help_text="e.g. ['ushering', 'media', 'sound']")
    availability_notes = models.CharField(max_length=500, blank=True)
    is_active = models.BooleanField(default=True)
    status = models.CharField(
        max_length=10,
        choices=VolunteerStatus.choices,
        default=VolunteerStatus.ACTIVE,
        help_text="Phase 9 onboarding lifecycle. Defaults to ACTIVE so existing rows and call sites that never set this stay behaviorally unchanged.",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "volunteers_profile"
        ordering = ["-created_at"]

    def __str__(self):
        return str(self.member)


class VolunteerRole(models.TextChoices):
    USHER = "USHER", "Usher"
    CHOIR = "CHOIR", "Choir"
    MEDIA = "MEDIA", "Media"
    SECURITY = "SECURITY", "Security"
    TECHNICAL = "TECHNICAL", "Technical"
    PROTOCOL = "PROTOCOL", "Protocol"
    OTHER = "OTHER", "Other"


class AssignmentStatus(models.TextChoices):
    """Assignment lifecycle status with controlled transitions."""
    PENDING = "PENDING", "Pending confirmation"
    CONFIRMED = "CONFIRMED", "Confirmed"
    DECLINED = "DECLINED", "Declined"
    COMPLETED = "COMPLETED", "Completed"
    CANCELLED = "CANCELLED", "Cancelled"


class VolunteerAssignment(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    volunteer = models.ForeignKey(VolunteerProfile, on_delete=models.CASCADE, related_name="assignments")
    event_schedule = models.ForeignKey(
        "events.EventSchedule", null=True, blank=True, on_delete=models.SET_NULL, related_name="volunteer_assignments"
    )
    group = models.ForeignKey(
        "ministries.Group", null=True, blank=True, on_delete=models.SET_NULL, related_name="volunteer_assignments"
    )
    role = models.CharField(max_length=20, choices=VolunteerRole.choices)
    status = models.CharField(max_length=10, choices=AssignmentStatus.choices, default=AssignmentStatus.PENDING)
    confirmed = models.BooleanField(default=False)
    notes = models.CharField(max_length=255, blank=True)
    hours_logged = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    responded_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    reminder_sent_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "volunteers_assignment"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["volunteer", "status"]),
        ]

    def __str__(self):
        return f"{self.volunteer} - {self.role} ({self.status})"


class VolunteerAvailability(models.Model):
    """
    Volunteer availability windows. By default (is_available=False), these
    represent UNAVAILABLE periods ('I'm busy Tuesday evenings'). If a
    volunteer opts into explicit availability tracking, is_available=True
    windows can be used instead.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    volunteer = models.ForeignKey(VolunteerProfile, on_delete=models.CASCADE, related_name="availability")
    weekday = models.IntegerField(
        choices=[
            (0, "Monday"),
            (1, "Tuesday"),
            (2, "Wednesday"),
            (3, "Thursday"),
            (4, "Friday"),
            (5, "Saturday"),
            (6, "Sunday"),
        ]
    )
    start_time = models.TimeField()
    end_time = models.TimeField()
    is_available = models.BooleanField(
        default=False,
        help_text="False (default) = this is an UNAVAILABLE window (the common case people record: 'busy Tuesday evenings'). "
                  "True = an explicit availability window, used only if the volunteer has opted into whitelist-style availability.",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "volunteers_availability"
        ordering = ["weekday", "start_time"]
        indexes = [
            models.Index(fields=["volunteer", "weekday"]),
        ]

    def __str__(self):
        avail = "Available" if self.is_available else "Unavailable"
        weekday_name = dict(self._meta.get_field('weekday').choices)[self.weekday]
        return f"{self.volunteer} - {weekday_name} {self.start_time}-{self.end_time} ({avail})"
