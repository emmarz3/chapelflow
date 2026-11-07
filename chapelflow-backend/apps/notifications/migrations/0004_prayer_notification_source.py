import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("notifications", "0003_birthday_announcement"),
        ("prayer", "0003_testimony"),
    ]

    operations = [
        migrations.AddField(
            model_name="notification",
            name="source_prayer_request",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="notifications",
                to="prayer.prayerrequest",
            ),
        ),
        migrations.AddConstraint(
            model_name="notification",
            constraint=models.UniqueConstraint(
                condition=models.Q(source_prayer_request__isnull=False),
                fields=("source_prayer_request", "recipient"),
                name="unique_prayer_notification_recipient",
            ),
        ),
    ]
