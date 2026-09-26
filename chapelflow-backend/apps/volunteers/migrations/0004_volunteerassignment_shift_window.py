from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("volunteers", "0003_volunteeravailability_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="volunteerassignment",
            name="shift_starts_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="volunteerassignment",
            name="shift_ends_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
