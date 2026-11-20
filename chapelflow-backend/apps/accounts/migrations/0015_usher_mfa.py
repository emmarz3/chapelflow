from django.db import migrations


def require_usher_mfa(apps, schema_editor):
    apps.get_model("accounts", "Role").objects.filter(code="ATTENDANCE_USHER").update(requires_mfa=True)


class Migration(migrations.Migration):
    dependencies = [("accounts", "0014_user_deleted_at")]
    operations = [migrations.RunPython(require_usher_mfa, migrations.RunPython.noop)]
