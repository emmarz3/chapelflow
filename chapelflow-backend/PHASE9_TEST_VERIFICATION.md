# PHASE 9 TEST VERIFICATION CHECKLIST

**Date:** September 1, 2026  
**Status:** Models reconciled, implementation complete, awaiting test execution

---

## ENVIRONMENT SETUP REQUIRED

Before running tests, ensure:

```bash
# Activate virtual environment (if exists)
# Install dependencies
pip install -r requirements.txt

# Verify Django installation
python manage.py --version

# Check database configuration
python manage.py check
```

---

## MIGRATION VERIFICATION

### 1. Check for Pending Migrations

```bash
python manage.py makemigrations --check volunteers --dry-run
```

**Expected Result:** No new migrations detected (models match migration 0003)

### 2. Verify Migration Plan

```bash
python manage.py migrate --plan
```

**Expected Result:** All migrations applied or ready to apply

### 3. Show Migration Status

```bash
python manage.py showmigrations volunteers
```

**Expected Result:**
```
volunteers
 [X] 0001_initial
 [X] 0002_phase1_default_ordering
 [X] 0003_volunteeravailability_and_more
```

### 4. Test Migration in Fresh Database

```bash
# In test environment
python manage.py migrate volunteers zero
python manage.py migrate volunteers
```

**Expected Result:** All migrations apply successfully without errors

---

## UNIT TESTS

### 1. Run All Phase 9 Tests

```bash
pytest tests/volunteers/ -v
```

**Expected Result:** All tests pass

### 2. Run Existing Phase 9 Tests

```bash
pytest tests/volunteers/test_phase9_volunteers.py -v
```

**Test Coverage:**
- ✓ Conflict detection (duplicate, overlapping, availability)
- ✓ Lifecycle transitions (confirm, decline, complete)
- ✓ Service hour logging
- ✓ Group scope validation
- ✓ Scope isolation (Unit Head, Branch Admin, Chaplain)
- ✓ API action endpoints
- ✓ Service history aggregation
- ✓ Reminder tasks

**Expected Result:** ~15-20 tests pass

### 3. Run Branch Isolation Tests

```bash
pytest tests/volunteers/test_branch_isolation.py -v
```

**Test Coverage:**
- ✓ Branch-scoped queryset filtering
- ✓ Chaplain organization-wide access
- ✓ Cross-branch isolation

**Expected Result:** ~10 tests pass

### 4. Run Security Test Suite

```bash
pytest tests/volunteers/test_phase9_security.py -v
```

**Test Coverage:**
- ✓ Member substitution attack prevention
- ✓ Volunteer substitution attack prevention
- ✓ Cross-branch event assignment prevention
- ✓ Cross-branch group assignment prevention
- ✓ Direct ID access protection
- ✓ Mass assignment protection
- ✓ Status manipulation protection
- ✓ Hours manipulation protection
- ✓ Historical assignment protection
- ✓ Availability ownership enforcement
- ✓ Lifecycle transition validation
- ✓ Conflict detection enforcement
- ✓ Permission enforcement

**Expected Result:** ~50+ security tests pass

---

## INTEGRATION TESTS

### 1. Test with Other Phases

```bash
# Test integration with Phase 4 (Members)
pytest tests/members/ tests/volunteers/ -k "member" -v

# Test integration with Phase 6 (Groups)
pytest tests/groups/ tests/volunteers/ -k "group" -v

# Test integration with Phase 7 (Events)
pytest tests/events/ tests/volunteers/ -k "event" -v
```

**Expected Result:** No integration failures

### 2. Test RBAC Integration

```bash
pytest tests/volunteers/ -k "permission" -v
```

**Expected Result:** All permission tests pass

---

## FUNCTIONAL TESTS

### 1. API Endpoint Tests

Test each endpoint manually or via API client:

