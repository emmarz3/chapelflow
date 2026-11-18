# Generated manually for Phase 3 - Dynamic RBAC
# Add database constraints for data integrity
#
# This migration adds CHECK constraints to ensure:
# 1. RolePermission has exactly one of role_obj or legacy_role_code set

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0007_phase3_migrate_users_optional'),
    ]

    operations = [
        # Add check constraint to ensure exactly one role type is set
        migrations.AddConstraint(
            model_name='rolepermission',
            constraint=models.CheckConstraint(
                condition=(
                    models.Q(role_obj__isnull=False, legacy_role_code__isnull=True) |
                    models.Q(role_obj__isnull=True, legacy_role_code__isnull=False)
                ),
                name='role_permission_one_role_type'
            ),
        ),
    ]
