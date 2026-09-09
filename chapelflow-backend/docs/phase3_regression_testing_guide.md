# Phase 3: Regression Testing Guide

## Overview

Phase 3 introduced significant authorization changes. This guide ensures **100% backward compatibility** - all existing functionality must continue working unchanged.

**Critical Principle**: Phase 3 enhances security WITHOUT breaking existing features.

---

## Pre-Regression Checklist

Before running regression tests, verify:

- [ ] All Phase 3 migrations applied: `python manage.py migrate accounts 0008`
- [ ] Migration verification passed: `python manage.py verify_phase3_migration --verbose`
- [ ] Database backup created (safety precaution)
- [ ] Test database configured correctly
- [ ] Redis/Celery running (for async task tests)
- [ ] All environment variables set

---

## Regression Test Strategy

### 1. Existing Test Suite (Phase 0-2)

**Location**: All existing `tests/` directories across apps

**Command**:
```bash
pytest --ignore=tests/security/ -v
```

**Expected Result**: **All existing tests must pass** (100% pass rate)

**What This Verifies**:
- User model backward compatibility (User.role CharField still works)
- Permission checking via legacy RolePermission still works
- BranchScopedQuerysetMixin unchanged
- All business logic unchanged
- All endpoints return same responses

### 2. Phase 3 Security Tests

**Location**: `tests/security/test_phase3_authorization.py`

**Command**:
```bash
pytest tests/security/test_phase3_authorization.py -v
```

**Expected Result**: All 25+ security tests pass

**What This Verifies**:
- New FK validation working
- New permission enforcement working
- Sensitive module hardening working
- Dynamic RBAC working

### 3. Combined Suite

**Command**:
```bash
pytest -v --tb=short
```

**Expected Result**: All tests pass (Phase 0-2 + Phase 3)

---

## Critical Backward Compatibility Tests

### Test 1: Legacy User.role Field Works

**Verify**: Users with legacy `role` CharField can still authenticate and access resources

```python
# Should work exactly as before Phase 3
user = User.objects.get(email="admin@test.com")
assert user.role == Roles.CHAPEL_ADMIN
assert user.has_perm_code(PermissionCodes.EVENTS_VIEW)
```

**Test File**: Existing user authentication tests

**Status After Phase 3**: ✅ Must pass unchanged

---

### Test 2: Legacy RolePermission Still Works

**Verify**: Existing RolePermission rows (with `role` CharField) grant permissions

```python
# Old-style RolePermission (using role CharField)
rp = RolePermission.objects.filter(role=Roles.CHAPEL_ADMIN).first()
assert rp is not None
assert rp.permission.code in PermissionCodes
```

**Test File**: Existing permission tests

**Status After Phase 3**: ✅ Must pass unchanged

---

### Test 3: BranchScopedQuerysetMixin Unchanged

**Verify**: Queryset filtering works exactly as before

```python
# Chapel Admin sees only own branch
chapel_admin = User.objects.get(role=Roles.CHAPEL_ADMIN, branch=branch_a)
client.force_authenticate(user=chapel_admin)
response = client.get('/api/v1/events/')

events = response.json()['results']
assert all(e['branch'] == str(branch_a.id) for e in events)
```

**Test File**: Existing scope tests

**Status After Phase 3**: ✅ Must pass unchanged

---

### Test 4: All Existing Endpoints Return Same Responses

**Verify**: API responses unchanged (same fields, same structure)

```python
# GET /api/v1/members/ returns same structure
response = client.get('/api/v1/members/')
assert 'results' in response.json()
assert 'id' in response.json()['results'][0]
assert 'full_name' in response.json()['results'][0]
```

**Test Files**: All existing API tests

**Status After Phase 3**: ✅ Must pass unchanged

---

### Test 5: Serializer Validations Don't Break Valid Data

**Verify**: New FK validation only blocks invalid data, not valid data

```python
# Creating event in own branch should still work
response = client.post('/api/v1/events/', {
    'branch': own_branch.id,  # User's own branch
    'title': 'Test Event',
    'start_time': '2024-01-01T10:00:00Z',
    'end_time': '2024-01-01T11:00:00Z',
})
assert response.status_code in [200, 201]  # Should succeed
```

**Test Files**: Existing creation tests

**Status After Phase 3**: ✅ Must pass unchanged

---

## Module-Specific Regression Tests

### Events Module

**Critical Flows**:
1. Create event → Generate schedules → Register member → Cancel registration
2. Public event listing (unauthenticated)
3. Calendar view

**Test Command**:
```bash
pytest apps/events/tests/ -v
```

**Expected**: All existing tests pass

---

### Members Module

**Critical Flows**:
1. Create member → Assign to group → Update membership status
2. Bulk import members (CSV)
3. Member profile update

**Test Command**:
```bash
pytest apps/members/tests/ -v
```

