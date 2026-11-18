# PHASE 9 VOLUNTEER MANAGEMENT — INITIAL AUDIT FINDINGS

**Date:** September 1, 2026  
**Auditor:** Kiro AI  
**Scope:** Complete reconciliation of Phase 9 volunteer management subsystem

---

## EXECUTIVE SUMMARY

The Phase 9 implementation is **INCOMPLETE AND INCONSISTENT**. The migration 0003 added extensive fields and models to the database schema, but the models.py file was never updated to match. This creates a critical mismatch where:

- **Services expect** fields that don't exist in models
- **Tests import** classes that aren't defined
- **Tasks reference** enums that are missing
- **Migrations created** a schema that models don't reflect

**Critical Issues Found:** 7  
**High-Priority Issues:** 5  
**Medium-Priority Issues:** 3  

**Verdict:** Phase 9 is NOT functional and requires complete reconciliation.

---

## DETAILED FINDINGS

### 1. MODELS vs MIGRATIONS MISMATCH (CRITICAL)

**Finding:** Migration `0003_volunteeravailability_and_more.py` adds extensive fields to `VolunteerAssignment` and creates `VolunteerAvailability` model, but `models.py` does not contain these.

**What Migration 0003 Adds:**
- `VolunteerAvailability` model (complete new model)
- `VolunteerAssignment.status` field with AssignmentStatus choices
- `VolunteerAssignment.completed_at` (DateTimeField)
- `VolunteerAssignment.hours_logged` (DecimalField)
- `VolunteerAssignment.reminder_sent_at` (DateTimeField)
- `VolunteerAssignment.responded_at` (DateTimeField)
- `VolunteerAssignment.group` (ForeignKey to ministries.Group)
- `VolunteerProfile.status` field with VolunteerStatus choices
- Indexes for performance

**What models.py Actually Contains:**
- `VolunteerProfile`: id, member, skills, availability_notes, is_active, created_at (NO status field)
- `VolunteerAssignment`: id, volunteer, event_schedule, role, confirmed, notes, created_at (NO status, hours_logged, completed_at, responded_at, reminder_sent_at, group)
- `VolunteerRole` enum (role choices)
- **MISSING:** `VolunteerAvailability` model entirely
- **MISSING:** `AssignmentStatus` enum
- **MISSING:** `VolunteerStatus` enum

**Impact:** Services, tasks, and tests all fail with AttributeError when accessing these fields.

---

### 2. SERVICES EXPECT NON-EXISTENT CLASSES (CRITICAL)

**File:** `apps/volunteers/services.py`

**Finding:** Imports `AssignmentStatus` from models but it doesn't exist:
```python
from .models import AssignmentStatus, VolunteerAssignment
```

**Usage in services.py:**
- `AssignmentStatus.PENDING`
- `AssignmentStatus.CONFIRMED`
- `AssignmentStatus.DECLINED`
- `AssignmentStatus.COMPLETED`
- `AssignmentStatus.CANCELLED`
- `assignment.status` field access
- `assignment.responded_at` field access
- `assignment.hours_logged` field access
- `assignment.completed_at` field access
- `assignment.group` field access
- `volunteer.availability` relation access (VolunteerAvailability)

**Impact:** All service functions fail immediately when imported.

---

### 3. TASKS EXPECT NON-EXISTENT CLASSES (CRITICAL)

**File:** `apps/volunteers/tasks.py`

**Finding:** Imports `AssignmentStatus` and uses fields that don't exist:
```python
from .models import AssignmentStatus, VolunteerAssignment
```

**Usage in tasks.py:**
- Filters by `status=AssignmentStatus.CONFIRMED`
- Checks `assignment.reminder_sent_at`
- Sets `assignment.reminder_sent_at`
- Accesses `event_schedule.occurrence_start` and `occurrence_end`

**Impact:** Celery tasks fail, volunteer reminders never sent.

---

### 4. TESTS IMPORT NON-EXISTENT CLASSES (CRITICAL)

**File:** `tests/volunteers/test_phase9_volunteers.py`

**Finding:** Multiple test classes import and use undefined models:
```python
from apps.volunteers.models import AssignmentStatus
from apps.volunteers.models import VolunteerAvailability
```

