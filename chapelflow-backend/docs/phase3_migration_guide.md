# Phase 3 Migration Guide: Dynamic RBAC

## Overview

Phase 3 introduces a dynamic, database-backed role system that coexists with the legacy hardcoded role system. This guide explains how to safely apply the migrations and what to expect.

---

## Migration Strategy

### The Dual-System Approach

Phase 3 uses a **dual-system approach** during migration:

1. **Legacy System** (Phase 0-2): `User.role` CharField with hardcoded choices
2. **New System** (Phase 3+): `User.role_obj` FK to dynamic `Role` model

**Both systems work simultaneously.** The code automatically uses whichever is set, with `role_obj` taking precedence.

---

## Migration Steps

### Step 1: Apply Core Migrations

```bash
# Apply migrations 0005 and 0006 (REQUIRED)
python manage.py migrate accounts 0006_phase3_seed_roles
```

**What happens**:
- ✅ Creates `Role` model
- ✅ Creates `RoleAssignmentHistory` model
- ✅ Enhances `Permission` model (adds `name`, `module`, `is_active`)
- ✅ Adds `User.role_obj` FK (nullable)
- ✅ Makes `User.role` nullable
- ✅ Renames `RolePermission.role` to `legacy_role_code`
- ✅ Adds `RolePermission.role_obj` FK
- ✅ Seeds 15 Role objects (8 active, 7 legacy)
- ✅ Links existing RolePermissions to Role objects
- ✅ Populates Permission metadata

**Your existing system**: ✅ **STILL WORKS EXACTLY THE SAME**
- All users continue using `User.role`
- All authorization checks work unchanged
- All permissions work unchanged
- Zero downtime, zero risk

### Step 2: Verify Migration

```bash
python manage.py verify_phase3_migration --verbose
```

**Expected output**:
```
=== Phase 3 Migration Verification ===

✓ Role table exists
  Total roles: 15
  System roles: 15
  Custom roles: 0
  Active roles: 8

✓ RolePermission migration:
  Total: 47
  Migrated to role_obj: 47
  Still using legacy: 0

✓ User role migration:
  Total users: 25
  Using role_obj: 0
  Using legacy role: 25

⚠ Users have not been migrated to role_obj yet
  This is OPTIONAL - system works with legacy roles

=== Migration Status Summary ===
✓ Role table exists
✓ System roles seeded (15/8+)
✓ RolePermissions linked to roles
✓ Permission metadata populated

Passed: 4/4 checks
✓ Phase 3 migration successfully applied
```

### Step 3: Optionally Migrate Users

**THIS STEP IS COMPLETELY OPTIONAL**

```bash
# OPTIONAL: Migrate users from legacy role to role_obj
python manage.py migrate accounts 0007_phase3_migrate_users_optional
```

**What happens**:
- ✅ For each user with `role` set:
  - Looks up corresponding `Role` object
  - Sets `user.role_obj = role`
  - Creates `RoleAssignmentHistory` record
- ⚠️ **Does NOT delete `user.role`** (kept for safety)

**You can run this**:
- Immediately after Step 1
- Weeks later
- Never (users work fine on legacy system)

### Step 4: Add Database Constraints

```bash
# Apply constraint migration (RECOMMENDED)
python manage.py migrate accounts 0008_phase3_add_constraints
```

**What happens**:
- ✅ Adds CHECK constraint: `RolePermission` must have exactly one of `role_obj` or `legacy_role_code`

---

## Backward Compatibility Guarantees

### 1. All Existing Code Works

```python
# OLD CODE (Phase 0-2) - STILL WORKS
if user.role == Roles.SUPER_ADMIN:
    # ...

if user.role in Roles.PRIVILEGED_ROLES:
    # ...

# Authorization checks
HasRolePermission  # Works with both systems
BranchScopedQuerysetMixin  # Works with both systems
```

### 2. All Existing Tests Pass

No test modifications required. Phase 0-2 tests pass unchanged.

### 3. Gradual Adoption

You can start using the new system immediately or gradually:

```python
# NEW CODE (Phase 3+) - Recommended for new features
role_code = user.get_role_code()  # Works with both
role_obj = user.get_role_obj()    # Works with both

if user.has_scope(ScopeType.GLOBAL):
    # ...
```

### 4. Safe Rollback

If any issues arise:

```bash
# Rollback to before Phase 3
python manage.py migrate accounts 0004

# Or keep Phase 3 but revert user migration
python manage.py migrate accounts 0006
```

**Data safety**: No data is ever deleted. Rollback just clears FK links.

---

## Verification Checklist

After applying migrations, verify:

- [ ] `python manage.py verify_phase3_migration` passes all checks
- [ ] Existing users can still log in
- [ ] Existing permissions still work
- [ ] No authorization errors in logs
- [ ] Admin interface accessible
- [ ] Role management endpoints work (if implemented)

---

## Common Scenarios

### Scenario 1: Fresh Installation

For new deployments:

```bash
# Apply all migrations at once
python manage.py migrate

# All users will use role_obj from day 1
```

### Scenario 2: Existing Production System

For live systems with users:

```bash
# 1. Apply during low-traffic period
python manage.py migrate accounts 0006_phase3_seed_roles

# 2. Verify immediately
python manage.py verify_phase3_migration

# 3. Monitor logs for 24 hours

# 4. Optionally migrate users (can wait)
python manage.py migrate accounts 0007_phase3_migrate_users_optional

# 5. Add constraints
python manage.py migrate accounts 0008_phase3_add_constraints
```

