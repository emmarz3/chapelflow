from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("attendance", "0008_attendancecorrection"),
    ]

    operations = [
        migrations.AddField(
            model_name="attendancesession",
            name="venue",
            field=models.CharField(blank=True, max_length=120),
        ),
    ]
