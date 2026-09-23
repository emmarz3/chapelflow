# Generated manually for Phase 3 - Dynamic RBAC
# This migration adds the new Role model and related structures while
# maintaining full backward compatibility with existing User.role field

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0004_alter_rolepermission_role_alter_user_role'),
    ]

    operations = [
        # 1. Create Role model
        migrations.CreateModel(
            name='Role',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('code', models.CharField(db_index=True, help_text="Unique role code, e.g. 'SUPER_ADMIN', 'FELLOWSHIP_LEADER'", max_length=32, unique=True)),
                ('name', models.CharField(help_text='Display name for UI', max_length=100)),
                ('description', models.TextField(blank=True)),
                ('scope_type', models.CharField(choices=[('GLOBAL', 'Global (all organizations)'), ('ORG_WIDE', 'Organization-wide'), ('BRANCH', 'Branch-only'), ('ASSIGNMENT', 'Assignment-based (Fellowship/Unit/Group)'), ('SELF', 'Self-only')], help_text='Determines what organizational scope this role can access', max_length=20)),
                ('assignment_group_types', models.JSONField(blank=True, default=list, help_text="For ASSIGNMENT scope: ['FELLOWSHIP'] | ['UNIT'] | ['MINISTRY']")),
                ('is_system', models.BooleanField(default=False, help_text='System role (seeded from code), cannot be deleted')),
                ('is_active', models.BooleanField(default=True, help_text='Inactive roles cannot be assigned to new users')),
                ('requires_mfa', models.BooleanField(default=False, help_text='Users with this role must complete MFA enrollment')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'db_table': 'accounts_role',
                'ordering': ['name'],
            },
        ),
        
        # 2. Create RoleAssignmentHistory model
        migrations.CreateModel(
            name='RoleAssignmentHistory',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('previous_role_code', models.CharField(blank=True, help_text='Previous role code (legacy or role_obj.code)', max_length=32)),
                ('new_role_code', models.CharField(blank=True, help_text='New role code (legacy or role_obj.code)', max_length=32)),
                ('reason', models.TextField(blank=True, help_text='Reason for role change')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('changed_by', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='role_changes_made', to=settings.AUTH_USER_MODEL)),
                ('new_role', models.ForeignKey(blank=True, help_text='New role object', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to='accounts.role')),
                ('previous_role', models.ForeignKey(blank=True, help_text='Previous role object', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to='accounts.role')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='role_history', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'db_table': 'accounts_role_assignment_history',
                'ordering': ['-created_at'],
            },
        ),
        
        # 3. Enhance Permission model (add new fields)
        migrations.AddField(
            model_name='permission',
            name='name',
            field=models.CharField(default='', help_text='Human-readable name', max_length=100),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='permission',
            name='module',
            field=models.CharField(blank=True, db_index=True, help_text='Module name: members, events, finance, etc.', max_length=50),
        ),
        migrations.AddField(
            model_name='permission',
            name='is_active',
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name='permission',
            name='created_at',
            field=models.DateTimeField(auto_now_add=True, null=True),
        ),
        
        # 4. Make User.role nullable (for migration to role_obj)
        migrations.AlterField(
            model_name='user',
            name='role',
            field=models.CharField(blank=True, db_index=True, help_text='LEGACY: Use role_obj for new code. Kept for backward compatibility.', max_length=32, null=True),
        ),
        
        # 5. Add role_obj FK to User
        migrations.AddField(
            model_name='user',
            name='role_obj',
            field=models.ForeignKey(blank=True, help_text='Phase 3: Dynamic role assignment', null=True, on_delete=django.db.models.deletion.PROTECT, related_name='users', to='accounts.role'),
        ),
        
        # 6. Update RolePermission structure
        # Rename existing 'role' field to 'legacy_role_code'
        migrations.RenameField(
            model_name='rolepermission',
            old_name='role',
            new_name='legacy_role_code',
        ),
        
        # Make legacy_role_code nullable
        migrations.AlterField(
            model_name='rolepermission',
            name='legacy_role_code',
            field=models.CharField(blank=True, db_index=True, help_text='LEGACY: For migration only, use role_obj for new code', max_length=32, null=True),
        ),
        
        # Drop the old auto-incrementing BigAutoField primary key from
        # 0001_initial before adding the new UUID one below — AddField
        # can't reuse the 'id' column name while the old one still
        # exists, and the model (apps/accounts/models.py) declares
        # id = UUIDField(primary_key=True, ...), so this must actually
        # become the primary key, not a plain field.
        migrations.RemoveField(
            model_name='rolepermission',
            name='id',
        ),

        # Add UUID primary key to RolePermission
        migrations.AddField(
            model_name='rolepermission',
            name='id',
            field=models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False),
            preserve_default=False,
        ),
        
        # Add role_obj FK to RolePermission
        migrations.AddField(
            model_name='rolepermission',
            name='role_obj',
            field=models.ForeignKey(blank=True, help_text='Phase 3: Dynamic role FK', null=True, on_delete=django.db.models.deletion.CASCADE, related_name='permissions', to='accounts.role'),
        ),
        
        # Add created_at timestamp
        migrations.AddField(
            model_name='rolepermission',
            name='created_at',
            field=models.DateTimeField(auto_now_add=True, null=True),
        ),
        
        # Remove old unique_together constraint
        migrations.AlterUniqueTogether(
            name='rolepermission',
            unique_together=set(),
        ),
        
        # 7. Add indexes
        migrations.AddIndex(
            model_name='rolepermission',
            index=models.Index(fields=['role_obj', 'permission'], name='accounts_ro_role_ob_idx'),
        ),
        migrations.AddIndex(
            model_name='rolepermission',
            index=models.Index(fields=['legacy_role_code', 'permission'], name='accounts_ro_legacy__idx'),
        ),
        migrations.AddIndex(
            model_name='roleassignmenthistory',
            index=models.Index(fields=['user', '-created_at'], name='accounts_ro_user_id_idx'),
        ),
        
        # 8. Add check constraint (will be enforced at application level for safety)
        # Note: CheckConstraint added separately in next migration to avoid issues
        # with existing data during migration
    ]