### Scenario 3: Staged Rollout

```bash
# Week 1: Apply core migrations only
python manage.py migrate accounts 0006

# Week 2-3: Monitor, verify everything works

# Week 4: Migrate 10% of users (manual)
# Use admin interface or management command

# Week 5-6: Gradually migrate remaining users

# Week 7: Apply constraints
python manage.py migrate accounts 0008
```

---

## Troubleshooting

### Issue: Migration 0006 fails with "Permission already exists"

**Cause**: Permissions already seeded

**Solution**: This is normal, migration is idempotent. Ignore the message.

### Issue: Users cannot log in after migration

**Cause**: This should NOT happen (backward compatible)

**Check**:
```bash
# Verify user still has role
python manage.py shell
>>> from apps.accounts.models import User
>>> user = User.objects.get(email='test@example.com')
>>> print(user.role, user.role_obj)
>>> print(user.get_role_code())  # Should return a role code
```

**Solution**: If issue persists, rollback and report bug:
```bash
python manage.py migrate accounts 0004
```

### Issue: "CheckConstraint violation" error

**Cause**: Trying to save RolePermission without either role type

**Solution**: Ensure migration 0006 ran successfully:
```bash
python manage.py verify_phase3_migration
```

### Issue: Some users show as "None" role after migration 0007

**Cause**: Role object doesn't exist for their legacy role code

**Solution**: Check which roles are missing:
```python
from apps.accounts.models import User, Role

# Find users with unmapped roles
for user in User.objects.filter(role_obj__isnull=True):
    if user.role and not Role.objects.filter(code=user.role).exists():
        print(f"User {user.id} has unmapped role: {user.role}")
```

Create missing Role manually or assign valid role to user.

---

## Performance Considerations

### Database Load

Migrations 0005-0008 are lightweight:
- No table rewrites
- No data copying
- Only adds columns and FK links

**Estimated time**:
- 1000 users: < 5 seconds
- 10,000 users: < 30 seconds
- 100,000 users: < 5 minutes

### Query Performance

No performance degradation:
- `get_role_code()` hits `role_obj` first (one DB lookup, cached)
- Falls back to `role` (in-memory, no DB hit)
- Caching used for legacy→Role object lookups

### Caching Strategy

Automatic caching in place:
```python
# Cached for 1 hour per user
cache_key = f"user_role:{user.id}"
cache_key = f"legacy_role_obj:{role_code}"
```

Cache invalidated on role changes.

---

## Migration Timeline Recommendation

**For Production Systems**:

| Week | Action | Rollback Point |
|------|--------|----------------|
| 1 | Apply 0006 in staging | Can rollback anytime |
| 2 | Apply 0006 in production (off-peak) | Can rollback anytime |
| 3-4 | Monitor logs, verify functionality | Can rollback anytime |
| 5 | Apply 0007 to test users (10%) | Can rollback anytime |
| 6 | Apply 0007 to all users | Can rollback anytime |
| 7 | Apply 0008 (constraints) | Can rollback (clears constraints) |
| 8+ | Start using role management UI | Fully committed to new system |

**For Staging/Development**:

Apply all migrations immediately:
```bash
python manage.py migrate
```

---

## Next Steps After Migration

Once migrations complete successfully:

1. ✅ **Implement Role Management UI** (Step 6 of Phase 3)
2. ✅ **Add FK validation to serializers** (Step 5 of Phase 3)
3. ✅ **Create custom roles** as needed
4. ✅ **Assign granular permissions** to roles
5. ✅ **Decommission legacy role constants** (Phase 4+)

---

## Support

If issues arise during migration:

1. Run verification: `python manage.py verify_phase3_migration --verbose`
2. Check application logs for errors
3. Verify database state manually
4. If needed, rollback: `python manage.py migrate accounts 0004`
5. Report issue with verification output

---

## Migration Files Reference

| File | Purpose | Required | Can Rollback |
|------|---------|----------|--------------|
| 0005_phase3_add_role_model.py | Add new models & fields | ✅ Yes | ✅ Yes |
| 0006_phase3_seed_roles.py | Seed Role objects, link RolePermissions | ✅ Yes | ✅ Yes |
| 0007_phase3_migrate_users_optional.py | Migrate users to role_obj | ❌ Optional | ✅ Yes |
| 0008_phase3_add_constraints.py | Add CHECK constraints | ⚠️ Recommended | ✅ Yes |

---

## FAQ

**Q: Do I have to migrate users to role_obj?**  
A: No, it's completely optional. System works with legacy roles indefinitely.

**Q: Can I create custom roles before migrating users?**  
A: Yes! Custom roles work immediately after migration 0006.

**Q: Will this break my frontend?**  
A: No, if frontend expects `user.role` field, it still exists and works.

**Q: How do I assign custom roles?**  
A: Use the role management API (to be implemented in Step 6) or Django admin.

**Q: Can I delete legacy roles?**  
A: System roles cannot be deleted, only deactivated. Custom roles can be deleted.

**Q: What happens to users with deleted custom roles?**  
A: Role FK is PROTECT - cannot delete role while users have it assigned.

**Q: Is there any downtime?**  
A: No, migrations are non-blocking and backward compatible.

---

**End of Phase 3 Migration Guide**
