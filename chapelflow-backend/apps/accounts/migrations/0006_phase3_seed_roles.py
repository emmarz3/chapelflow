# Generated manually for Phase 3 - Dynamic RBAC
# This migration seeds the Role objects from existing role constants
# and links existing RolePermissions to the new Role objects

from django.db import migrations


def seed_roles(apps, schema_editor):
    """
    Create Role objects for all current role codes from constants.
    These become the system roles that cannot be deleted.
    """
    Role = apps.get_model('accounts', 'Role')
    
    # Define all system roles with their configurations
    system_roles = [
        {
            'code': 'SUPER_ADMIN',
            'name': 'Super Admin',
            'description': 'System-wide administrative access. Can manage all organizations, branches, and users.',
            'scope_type': 'GLOBAL',
            'assignment_group_types': [],
            'is_system': True,
            'is_active': True,
            'requires_mfa': True,
        },
        {
            'code': 'CHAPLAIN',
            'name': 'Chaplain',
            'description': 'University-wide Chapel operational authority. Can access all branches within their organization.',
            'scope_type': 'ORG_WIDE',
            'assignment_group_types': [],
            'is_system': True,
            'is_active': True,
            'requires_mfa': True,
        },
        {
            'code': 'CHAPEL_ADMIN',
            'name': 'Chapel Admin',
            'description': 'Branch-level Chapel administration. Can manage their assigned branch only.',
            'scope_type': 'BRANCH',
            'assignment_group_types': [],
            'is_system': True,
            'is_active': True,
            'requires_mfa': True,
        },
        {
            'code': 'FELLOWSHIP_LEADER',
            'name': 'Fellowship Leader',
            'description': 'Leads one or more Fellowships. Can only access their assigned Fellowship(s).',
            'scope_type': 'ASSIGNMENT',
            'assignment_group_types': ['FELLOWSHIP'],
            'is_system': True,
            'is_active': True,
            'requires_mfa': False,
        },
        {
            'code': 'UNIT_HEAD',
            'name': 'Unit Head',
            'description': 'Leads one or more Units. Can only access their assigned Unit(s).',
            'scope_type': 'ASSIGNMENT',
            'assignment_group_types': ['UNIT'],
            'is_system': True,
            'is_active': True,
            'requires_mfa': False,
        },
        {
            'code': 'MINISTRY_GROUP_LEADER',
            'name': 'Ministry/Group Leader',
            'description': 'Leads one or more Ministry Groups. Can only access their assigned group(s).',
            'scope_type': 'ASSIGNMENT',
            'assignment_group_types': ['MINISTRY'],
            'is_system': True,
            'is_active': True,
            'requires_mfa': False,
        },
        {
            'code': 'MEMBER',
            'name': 'Member',
            'description': 'Regular member with self-only access. Can view and update own profile.',
            'scope_type': 'SELF',
            'assignment_group_types': [],
            'is_system': True,
            'is_active': True,
            'requires_mfa': False,
        },
        {
            'code': 'VISITOR',
            'name': 'Visitor',
            'description': 'Limited access for visitors and first-timers.',
            'scope_type': 'SELF',
            'assignment_group_types': [],
            'is_system': True,
            'is_active': True,
            'requires_mfa': False,
        },
        # Legacy roles - kept for backward compatibility but marked inactive
        {
            'code': 'PASTOR',
            'name': 'Pastor (Legacy)',
            'description': 'Legacy role - migrated users should be assigned to appropriate current roles.',
            'scope_type': 'ORG_WIDE',
            'assignment_group_types': [],
            'is_system': True,
            'is_active': False,  # Inactive - cannot be assigned to new users
            'requires_mfa': True,
        },
        {
            'code': 'FINANCE_OFFICER',
            'name': 'Finance Officer (Legacy)',
            'description': 'Legacy role - migrated users should be assigned to appropriate current roles.',
            'scope_type': 'BRANCH',
            'assignment_group_types': [],
            'is_system': True,
            'is_active': False,
            'requires_mfa': True,
        },
        {
            'code': 'COMMUNITY_LEADER',
            'name': 'Community Leader (Legacy)',
            'description': 'Legacy role - migrated users should be assigned to appropriate current roles.',
            'scope_type': 'BRANCH',
            'assignment_group_types': [],
            'is_system': True,
            'is_active': False,
            'requires_mfa': False,
        },
        {
            'code': 'MINISTRY_LEADER',
            'name': 'Ministry Leader (Legacy)',
            'description': 'Legacy role - migrated users should be assigned to appropriate current roles.',
            'scope_type': 'ASSIGNMENT',
            'assignment_group_types': ['MINISTRY'],
            'is_system': True,
            'is_active': False,
            'requires_mfa': False,
        },
        {
            'code': 'DEPARTMENT_LEADER',
            'name': 'Department Leader (Legacy)',
            'description': 'Legacy role - migrated users should be assigned to appropriate current roles.',
            'scope_type': 'BRANCH',
            'assignment_group_types': [],
            'is_system': True,
            'is_active': False,
            'requires_mfa': False,
        },
        {
            'code': 'UNIT_LEADER',
            'name': 'Unit Leader (Legacy)',
            'description': 'Legacy role - migrated to UNIT_HEAD.',
            'scope_type': 'ASSIGNMENT',
            'assignment_group_types': ['UNIT'],
            'is_system': True,
            'is_active': False,
            'requires_mfa': False,
        },
        {
            'code': 'VOLUNTEER',
            'name': 'Volunteer (Legacy)',
            'description': 'Legacy role - migrated users should be assigned MEMBER role.',
            'scope_type': 'SELF',
            'assignment_group_types': [],
            'is_system': True,
            'is_active': False,
            'requires_mfa': False,
        },
    ]
    
    created_count = 0
    for role_data in system_roles:
        role, created = Role.objects.get_or_create(
            code=role_data['code'],
            defaults=role_data
        )
        if created:
            created_count += 1
    
    print(f"Phase 3: Created {created_count} Role objects")