**VolunteerProfile Endpoints:**
- `GET /api/v1/volunteers/profiles/` - List profiles
- `POST /api/v1/volunteers/profiles/` - Create profile
- `GET /api/v1/volunteers/profiles/{id}/` - Retrieve profile
- `PATCH /api/v1/volunteers/profiles/{id}/` - Update profile
- `DELETE /api/v1/volunteers/profiles/{id}/` - Delete profile
- `GET /api/v1/volunteers/profiles/{id}/history/` - Service history

**VolunteerAvailability Endpoints:**
- `GET /api/v1/volunteers/availability/` - List availability
- `POST /api/v1/volunteers/availability/` - Create window
- `GET /api/v1/volunteers/availability/{id}/` - Retrieve window
- `PATCH /api/v1/volunteers/availability/{id}/` - Update window
- `DELETE /api/v1/volunteers/availability/{id}/` - Delete window

**VolunteerAssignment Endpoints:**
- `GET /api/v1/volunteers/assignments/` - List assignments
- `POST /api/v1/volunteers/assignments/` - Create assignment
- `GET /api/v1/volunteers/assignments/{id}/` - Retrieve assignment
- `PATCH /api/v1/volunteers/assignments/{id}/` - Update assignment
- `DELETE /api/v1/volunteers/assignments/{id}/` - Delete assignment
- `POST /api/v1/volunteers/assignments/{id}/confirm/` - Confirm
- `POST /api/v1/volunteers/assignments/{id}/decline/` - Decline
- `POST /api/v1/volunteers/assignments/{id}/complete/` - Complete

### 2. Workflow Tests

**Scenario 1: Happy Path Assignment**
1. Create volunteer profile
2. Add availability window (unavailable Tuesday evening)
3. Create assignment for Wednesday (succeeds)
4. Create assignment for Tuesday evening (fails - unavailable)
5. Confirm assignment
6. Complete assignment with hours
7. View service history

**Scenario 2: Conflict Detection**
1. Create two overlapping event schedules
2. Assign volunteer to first event
3. Confirm first assignment
4. Attempt to assign to overlapping event (fails)
5. Decline first assignment
6. Assign to second event (succeeds)

**Scenario 3: Cross-Branch Protection**
1. Authenticate as Branch A admin
2. Attempt to create profile for Branch B member (fails)
3. Attempt to assign Branch A volunteer to Branch B event (fails)
4. Attempt to assign Branch A volunteer to Branch B group (fails)
5. Attempt to view Branch B volunteer profile (404)

### 3. Admin Interface Tests

Manually verify in Django admin:

1. **VolunteerProfile Admin:**
   - View list with calculated service hours
   - Edit profile with inline availability and assignments
   - Filter by status, branch
   - Search by member name

2. **VolunteerAvailability Admin:**
   - View list with color-coded availability type
   - Create/edit availability window
   - Validate time range consistency

3. **VolunteerAssignment Admin:**
   - View list with color-coded status
   - View assignment details with timeline
   - Verify completed assignments have readonly fields
   - Prevent direct inline assignment creation

---

## PERFORMANCE TESTS

### 1. N+1 Query Detection

```bash
# Run with query logging enabled
pytest tests/volunteers/ --count-queries -v
```

**Check for N+1 queries in:**
- Assignment list endpoint
- Profile history endpoint
- Availability list endpoint

**Expected:** Proper use of `select_related()` and `prefetch_related()`

### 2. Conflict Detection Performance

Test with:
- 100 volunteers
- 50 concurrent events
- 1000+ assignments

Verify conflict checks complete in < 100ms per assignment.

---

## CELERY TASK TESTS

### 1. Reminder Task Test

```bash
# Test individual reminder
python manage.py shell
>>> from apps.volunteers.tasks import send_assignment_reminder
>>> send_assignment_reminder('assignment-id-here')
```

**Verify:**
- Notification created
- reminder_sent_at timestamp set
- Idempotency (running again has no effect)

### 2. Batch Reminder Test

