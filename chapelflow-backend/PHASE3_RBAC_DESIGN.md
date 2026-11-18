# Phase 3 Dynamic RBAC Architecture Design

## OVERVIEW

This document defines the architecture for converting ChapelFlow's hardcoded role system into a fully dynamic, database-backed RBAC system while maintaining 100% backward compatibility with existing users and permissions.

---

## DESIGN PRINCIPLES

1. **Zero Breaking Changes**: Existing users, permissions, and authorization behavior must work identically
2. **Gradual Migration**: Support both legacy string roles and new Role model during transition
3. **Backward Compatible**: Old code using `user.role` string checks continues working
4. **Future Ready**: New code uses Role model for dynamic capabilities
5. **Safe Rollback**: Can revert to legacy system if issues discovered

---

## CURRENT STATE

```python
# Current (Phase 0-2)
User.role = CharField(max_length=32, choices=Roles.CHOICES)  # Hardcoded

RolePermission.role = CharField(max_length=32, choices=Roles.CHOICES)  # Hardcoded

# Authorization check
if user.role == Roles.SUPER_ADMIN:
    # ...

if user.role in Roles.PRIVILEGED_ROLES:
    # ...
```

**Problems**:
- Cannot create custom roles without code deployment
- Cannot modify role permissions without running seed script
- Cannot configure scope per role at runtime
- Role metadata (description, MFA policy) scattered across codebase

---

## TARGET STATE

```python
# Target (Phase 3)
class Role(models.Model):
    code = CharField(unique=True)  # e.g., "SUPER_ADMIN"
    name = CharField()  # Display name
    description = TextField()
    scope_type = CharField(choices=ScopeType.CHOICES)
    is_active = BooleanField(default=True)
    is_system = BooleanField(default=True)  # Cannot be deleted
    requires_mfa = BooleanField(default=False)
    created_at, updated_at = ...

User.role = CharField()  # Backward compatible legacy field
User.role_obj = ForeignKey(Role, null=True)  # New dynamic field

RolePermission.role_obj = ForeignKey(Role)  # New relationship

# Authorization check (backward compatible)
if user.get_role_code() == Roles.SUPER_ADMIN:  # Works with both
    # ...

if user.has_scope(ScopeType.GLOBAL):  # New capability
    # ...
```

**Benefits**:
- Administrators can create/edit roles via UI
- Role permissions editable without deployment
- Scope configuration per role
- MFA policy per role
- Full audit trail of role changes

---

## DATABASE SCHEMA

### New Models

#### 1. Role Model

```python
class ScopeType(models.TextChoices):
    """Organizational scope of a role."""
    GLOBAL = "GLOBAL", "Global (all organizations)"
    ORG_WIDE = "ORG_WIDE", "Organization-wide"
    BRANCH = "BRANCH", "Branch-only"
    ASSIGNMENT = "ASSIGNMENT", "Assignment-based (Fellowship/Unit/Group)"
    SELF = "SELF", "Self-only"

class Role(models.Model):
    """
    Database-backed role definition. System roles (is_system=True) are
    seeded and cannot be deleted, only deactivated. Custom roles
    (is_system=False) can be freely created/deleted by admins.
    """
    id = UUIDField(primary_key=True, default=uuid.uuid4)
    
    # Identity
    code = CharField(max_length=32, unique=True, db_index=True)
    name = CharField(max_length=100)
    description = TextField(blank=True)
    
    # Scope configuration
    scope_type = CharField(max_length=20, choices=ScopeType.CHOICES)
    
    # For ASSIGNMENT scope type, which group types can be led
    assignment_group_types = JSONField(
        default=list,
        help_text="For ASSIGNMENT scope: ['FELLOWSHIP'] | ['UNIT'] | ['MINISTRY']"
    )
    
    # Metadata
    is_system = BooleanField(default=False, help_text="System role, cannot be deleted")
    is_active = BooleanField(default=True)
    requires_mfa = BooleanField(default=False)
    
    # Audit
    created_at = DateTimeField(auto_now_add=True)
    updated_at = DateTimeField(auto_now=True)
    created_by = ForeignKey(User, null=True, on_delete=SET_NULL, related_name="+")
    
    class Meta:
        db_table = "accounts_role"
        ordering = ["name"]
    
    def __str__(self):
        return self.name
```

