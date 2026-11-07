# Generated for ChapelFlow operations endpoints.
import django.db.models.deletion
import uuid
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("organizations", "0001_initial"),
    ]
    operations = [
        migrations.CreateModel(
            name="DutyRoster",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("title", models.CharField(max_length=255)),
                ("details", models.TextField()),
                ("status", models.CharField(default="DRAFT", max_length=20)),
                ("branch", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="%(app_label)s_%(class)s_records", to="organizations.branch")),
                ("created_by", models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="+", to=settings.AUTH_USER_MODEL)),
            ],
            options={"db_table": "operations_duty_roster", "ordering": ["-created_at"]},
        ),
        migrations.CreateModel(
            name="WorkerLeaveRequest",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("reason", models.TextField()),
                ("status", models.CharField(default="PENDING", max_length=20)),
                ("branch", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="%(app_label)s_%(class)s_records", to="organizations.branch")),
                ("created_by", models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="+", to=settings.AUTH_USER_MODEL)),
            ],
            options={"db_table": "operations_worker_leave_request", "ordering": ["-created_at"]},
        ),
        migrations.CreateModel(
            name="FinanceTransaction",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("description", models.CharField(max_length=255)),
                ("amount", models.DecimalField(decimal_places=2, max_digits=14)),
                ("category", models.CharField(max_length=100)),
                ("transaction_type", models.CharField(choices=[("INCOME", "Income"), ("EXPENSE", "Expense")], default="INCOME", max_length=10)),
                ("status", models.CharField(default="RECORDED", max_length=20)),
                ("branch", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="%(app_label)s_%(class)s_records", to="organizations.branch")),
                ("created_by", models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="+", to=settings.AUTH_USER_MODEL)),
            ],
            options={"db_table": "operations_finance_transaction", "ordering": ["-created_at"]},
        ),
        migrations.CreateModel(
            name="Asset",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("name", models.CharField(max_length=255)),
                ("details", models.TextField()),
                ("status", models.CharField(default="AVAILABLE", max_length=20)),
                ("branch", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="%(app_label)s_%(class)s_records", to="organizations.branch")),
                ("created_by", models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="+", to=settings.AUTH_USER_MODEL)),
            ],
            options={"db_table": "operations_asset", "ordering": ["name"]},
        ),
        migrations.CreateModel(
            name="MediaItem",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("title", models.CharField(max_length=255)),
                ("details", models.TextField()),
                ("status", models.CharField(default="DRAFT", max_length=20)),
                ("branch", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="%(app_label)s_%(class)s_records", to="organizations.branch")),
                ("created_by", models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="+", to=settings.AUTH_USER_MODEL)),
            ],
            options={"db_table": "operations_media_item", "ordering": ["-created_at"]},
        ),
        migrations.CreateModel(
            name="ContentEntry",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("title", models.CharField(max_length=255)),
                ("slug", models.SlugField(max_length=255)),
                ("details", models.TextField()),
                ("status", models.CharField(default="DRAFT", max_length=20)),
                ("published_at", models.DateTimeField(blank=True, null=True)),
                ("branch", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="%(app_label)s_%(class)s_records", to="organizations.branch")),
                ("created_by", models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="+", to=settings.AUTH_USER_MODEL)),
            ],
            options={"db_table": "operations_content_entry", "ordering": ["-updated_at"]},
        ),
        migrations.CreateModel(
            name="PrivacyRequest",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("request_type", models.CharField(choices=[("EXPORT", "Data export"), ("DELETION", "Account deletion")], max_length=10)),
                ("reason", models.TextField(blank=True)),
                ("status", models.CharField(default="PENDING", max_length=20)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("completed_at", models.DateTimeField(blank=True, null=True)),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="privacy_requests", to=settings.AUTH_USER_MODEL)),
            ],
            options={"db_table": "operations_privacy_request", "ordering": ["-created_at"]},
        ),
        migrations.AddConstraint(model_name="financetransaction", constraint=models.CheckConstraint(condition=models.Q(("amount__gt", 0)), name="operations_finance_amount_positive")),
        migrations.AddConstraint(model_name="contententry", constraint=models.UniqueConstraint(fields=("branch", "slug"), name="unique_content_slug_per_branch")),
        migrations.AddConstraint(model_name="privacyrequest", constraint=models.UniqueConstraint(condition=models.Q(("status", "PENDING")), fields=("user", "request_type"), name="one_pending_privacy_request_per_type")),
    ]
