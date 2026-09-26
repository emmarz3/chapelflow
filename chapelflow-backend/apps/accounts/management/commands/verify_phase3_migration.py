"""
Phase 3: Management command to verify the dynamic RBAC migration status.

Usage:
    python manage.py verify_phase3_migration
    python manage.py verify_phase3_migration --verbose
"""
from django.core.management.base import BaseCommand
from django.db import connection

from apps.accounts.models import Role, RolePermission, User, RoleAssignmentHistory


class Command(BaseCommand):
    help = 'Verify Phase 3 dynamic RBAC migration status'

    def add_arguments(self, parser):
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Show detailed migration status',
        )

    def handle(self, *args, **options):
        verbose = options['verbose']
        
        self.stdout.write(self.style.SUCCESS('\n=== Phase 3 Migration Verification ===\n'))
        
        # Check if Role table exists
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT COUNT(*) 
                FROM information_schema.tables 
                WHERE table_name = 'accounts_role'
            """)
            role_table_exists = cursor.fetchone()[0] > 0
        
        if not role_table_exists:
            self.stdout.write(self.style.ERROR('❌ Role table does not exist - migrations not applied'))
            return
        
        self.stdout.write(self.style.SUCCESS('✓ Role table exists'))
        
        # Check Role objects
        role_count = Role.objects.count()
        system_role_count = Role.objects.filter(is_system=True).count()
        custom_role_count = Role.objects.filter(is_system=False).count()
        active_role_count = Role.objects.filter(is_active=True).count()
        
        self.stdout.write(f'  Total roles: {role_count}')
        self.stdout.write(f'  System roles: {system_role_count}')
        self.stdout.write(f'  Custom roles: {custom_role_count}')
        self.stdout.write(f'  Active roles: {active_role_count}')
        
        if verbose:
            self.stdout.write('\n  System roles:')
            for role in Role.objects.filter(is_system=True).order_by('code'):
                status = '✓ active' if role.is_active else '○ inactive'
                mfa = '🔒 MFA' if role.requires_mfa else '  '
                self.stdout.write(f'    - {role.code:30s} {status:12s} {mfa:6s} [{role.scope_type}]')
        
        # Check RolePermission migration
        total_rp = RolePermission.objects.count()
        legacy_rp = RolePermission.objects.filter(legacy_role_code__isnull=False, role_obj__isnull=True).count()
        migrated_rp = RolePermission.objects.filter(role_obj__isnull=False).count()
        
        self.stdout.write(f'\n✓ RolePermission migration:')
        self.stdout.write(f'  Total: {total_rp}')
        self.stdout.write(f'  Migrated to role_obj: {migrated_rp}')
        self.stdout.write(f'  Still using legacy: {legacy_rp}')
        
        if legacy_rp > 0:
            self.stdout.write(self.style.WARNING(
                f'  ⚠ {legacy_rp} RolePermissions still using legacy role codes'
            ))
        
        # Check User migration
        total_users = User.objects.count()
        migrated_users = User.objects.filter(role_obj__isnull=False).count()
        legacy_users = User.objects.filter(role_obj__isnull=True).exclude(role__isnull=True).exclude(role='').count()
        null_role_users = User.objects.filter(role_obj__isnull=True, role__isnull=True).count()
        
        self.stdout.write(f'\n✓ User role migration:')
        self.stdout.write(f'  Total users: {total_users}')
        self.stdout.write(f'  Using role_obj: {migrated_users}')
        self.stdout.write(f'  Using legacy role: {legacy_users}')
        self.stdout.write(f'  No role assigned: {null_role_users}')
        
        migration_percentage = (migrated_users / total_users * 100) if total_users > 0 else 0
        
        if migrated_users == 0 and legacy_users > 0:
            self.stdout.write(self.style.WARNING(
                '\n  ⚠ Users have not been migrated to role_obj yet'
            ))
            self.stdout.write(self.style.WARNING(
                '    This is OPTIONAL - system works with legacy roles'
            ))
            self.stdout.write(self.style.WARNING(
                f'    To migrate: python manage.py migrate accounts 0007_phase3_migrate_users_optional'
            ))
        elif legacy_users > 0:
            self.stdout.write(self.style.WARNING(
                f'\n  ⚠ {legacy_users} users still using legacy role field'
            ))
            self.stdout.write(f'    Migration: {migration_percentage:.1f}% complete')
        else:
            self.stdout.write(self.style.SUCCESS(
                f'\n  ✓ All users migrated to role_obj system'
            ))
        
        if verbose and legacy_users > 0:
            self.stdout.write('\n  Users with legacy roles:')
            for user in User.objects.filter(role_obj__isnull=True).exclude(role__isnull=True).exclude(role='')[:10]:
                self.stdout.write(f'    - {user.email or user.matric_no or user.id}: {user.role}')
            if legacy_users > 10:
                self.stdout.write(f'    ... and {legacy_users - 10} more')
        
        # Check RoleAssignmentHistory
        history_count = RoleAssignmentHistory.objects.count()
        self.stdout.write(f'\n✓ RoleAssignmentHistory: {history_count} records')
        
        if verbose and history_count > 0:
            recent = RoleAssignmentHistory.objects.order_by('-created_at')[:5]
            self.stdout.write('\n  Recent role changes:')
            for record in recent:
                user_display = record.user.email or record.user.matric_no or str(record.user.id)
                change = f'{record.previous_role_code or "None"} → {record.new_role_code or "None"}'
                self.stdout.write(f'    - {user_display}: {change}')
        
        # Check Permission enhancements
        permissions_with_module = Permission.objects.exclude(module='').count()
        permissions_total = Permission.objects.count()
        
        self.stdout.write(f'\n✓ Permission enhancements:')
        self.stdout.write(f'  Total permissions: {permissions_total}')
        self.stdout.write(f'  With module metadata: {permissions_with_module}')
        
        # Summary
        self.stdout.write(self.style.SUCCESS('\n=== Migration Status Summary ===\n'))
        
        all_checks = [
            (role_table_exists, 'Role table exists'),
            (role_count >= 8, f'System roles seeded ({role_count}/8+)'),
            (migrated_rp > 0, 'RolePermissions linked to roles'),
            (permissions_with_module > 0, 'Permission metadata populated'),
        ]
        
        passed = sum(1 for check, _ in all_checks if check)
        total = len(all_checks)
        
        for check, description in all_checks:
            status = '✓' if check else '✗'
            color = self.style.SUCCESS if check else self.style.ERROR
            self.stdout.write(color(f'{status} {description}'))
        
        self.stdout.write(f'\nPassed: {passed}/{total} checks')
        
        if passed == total:
            self.stdout.write(self.style.SUCCESS('\n✓ Phase 3 migration successfully applied'))
            
            if legacy_users > 0:
                self.stdout.write(self.style.WARNING(
                    f'\nNote: {legacy_users} users still on legacy role system'
                ))
                self.stdout.write(self.style.WARNING(
                    'This is normal - migration 0007 is optional'
                ))
        else:
            self.stdout.write(self.style.ERROR('\n✗ Phase 3 migration incomplete'))
            self.stdout.write('Run: python manage.py migrate accounts')
        
        self.stdout.write('')  # Blank line


from apps.accounts.models import Permission
