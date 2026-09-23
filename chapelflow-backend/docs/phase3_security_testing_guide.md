# Phase 3: Security Testing Guide

## Overview

This guide covers running and interpreting the comprehensive security test suite for Phase 3 Dynamic RBAC & Authorization.

**Test Suite Location**: `tests/security/test_phase3_authorization.py`

**Test Coverage**:
- FK Validation (Serializers)
- ViewSet Permissions
- Sensitive Module Security
- Celery Task Re-validation
- Dynamic RBAC
- Self-Escalation Prevention
- Cross-Branch Protection

---

## Running Security Tests

### Run All Phase 3 Security Tests

```bash
pytest tests/security/test_phase3_authorization.py -v
```

### Run Specific Test Classes

```bash
# FK Validation tests only
pytest tests/security/test_phase3_authorization.py::TestSerializerFKValidation -v

# ViewSet permission tests
pytest tests/security/test_phase3_authorization.py::TestViewSetPermissions -v

# Finance module security
pytest tests/security/test_phase3_authorization.py::TestFinanceModuleSecurity -v

# Pastoral module security
pytest tests/security/test_phase3_authorization.py::TestPastoralModuleSecurity -v

# Prayer module security
pytest tests/security/test_phase3_authorization.py::TestPrayerModuleSecurity -v

# Celery task authorization
pytest tests/security/test_phase3_authorization.py::TestCeleryTaskAuthorization -v

# Dynamic RBAC
pytest tests/security/test_phase3_authorization.py::TestDynamicRBAC -v

# Self-escalation prevention
pytest tests/security/test_phase3_authorization.py::TestSelfEscalationPrevention -v

# Cross-branch protection
pytest tests/security/test_phase3_authorization.py::TestCrossBranchProtection -v
```

### Run with Coverage Report

```bash
pytest tests/security/test_phase3_authorization.py --cov=apps --cov=common --cov-report=html
```

### Run with Detailed Output

```bash
pytest tests/security/test_phase3_authorization.py -vv --tb=short
```

---

## Test Classes and Coverage

### 1. TestSerializerFKValidation

**Purpose**: Verify FK validation in serializers prevents cross-branch attacks

**Tests**:
- `test_cannot_create_event_in_unauthorized_branch`: Cannot POST with branch user lacks access to
- `test_cannot_use_location_from_unauthorized_branch`: Cannot use FK to Location from different branch
- `test_cannot_assign_member_from_different_branch`: Cannot link Member from different branch
- `test_super_admin_can_create_cross_branch`: Super Admin can bypass restrictions

**Expected Results**: ✅ All should pass after Step 5 implementation

**What It Verifies**:
- ScopedFKValidationMixin working correctly
- validate_branch_fk() blocks unauthorized branches
- validate_related_branch_fk() checks nested branch access
- Super Admin global scope works

---

### 2. TestViewSetPermissions

**Purpose**: Verify ViewSets enforce permission_action_map

**Tests**:
- `test_member_cannot_create_event`: Regular members cannot create events
- `test_chapel_admin_can_create_event`: Chapel Admin can create events
- `test_unauthenticated_cannot_access_protected_endpoint`: Authentication required

**Expected Results**: ✅ All should pass after Step 6 implementation

**What It Verifies**:
- HasRolePermission class working
- permission_action_map enforced
- Unauthenticated requests rejected

---

### 3. TestFinanceModuleSecurity

**Purpose**: Verify Finance module requires MFA and proper role

**Tests**:
- `test_finance_requires_finance_role`: Non-finance roles blocked
- `test_finance_requires_mfa`: MFA required for finance operations

**Expected Results**: ✅ All should pass after Step 7 implementation

**What It Verifies**:
- IsFinanceAuthorized permission class working
- FINANCE_ACCESS_ROLES enforced
- MFA requirement enforced

---

### 4. TestPastoralModuleSecurity

**Purpose**: Verify Pastoral module object-level permissions and MFA

**Tests**:
- `test_pastoral_requires_mfa`: MFA required for pastoral access
- `test_member_can_only_see_own_pastoral_cases`: Members see only own cases

**Expected Results**: ✅ All should pass after Step 7 implementation

**What It Verifies**:
- IsPastoralAuthorized permission class working
- MFA requirement (Phase 3 enhancement)
- Object-level permission checks
- Queryset filtering by member/assigned_to