def link_role_permissions_to_roles(apps, schema_editor):
    """
    Link existing RolePermission entries (with legacy_role_code) to
    the new Role objects.
    """
    Role = apps.get_model('accounts', 'Role')
    RolePermission = apps.get_model('accounts', 'RolePermission')
    
    linked_count = 0
    skipped_count = 0
    
    for rp in RolePermission.objects.filter(role_obj__isnull=True):
        if rp.legacy_role_code:
            try:
                role_obj = Role.objects.get(code=rp.legacy_role_code)
                rp.role_obj = role_obj
                rp.save(update_fields=['role_obj'])
                linked_count += 1
            except Role.DoesNotExist:
                skipped_count += 1
                print(f"Warning: No Role object found for legacy code '{rp.legacy_role_code}'")
    
    print(f"Phase 3: Linked {linked_count} RolePermissions to Role objects ({skipped_count} skipped)")


def populate_permission_metadata(apps, schema_editor):
    """
    Populate the new Permission.name and Permission.module fields
    from existing Permission.code values.
    """
    Permission = apps.get_model('accounts', 'Permission')
    
    updated_count = 0
    for perm in Permission.objects.filter(name=''):
        # Extract module and action from code (e.g., "members.view" -> "members", "view")
        parts = perm.code.split('.', 1)
        if len(parts) == 2:
            module, action = parts
            perm.module = module
            # Create readable name from code
            perm.name = f"{module.capitalize()} - {action.capitalize()}"
        else:
            perm.name = perm.code.replace('.', ' ').title()
            perm.module = 'system'
        
        perm.save(update_fields=['name', 'module'])
        updated_count += 1
    
    print(f"Phase 3: Updated {updated_count} Permission metadata fields")


def reverse_migration(apps, schema_editor):
    """
    Reverse operations - clear role_obj links but keep legacy_role_code intact.
    This allows safe rollback without losing permission data.
    """
    RolePermission = apps.get_model('accounts', 'RolePermission')
    
    # Clear role_obj FK but keep legacy_role_code
    RolePermission.objects.update(role_obj=None)
    
    print("Phase 3: Cleared role_obj links (rollback)")


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0005_phase3_add_role_model'),
    ]

    operations = [
        migrations.RunPython(seed_roles, reverse_migration),
        migrations.RunPython(link_role_permissions_to_roles, migrations.RunPython.noop),
        migrations.RunPython(populate_permission_metadata, migrations.RunPython.noop),
    ]
