from django.db import migrations


def require_student_chaplain_mfa(apps, schema_editor):
    Role = apps.get_model("accounts", "Role")
    Role.objects.filter(code="STUDENT_CHAPLAIN").update(requires_mfa=True)


class Migration(migrations.Migration):

    dependencies = [("accounts", "0011_migrate_legacy_unit_leaders")]

    operations = [migrations.RunPython(require_student_chaplain_mfa, migrations.RunPython.noop)]
