from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("communications", "0003_announcement_audience_type_announcement_channels_and_more")]

    operations = [
        migrations.AddField(
            model_name="communicationpreference",
            name="prayer_notifications_enabled",
            field=models.BooleanField(default=False),
        ),
    ]
