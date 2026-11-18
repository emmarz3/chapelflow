import secrets
import uuid

from django.conf import settings
from django.db import models


class MembershipStatus(models.TextChoices):
    ACTIVE = "ACTIVE", "Active"
    INACTIVE = "INACTIVE", "Inactive"
    TRANSFERRED = "TRANSFERRED", "Transferred"
    DECEASED = "DECEASED", "Deceased"
    PENDING = "PENDING", "Pending"


class CommunityClassification(models.TextChoices):
    """
    Staff Community is NOT a role (spec section 1) — it's a member
    classification/segment, alongside Student. Used for attendance/report
    segmentation and communication targeting, never for RBAC.
    """
    STUDENT = "STUDENT", "Student"
    STAFF = "STAFF", "Staff Community"
    GUEST = "GUEST", "Guest"


class AcademicLevel(models.TextChoices):
    JUPEB = "JUPEB", "JUPEB"
    LEVEL_100 = "100", "100 Level"
    LEVEL_200 = "200", "200 Level"
    LEVEL_300 = "300", "300 Level"
    LEVEL_400 = "400", "400 Level"
    LEVEL_500 = "500", "500 Level"
    LEVEL_600 = "600", "600 Level"


class Member(models.Model):
    """
    Church/member profile, separated from the auth identity (accounts.User).
    Not every member has a login (e.g. children, elderly members registered
    by a family head), so this is NOT a strict 1:1 with User.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="member_profile"
    )
    branch = models.ForeignKey("organizations.Branch", on_delete=models.PROTECT, related_name="members")
    household = models.ForeignKey(
        "households.Household", null=True, blank=True, on_delete=models.SET_NULL, related_name="members"
    )

    # University Edition academic affiliation (spec section 2/8). Deliberately
    # separate from Chapel-side Fellowship/Unit/Ministry (apps.groups) — see
    # docs/university_structure.md. Optional because not every branch runs
    # the University Edition and not every member type has one (e.g. staff
    # without a College/Department).
    college = models.ForeignKey(
        "university.College", null=True, blank=True, on_delete=models.SET_NULL, related_name="members"
    )
    department = models.ForeignKey(
        "university.Department", null=True, blank=True, on_delete=models.SET_NULL, related_name="members"
    )
    community = models.CharField(
        max_length=10, choices=CommunityClassification.choices, blank=True,
        help_text="Student or Staff Community. A classification, not a role — see CommunityClassification.",
    )
    academic_level = models.CharField(
        max_length=5,
        choices=AcademicLevel.choices,
        blank=True,
        db_index=True,
        help_text="Required for students; not applicable to staff community members.",
    )
    fellowship = models.ForeignKey(
        "ministries.Group", null=True, blank=True, on_delete=models.SET_NULL,
        related_name="fellowship_members", limit_choices_to={"group_type": "FELLOWSHIP"},
        help_text="A member has at most one Fellowship (spec section 2). Units/Ministries are many-to-many via GroupMembership.",
    )

    first_name = models.CharField(max_length=150)
    last_name = models.CharField(max_length=150)
    other_names = models.CharField(max_length=150, blank=True)
    gender = models.CharField(max_length=10, choices=[("MALE", "Male"), ("FEMALE", "Female")], blank=True)
    date_of_birth = models.DateField(null=True, blank=True)

    email = models.EmailField(blank=True)
    phone_number = models.CharField(max_length=20, blank=True)
    address = models.CharField(max_length=500, blank=True)

    photo_url = models.URLField(blank=True)

    membership_status = models.CharField(max_length=20, choices=MembershipStatus.choices, default=MembershipStatus.ACTIVE)
    membership_date = models.DateField(null=True, blank=True)

    emergency_contact_name = models.CharField(max_length=150, blank=True)
    emergency_contact_phone = models.CharField(max_length=20, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "members_member"
        ordering = ["last_name", "first_name"]
        indexes = [
            models.Index(fields=["branch", "membership_status"]),
            models.Index(fields=["last_name", "first_name"]),
        ]

    def __str__(self):
        return f"{self.first_name} {self.last_name}"

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}".strip()


def is_student_community_member(member):
    """True only for student records; legacy blank classifications remain students."""
    return bool(member) and (member.community or CommunityClassification.STUDENT) == CommunityClassification.STUDENT


class JupebStudent(Member):
    class Meta:
        proxy = True
        verbose_name = "JUPEB student"
        verbose_name_plural = "JUPEB students"


class Level100Student(Member):
    class Meta:
        proxy = True
        verbose_name = "100 Level student"
        verbose_name_plural = "100 Level students"


class Level200Student(Member):
    class Meta:
        proxy = True
        verbose_name = "200 Level student"
        verbose_name_plural = "200 Level students"


class Level300Student(Member):
    class Meta:
        proxy = True
        verbose_name = "300 Level student"
        verbose_name_plural = "300 Level students"


class Level400Student(Member):
    class Meta:
        proxy = True
        verbose_name = "400 Level student"
        verbose_name_plural = "400 Level students"


class Level500Student(Member):
    class Meta:
        proxy = True
        verbose_name = "500 Level student"
        verbose_name_plural = "500 Level students"


class Level600Student(Member):
    class Meta:
        proxy = True
        verbose_name = "600 Level student"
        verbose_name_plural = "600 Level students"


class MemberTag(models.Model):
    member = models.ForeignKey(Member, on_delete=models.CASCADE, related_name="tags")
    label = models.CharField(max_length=64)

    class Meta:
        db_table = "members_tag"
        unique_together = ("member", "label")


class MembershipHistory(models.Model):
    member = models.ForeignKey(Member, on_delete=models.CASCADE, related_name="history")
    previous_status = models.CharField(max_length=20, choices=MembershipStatus.choices, blank=True)
    new_status = models.CharField(max_length=20, choices=MembershipStatus.choices)
    previous_branch = models.ForeignKey(
        "organizations.Branch", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    new_branch = models.ForeignKey(
        "organizations.Branch", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    note = models.CharField(max_length=500, blank=True)
    changed_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "members_membership_history"
        ordering = ["-created_at"]


def _generate_qr_token():
    return secrets.token_urlsafe(24)


class MemberQRCode(models.Model):
    """
    A secure random token mapped internally to a member. The QR image
    encodes ONLY this token — never name, email, phone, or any PII.
    """

    member = models.OneToOneField(Member, on_delete=models.CASCADE, related_name="qr_code")
    token = models.CharField(max_length=64, unique=True, default=_generate_qr_token, editable=False)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    regenerated_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "members_qr_code"

    def regenerate(self):
        from django.utils import timezone
        self.token = _generate_qr_token()
        self.regenerated_at = timezone.now()
        self.save(update_fields=["token", "regenerated_at"])



class MemberFollowUpMilestone(models.TextChoices):
    """
    Phase 11: New member follow-up milestones.
    Auto-generated at 7, 30, and 90 days after membership.
    """
    DAY_7 = "DAY_7", "7-Day Follow-Up"
    DAY_30 = "DAY_30", "30-Day Follow-Up"
    DAY_90 = "DAY_90", "90-Day Follow-Up"


class MemberFollowUp(models.Model):
    """
    Phase 11: New member follow-up tracking.
    
    Automatically created on member registration (via signal).
    Mirrors the visitor follow-up architecture for consistency.
    
    Workflow:
    1. Member created with ACTIVE status
    2. Signal generates 3 follow-up tasks (7/30/90 days)
    3. Tasks assigned to fellowship leader or pastoral staff
    4. Periodic task sends reminders when due
    5. Staff completes follow-up and records notes
    
    Security:
    - Branch-scoped (via member.branch)
    - Assignment restricted by RBAC
    - Notes visible to assigned staff + pastoral team
    
    Idempotency:
    - reminder_sent_at ensures no duplicate reminders
    - unique_together prevents duplicate milestones per member
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    member = models.ForeignKey(
        Member,
        on_delete=models.CASCADE,
        related_name="follow_ups",
        help_text="Member being followed up"
    )
    milestone = models.CharField(
        max_length=10,
        choices=MemberFollowUpMilestone.choices,
        help_text="Which follow-up milestone (7/30/90 days)"
    )
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="member_follow_up_assignments",
        help_text="Staff member assigned to complete this follow-up"
    )
    scheduled_for = models.DateTimeField(
        help_text="When this follow-up is due"
    )
    completed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When follow-up was completed"
    )
    notes = models.TextField(
        blank=True,
        help_text="Follow-up notes (what was discussed, next steps)"
    )
    reminder_sent_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When reminder was sent. Prevents duplicate reminders (idempotency)."
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = "members_follow_up"
        ordering = ["scheduled_for"]
        unique_together = [["member", "milestone"]]  # Prevent duplicate milestones
        indexes = [
            models.Index(fields=["scheduled_for", "completed_at"]),
            models.Index(fields=["assigned_to", "completed_at"]),
            models.Index(fields=["reminder_sent_at"]),
        ]
    
    def __str__(self):
        return f"{self.get_milestone_display()} for {self.member.full_name}"