```bash
python manage.py shell
>>> from apps.volunteers.tasks import remind_upcoming_volunteer_assignments
>>> result = remind_upcoming_volunteer_assignments(hours_ahead=24)
>>> print(f"Queued {result} reminders")
```

**Verify:**
- Only CONFIRMED assignments processed
- Only unreminded assignments processed
- No duplicates sent

---

## REGRESSION TESTS

Run full test suite to ensure Phase 9 doesn't break other phases:

```bash
pytest tests/ -v
```

**Critical Areas:**
- Phase 3 RBAC still works
- Phase 4 Member operations unaffected
- Phase 6 Group operations unaffected
- Phase 7 Event operations unaffected
- Phase 10 Notification system unaffected

---

## DATA INTEGRITY CHECKS

### 1. Verify Model Constraints

```python
# In Django shell
from apps.volunteers.models import *

# Test unique constraints
# Test foreign key cascades
# Test default values
# Test enum choices
```

### 2. Verify Database Schema

```bash
python manage.py dbshell
```

```sql
-- Check volunteers_profile table
\d volunteers_profile

-- Check volunteers_assignment table
\d volunteers_assignment

-- Check volunteers_availability table
\d volunteers_availability

-- Verify indexes
\di volunteers_*

-- Check for any orphaned records
SELECT COUNT(*) FROM volunteers_assignment WHERE volunteer_id NOT IN (SELECT id FROM volunteers_profile);
```

---

## SECURITY VALIDATION

### 1. Permission Tests

For each role (SUPER_ADMIN, CHAPLAIN, CHAPEL_ADMIN, UNIT_HEAD, MINISTRY_GROUP_LEADER, MEMBER, VISITOR):

Test access to:
- View volunteers
- Create volunteers
- Update volunteers
- Delete volunteers
- Assign volunteers
- Confirm assignments
- Complete assignments

**Expected:** Only authorized roles succeed

### 2. Scope Tests

For each scope (GLOBAL, ORG_WIDE, BRANCH, UNIT, GROUP):

Test access to:
- Own branch volunteers
- Other branch volunteers
- Own unit volunteers
- Other unit volunteers

**Expected:** Scope properly enforced

### 3. Attack Vector Tests

Run all tests in `test_phase9_security.py` and verify:
- All 50+ security tests pass
- No unauthorized access granted
- No data leakage across branches

---

## DOCUMENTATION VERIFICATION

### 1. API Documentation

```bash
# Generate OpenAPI schema
python manage.py spectacular --file schema.yml

# Verify Phase 9 endpoints documented
grep -A 10 "volunteers" schema.yml
```

### 2. Code Documentation

Verify docstrings exist for:
- All models
- All serializers
- All views
- All service functions
- All permissions
- All tasks

---

## ACCEPTANCE CRITERIA CHECKLIST

Phase 9 passes when:

- [ ] All migrations apply cleanly
- [ ] `makemigrations --check` reports no changes
- [ ] All existing Phase 9 tests pass
- [ ] All new security tests pass
- [ ] No N+1 query issues
- [ ] Cross-phase integration tests pass
- [ ] API endpoints return correct responses
- [ ] Admin interface functional
- [ ] Celery tasks work correctly
- [ ] No security vulnerabilities found
- [ ] Documentation complete
- [ ] Code review approved

---

## KNOWN LIMITATIONS

1. **Phase 10 Integration:** Communication preferences not checked yet (Phase 10 may not be fully implemented)
2. **Self-Service Permissions:** Custom permissions created but not yet wired into views (future enhancement)
3. **Concurrency:** select_for_update() used but not stress-tested under high concurrency

---

## NEXT STEPS AFTER TEST EXECUTION

1. Document any test failures
2. Fix identified issues
3. Re-run tests
4. Update PHASE9_IMPLEMENTATION_REPORT.md with test results
5. Mark Phase 9 as COMPLETE or NEEDS_WORK

---

**End of Test Verification Checklist**
