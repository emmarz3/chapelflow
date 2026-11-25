import uuid
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("communications", "0006_backfill_preference_users"),
        ("ministries", "0005_group_unique_group_name_per_branch_type"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="LeadershipNotice",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("title", models.CharField(max_length=180)),
                ("body", models.TextField(max_length=5000)),
                ("audience", models.CharField(choices=[("ALL", "All unit and fellowship leaders"), ("UNIT", "Unit heads"), ("FELLOWSHIP", "Fellowship leaders"), ("SELECTED", "Selected communities")], max_length=12)),
                ("email_requested", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("branch", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="leadership_notices", to="organizations.branch")),
                ("created_by", models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="sent_leadership_notices", to=settings.AUTH_USER_MODEL)),
                ("target_groups", models.ManyToManyField(blank=True, related_name="leadership_notices", to="ministries.group")),
            ],
            options={"db_table": "communications_leadership_notice"},
        ),
        migrations.CreateModel(
            name="LeadershipDelivery",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("read_at", models.DateTimeField(blank=True, null=True)),
                ("acknowledged_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("notice", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="deliveries", to="communications.leadershipnotice")),
                ("recipient", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="leadership_deliveries", to=settings.AUTH_USER_MODEL)),
            ],
            options={"db_table": "communications_leadership_delivery"},
        ),
        migrations.CreateModel(
            name="LeadershipReply",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("body", models.TextField(max_length=2000)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("author", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="+", to=settings.AUTH_USER_MODEL)),
                ("delivery", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="replies", to="communications.leadershipdelivery")),
            ],
            options={"db_table": "communications_leadership_reply", "ordering": ["created_at", "id"]},
        ),
        migrations.AddConstraint(
            model_name="leadershipdelivery",
            constraint=models.UniqueConstraint(fields=("notice", "recipient"), name="unique_leadership_notice_recipient"),
        ),
        migrations.AddIndex(
            model_name="leadershipnotice",
            index=models.Index(fields=["branch", "-created_at"], name="comm_lead_branch_created_idx"),
        ),
    ]