---

### 5. TestPrayerModuleSecurity

**Purpose**: Verify Prayer module privacy filtering

**Tests**:
- `test_private_prayer_requests_not_visible_to_others`: is_private filtering works

**Expected Results**: ✅ All should pass

**What It Verifies**:
- Privacy filtering in PrayerRequestViewSet.get_queryset()
- is_private=True requests hidden from other members
- is_private=False requests visible to branch members

---

### 6. TestCeleryTaskAuthorization

**Purpose**: Verify Celery tasks re-validate authorization at execution

**Tests**:
- `test_bulk_import_task_revalidates_permission`: bulk_import checks members.create at runtime
- `test_report_job_task_revalidates_branch_access`: run_report_job checks branch access at runtime

**Expected Results**: ✅ All should pass after Step 7 implementation

**What It Verifies**:
- Tasks check permissions at execution time (not just queue time)
- Graceful failure when permission revoked
- No stale authorization exploits

---

### 7. TestDynamicRBAC

**Purpose**: Verify dynamic role creation and permission assignment

**Tests**:
- `test_can_create_dynamic_role`: Can create roles at runtime
- `test_can_assign_permissions_to_role`: Can assign permissions to roles
- `test_user_with_dynamic_role_has_permissions`: Users with dynamic roles have permissions

**Expected Results**: ✅ All should pass after Step 3 implementation

**What It Verifies**:
- Role model working
- RolePermission model working
- User.has_perm_code() checks both legacy and dynamic roles
- Dual-path backward compatibility

---

### 8. TestSelfEscalationPrevention

**Purpose**: Verify users cannot escalate their own privileges

**Tests**:
- `test_user_cannot_assign_higher_role_to_self`: Cannot self-assign Super Admin
- `test_user_cannot_grant_permission_they_lack`: Cannot grant permissions user lacks

**Expected Results**: ✅ All should pass after Step 3 implementation

**What It Verifies**:
- role_services.assign_role_to_user() checks assigner permissions
- role_services.grant_permission_to_role() checks granter permissions
- Self-escalation blocked at service layer

---

### 9. TestCrossBranchProtection

**Purpose**: Verify users cannot access resources from other branches

**Tests**:
- `test_cannot_view_events_from_other_branch`: Cannot GET event from other branch
- `test_cannot_update_event_in_other_branch`: Cannot PATCH event in other branch

**Expected Results**: ✅ All should pass

**What It Verifies**:
- BranchScopedQuerysetMixin filtering working
- 404 responses for cross-branch access attempts
- No data leakage across branch boundaries

---

## Interpreting Test Results

### All Tests Pass ✅

```
tests/security/test_phase3_authorization.py::TestSerializerFKValidation::test_cannot_create_event_in_unauthorized_branch PASSED
tests/security/test_phase3_authorization.py::TestSerializerFKValidation::test_cannot_use_location_from_unauthorized_branch PASSED
...
======================== 25 passed in 5.23s ========================
```

**Action**: Phase 3 security hardening verified. Proceed to Step 9 (regression testing).

### Some Tests Fail ❌

```
tests/security/test_phase3_authorization.py::TestSerializerFKValidation::test_cannot_create_event_in_unauthorized_branch FAILED
FAILED tests/security/test_phase3_authorization.py::TestSerializerFKValidation::test_cannot_create_event_in_unauthorized_branch - AssertionError: assert 201 == 400
```

**Action**: Security vulnerability still present. Fix implementation before proceeding.

**Common Failure Causes**:
1. **201 instead of 400**: FK validation not implemented in serializer
2. **200 instead of 403**: Permission class not applied to ViewSet
3. **No 'branch' in response.json()**: Wrong validation error format
4. **404 instead of expected**: Queryset filtering issue

### Test Errors ⚠️

```
ERROR tests/security/test_phase3_authorization.py::TestDynamicRBAC::test_can_create_dynamic_role
django.db.utils.IntegrityError: ...
```

**Action**: Database migration issue. Run migrations first:

```bash
python manage.py migrate accounts 0006_phase3_seed_roles
```

---

## Security Test Checklist

Before marking Phase 3 complete, verify:

- [ ] All 25+ security tests pass
- [ ] FK validation tests pass (4 tests)
- [ ] ViewSet permission tests pass (3 tests)
- [ ] Finance security tests pass (2 tests)
- [ ] Pastoral security tests pass (2 tests)
- [ ] Prayer security tests pass (1 test)
- [ ] Celery task tests pass (2 tests)
- [ ] Dynamic RBAC tests pass (3 tests)
- [ ] Self-escalation tests pass (2 tests)
- [ ] Cross-branch tests pass (2 tests)
- [ ] No security regressions in existing tests
- [ ] Test coverage >80% for security-critical modules

---

## Manual Security Testing

Automated tests don't catch everything. Manually verify:

### 1. Cross-Branch Attack Simulation

```bash
# As Chapel Admin Branch A, try to create event in Branch B
curl -X POST http://localhost:8000/api/v1/events/ \
  -H "Authorization: Bearer $TOKEN_ADMIN_A" \
  -H "Content-Type: application/json" \
  -d '{"branch": "$BRANCH_B_ID", "title": "Attack", "start_time": "2024-01-01T10:00:00Z", "end_time": "2024-01-01T11:00:00Z"}'

# Expected: 400 with validation error on branch field
```

### 2. Finance MFA Bypass Attempt

```bash
# As Finance Officer WITHOUT MFA, try to access finance endpoint
curl http://localhost:8000/api/v1/finance/giving/ \
  -H "Authorization: Bearer $TOKEN_FINANCE_NO_MFA"

# Expected: 403 Forbidden (MFA required)
```

### 3. Pastoral Case Privacy Test

```bash
# As Member B, try to access Member A's pastoral case
curl http://localhost:8000/api/v1/pastoral/cases/$CASE_A_ID/ \
  -H "Authorization: Bearer $TOKEN_MEMBER_B"

# Expected: 404 Not Found (queryset filtered)
```

### 4. Self-Escalation Attempt

```python
# In Django shell
from apps.accounts.role_services import assign_role_to_user
from apps.accounts.models import Role, User

chapel_admin = User.objects.get(email="admin@test.com")
super_admin_role = Role.objects.get(code="SUPER_ADMIN")

# Try to self-assign
assign_role_to_user(
    user=chapel_admin,
    role=super_admin_role,
    assigner=chapel_admin
)

# Expected: RoleAssignmentError raised
```

### 5. Stale Authorization in Celery

```python
# Queue a report job
job = ReportJob.objects.create(...)

# Revoke user's branch access
user.branch = other_branch
user.save()

# Run task
run_report_job(job.id)

# Expected: Job fails with "Permission denied" error
```

---

## Continuous Security Testing

### Pre-Commit Hook

Add to `.git/hooks/pre-commit`:

```bash
#!/bin/bash
pytest tests/security/test_phase3_authorization.py --tb=short
if [ $? -ne 0 ]; then
    echo "Security tests failed. Commit aborted."
    exit 1
fi
```

### CI/CD Integration

Add to `.github/workflows/tests.yml` or equivalent:

```yaml
- name: Run Phase 3 Security Tests
  run: |
    pytest tests/security/test_phase3_authorization.py -v
    if [ $? -ne 0 ]; then
      echo "CRITICAL: Security tests failed!"
      exit 1
    fi
```

---

## Performance Impact

Security tests may be slower than unit tests due to:
- Database transactions
- Authentication setup
- Mock objects

**Optimization Tips**:
- Use `pytest-xdist` for parallel execution: `pytest -n auto`
- Use `--reuse-db` flag to avoid recreating database
- Run security tests separately from unit tests in CI

---

## Troubleshooting

### Tests Hang or Timeout

**Cause**: Celery task waiting for queue  
**Fix**: Mock Celery tasks in tests or use `task.apply()` instead of `.delay()`

### Migrations Not Applied

**Cause**: Test database out of sync  
**Fix**: `pytest --create-db` to recreate test database

### MFA Mock Not Working

**Cause**: Mock path incorrect  
**Fix**: Verify patch path matches import location

### Fixture Errors

**Cause**: Missing dependencies  
**Fix**: Check fixture dependency chain, ensure all required fixtures exist

---

## Next Steps After Tests Pass

1. ✅ All security tests passing
2. Run full regression suite (Step 9)
3. Manual penetration testing
4. Security audit review (Step 10)
5. Generate final Phase 3 report

---

**Status**: Tests created and documented  
**Coverage**: 25+ security-critical test cases  
**Next**: Run tests and verify all pass