#### 2. Updated RolePermission

```python
class RolePermission(models.Model):
    """
    Maps a role to permissions. Now supports BOTH legacy string roles
    (during migration) and new Role objects (post-migration).
    """
    id = UUIDField(primary_key=True, default=uuid.uuid4)
    
    # NEW: FK to Role model
    role_obj = ForeignKey(
        Role, null=True, blank=True, on_delete=CASCADE,
        related_name="permissions"
    )
    
    # LEGACY: Keep for backward compatibility during migration
    legacy_role_code = CharField(
        max_length=32, null=True, blank=True, db_index=True,
        help_text="Deprecated: for migration only"
    )
    
    permission = ForeignKey(Permission, on_delete=CASCADE, related_name="role_grants")
    
    created_at = DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = "accounts_role_permission"
        # Ensure one of role_obj OR legacy_role_code is set
        constraints = [
            models.CheckConstraint(
                check=(
                    models.Q(role_obj__isnull=False, legacy_role_code__isnull=True) |
                    models.Q(role_obj__isnull=True, legacy_role_code__isnull=False)
                ),
                name="role_permission_one_role_type"
            )
        ]
        indexes = [
            models.Index(fields=["role_obj", "permission"]),
            models.Index(fields=["legacy_role_code", "permission"]),
        ]
    
    def __str__(self):
        role_display = self.role_obj.name if self.role_obj else self.legacy_role_code
        return f"{role_display} -> {self.permission.code}"
```

#### 3. Updated User Model

```python
class User(AbstractBaseUser, PermissionsMixin):
    # ... existing fields ...
    
    # LEGACY: Keep for backward compatibility
    role = CharField(
        max_length=32, null=True, blank=True, db_index=True,
        help_text="Deprecated: legacy role code for backward compatibility"
    )
    
    # NEW: FK to Role model
    role_obj = ForeignKey(
        Role, null=True, blank=True, on_delete=PROTECT,
        related_name="users",
        help_text="Dynamic role assignment (Phase 3+)"
    )
    
    # ... rest of model ...
    
    def get_role_code(self) -> str:
        """
        Get role code for authorization checks. Tries role_obj first
        (Phase 3+), falls back to legacy role field (Phase 0-2).
        This ensures both old and new code work during transition.
        """
        if self.role_obj_id:
            return self.role_obj.code
        return self.role or Roles.MEMBER
    
    def get_role_obj(self):
        """Get Role object, works with both legacy and new systems."""
        if self.role_obj:
            return self.role_obj
        # During migration: create virtual Role object from legacy code
        if self.role:
            return self._get_legacy_role_as_obj()
        return None
    
    def _get_legacy_role_as_obj(self):
        """
        Create a virtual Role object from legacy role code.
        Used during migration period.
        """
        from django.core.cache import cache
        cache_key = f"legacy_role_obj:{self.role}"
        cached = cache.get(cache_key)
        if cached:
            return cached
        
        # Look up or create Role object for legacy code
        role_obj, _ = Role.objects.get_or_create(
            code=self.role,
            defaults={
                "name": dict(Roles.CHOICES).get(self.role, self.role),
                "is_system": True,
                "is_active": True,
                "scope_type": self._infer_scope_type(self.role),
                "requires_mfa": self.role in Roles.PRIVILEGED_ROLES,
            }
        )
        cache.set(cache_key, role_obj, 3600)  # Cache 1 hour
        return role_obj
    
    def _infer_scope_type(self, role_code):
        """Map legacy role codes to scope types."""
        if role_code in Roles.GLOBAL_SCOPE_ROLES:
            return ScopeType.GLOBAL
        if role_code in Roles.ORG_WIDE_SCOPE_ROLES:
            return ScopeType.ORG_WIDE
        if role_code in Roles.ASSIGNMENT_SCOPED_ROLES:
            return ScopeType.ASSIGNMENT
        if role_code == Roles.MEMBER:
            return ScopeType.SELF
        return ScopeType.BRANCH
    
    def has_perm_code(self, code: str) -> bool:
        """Check permission (works with both legacy and new system)."""
        role_code = self.get_role_code()
        if role_code == Roles.SUPER_ADMIN:
            return True
        
        # Try new system first
        if self.role_obj_id:
            return self.role_obj.permissions.filter(permission__code=code).exists()
        
        # Fall back to legacy system
        return RolePermission.objects.filter(
            models.Q(role_obj__code=role_code) | models.Q(legacy_role_code=role_code),
            permission__code=code
        ).exists()
    
    def has_scope(self, scope_type: str) -> bool:
        """Check if user's role has given scope type."""
        role_obj = self.get_role_obj()
        if not role_obj:
            return False
        return role_obj.scope_type == scope_type
    
    def requires_mfa(self) -> bool:
        """Check if user's role requires MFA."""
        role_obj = self.get_role_obj()
        if not role_obj:
            return False
        return role_obj.requires_mfa
```

