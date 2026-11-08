"""Store Chapel leadership office labels and register least-privilege account roles."""
from django.db import migrations, models


def seed_office_roles(apps, schema_editor):
    Role = apps.get_model("accounts", "Role")
    Permission = apps.get_model("accounts", "Permission")
    RolePermission = apps.get_model("accounts", "RolePermission")
    offices = [
        ("ASSISTANT_STUDENT_CHAPLAIN", "Assistant Student Chaplain", True, ["events.view", "members.view"]),
        ("HOSTEL_COORDINATOR", "Hostel Fellowship Coordinator", False, ["events.view"]),
    ]
    for code, name, requires_mfa, grants in offices:
        role, _ = Role.objects.get_or_create(
            code=code,
            defaults={
                "name": name,
                "description": "Chapel leadership role restricted to the assigned branch and explicitly granted permissions.",
                "scope_type": "BRANCH",
                "assignment_group_types": [],
                "is_system": True,
                "is_active": True,
                "requires_mfa": requires_mfa,
            },
        )
        # Do not replace or broaden an existing customized role's permissions.
        for permission in Permission.objects.filter(code__in=grants):
            RolePermission.objects.get_or_create(role_obj=role, permission=permission)


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0012_student_chaplain_mfa"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="institutional_office",
            field=models.CharField(
                blank=True, default="", max_length=64,
                help_text="Position in Chapel leadership register; never prefilled with a person name.",
            ),
        ),
        migrations.RunPython(seed_office_roles, migrations.RunPython.noop),
    ]
