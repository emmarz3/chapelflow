from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("accounts", "0016_user_photo_url")]

    operations = [
        migrations.AddField(
            model_name="user",
            name="bio",
            field=models.CharField(blank=True, default="", max_length=200),
        ),
    ]