#### 4. RoleAssignmentHistory (New)

```python
class RoleAssignmentHistory(models.Model):
    """
    Audit trail for role changes. Critical for security review and
    compliance - must know who gave what role to whom and when.
    """
    id = UUIDField(primary_key=True, default=uuid.uuid4)
    
    user = ForeignKey(User, on_delete=CASCADE, related_name="role_history")
    previous_role = ForeignKey(
        Role, null=True, blank=True, on_delete=SET_NULL, related_name="+"
    )
    new_role = ForeignKey(
        Role, null=True, blank=True, on_delete=SET_NULL, related_name="+"
    )
    
    # Legacy support
    previous_role_code = CharField(max_length=32, blank=True)
    new_role_code = CharField(max_length=32, blank=True)
    
    reason = TextField(blank=True)
    changed_by = ForeignKey(
        User, on_delete=SET_NULL, null=True, related_name="role_changes_made"
    )
    
    created_at = DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = "accounts_role_assignment_history"
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["user", "-created_at"])]
```

#### 5. Enhanced Permission Model

```python
class Permission(models.Model):
    """Fine-grained action permissions."""
    code = CharField(max_length=64, unique=True, db_index=True)
    name = CharField(max_length=100)  # NEW: Human-readable name
    description = TextField(blank=True)
    
    # NEW: Categorization
    module = CharField(
        max_length=50, db_index=True,
        help_text="Module name: members, events, finance, etc."
    )
    
    # NEW: Metadata
    is_active = BooleanField(default=True)
    created_at = DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = "accounts_permission"
        ordering = ["module", "code"]
    
    def __str__(self):
        return f"{self.code} - {self.name}"
```

---

## MIGRATION STRATEGY

### Phase 3A: Add New Models (No Breaking Changes)

**Migration 1**: Add Role model, role_obj field to User (nullable)

```python
# 0001_phase3_add_role_model.py
- Create Role model
- Add User.role_obj (nullable FK)
- Add RolePermission.role_obj (nullable FK)
- Add RolePermission.legacy_role_code
- Rename RolePermission.role to legacy_role_code
- Add RoleAssignmentHistory model
- Enhance Permission model (add name, module, is_active)
```

**Migration 2**: Seed system roles from existing constants

```python
# 0002_phase3_seed_roles.py
def seed_roles(apps, schema_editor):
    Role = apps.get_model("accounts", "Role")
    
    # Create Role objects for all current role codes
    roles_to_create = [
        {
            "code": "SUPER_ADMIN",
            "name": "Super Admin",
            "scope_type": "GLOBAL",
            "is_system": True,
            "requires_mfa": True,
        },
        {
            "code": "CHAPLAIN",
            "name": "Chaplain",
            "scope_type": "ORG_WIDE",
            "is_system": True,
            "requires_mfa": True,
        },
        # ... all current roles
    ]
    
    for role_data in roles_to_create:
        Role.objects.get_or_create(code=role_data["code"], defaults=role_data)
```

**Migration 3**: Link existing RolePermissions to Role objects

```python
# 0003_phase3_link_role_permissions.py
def link_role_permissions(apps, schema_editor):
    Role = apps.get_model("accounts", "Role")
    RolePermission = apps.get_model("accounts", "RolePermission")
    
    for rp in RolePermission.objects.filter(role_obj__isnull=True):
        if rp.legacy_role_code:
            try:
                role_obj = Role.objects.get(code=rp.legacy_role_code)
                rp.role_obj = role_obj
                rp.save(update_fields=["role_obj"])
            except Role.DoesNotExist:
                pass  # Keep legacy_role_code for unmapped roles
```

### Phase 3B: Gradual User Migration (Optional)