class EngagementMetrics(models.Model):
    """
    Phase 11: Materialized engagement metrics per member.
    
    Calculated periodically (daily) via Celery task rather than on-demand
    for performance. Tracks participation across:
    - Services (attendance)
    - Events
    - Volunteering
    - Giving (optional - privacy consideration)
    
    Engagement score (0-100):
    - Attendance: max 40 points
    - Events: max 20 points
    - Volunteering: max 30 points
    - Giving: max 10 points
    
    Used for:
    - Pastor dashboard (member engagement overview)
    - Inactive member detection
    - Fellowship leader reports
    - Targeted outreach campaigns
    """
    member = models.OneToOneField(
        Member,
        on_delete=models.CASCADE,
        related_name="engagement_metrics",
        primary_key=True
    )
    
    # Attendance metrics
    services_attended_30d = models.IntegerField(
        default=0,
        help_text="Services attended in last 30 days"
    )
    services_attended_90d = models.IntegerField(
        default=0,
        help_text="Services attended in last 90 days"
    )
    last_service_date = models.DateField(
        null=True,
        blank=True,
        help_text="Date of most recent service attendance"
    )
    attendance_rate_30d = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0,
        help_text="Attendance rate in last 30 days (0-100%)"
    )
    
    # Event participation
    events_attended_30d = models.IntegerField(
        default=0,
        help_text="Events attended in last 30 days"
    )
    events_attended_90d = models.IntegerField(
        default=0,
        help_text="Events attended in last 90 days"
    )
    last_event_date = models.DateField(
        null=True,
        blank=True,
        help_text="Date of most recent event attendance"
    )
    
    # Volunteering
    volunteer_assignments_active = models.IntegerField(
        default=0,
        help_text="Currently active volunteer assignments"
    )
    volunteer_assignments_completed = models.IntegerField(
        default=0,
        help_text="Total volunteer assignments completed (all time)"
    )
    last_volunteer_date = models.DateField(
        null=True,
        blank=True,
        help_text="Date of most recent volunteer activity"
    )
    
    # Giving (optional - may be disabled for privacy)
    giving_count_30d = models.IntegerField(
        default=0,
        help_text="Number of gifts in last 30 days"
    )
    giving_count_90d = models.IntegerField(
        default=0,
        help_text="Number of gifts in last 90 days"
    )
    last_giving_date = models.DateField(
        null=True,
        blank=True,
        help_text="Date of most recent giving"
    )
    
    # Overall engagement
    engagement_score = models.IntegerField(
        default=0,
        help_text="Overall engagement score (0-100)"
    )
    days_since_last_activity = models.IntegerField(
        default=0,
        help_text="Days since any recorded activity"
    )
    
    # Metadata
    last_calculated_at = models.DateTimeField(
        auto_now=True,
        help_text="When metrics were last calculated"
    )
    
    class Meta:
        db_table = "members_engagement_metrics"
        indexes = [
            models.Index(fields=["engagement_score"]),
            models.Index(fields=["days_since_last_activity"]),
        ]
    
    def __str__(self):
        return f"Engagement: {self.member.full_name} (Score: {self.engagement_score})"