**Test expectations:**
- `AssignmentStatus.PENDING`, `.CONFIRMED`, `.DECLINED`, `.COMPLETED`
- `assignment.status` equality checks
- `assignment.confirmed` boolean sync with status
- `assignment.hours_logged` decimal field
- `assignment.responded_at` timestamp
- `assignment.completed_at` timestamp
- `VolunteerAvailability.objects.create()`
- Conflict detection with availability windows
- Group assignment scope validation
- Lifecycle transitions (confirm → complete)

**Impact:** All Phase 9 tests fail immediately. Test suite gives false impression of coverage.

---

### 5. SERIALIZERS DON'T EXPOSE NEW FIELDS (HIGH)

**File:** `apps/volunteers/serializers.py`

**Current State:**
- `VolunteerProfileSerializer` exposes: id, member, skills, availability_notes, is_active, created_at
- `VolunteerAssignmentSerializer` exposes: id, volunteer, event_schedule, role, confirmed, notes, created_at

**Missing Fields:**
- No `status` in VolunteerProfileSerializer (migration added it)
- No `status` in VolunteerAssignmentSerializer (migration added it)
- No `hours_logged` in VolunteerAssignmentSerializer
- No `completed_at` in VolunteerAssignmentSerializer
- No `responded_at` in VolunteerAssignmentSerializer
- No `reminder_sent_at` in VolunteerAssignmentSerializer
- No `group` in VolunteerAssignmentSerializer
- **MISSING:** `VolunteerAvailabilitySerializer` entirely

**Security Issue:** When fields are added, they need proper read-only protection. Fields like `hours_logged`, `completed_at`, `reminder_sent_at` must be server-controlled.

---

### 6. VIEWS MISSING CUSTOM ACTIONS (HIGH)

**File:** `apps/volunteers/views.py`

**Current State:** Only standard CRUD operations (list, retrieve, create, update, partial_update, destroy)

**Missing Actions Expected by Tests:**
- `POST /assignments/{id}/confirm/` - transition to CONFIRMED status
- `POST /assignments/{id}/decline/` - transition to DECLINED status with reason
- `POST /assignments/{id}/complete/` - transition to COMPLETED status with hours_logged
- `GET /profiles/{id}/history/` - retrieve volunteer service history with total hours

**Impact:** Tests reference these endpoints but they don't exist. Lifecycle management is incomplete.

---

### 7. CREATE-TIME AUTHORIZATION NOT ENFORCED (CRITICAL - SECURITY)

**File:** `apps/volunteers/views.py`

**Finding:** ViewSets use `BranchScopedQuerysetMixin` which only protects list/retrieve/update/destroy. The `get_queryset()` scoping doesn't prevent unauthorized POST.

**Attack Vectors:**
1. **Member Substitution:** Chapel Admin A creates VolunteerProfile for Member B in Branch B
2. **Volunteer Substitution:** User changes `volunteer` ID to another volunteer when creating assignment
3. **Cross-Branch Event:** Branch A admin assigns volunteer to Branch B event
4. **Cross-Branch Group:** Branch A admin assigns volunteer to Branch B group/unit
5. **Status Manipulation:** Client sends `status=COMPLETED` on creation
6. **Hours Manipulation:** Client sends `hours_logged=999` on creation

**Current Protection:** NONE for creation. Only read operations are protected.

**Required:** Explicit validation in serializer `create()` method or view `perform_create()`.

---

### 8. NO COMMUNICATION PREFERENCE INTEGRATION (HIGH)

**File:** `apps/volunteers/tasks.py`

**Finding:** `send_assignment_reminder()` creates notifications without checking if the user has opted into that channel.

**Current Code:**
```python
notification = Notification.objects.create(
    recipient=user, recipient_member=assignment.volunteer.member,
    channel=NotificationChannel.EMAIL, title=title, body=body,
)
```

**Missing:** 
- No check if user has enabled EMAIL notifications
- No check if user has opted out of volunteer reminders
- No respect for Phase 10 communication preferences

**Expected Pattern:** Query user preferences before creating notification, or use a service that encapsulates this check.

**Note:** Initial search found NO CommunicationPreference model in notifications app, suggesting Phase 10 might not be fully implemented either. Need to verify Phase 10 status.

---

### 9. CONFIRMED FIELD REDUNDANT WITH STATUS (MEDIUM)

**Finding:** Both `confirmed` boolean and `status` enum exist on VolunteerAssignment.

**Migration 0001 added:** `confirmed` boolean (default=False)
**Migration 0003 added:** `status` enum (default='PENDING')

