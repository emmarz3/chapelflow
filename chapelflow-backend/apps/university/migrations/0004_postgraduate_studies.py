from django.db import migrations


def add_postgraduate_studies(apps, schema_editor):
    alias = schema_editor.connection.alias
    University = apps.get_model("university", "University")
    College = apps.get_model("university", "College")
    Department = apps.get_model("university", "Department")
    university = University.objects.using(alias).filter(slug="chrisland-university").first()
    if not university:
        return  # bootstrap_chapel will create the catalogue when the chapel is initialized.
    college, _ = College.objects.using(alias).get_or_create(
        university=university, name="Postgraduate College",
    )
    Department.objects.using(alias).get_or_create(college=college, name="Postgraduate Studies")


class Migration(migrations.Migration):
    dependencies = [("university", "0003_seed_chrisland_programmes")]
    operations = [migrations.RunPython(add_postgraduate_studies, migrations.RunPython.noop)]