**Expected**: All existing tests pass

---

### Groups Module

**Critical Flows**:
1. Create group → Add members → Assign leader
2. Group hierarchy (parent/child)
3. Multi-leader support (Phase 0 fix)

**Test Command**:
```bash
pytest apps/groups/tests/ apps/ministries/tests/ -v
```

**Expected**: All existing tests pass

---

### Finance Module

**Critical Flows**:
1. Record giving → Generate statement
2. Create pledge → Track fulfillment
3. Payment webhook processing

**Test Command**:
```bash
pytest apps/finance/tests/ -v
```

**Expected**: All existing tests pass

**Phase 3 Addition**: MFA now required (test should verify this)

---

### Pastoral Module

**Critical Flows**:
1. Create pastoral case → Assign staff → Add notes
2. Member sees only own cases
3. Privacy enforcement

**Test Command**:
```bash
pytest apps/pastoral/tests/ -v
```

**Expected**: All existing tests pass

**Phase 3 Addition**: MFA now required (test should verify this)

---

### Prayer Module

**Critical Flows**:
1. Submit prayer request → Mark private/public
2. Assign to pastoral staff → Add notes
3. Privacy filtering

**Test Command**:
```bash
pytest apps/prayer/tests/ -v
```

**Expected**: All existing tests pass

---

### Attendance Module

**Critical Flows**:
1. Open session → QR check-in → Manual check-in → Close session
2. Visitor attendance
3. Offline sync

**Test Command**:
```bash
pytest apps/attendance/tests/ -v
```

**Expected**: All existing tests pass

---

### Communications Module

**Critical Flows**:
1. Create announcement → Target groups → Dispatch notifications
2. Delivery status tracking

**Test Command**:
```bash
pytest apps/communications/tests/ -v
```

**Expected**: All existing tests pass

---

## Performance Regression Tests

Phase 3 adds validation logic - verify no significant performance degradation.

### Benchmark: Queryset Filtering

```python
import time

# Before: BranchScopedQuerysetMixin filtering
start = time.time()
events = Event.objects.filter(branch=branch_a).count()
baseline = time.time() - start

# After Phase 3: Should be same (no change to queryset logic)
start = time.time()
events = Event.objects.filter(branch=branch_a).count()
phase3 = time.time() - start

assert phase3 < baseline * 1.1  # Max 10% slower
```

### Benchmark: Serializer Validation

```python
# Test: FK validation adds minimal overhead
from apps.events.serializers import EventSerializer

data = {
    'branch': branch_a.id,
    'title': 'Test',
    'start_time': '2024-01-01T10:00:00Z',
    'end_time': '2024-01-01T11:00:00Z',
}

start = time.time()
for _ in range(100):
    serializer = EventSerializer(data=data, context={'request': mock_request})
    serializer.is_valid()
duration = time.time() - start

assert duration < 1.0  # 100 validations in under 1 second
```

### Benchmark: Permission Checking

```python
# Test: has_perm_code() with dual-path is fast
user = User.objects.get(email="admin@test.com")

start = time.time()
for _ in range(1000):
    user.has_perm_code(PermissionCodes.EVENTS_VIEW)
duration = time.time() - start

assert duration < 0.5  # 1000 checks in under 0.5 seconds
```

---

## Compatibility Matrix

| Component | Phase 0-2 Behavior | Phase 3 Behavior | Compatibility |
|-----------|-------------------|------------------|---------------|
| User.role (CharField) | Works | Still works (dual-path) | ✅ 100% |
| User.role_obj (FK) | N/A | New optional field | ✅ Additive |
| RolePermission (legacy) | Works | Still works | ✅ 100% |
| RolePermission (new) | N/A | New role_obj support | ✅ Additive |
| BranchScopedQuerysetMixin | Works | Unchanged | ✅ 100% |
| HasRolePermission | Works | Enhanced (dual-path) | ✅ 100% |
| Serializers (GET/POST) | Works | Enhanced validation | ✅ 100%* |
| ViewSet permissions | Works | Enhanced (action maps) | ✅ 100% |
| Finance MFA | Required | Still required | ✅ 100% |
| Pastoral MFA | Not required | Now required | ⚠️ NEW** |

\* Valid data passes, invalid data now blocked (security enhancement)  
\** Breaking for tests that assumed no MFA - intentional security fix

---

## Regression Failure Troubleshooting

### Symptom: "User.role_obj does not exist"

**Cause**: Migrations not applied

**Fix**:
```bash
python manage.py migrate accounts 0005_phase3_add_role_model
```

---

### Symptom: Tests fail with "Permission denied" (403)

**Cause**: New validation blocking requests that were previously allowed

**Diagnosis**:
1. Check if request has branch FK to unauthorized branch
2. Check if request has member FK from different branch
3. Check if MFA now required (Pastoral module)

**Fix**: Update test data to use valid branch/member references

