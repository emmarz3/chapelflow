import uuid

from django.conf import settings
from django.db import models


class VisitorStatus(models.TextChoices):
    """
    Spec section 4 flow:
    Visitor -> First-Timer Form -> Visitor Record -> Follow-Up ->
    Optional Full Registration -> Member
    """
    NEW = "NEW", "New"
    CONTACTED = "CONTACTED", "Contacted"
    FOLLOWED_UP = "FOLLOWED_UP", "Followed Up"
    REGISTERED = "REGISTERED", "Registered as Member"
    LAPSED = "LAPSED", "Lapsed (no further contact)"


class Visitor(models.Model):
    """
    The proper visitor/first-timer domain record (spec section 4).
    Deliberately separate from apps.attendance.VisitorAttendance — that
    model only captures "someone unregistered checked in to a session";
    this one is the actual first-timer relationship: who they are, how
    they heard about the Chapel, and where they are in the follow-up ->
    registration pipeline, independent of any single attendance record.
    A Visitor is public/guest data — no branch-scoped RBAC beyond branch
    isolation is needed, since visitors have no login of their own here.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    branch = models.ForeignKey("organizations.Branch", on_delete=models.PROTECT, related_name="visitors")

    full_name = models.CharField(max_length=255)
    phone_number = models.CharField(max_length=20, blank=True)
    email = models.EmailField(blank=True)
    gender = models.CharField(max_length=10, choices=[("MALE", "Male"), ("FEMALE", "Female")], blank=True)
    address = models.CharField(max_length=500, blank=True)

    how_heard = models.CharField(max_length=255, blank=True)
    invited_by = models.ForeignKey(
        "members.Member", null=True, blank=True, on_delete=models.SET_NULL, related_name="invited_visitors_v2"
    )

    first_visit_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=VisitorStatus.choices, default=VisitorStatus.NEW)

    # Set only once the Optional Full Registration step (spec section 4)
    # actually happens — the Visitor record itself is never deleted, so
    # the first-timer history survives the conversion.
    converted_member = models.OneToOneField(
        "members.Member", null=True, blank=True, on_delete=models.SET_NULL, related_name="visitor_origin"
    )
    converted_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "visitors_visitor"
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["branch", "status"])]

    def __str__(self):
        return self.full_name


class VisitorFollowUp(models.Model):
    """One follow-up touchpoint in the pipeline. A Visitor can have several."""

    class Method(models.TextChoices):
        CALL = "CALL", "Phone Call"
        SMS = "SMS", "SMS"
        EMAIL = "EMAIL", "Email"
        VISIT = "VISIT", "In-Person Visit"
        WHATSAPP = "WHATSAPP", "WhatsApp"

    class Outcome(models.TextChoices):
        PENDING = "PENDING", "Pending"
        REACHED = "REACHED", "Reached"
        NO_RESPONSE = "NO_RESPONSE", "No Response"
        NOT_INTERESTED = "NOT_INTERESTED", "Not Interested"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    visitor = models.ForeignKey(Visitor, on_delete=models.CASCADE, related_name="follow_ups")
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="visitor_follow_ups"
    )
    method = models.CharField(max_length=20, choices=Method.choices)
    outcome = models.CharField(max_length=20, choices=Outcome.choices, default=Outcome.PENDING)
    notes = models.CharField(max_length=1000, blank=True)
    scheduled_for = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    reminder_sent_at = models.DateTimeField(
        null=True, blank=True,
        help_text="Stamped by apps.visitors.tasks.send_pending_follow_up_reminders the first (and only) "
                   "time a reminder notification is sent for this follow-up, so a periodic beat task "
                   "never reminds the same follow-up twice.",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "visitors_follow_up"
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["visitor", "outcome"])]

    def __str__(self):
        return f"Follow-up for {self.visitor} via {self.method}"
