from django.db import migrations


def migrate_legacy_unit_leaders(apps, schema_editor):
    User = apps.get_model("accounts", "User")
    Role = apps.get_model("accounts", "Role")

    User.objects.filter(role="UNIT_LEADER").update(role="UNIT_HEAD")

    legacy_role = Role.objects.filter(code="UNIT_LEADER").first()
    current_role = Role.objects.filter(code="UNIT_HEAD").first()
    if legacy_role is not None and current_role is not None:
        User.objects.filter(role_obj=legacy_role).update(
            role="UNIT_HEAD",
            role_obj=current_role,
        )


class Migration(migrations.Migration):
    dependencies = [("accounts", "0010_institutionalaccountcontrol_user_created_by_and_more")]

    operations = [
        migrations.RunPython(migrate_legacy_unit_leaders, migrations.RunPython.noop),
    ]
