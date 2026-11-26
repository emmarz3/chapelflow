from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("notifications", "0008_alter_notification_category"),
    ]

    operations = [
        migrations.AlterField(
            model_name="notification",
            name="category",
            field=models.CharField(
                choices=[
                    ("ANNOUNCEMENT", "Chapel announcement"),
                    ("EVENT", "Event"),
                    ("SERVICE", "Service reminder"),
                    ("DEVOTIONAL", "Devotional"),
                    ("PRAYER", "Prayer update"),
                    ("PUBLIC_PRAYER", "Public prayer"),
                    ("FELLOWSHIP", "Fellowship update"),
                    ("LIVE_SERVICE", "Live service"),
                    ("ADMIN_ALERT", "Administrative alert"),
                    ("AD_REVIEW", "Advertising review"),
                    ("BIRTHDAY", "Birthday"),
                    ("OTHER", "Other"),
                ],
                default="OTHER",
                max_length=16,
            ),
        ),
    ]
