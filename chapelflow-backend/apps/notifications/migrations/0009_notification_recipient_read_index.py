from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("notifications", "0008_alter_notification_category"),
    ]

    operations = [
        migrations.AddIndex(
            model_name="notification",
            index=models.Index(
                fields=["recipient", "read_at", "created_at"],
                name="notif_rec_read_created_idx",
            ),
        ),
    ]
