from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("reports", "0001_initial")]

    operations = [
        migrations.AddField(
            model_name="reportjob",
            name="progress",
            field=models.PositiveSmallIntegerField(default=0),
        ),
        migrations.AddField(
            model_name="reportjob",
            name="rows_processed",
            field=models.PositiveIntegerField(default=0),
        ),
    ]
