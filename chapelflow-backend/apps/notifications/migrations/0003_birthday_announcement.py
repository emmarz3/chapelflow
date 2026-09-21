# Generated manually to keep the new birthday workflow independently deployable.

import uuid

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("notifications", "0002_notification_source_announcement_and_more"),
        ("members", "0006_alter_member_community"),
    ]

    operations = [
        migrations.CreateModel(
            name="BirthdayAnnouncement",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("celebrated_on", models.DateField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("member", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="birthday_announcements", to="members.member")),
            ],
            options={"db_table": "notifications_birthday_announcement"},
        ),
        migrations.AddConstraint(
            model_name="birthdayannouncement",
            constraint=models.UniqueConstraint(fields=("member", "celebrated_on"), name="unique_member_birthday_announcement"),
        ),
        migrations.AddIndex(
            model_name="birthdayannouncement",
            index=models.Index(fields=["celebrated_on"], name="notificatio_celebra_e72f02_idx"),
        ),
        migrations.AddField(
            model_name="notification",
            name="birthday_announcement",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="notifications", to="notifications.birthdayannouncement"),
        ),
    ]
