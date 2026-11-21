from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("accounts", "0015_usher_mfa")]
    operations = [
        migrations.AddField(
            model_name="user", name="photo_url",
            field=models.URLField(blank=True, default="", max_length=500),
        ),
    ]