**Migration 4**: Optionally migrate users to role_obj

```python
# 0004_phase3_migrate_users.py (OPTIONAL - can run later)
def migrate_users_to_role_obj(apps, schema_editor):
    User = apps.get_model("accounts", "User")
    Role = apps.get_model("accounts", "Role")
    
    for user in User.objects.filter(role_obj__isnull=True).exclude(role=""):
        try:
            role_obj = Role.objects.get(code=user.role)
            user.role_obj = role_obj
            user.save(update_fields=["role_obj"])
        except Role.DoesNotExist:
            pass  # Keep using legacy role field
```

**Note**: This migration is OPTIONAL and non-breaking. Users can continue using legacy `role` field indefinitely.

### Phase 3C: Update Code (Gradual)

**Step 1**: Update authorization checks to use `get_role_code()`

```python
# OLD (still works)
if user.role == Roles.SUPER_ADMIN:
    ...

# NEW (recommended, works with both)
if user.get_role_code() == Roles.SUPER_ADMIN:
    ...
```

**Step 2**: Update scoping.py to use Role model

```python
# scoping.py
def led_group_ids(user):
    role_obj = user.get_role_obj()
    if not role_obj or role_obj.scope_type != ScopeType.ASSIGNMENT:
        return []
    
    group_types = role_obj.assignment_group_types
    # ... rest of logic
```

**Step 3**: Update RBAC classes to use Role model

```python
# rbac.py
def user_has_completed_required_mfa(user) -> bool:
    role_obj = user.get_role_obj()
    if not role_obj:
        return True
    
    if not role_obj.requires_mfa:
        return True
    
    return bool(getattr(user, "mfa_enabled", False))
```

---

## API ENDPOINTS

### Role Management

```
GET    /api/v1/roles/               # List all roles (filtered by permission)
POST   /api/v1/roles/               # Create custom role
GET    /api/v1/roles/{id}/          # Get role details
PATCH  /api/v1/roles/{id}/          # Update role (except system roles)
DELETE /api/v1/roles/{id}/          # Delete role (custom roles only)
POST   /api/v1/roles/{id}/activate/ # Activate role
POST   /api/v1/roles/{id}/deactivate/ # Deactivate role

GET    /api/v1/roles/{id}/permissions/ # List role's permissions
POST   /api/v1/roles/{id}/permissions/ # Grant permission
DELETE /api/v1/roles/{id}/permissions/{perm_id}/ # Revoke permission
```

### Permission Management

```
GET    /api/v1/permissions/         # List all permissions (grouped by module)
POST   /api/v1/permissions/         # Create custom permission (rare)
GET    /api/v1/permissions/{id}/    # Get permission details
```

### Role Assignment

```
POST   /api/v1/users/{id}/assign-role/    # Assign role to user
GET    /api/v1/users/{id}/role-history/   # View role assignment history
```

---

## AUTHORIZATION

### Who Can Manage Roles?

**Create Custom Roles**: `ROLES_CREATE` permission
**Edit Roles**: `ROLES_UPDATE` permission
**Delete Custom Roles**: `ROLES_DELETE` permission
**Assign Roles**: `ROLES_ASSIGN` permission

**System Roles**:
- Cannot be deleted
- Can be deactivated (prevents new assignments)
- Permissions can be modified
- Scope type can be modified (with caution)

### Self-Escalation Prevention

```python
# In RoleViewSet and UserViewSet
def check_role_grant_permission(granter, role_to_grant):
    """
    Prevent users from granting roles/permissions they don't possess.
    A Chapel Admin cannot grant SUPER_ADMIN.
    """
    # Super Admin can grant anything
    if granter.get_role_code() == Roles.SUPER_ADMIN:
        return True
    
    # Cannot grant a role with broader scope than own
    granter_role = granter.get_role_obj()
    if not granter_role:
        return False
    
    scope_hierarchy = [
        ScopeType.GLOBAL,      # Highest
        ScopeType.ORG_WIDE,
        ScopeType.BRANCH,
        ScopeType.ASSIGNMENT,
        ScopeType.SELF,        # Lowest
    ]
    
    granter_scope_level = scope_hierarchy.index(granter_role.scope_type)
    target_scope_level = scope_hierarchy.index(role_to_grant.scope_type)
    
    if target_scope_level < granter_scope_level:
        return False  # Cannot grant broader scope
    
    # Cannot grant permissions granter doesn't have
    role_permissions = set(
        role_to_grant.permissions.values_list("permission__code", flat=True)
    )
    granter_permissions = set(
        granter_role.permissions.values_list("permission__code", flat=True)
    )
    
    if not role_permissions.issubset(granter_permissions):
        return False  # Role has permissions granter doesn't possess
    
    return True
```