**Current service logic:**
- `services.confirm_assignment()` sets BOTH `status=CONFIRMED` and `confirmed=True`
- Tests check BOTH fields

**Issue:** Two sources of truth for the same concept. Potential for inconsistency.

**Recommendation:** Either deprecate `confirmed` field (prefer status enum) OR ensure confirmed syncs automatically via model save() override.

---

### 10. NO DUPLICATE REMINDER PROTECTION IN DATABASE (MEDIUM)

**Finding:** `reminder_sent_at` timestamp is checked in task logic but not enforced as a constraint.

**Current Protection:** 
```python
if assignment is None or assignment.reminder_sent_at is not None:
    return
```

**Race Condition:** Two concurrent Celery tasks could both pass the check and send duplicate reminders.

**Recommendation:** Use `select_for_update()` or implement idempotency key at notification level.

---

### 11. ADMIN INTERFACE TOO SIMPLE (LOW)

**File:** `apps/volunteers/admin.py`

**Current State:**
```python
admin.site.register(VolunteerProfile)
admin.site.register(VolunteerAssignment)
```

**Issues:**
- No VolunteerAvailability registered
- No custom list_display for useful columns
- No filters for status, branch, etc.
- No readonly_fields protection for historical data
- No inlines for related objects

**Impact:** Admin users cannot effectively manage Phase 9 through Django admin.

---

### 12. NO PERMISSIONS.PY FOR FINE-GRAINED CONTROL (MEDIUM)

**Finding:** No `apps/volunteers/permissions.py` file exists.

**Current Situation:** Views use only RBAC via `HasRolePermission` and scope via `BranchScopedQuerysetMixin`.

**Missing Scenarios:**
- Volunteers managing their OWN availability (self-service)
- Volunteers viewing their OWN assignments
- Volunteers confirming/declining their OWN assignments
- Staff managing ANY volunteer in scope

**Recommendation:** Create permission classes for:
- `IsVolunteerOwnerOrStaff` - volunteer can manage own data, staff can manage any
- `CanManageAssignment` - check ownership + status transition rules

---

### 13. PERMISSION CODES EXIST BUT NOT USED CORRECTLY (HIGH)

**Finding:** `PermissionCodes.VOLUNTEERS_*` exists but views don't fully utilize them.

**Available Codes:**
- `VOLUNTEERS_VIEW`
- `VOLUNTEERS_CREATE`
- `VOLUNTEERS_UPDATE`
- `VOLUNTEERS_DELETE`
- `VOLUNTEERS_ASSIGN`

**Current Usage in Views:**
- VolunteerProfileViewSet maps to `MEMBERS_VIEW` and `MEMBERS_UPDATE` (WRONG!)
- VolunteerAssignmentViewSet maps to `EVENTS_VIEW` and `EVENTS_UPDATE` (WRONG!)

**Should Be:**
- VolunteerProfileViewSet → `VOLUNTEERS_VIEW`, `VOLUNTEERS_CREATE`, `VOLUNTEERS_UPDATE`, `VOLUNTEERS_DELETE`
- VolunteerAssignmentViewSet → `VOLUNTEERS_VIEW`, `VOLUNTEERS_ASSIGN`, `VOLUNTEERS_UPDATE`, `VOLUNTEERS_DELETE`

**Impact:** Users with MEMBERS or EVENTS permissions incorrectly get volunteer management access. Users with VOLUNTEERS permissions don't get access.

---

### 14. INDEXES CREATED BY MIGRATION (GOOD)

**Finding:** Migration 0003 adds appropriate indexes:
- `volunteers_assignment` index on `(volunteer, status)`
- `volunteers_availability` index on `(volunteer, weekday)`

**Status:** ✅ This is correct and will improve query performance once models are fixed.

---

### 15. NO TESTS FOR SECURITY ATTACKS (CRITICAL)

**Missing Test Coverage:**
- Member substitution attack
- Volunteer substitution attack  
- Cross-branch event assignment attack
- Cross-branch group assignment attack
- Direct ID access attack (knowing an ID grants access)
- Mass assignment attack (unauthorized fields in POST)
- Status manipulation attack (client sets COMPLETED)
- Hours manipulation attack (client sets hours_logged)
- Historical assignment modification attack
- Unauthorized deletion
- Communication preference bypass

**Current Tests:** Only positive path tests (expected behavior works) and some conflict detection. NO security/attack tests.

