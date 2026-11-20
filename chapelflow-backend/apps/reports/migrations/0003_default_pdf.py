from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("reports", "0002_reportjob_progress")]

    operations = [
        migrations.AlterField(
            model_name="reportjob",
            name="export_format",
            field=models.CharField(
                choices=[("CSV", "CSV"), ("EXCEL", "Excel"), ("PDF", "PDF")],
                default="PDF", max_length=10,
            ),
        ),
    ]