### User Self-Modification Prevention

```python
# In UserSerializer
def validate_role_obj(self, role_obj):
    """Prevent users from changing their own role."""
    request = self.context.get("request")
    if not request:
        return role_obj
    
    # Updating own user
    if self.instance and self.instance.id == request.user.id:
        if role_obj != self.instance.role_obj:
            raise serializers.ValidationError(
                "You cannot change your own role. Contact an administrator."
            )
    
    # Check if granter can assign this role
    from apps.accounts.services import check_role_grant_permission
    if not check_role_grant_permission(request.user, role_obj):
        raise serializers.ValidationError(
            "You are not authorized to assign this role."
        )
    
    return role_obj
```

---

## BACKWARD COMPATIBILITY GUARANTEES

### 1. Existing Code Continues Working

```python
# All existing code using user.role still works
if user.role == Roles.SUPER_ADMIN:  # ✅ Works
if user.role in Roles.PRIVILEGED_ROLES:  # ✅ Works
```

### 2. Existing Tests Pass Unchanged

```python
# Phase 0-2 tests don't need modification
user = User.objects.create(role=Roles.CHAPEL_ADMIN)  # ✅ Works
assert user.role == Roles.CHAPEL_ADMIN  # ✅ Passes
```

### 3. Existing Serializers Work

```python
# UserSerializer with role field still works
class UserSerializer:
    class Meta:
        fields = ["role", ...]  # ✅ Works (legacy field)
```

### 4. Existing Migrations Safe

All new migrations are additive only. No data loss. Can roll back safely.

### 5. Gradual Adoption

Teams can adopt Role model incrementally:
- Day 1: Models added, all existing code works
- Week 1-2: Update authorization checks to `get_role_code()`
- Week 3-4: Add role management UI
- Week 5+: Create custom roles as needed

---

## PERFORMANCE CONSIDERATIONS

### Caching Strategy

```python
# Cache role lookups to avoid repeated DB hits
from django.core.cache import cache

def get_user_role_code_cached(user_id):
    cache_key = f"user_role:{user_id}"
    role_code = cache.get(cache_key)
    if role_code is None:
        user = User.objects.get(id=user_id)
        role_code = user.get_role_code()
        cache.set(cache_key, role_code, 3600)  # 1 hour
    return role_code

# Invalidate on role change
@receiver(post_save, sender=User)
def invalidate_role_cache(sender, instance, **kwargs):
    if instance._state.adding or "role_obj" in instance.get_deferred_fields():
        cache.delete(f"user_role:{instance.id}")
```

### Query Optimization

```python
# Prefetch role and permissions in bulk operations
users = User.objects.select_related("role_obj").prefetch_related(
    "role_obj__permissions__permission"
)
```

---

## TESTING STRATEGY

### Unit Tests

```python
# tests/accounts/test_role_model.py
@pytest.mark.django_db
class TestRoleModel:
    def test_system_role_cannot_be_deleted(self):
        role = Role.objects.create(code="SUPER_ADMIN", is_system=True)
        with pytest.raises(ValidationError):
            role.delete()
    
    def test_custom_role_can_be_deleted(self):
        role = Role.objects.create(code="CUSTOM", is_system=False)
        role.delete()  # Should succeed
    
    def test_user_get_role_code_with_role_obj(self):
        role = Role.objects.create(code="TEST_ROLE")
        user = User.objects.create(role_obj=role)
        assert user.get_role_code() == "TEST_ROLE"
    
    def test_user_get_role_code_with_legacy_role(self):
        user = User.objects.create(role=Roles.MEMBER)
        assert user.get_role_code() == Roles.MEMBER
```

### Integration Tests

