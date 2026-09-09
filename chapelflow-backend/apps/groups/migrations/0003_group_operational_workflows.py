import django.db.models.deletion
import uuid
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("groups", "0002_initial"),
        ("members", "0001_initial"),
        ("ministries", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="GroupJoinRequest",
            fields=[
                ("id", models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, serialize=False)),
                ("message", models.CharField(max_length=500, blank=True)),
                ("status", models.CharField(max_length=12, choices=[("PENDING", "Pending"), ("APPROVED", "Approved"), ("REJECTED", "Rejected")], default="PENDING")),
                ("requested_at", models.DateTimeField(auto_now_add=True)),
                ("resolved_at", models.DateTimeField(null=True, blank=True)),
                ("group", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="join_requests", to="ministries.group")),
                ("member", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="group_join_requests", to="members.member")),
                ("resolved_by", models.ForeignKey(null=True, blank=True, on_delete=django.db.models.deletion.SET_NULL, related_name="resolved_group_join_requests", to=settings.AUTH_USER_MODEL)),
            ],
            options={"db_table": "groups_join_request"},
        ),
        migrations.CreateModel(
            name="GroupTask",
            fields=[
                ("id", models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, serialize=False)),
                ("title", models.CharField(max_length=180)), ("description", models.TextField(blank=True)),
                ("status", models.CharField(max_length=15, choices=[("OPEN", "Open"), ("IN_PROGRESS", "In progress"), ("COMPLETE", "Complete")], default="OPEN")),
                ("due_at", models.DateTimeField(null=True, blank=True)), ("created_at", models.DateTimeField(auto_now_add=True)), ("completed_at", models.DateTimeField(null=True, blank=True)),
                ("assignee", models.ForeignKey(null=True, blank=True, on_delete=django.db.models.deletion.SET_NULL, related_name="group_tasks", to="members.member")),
                ("created_by", models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="created_group_tasks", to=settings.AUTH_USER_MODEL)),
                ("group", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="tasks", to="ministries.group")),
            ], options={"db_table": "groups_task"},
        ),
        migrations.CreateModel(
            name="GroupMeeting",
            fields=[
                ("id", models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, serialize=False)),
                ("title", models.CharField(max_length=180)), ("starts_at", models.DateTimeField()), ("ends_at", models.DateTimeField(null=True, blank=True)),
                ("location", models.CharField(max_length=255, blank=True)), ("agenda", models.TextField(blank=True)), ("created_at", models.DateTimeField(auto_now_add=True)),
                ("created_by", models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="created_group_meetings", to=settings.AUTH_USER_MODEL)),
                ("group", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="meetings", to="ministries.group")),
            ], options={"db_table": "groups_meeting"},
        ),
        migrations.CreateModel(
            name="GroupMeetingAttendance",
            fields=[
                ("id", models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, serialize=False)), ("present", models.BooleanField(default=True)), ("recorded_at", models.DateTimeField(auto_now=True)),
                ("meeting", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="attendance", to="groups.groupmeeting")),
                ("member", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="group_meeting_attendance", to="members.member")),
                ("recorded_by", models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="recorded_group_meeting_attendance", to=settings.AUTH_USER_MODEL)),
            ], options={"db_table": "groups_meeting_attendance"},
        ),
        migrations.AddConstraint(model_name="groupjoinrequest", constraint=models.UniqueConstraint(fields=("group", "member"), name="unique_group_join_request")),
        migrations.AddConstraint(model_name="groupmeetingattendance", constraint=models.UniqueConstraint(fields=("meeting", "member"), name="unique_group_meeting_attendance")),
        migrations.AddIndex(model_name="groupjoinrequest", index=models.Index(fields=["group", "status"], name="groups_join_group_i_700b8c_idx")),
        migrations.AddIndex(model_name="grouptask", index=models.Index(fields=["group", "status", "due_at"], name="groups_task_group_i_977a52_idx")),
        migrations.AddIndex(model_name="groupmeeting", index=models.Index(fields=["group", "starts_at"], name="groups_meet_group_i_4bab38_idx")),
    ]