---

## ARCHITECTURE INCONSISTENCIES

### Integration Points

**✅ GOOD:**
- Uses existing `members.Member` model (no duplicate)
- Uses existing `events.EventSchedule` model (no duplicate)
- Uses existing `ministries.Group` model (per migration 0003)
- Uses existing Phase 3 RBAC via `HasRolePermission`
- Uses existing scope mixin `BranchScopedQuerysetMixin`

**❌ BAD:**
- Does NOT use existing Phase 10 notification preferences (if they exist)
- Does NOT audit sensitive operations
- Does NOT have self-service endpoints (e.g. `/me/availability/`)

---

## MIGRATION HISTORY ASSESSMENT

**Migration 0001 (initial):**
- Creates VolunteerProfile (basic)
- Creates VolunteerAssignment (basic)
- Status: ✅ Executed successfully

**Migration 0002 (phase1_default_ordering):**
- Adds ordering to Meta classes
- Status: ✅ Executed successfully

**Migration 0003 (volunteeravailability_and_more):**
- Adds EXTENSIVE new fields and models
- Status: ✅ Executed in database
- **CRITICAL ISSUE:** Models.py never updated to reflect these changes

**Conclusion:** Database schema is at migration 0003 state, but models.py is at migration 0001 state. This is the root cause of all Phase 9 failures.

---

## DEPENDENCY ANALYSIS

**Phase 9 Depends On:**
- ✅ Phase 3 (RBAC) - Present and used
- ✅ Phase 4 (Members) - Present and integrated
- ✅ Phase 6 (Groups/Ministries) - Present, migration references it
- ✅ Phase 7 (Events) - Present and integrated via EventSchedule
- ❓ Phase 10 (Notifications) - Used but preferences not checked
- ❌ Phase 8 (Finance) - Not relevant to volunteers

**Phases That Depend On Phase 9:**
- None found (Phase 9 is a leaf feature)

---

## REQUIRED ACTIONS

### CRITICAL (Must Fix Before Phase 9 Can Function):
1. ✅ Add AssignmentStatus enum to models.py
2. ✅ Add VolunteerStatus enum to models.py  
3. ✅ Add all missing fields to VolunteerAssignment model
4. ✅ Add VolunteerAvailability model
5. ✅ Add missing field to VolunteerProfile model (status)
6. ✅ Fix services.py imports (will work after models fixed)
7. ✅ Fix tasks.py imports (will work after models fixed)
8. ✅ Create VolunteerAvailabilitySerializer
9. ✅ Add custom actions to views (confirm, decline, complete, history)
10. ✅ Enforce create-time authorization in views/serializers
11. ✅ Fix permission_action_map to use VOLUNTEERS_* codes

### HIGH (Security/Functionality Gaps):
12. ✅ Create comprehensive security test suite
13. ✅ Integrate with Phase 10 communication preferences (or stub if missing)
14. ✅ Add proper read-only fields to serializers
15. ✅ Create permissions.py for self-service scenarios

### MEDIUM (Quality/Maintainability):
16. ✅ Improve admin.py with proper configuration
17. ✅ Add concurrency protection for duplicate reminders
18. ✅ Decide on confirmed field vs status enum strategy

### LOW (Nice to Have):
19. ✅ Add self-service /me/ endpoints for volunteers
20. ✅ Enhance audit logging for sensitive operations

---

## RECONCILIATION STRATEGY

**Approach:** Update models.py to match migration 0003 schema WITHOUT creating new migrations (schema already correct).

**Steps:**
1. Add all enums (AssignmentStatus, VolunteerStatus)
2. Add VolunteerAvailability model matching migration
3. Add all missing fields to existing models matching migration
4. Verify with `python manage.py makemigrations --check` (should report no changes)
5. Update serializers
6. Update views
7. Write tests
8. Run tests
9. Generate report

**DO NOT:** Create new migrations. The database schema is already correct.

---

## CONCLUSION

Phase 9 is in a **BROKEN STATE** due to models.py not being updated to match the migration schema. This is not a minor bug but a fundamental architectural mismatch that prevents the entire subsystem from functioning.

**Estimated Effort:** 4-6 hours to fully reconcile and secure.

**Risk Level:** HIGH - No functionality works currently, but fixing is straightforward since migrations are correct.

**Recommendation:** Proceed with full reconciliation following the strategy above.

---

**End of Audit Report**
