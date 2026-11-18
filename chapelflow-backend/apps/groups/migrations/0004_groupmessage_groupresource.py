import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("groups", "0003_group_operational_workflows"),
        ("ministries", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="GroupMessage",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("body", models.TextField(max_length=4000)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("author", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="group_messages", to=settings.AUTH_USER_MODEL)),
                ("group", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="messages", to="ministries.group")),
            ],
            options={"db_table": "groups_message", "ordering": ["created_at", "id"]},
        ),
        migrations.CreateModel(
            name="GroupResource",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("title", models.CharField(max_length=180)),
                ("url", models.URLField(max_length=2048)),
                ("description", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("created_by", models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="created_group_resources", to=settings.AUTH_USER_MODEL)),
                ("group", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="resources", to="ministries.group")),
            ],
            options={"db_table": "groups_resource", "ordering": ["-created_at", "-id"]},
        ),
        migrations.AddIndex(model_name="groupmessage", index=models.Index(fields=["group", "created_at"], name="groups_mes_group_created_idx")),
        migrations.AddIndex(model_name="groupresource", index=models.Index(fields=["group", "created_at"], name="groups_res_group_created_idx")),
    ]
