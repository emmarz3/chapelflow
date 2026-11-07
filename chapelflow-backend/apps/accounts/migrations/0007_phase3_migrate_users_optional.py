# Generated manually for Phase 3 - Dynamic RBAC
# OPTIONAL MIGRATION: Migrate existing users from legacy role field to role_obj FK
#
# This migration is OPTIONAL and NON-BREAKING. It can be run at any time
# after 0006, or skipped entirely. Users will continue working with legacy
# role field until this is run.
#
# To apply: python manage.py migrate accounts 0007_phase3_migrate_users_optional
# To skip: Don't run this migration - users stay on legacy system

from django.db import migrations


def migrate_users_to_role_obj(apps, schema_editor):
    """
    Migrate users from legacy User.role string to User.role_obj FK.
    
    This is OPTIONAL - the system works with either approach. This migration
    simply moves users to the new system for consistency.
    """
    User = apps.get_model('accounts', 'User')
    Role = apps.get_model('accounts', 'Role')
    RoleAssignmentHistory = apps.get_model('accounts', 'RoleAssignmentHistory')
    
    migrated_count = 0
    skipped_count = 0
    
    # Only migrate users who haven't been migrated yet and have a legacy role
    for user in User.objects.filter(role_obj__isnull=True).exclude(role__isnull=True).exclude(role=''):
        try:
            role_obj = Role.objects.get(code=user.role)
            
            # Save previous state for audit
            previous_role_code = user.role
            
            # Migrate to role_obj
            user.role_obj = role_obj
            user.save(update_fields=['role_obj'])
            
            # Create audit record
            RoleAssignmentHistory.objects.create(
                user=user,
                previous_role_code=previous_role_code,
                new_role=role_obj,
                new_role_code=role_obj.code,
                reason='Automated migration from legacy role to dynamic role system (Phase 3)',
                changed_by=None  # System migration
            )
            
            migrated_count += 1
            
        except Role.DoesNotExist:
            skipped_count += 1
            print(f"Warning: No Role object found for user {user.id} with legacy role '{user.role}'")
    
    print(f"Phase 3: Migrated {migrated_count} users to role_obj ({skipped_count} skipped)")
    
    if skipped_count > 0:
        print(f"WARNING: {skipped_count} users were not migrated due to missing Role objects.")
        print("These users will continue using the legacy role field.")


def reverse_migration(apps, schema_editor):
    """
    Reverse the migration - clear role_obj but restore legacy role field.
    """
    User = apps.get_model('accounts', 'User')
    
    # For users with role_obj set, restore the role code to legacy field
    for user in User.objects.filter(role_obj__isnull=False):
        if user.role_obj:
            user.role = user.role_obj.code
            user.role_obj = None
            user.save(update_fields=['role', 'role_obj'])
    
    print("Phase 3: Reversed user migration (restored legacy role field)")


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0006_phase3_seed_roles'),
    ]

    operations = [
        migrations.RunPython(migrate_users_to_role_obj, reverse_migration),
    ]
