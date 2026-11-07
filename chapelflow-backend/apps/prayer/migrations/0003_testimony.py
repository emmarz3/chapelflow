# Generated manually for ChapelFlow testimony moderation.

import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("members", "0004_engagementmetrics_memberfollowup"),
        ("organizations", "0001_initial"),
        ("prayer", "0002_prayerrequest_answered_at_and_more"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Testimony",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("title", models.CharField(max_length=180)),
                ("details", models.TextField()),
                ("consent_to_publish", models.BooleanField(default=False)),
                ("status", models.CharField(choices=[("PENDING", "Pending pastoral review"), ("APPROVED", "Approved for sharing"), ("REJECTED", "Not approved")], default="PENDING", max_length=12)),
                ("reviewed_at", models.DateTimeField(blank=True, null=True)),
                ("rejection_reason", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("branch", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="testimonies", to="organizations.branch")),
                ("member", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="testimonies", to="members.member")),
                ("reviewed_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="reviewed_testimonies", to=settings.AUTH_USER_MODEL)),
            ],
            options={"db_table": "prayer_testimony", "ordering": ["-created_at"]},
        ),
        migrations.AddIndex(model_name="testimony", index=models.Index(fields=["branch", "status"], name="prayer_tes_branch_status_idx")),
        migrations.AddIndex(model_name="testimony", index=models.Index(fields=["member", "status"], name="prayer_tes_member_status_idx")),
    ]
