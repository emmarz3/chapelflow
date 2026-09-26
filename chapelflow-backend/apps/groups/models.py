import uuid

from django.db import models


class GroupRole(models.TextChoices):
    LEADER = "LEADER", "Leader"
    ASSISTANT_LEADER = "ASSISTANT_LEADER", "Assistant Leader"
    MEMBER = "MEMBER", "Member"


class GroupMembership(models.Model):
    """
    Join table between members.Member and ministries.Group. Kept in its
    own app (rather than a plain ManyToManyField) so a member's role,
    join date, and status within the group can be tracked explicitly.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    member = models.ForeignKey("members.Member", on_delete=models.CASCADE, related_name="group_memberships")
    group = models.ForeignKey("ministries.Group", on_delete=models.CASCADE, related_name="memberships")
    role = models.CharField(max_length=20, choices=GroupRole.choices, default=GroupRole.MEMBER)
    joined_at = models.DateField(auto_now_add=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "groups_membership"
        unique_together = ("member", "group")
        indexes = [models.Index(fields=["group", "role"])]

    def __str__(self):
        return f"{self.member} in {self.group} as {self.role}"


class JoinRequestStatus(models.TextChoices):
    PENDING = "PENDING", "Pending"
    APPROVED = "APPROVED", "Approved"
    REJECTED = "REJECTED", "Rejected"


class GroupJoinRequest(models.Model):
    """A reviewable request; membership is created only on explicit approval."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    group = models.ForeignKey("ministries.Group", on_delete=models.CASCADE, related_name="join_requests")
    member = models.ForeignKey("members.Member", on_delete=models.CASCADE, related_name="group_join_requests")
    message = models.CharField(max_length=500, blank=True)
    status = models.CharField(max_length=12, choices=JoinRequestStatus.choices, default=JoinRequestStatus.PENDING)
    requested_at = models.DateTimeField(auto_now_add=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    resolved_by = models.ForeignKey("accounts.User", null=True, blank=True, on_delete=models.SET_NULL, related_name="resolved_group_join_requests")

    class Meta:
        db_table = "groups_join_request"
        constraints = [models.UniqueConstraint(fields=["group", "member"], name="unique_group_join_request")]
        indexes = [models.Index(fields=["group", "status"])]


class GroupTaskStatus(models.TextChoices):
    OPEN = "OPEN", "Open"
    IN_PROGRESS = "IN_PROGRESS", "In progress"
    COMPLETE = "COMPLETE", "Complete"


class GroupTask(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    group = models.ForeignKey("ministries.Group", on_delete=models.CASCADE, related_name="tasks")
    title = models.CharField(max_length=180)
    description = models.TextField(blank=True)
    assignee = models.ForeignKey("members.Member", null=True, blank=True, on_delete=models.SET_NULL, related_name="group_tasks")
    status = models.CharField(max_length=15, choices=GroupTaskStatus.choices, default=GroupTaskStatus.OPEN)
    due_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey("accounts.User", null=True, on_delete=models.SET_NULL, related_name="created_group_tasks")
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "groups_task"
        indexes = [models.Index(fields=["group", "status", "due_at"])]


class GroupMeeting(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    group = models.ForeignKey("ministries.Group", on_delete=models.CASCADE, related_name="meetings")
    title = models.CharField(max_length=180)
    starts_at = models.DateTimeField()
    ends_at = models.DateTimeField(null=True, blank=True)
    location = models.CharField(max_length=255, blank=True)
    agenda = models.TextField(blank=True)
    created_by = models.ForeignKey("accounts.User", null=True, on_delete=models.SET_NULL, related_name="created_group_meetings")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "groups_meeting"
        indexes = [models.Index(fields=["group", "starts_at"])]


class GroupMeetingAttendance(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    meeting = models.ForeignKey(GroupMeeting, on_delete=models.CASCADE, related_name="attendance")
    member = models.ForeignKey("members.Member", on_delete=models.CASCADE, related_name="group_meeting_attendance")
    present = models.BooleanField(default=True)
    recorded_by = models.ForeignKey("accounts.User", null=True, on_delete=models.SET_NULL, related_name="recorded_group_meeting_attendance")
    recorded_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "groups_meeting_attendance"
        constraints = [models.UniqueConstraint(fields=["meeting", "member"], name="unique_group_meeting_attendance")]


class GroupMessage(models.Model):
    """A membership-only conversation message; messages are intentionally append-only."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    group = models.ForeignKey("ministries.Group", on_delete=models.CASCADE, related_name="messages")
    author = models.ForeignKey("accounts.User", on_delete=models.CASCADE, related_name="group_messages")
    body = models.TextField(max_length=4000)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "groups_message"
        ordering = ["created_at", "id"]
        indexes = [models.Index(fields=["group", "created_at"], name="groups_mes_group_created_idx")]


class GroupResource(models.Model):
    """Leader-managed links for a group’s study, meeting and training material."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    group = models.ForeignKey("ministries.Group", on_delete=models.CASCADE, related_name="resources")
    title = models.CharField(max_length=180)
    url = models.URLField(max_length=2048)
    description = models.TextField(blank=True)
    created_by = models.ForeignKey("accounts.User", null=True, on_delete=models.SET_NULL, related_name="created_group_resources")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "groups_resource"
        ordering = ["-created_at", "-id"]
        indexes = [models.Index(fields=["group", "created_at"], name="groups_res_group_created_idx")]