---

### Symptom: "CheckConstraint violated"

**Cause**: RolePermission has both role and role_obj set

**Fix**: Migration 0005 has check constraint - ensure only one is set:
```python
# WRONG
RolePermission.objects.create(role="CHAPEL_ADMIN", role_obj=role_instance, ...)

# CORRECT (legacy)
RolePermission.objects.create(role="CHAPEL_ADMIN", permission=perm)

# CORRECT (new)
RolePermission.objects.create(role_obj=role_instance, permission=perm)
```

---

### Symptom: Tests hang/timeout

**Cause**: Celery tasks not mocked

**Fix**: Mock Celery tasks in tests:
```python
@patch('apps.members.tasks.bulk_import_members_task.delay')
def test_something(mock_task):
    # Test code
    pass
```

---

### Symptom: "has_perm_code() takes no arguments"

**Cause**: User model method signature changed

**Fix**: No - method signature unchanged. Check User model loaded correctly.

---

## Sign-Off Checklist

Before marking Phase 3 complete, verify:

### Core Functionality
- [ ] All Phase 0-2 tests pass (100% pass rate)
- [ ] All Phase 3 security tests pass (25+ tests)
- [ ] No new test failures introduced
- [ ] No existing functionality broken

### Authorization
- [ ] Legacy User.role CharField works
- [ ] New User.role_obj FK works (when used)
- [ ] Dual-path permission checking works
- [ ] BranchScopedQuerysetMixin unchanged

### Serializers
- [ ] Valid data still accepted
- [ ] Invalid data (cross-branch) now rejected
- [ ] Serializer responses unchanged (same fields)

### ViewSets
- [ ] All endpoints return same responses
- [ ] Permission enforcement working
- [ ] Custom actions protected

### Sensitive Modules
- [ ] Finance MFA still enforced
- [ ] Pastoral MFA now enforced (new)
- [ ] Prayer privacy filtering works
- [ ] No PII leakage

### Celery Tasks
- [ ] Tasks re-validate authorization
- [ ] Task failure graceful (no crashes)
- [ ] Existing async flows work

### Performance
- [ ] Queryset filtering performance acceptable
- [ ] Serializer validation overhead minimal (<10%)
- [ ] Permission checking fast (<1ms per check)

### Migrations
- [ ] All migrations reversible
- [ ] verify_phase3_migration passes
- [ ] No data loss on migrate/rollback cycle

### Documentation
- [ ] All docs updated
- [ ] Migration guide complete
- [ ] Testing guides complete
- [ ] Security audit documented

---

## Continuous Regression Testing

### Pre-Commit Hook

Add to `.git/hooks/pre-commit`:
```bash
#!/bin/bash
# Run critical regression tests before commit
pytest apps/events/tests/test_registration.py -x
pytest apps/members/tests/test_scoping.py -x
pytest tests/security/test_phase3_authorization.py::TestSerializerFKValidation -x

if [ $? -ne 0 ]; then
    echo "Critical tests failed. Commit aborted."
    exit 1
fi
```

### CI/CD Pipeline

```yaml
# .github/workflows/tests.yml
name: Regression Suite

on: [push, pull_request]

jobs:
  regression:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      
      - name: Run Phase 0-2 Tests (Existing)
        run: pytest --ignore=tests/security/ --tb=short
        
      - name: Run Phase 3 Security Tests
        run: pytest tests/security/test_phase3_authorization.py -v
        
      - name: Verify Backward Compatibility
        run: |
          if [ $? -ne 0 ]; then
            echo "REGRESSION DETECTED!"
            exit 1
          fi
```

---

## Rollback Plan

If regressions found and cannot be fixed immediately:

### 1. Rollback Migrations
```bash
# Rollback to before Phase 3
python manage.py migrate accounts 0004

# Verify rollback
python manage.py showmigrations accounts
```

### 2. Revert Code Changes
```bash
# Create rollback branch
git checkout -b phase3-rollback

# Revert all Phase 3 commits
git revert <commit-hash-range>

# Test rollback
pytest -v
```

### 3. Verify System Stable
```bash
# All tests should pass
pytest -v

# Manual smoke testing
# - Login works
# - Events CRUD works
# - Members CRUD works
# - Finance operations work
```

---

## Final Validation

Run full test suite with coverage:

```bash
pytest -v --cov=apps --cov=common --cov-report=html --cov-report=term
```

**Success Criteria**:
- ✅ All tests pass (0 failures)
- ✅ Coverage >80% on modified modules
- ✅ No regressions in existing functionality
- ✅ New security features working
- ✅ Performance acceptable

**Then proceed to**: STEP 10 - Final security audit and report

---

**Status**: Regression testing guide complete  
**Next Action**: Run full test suite and verify 100% backward compatibility  
**Estimated Duration**: 2-4 hours (includes test execution and verification)