```python
# tests/accounts/test_role_assignment.py
@pytest.mark.django_db
class TestRoleAssignment:
    def test_cannot_self_escalate(self):
        chapel_admin = User.objects.create(role=Roles.CHAPEL_ADMIN)
        super_admin_role = Role.objects.get(code=Roles.SUPER_ADMIN)
        
        # Attempt to assign SUPER_ADMIN to self
        with pytest.raises(PermissionError):
            assign_role(chapel_admin, chapel_admin, super_admin_role)
    
    def test_cannot_grant_broader_scope(self):
        chapel_admin = User.objects.create(role=Roles.CHAPEL_ADMIN)
        chaplain_role = Role.objects.get(code=Roles.CHAPLAIN)
        member = User.objects.create(role=Roles.MEMBER)
        
        # Chapel Admin (BRANCH scope) cannot grant Chaplain (ORG_WIDE)
        with pytest.raises(PermissionError):
            assign_role(chapel_admin, member, chaplain_role)
```

### Migration Tests

```python
# tests/accounts/test_migrations.py
@pytest.mark.django_db
class TestRoleMigration:
    def test_legacy_users_still_work(self):
        # User with only legacy role field
        user = User.objects.create(
            email="test@example.com",
            role=Roles.CHAPEL_ADMIN,
            role_obj=None
        )
        
        # Should still pass authorization
        assert user.get_role_code() == Roles.CHAPEL_ADMIN
        assert user.has_perm_code(PermissionCodes.MEMBERS_VIEW)
    
    def test_mixed_users_coexist(self):
        # One legacy, one new
        legacy_user = User.objects.create(role=Roles.MEMBER, role_obj=None)
        new_role = Role.objects.get(code=Roles.MEMBER)
        new_user = User.objects.create(role_obj=new_role)
        
        # Both should work identically
        assert legacy_user.get_role_code() == new_user.get_role_code()
```

---

## ROLLBACK PLAN

If issues discovered after Phase 3A deployment:

### Emergency Rollback

```python
# Migration rollback
python manage.py migrate accounts 0002_phase2_final  # Before Phase 3A

# Code rollback
git revert <phase3-commits>
```

**Safe because**:
- New fields are nullable
- Legacy fields still present
- Old code paths intact
- No data deleted

### Gradual Rollback

If only role_obj causing issues, can disable feature flags:

```python
# settings.py
ENABLE_DYNAMIC_ROLES = False  # Feature flag

# User model
def get_role_code(self):
    if not settings.ENABLE_DYNAMIC_ROLES:
        return self.role or Roles.MEMBER
    # ... Phase 3 logic
```

---

## DOCUMENTATION REQUIREMENTS

### 1. Admin Guide

- How to create custom roles
- How to assign permissions
- How to assign roles to users
- Scope type explanations
- Security best practices

### 2. API Documentation

- OpenAPI schemas for all new endpoints
- Permission requirements clearly stated
- Examples of role creation/assignment

### 3. Developer Guide

- How to check permissions in views
- How to check scope in queries
- Migration guide from legacy to new system
- Testing guidelines

---

## SUCCESS CRITERIA

Phase 3 design is complete when:

- ✅ Database schema defined
- ✅ Migration strategy documented
- ✅ Backward compatibility guaranteed
- ✅ Authorization patterns defined
- ✅ Security measures documented
- ✅ Performance considerations addressed
- ✅ Testing strategy outlined
- ✅ Rollback plan defined

**Status**: ✅ **DESIGN COMPLETE**

**Next Step**: Implement models and migrations (STEP 3)

---

## APPENDIX: Scope Type Decision Matrix

| Role | Scope Type | Can Access | Cannot Access |
|------|------------|------------|---------------|
| SUPER_ADMIN | GLOBAL | Everything across all orgs | N/A |
| CHAPLAIN | ORG_WIDE | All branches in their org | Other organizations |
| CHAPEL_ADMIN | BRANCH | Their assigned branch only | Other branches |
| FELLOWSHIP_LEADER | ASSIGNMENT | Their fellowship(s) only | Other fellowships, units, ministries |
| UNIT_HEAD | ASSIGNMENT | Their unit(s) only | Other units, fellowships, ministries |
| MINISTRY_GROUP_LEADER | ASSIGNMENT | Their ministry group(s) only | Other groups, units, fellowships |
| MEMBER | SELF | Own profile, own data | Other members' data |
| VISITOR | SELF | Public forms, limited access | Member-only features |
| Custom Role | Configurable | Defined by scope_type | Defined by scope_type |
