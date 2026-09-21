# Phase 3 Authorization Architecture Audit

## STEP 1 — EXISTING ARCHITECTURE INVENTORY

**Audit Date**: January 2025  
**Purpose**: Map existing authorization before implementing dynamic RBAC

---

## 1. ROLE SYSTEM

### Current Implementation

**Location**: `common/constants/roles.py`

**Architecture**: Hardcoded role constants with CharField choices

```python
User.role = CharField(max_length=32, choices=Roles.CHOICES)
```

**Current Roles**:
- `SUPER_ADMIN` - Global scope
- `CHAPLAIN` - Organization-wide scope
- `CHAPEL_ADMIN` - Branch scope
- `FELLOWSHIP_LEADER` - Fellowship scope (assignment-based)
- `UNIT_HEAD` - Unit scope (assignment-based)
- `MINISTRY_GROUP_LEADER` - Ministry scope (assignment-based)
- `MEMBER` - Self scope
- `VISITOR` - Limited public scope

**Legacy Roles** (deprecated but valid for existing users):
- `PASTOR`, `FINANCE_OFFICER`, `COMMUNITY_LEADER`, `MINISTRY_LEADER`, `DEPARTMENT_LEADER`, `UNIT_LEADER`, `VOLUNTEER`

### Critical Gap: ❌ **NOT DYNAMIC**

Roles are hardcoded constants, not database entities. Cannot create custom roles without code changes.

---

## 2. PERMISSION SYSTEM

### Current Implementation

**Models**: 
- `apps/accounts/models.py`: `Permission`, `RolePermission`
- `common/constants/roles.py`: `PermissionCodes` class

**Architecture**: Database-backed permissions with hardcoded codes

```python
class Permission(models.Model):
    code = models.CharField(max_length=64, unique=True)
    description = models.CharField(max_length=255)

class RolePermission(models.Model):
    role = models.CharField(max_length=32, choices=Roles.CHOICES)
    permission = models.ForeignKey(Permission, ...)
```

**Seeding**: `scripts/seed_roles.py`

**Existing Permission Codes**:
```
MEMBERS_VIEW, MEMBERS_CREATE, MEMBERS_UPDATE, MEMBERS_DELETE, MEMBERS_IMPORT
ATTENDANCE_VIEW, ATTENDANCE_CREATE, ATTENDANCE_EXPORT
EVENTS_VIEW, EVENTS_CREATE, EVENTS_UPDATE, EVENTS_DELETE
FINANCE_VIEW, FINANCE_CREATE, FINANCE_UPDATE, FINANCE_EXPORT
PASTORAL_VIEW, PASTORAL_CREATE, PASTORAL_UPDATE
REPORTS_VIEW, REPORTS_EXPORT
AUDIT_VIEW
ROLE_MANAGE
```

### Missing Permissions

❌ `GROUPS_VIEW`, `GROUPS_CREATE`, `GROUPS_UPDATE`, `GROUPS_DELETE`
❌ `VOLUNTEERS_VIEW`, `VOLUNTEERS_CREATE`, `VOLUNTEERS_UPDATE`, `VOLUNTEERS_DELETE`
❌ `VISITORS_VIEW`, `VISITORS_CREATE`, `VISITORS_UPDATE`, `VISITORS_CONVERT`
❌ `COMMUNICATIONS_VIEW`, `COMMUNICATIONS_CREATE`, `COMMUNICATIONS_SEND`
❌ `PRAYER_VIEW`, `PRAYER_CREATE`, `PRAYER_UPDATE`
❌ `HOUSEHOLDS_VIEW`, `HOUSEHOLDS_CREATE`, `HOUSEHOLDS_UPDATE`
❌ `ROLES_CREATE`, `ROLES_UPDATE`, `ROLES_DELETE`, `ROLES_ASSIGN`

---

## 3. AUTHORIZATION CLASSES

### Permission Classes

**Location**: `common/permissions/rbac.py`

#### `HasRolePermission`
- Checks role against `permission_action_map` on ViewSet
- Super Admin bypass
- MFA enforcement before permission check
- Database-backed via `RolePermission`

#### `IsChapelAdminOrSuperAdmin`
- Role-based (not permission-based)
- Used for sensitive admin operations (MFA reset)

#### `IsPastoralAuthorized`
- Highly restricted for pastoral records
- Object-level authorization
- Checks: pastoral access roles OR assigned staff OR record owner

#### `IsFinanceAuthorized`
- Finance-specific role check
- MFA required

#### `IsAuthenticatedAndActive`
- Basic authentication + active status

#### `IsSuperAdmin`
- Super Admin only

### Scoping Classes

**Location**: `common/permissions/scoping.py`

#### `BranchScopedQuerysetMixin`
- **Critical security component**
- Filters queryset by branch/org scope
- Handles: Global, Org-wide, Branch, Leader scopes
- Forces subclasses to override `get_base_queryset()` not `get_queryset()`
- Prevents direct-ID attacks (returns 404, not 403)

#### Helper Functions

**`led_group_ids(user)`**:
- Returns group IDs user actively leads via `GroupMembership`
- Respects `ROLE_TO_GROUP_TYPE` mapping
- Ignores inactive memberships
- ✅ **Correct source of authority**

**`user_can_access_branch(user, branch_id)`**:
- Validates branch access for given user
- Handles global, org-wide, branch scopes

**`user_can_access_group(user, group)`**:
- Validates group access
- Checks branch scope THEN leader scope

---

## 4. VIEWSET AUDIT

### ViewSets Using `BranchScopedQuerysetMixin` ✅

**Accounts/Members**:
- `MemberViewSet`
- `HouseholdViewSet`

**Groups**:
- `GroupViewSet` (ministries app)
- `GroupMembershipViewSet`

**Organizations**:
- `BranchViewSet`

**Events**:
- `EventViewSet`
- `EventRegistrationViewSet`
- `LocationViewSet`

**Attendance**:
- `AttendanceSessionViewSet`
- `AttendanceRecordViewSet`
- `CheckInDeviceViewSet`
- `VisitorAttendanceViewSet`

**Volunteers**:
- `VolunteerProfileViewSet`
- `VolunteerAssignmentViewSet`

**Visitors**:
- `VisitorViewSet`

**Finance**:
- `GivingViewSet`
- `PledgeViewSet`
- `PaymentViewSet`
- `FinancialStatementViewSet`
- `ReconciliationViewSet`

**Reports**:
- `ReportJobViewSet`

**Uploads**:
- `UploadListView`

### ViewSets WITHOUT Scoping ⚠️

**University Structure** (intentionally public reads):
- `UniversityViewSet` - AllowAny for GET
- `CollegeViewSet` - AllowAny for GET
- `DepartmentViewSet` - AllowAny for GET

**Reference Data** (intentionally org-wide):
- `GivingCategoryViewSet` - No branch field (shared lookup)
- `EventTypeViewSet` - No branch field (shared lookup)

**User-scoped** (self-only):
- `NotificationViewSet` - Filters by `recipient=request.user`

**Organization Management** (Super Admin only):
- `OrganizationViewSet` - Top-level, no scoping needed

**Prayer** ⚠️:
- `PrayerRequestViewSet` - Custom privacy model (self + staff)
- `PrayerNoteViewSet` - Inherits from parent request

**Pastoral** ✅:
- `PastoralCaseViewSet` - Strict custom filtering + IsPastoralAuthorized
- `PastoralNoteViewSet` - IsPastoralAuthorized

---

## 5. CUSTOM ACTION AUDIT

### Member Actions

**`MemberViewSet`**:
- `deactivate` - ✅ Uses `get_object()` (scoped)
- `reactivate` - ✅ Uses `get_object()` (scoped)
- `transfer` - ⚠️ **CRITICAL**: Validates target branch, but needs audit
- `duplicates` - ✅ Scoped to caller
- `merge` - ⚠️ **CRITICAL**: Validates both members, needs comprehensive audit
- `regenerate_qr` - ✅ Uses `get_object()` (scoped)
- `import` - ⚠️ **CRITICAL**: Batch operation, needs scope validation per row

### Visitor Actions

**`VisitorViewSet`**:
- `first_timer_form` - ✅ AllowAny (public), validates branch
- `add_follow_up` - ✅ Uses `get_object()` (scoped)
- `convert` - ⚠️ **CRITICAL**: Creates member, needs target scope validation
- `duplicates` - ✅ Scoped
- `analytics` - ✅ Scoped

### Event Actions

**`EventViewSet`**:
- `generate_schedules` - ✅ Uses `get_object()` (scoped)
- `public` - ✅ AllowAny but filters `is_public=True`
- `calendar` - ✅ HasRolePermission + scoped queryset

**`EventRegistrationViewSet`**:
- `cancel` - ✅ Uses `get_object()` (scoped)

### Attendance Actions

**`AttendanceRecordViewSet`**:
- `analytics` - ✅ Scoped queryset
- `member_history` - ⚠️ Validates member_id, but needs scope check

**`CheckInDeviceViewSet`**:
- `rotate_secret` - ✅ Uses `get_object()` (scoped)
- `revoke` - ✅ Uses `get_object()` (scoped)

### Communication Actions

**`AnnouncementViewSet`**:
- `delivery_status` - ✅ Uses `get_object()` (scoped)

### Report Actions

**`ReportJobViewSet`**:
- `formats` - ✅ No object access

### Notification Actions

**`NotificationViewSet`**:
- `mark_read` - ✅ Uses `get_object()` (self-scoped)

---

## 6. SERIALIZER VALIDATION AUDIT

### FK Validation Present ✅

**`MemberSerializer`**:
- ✅ `validate_branch()` - Checks `user_can_access_branch()`
- ✅ `update()` - Prevents branch/fellowship changes via PATCH (requires transfer action)

### FK Validation MISSING ❌

**`EventSerializer`**:
- ❌ No `validate_branch()`
- ❌ No `validate_location()` - could reference another branch's location

**`EventRegistrationSerializer`**:
- ❌ No `validate_schedule()` - could register for another branch's event
- ❌ No `validate_member()` - could register another branch's member

**`GroupSerializer`**:
- ❌ No `validate_branch()`
- ❌ No `validate_parent()` - could set parent from another branch

**`GroupMembershipSerializer`**:
- ❌ No `validate_group()` - could add to another branch's group
- ❌ No `validate_member()` - could add another branch's member

**`HouseholdSerializer`**:
- ❌ No `validate_branch()`

**`AttendanceSessionSerializer`**:
- ❌ No `validate_event()` - could link to another branch's event
- ❌ No `validate_branch()`

**`VolunteerAssignmentSerializer`**:
- ❌ No `validate_volunteer()` - could assign another branch's volunteer
- ❌ No `validate_event()` - could assign to another branch's event

**`GivingSerializer`**:
- ❌ No `validate_member()` - could record giving for another branch's member
- ❌ No `validate_branch()`

**`PledgeSerializer`**:
- ❌ No `validate_member()`
- ❌ No `validate_branch()`

**`PastoralCaseSerializer`**:
- ❌ No `validate_member()`
- ❌ No `validate_assigned_to()` - could assign to staff in another branch

**`PrayerRequestSerializer`**:
- ❌ No `validate_member()`
- ❌ No `validate_branch()`

**`AnnouncementSerializer`**:
- ❌ No `validate_branch()`
- ❌ No `validate_target_groups()` - could target another branch's groups

**`LocationSerializer`**:
- ❌ No `validate_branch()`

**`VisitorSerializer`**:
- ❌ No `validate_branch()`
- ❌ No `validate_invited_by()` - could reference another branch's member

**`VisitorFollowUpSerializer`**:
- ❌ No `validate_assigned_to()` - could assign to staff in another branch

---

## 7. PUBLIC ENDPOINT INVENTORY

### Truly Public (AllowAny) ✅

1. **Health/Readiness**:
   - `GET /health/` - No auth, no data
   - `GET /liveness/` - No auth, no data
   - `GET /readiness/` - No auth, system status only

2. **Authentication**:
   - `POST /api/v1/auth/register/` - Public registration
   - `POST /api/v1/auth/login/` - Public login
   - `POST /api/v1/auth/refresh/` - Public refresh (requires refresh token)
   - `POST /api/v1/auth/password-reset-request/` - Public password reset
   - `POST /api/v1/auth/password-reset-confirm/` - Public password reset confirm

3. **First-Timer Form**:
   - `POST /api/v1/visitors/first-timer-form/` - AllowAny, validates branch exists

4. **Public Events**:
   - `GET /api/v1/events/public/` - AllowAny, filters `is_public=True` only

5. **University Structure** (reference data):
   - `GET /api/v1/universities/`, `/colleges/`, `/departments/` - AllowAny GET

6. **Payment Webhooks**:
   - `POST /api/v1/payments/webhook/<provider>/` - AllowAny (verified by signature)

### Potential Information Disclosure ⚠️

**University Structure GET endpoints**:
- Returns all universities, colleges, departments
- Needed for registration forms
- ✅ Safe: no PII, just academic structure

**Public Events endpoint**:
- Returns events where `is_public=True`
- ❌ **POTENTIAL ISSUE**: Does NOT filter by branch
- ❌ Could expose events from branches user shouldn't know about
- ❌ Should add branch awareness or at minimum not leak internal events

---

## 8. OWNERSHIP FIELD AUDIT

### Protected Fields ✅

**`Member.user`**:
- ✅ Not in writable fields typically
- ⚠️ Need to verify serializer doesn't allow writes

**`Member.branch`**:
- ✅ Protected by `MemberSerializer.update()` - requires transfer action

**`Member.fellowship`**:
- ✅ Protected by `MemberSerializer.update()` - requires transfer action

### Potentially Vulnerable Fields ❌

**`PastoralCase.assigned_to`**:
- ❌ Writable in serializer
- ❌ Could assign to staff in another branch

**`VisitorFollowUp.assigned_to`**:
- ❌ Writable in serializer
- ❌ Could assign to staff in another branch

**`VolunteerAssignment.volunteer`**:
- ❌ Writable in serializer
- ❌ Could assign volunteers from another branch

**`Announcement.created_by`**:
- ⚠️ Need to verify auto-set, not writable

**Many models with `branch` field**:
- ❌ Most serializers allow `branch` writes without validation

---

## 9. NESTED ENDPOINT AUDIT

### No Nested Endpoints Found

The current API structure uses flat endpoints with filtering, not nested resources like:
- `/groups/{id}/members/`
- `/events/{id}/registrations/`

This is actually SAFER as each endpoint has explicit authorization.

---

## 10. CELERY TASK SECURITY AUDIT

**Location**: `apps/*/tasks.py`

### Task Inventory

**Members**:
- `parse_and_import_members` - ⚠️ Takes `branch_id`, `user_id` - needs validation

**Communications**:
- `dispatch_announcement` - Takes `announcement_id` - ⚠️ needs to verify announcement.branch matches original caller's scope

**Visitors**:
- `send_pending_follow_up_reminders` - Queries all pending, no scope issue

**Reports**:
- `run_report_job` - Takes `job_id` - ⚠️ Report must respect job owner's scope

**Notifications**:
- `deliver_notification` - Takes `notification_id` - Sends to intended recipient, no bypass risk

### Critical Finding ❌

**Celery tasks receive IDs but don't re-validate authorization context.**

Example attack:
1. User A (Branch A) cannot access Branch B
2. User A discovers announcement_id from Branch B
3. User A triggers a task with that ID
4. Task processes Branch B's announcement without checking if User A should have access

**Required Fix**: Tasks must either:
1. Store original caller's user_id and re-validate scope, OR
2. Only accept pre-validated data, never raw IDs

---

## 11. REPORT AUTHORIZATION AUDIT

**Location**: `apps/reports/services.py`

### Current Implementation

```python
def generate_member_report(queryset):
    # Takes a queryset - relies on caller to scope correctly
```

### Gap ❌

Reports accept pre-filtered querysets but don't enforce their own scoping.

**Attack vector**:
- If a ViewSet incorrectly passes an unscoped queryset to report generator
- Report will export data outside caller's scope

**Mitigation**: ✅ All report-triggering ViewSets use `BranchScopedQuerysetMixin`

**Remaining Risk**: Custom report types or future reports might forget scoping.

---

## 12. EXPORT SECURITY AUDIT

**Formats**: CSV, Excel, PDF via `apps/reports/services.py`

### Current Implementation ✅

Exports use the same queryset as views:
- `ReportJobViewSet` uses `BranchScopedQuerysetMixin`
- Report services receive pre-scoped queryset

### Gap ❌

No explicit permission for export separate from view.

**Current**: If you can VIEW, you can EXPORT
**Better**: Separate `*_EXPORT` permissions (partially implemented for some modules)

---

## 13. DASHBOARD AUTHORIZATION AUDIT

**Location**: `apps/dashboard/views.py`

### Known Issue from Phase 1 ⚠️

**Chaplain org-wide scoping gap documented but unfixed**

Current implementation:
```python
def _branch_qs_or_all(model, user):
    if user.role in Roles.GLOBAL_SCOPE_ROLES:
        return model.objects.all()
    return model.objects.filter(branch=user.branch)
```

**Problem**: Chaplain should see organization-wide, not just their branch.

**Status**: Explicitly deferred to Phase 3 in Phase 1 report.

---

## 14. SECURITY INVARIANTS CHECK

| Invariant | Status | Evidence |
|-----------|--------|----------|
| 1. Cannot access object outside scope | 🟡 PARTIAL | BranchScopedQuerysetMixin enforces for GET, but POST/PATCH gaps |
| 2. Cannot create in unauthorized scope | ❌ FAIL | Most serializers lack FK validation |
| 3. Cannot update into unauthorized scope | 🟡 PARTIAL | Member protected, others not |
| 4. Cannot change ownership | 🟡 PARTIAL | Some fields protected, others not |
| 5. Cannot grant unauthorized permissions | ❌ NOT TESTED | No role management implementation yet |
| 6. Cannot elevate own role | ❌ NOT TESTED | No protection visible |
| 7. Direct-ID doesn't grant access | ✅ PASS | BranchScopedQuerysetMixin returns 404 |
| 8. Nested endpoints can't bypass | ✅ PASS | No nested endpoints exist |
| 9. Custom actions can't bypass | 🟡 PARTIAL | Most use `get_object()`, some gaps |
| 10. Background tasks can't bypass | ❌ FAIL | Tasks accept IDs without re-validation |
| 11. Reports respect scope | ✅ PASS | Reports use scoped querysets |
| 12. Inactive leadership = no authority | ✅ PASS | `led_group_ids()` filters is_active=True |

---

## 15. CRITICAL VULNERABILITIES FOUND

### HIGH SEVERITY

#### V1: Request Body FK Injection
**Affected**: All serializers except MemberSerializer
**Attack**: Submit `branch`, `group`, `member`, `assigned_to` IDs from unauthorized scope
**Impact**: Cross-branch data manipulation, privilege escalation
**Example**:
```json
POST /api/v1/events/
{"branch": "<other_branch_id>", "title": "Malicious Event"}
```
**Fix**: Add `validate_<field>()` to all serializers with FK fields

#### V2: Celery Authorization Bypass
**Affected**: All Celery tasks accepting object IDs
**Attack**: Trigger task with ID from unauthorized scope
**Impact**: Background operations on unauthorized data
**Fix**: Tasks must re-validate scope or store authorized object set

#### V3: Public Events Information Disclosure
**Affected**: `GET /api/v1/events/public/`
**Attack**: Enumerate events across all branches
**Impact**: Information leakage about other branches
**Fix**: Consider adding branch context or ensuring truly public events only

### MEDIUM SEVERITY

#### V4: Ownership Field Writable
**Affected**: `PastoralCase.assigned_to`, `VisitorFollowUp.assigned_to`, `Announcement.created_by`
**Attack**: Assign to staff in unauthorized branch
**Impact**: Cross-branch assignment, audit trail manipulation
**Fix**: Auto-set or validate against caller's scope

#### V5: Dashboard Chaplain Scope
**Affected**: `apps/dashboard/views.py`
**Attack**: N/A (known limitation, not vulnerability)
**Impact**: Chaplain sees less than intended
**Fix**: Update `_branch_qs_or_all()` to handle ORG_WIDE_SCOPE_ROLES

#### V6: No Export Permission Separation
**Affected**: All export endpoints
**Attack**: User with VIEW can export bulk data
**Impact**: Potential data exfiltration
**Fix**: Separate EXPORT permissions

### LOW SEVERITY

#### V7: No Self-Escalation Protection
**Affected**: User model updates
**Attack**: PATCH own user with `role=SUPER_ADMIN`
**Impact**: Role escalation
**Status**: Likely blocked by ViewSet permissions, needs explicit test
**Fix**: Add read-only protection on sensitive user fields

#### V8: No Dynamic RBAC
**Affected**: Entire role system
**Attack**: N/A (functionality gap, not vulnerability)
**Impact**: Cannot customize roles without code deployment
**Fix**: Implement database-backed role model

---

## 16. EXISTING TEST COVERAGE

### Security Tests Present ✅

**Phase 0**:
- `tests/accounts/test_auth.py` - Authentication
- `tests/accounts/test_mfa.py` - MFA enforcement
- `tests/members/test_phase0_member_lifecycle.py` - Member operations
- `tests/members/test_chaplain_scope.py` - Chaplain org-wide
- `tests/members/test_multi_leader_scoping.py` - Leader scoping
- `tests/members/test_phase0_endpoint_sweep.py` - Direct-ID attacks
- `tests/visitors/test_visitor_pipeline.py` - Visitor conversion
- `tests/groups/test_leader_deprecation.py` - Multi-leader support

**Phase 1**:
- `tests/audit/test_branch_isolation.py` - Audit log scoping
- `tests/organizations/test_branch_isolation.py` - Branch scoping
- `tests/volunteers/test_branch_isolation.py` - Volunteer scoping
- `tests/attendance/test_branch_isolation.py` - Attendance scoping

### Tests MISSING ❌

- ❌ Request body FK injection tests
- ❌ Ownership field protection tests
- ❌ Celery task authorization tests
- ❌ Self-role-escalation tests
- ❌ Permission escalation tests
- ❌ Cross-fellowship/unit tests (beyond member scoping)
- ❌ Comprehensive custom action authorization tests
- ❌ Export permission tests
- ❌ Dashboard scope tests

---

## 17. RECOMMENDATIONS

### IMMEDIATE (Phase 3 Core)

1. ✅ **Add FK validation to all serializers**
   - Priority: HIGH
   - Effort: 2-3 days
   - Impact: Blocks V1

2. ✅ **Implement dynamic role model**
   - Priority: HIGH (Phase 3 requirement)
   - Effort: 1 week
   - Impact: Enables customization

3. ✅ **Fix Celery task authorization**
   - Priority: HIGH
   - Effort: 2-3 days
   - Impact: Blocks V2

4. ✅ **Add ownership field protection**
   - Priority: HIGH
   - Effort: 1 day
   - Impact: Blocks V4

5. ✅ **Expand permission catalog**
   - Priority: MEDIUM
   - Effort: 1 day
   - Impact: Completeness

6. ✅ **Fix dashboard Chaplain scope**
   - Priority: MEDIUM
   - Effort: 2 hours
   - Impact: Closes Phase 1 gap

7. ✅ **Add comprehensive security tests**
   - Priority: HIGH
   - Effort: 1 week
   - Impact: Verification

### FUTURE (Post-Phase 3)

8. ◯ Fix public events information disclosure (V3)
9. ◯ Separate export permissions (V6)
10. ◯ Add inactivity timeout (Phase 2 gap)
11. ◯ Add QR expiration (Phase 8 gap)

---

## 18. PHASE 3 IMPLEMENTATION PLAN

Based on audit findings, Phase 3 will proceed as follows:

### Step 2: Design Dynamic RBAC Architecture
- Create `Role` model (database-backed)
- Create migration path from hardcoded to dynamic
- Preserve existing role behavior during transition

### Step 3: Implement Authorization Engine
- Extend permission catalog
- Add scope configuration per role
- Implement role management endpoints

### Step 4: Safe Migration
- Migrate existing users to new role model
- Preserve all existing permissions
- Zero downtime migration strategy

### Step 5: Harden Serializers
- Add `validate_<field>()` to ALL serializers with FKs
- Protect ownership fields
- Add comprehensive validation

### Step 6: Audit ViewSets
- Review every ViewSet for authorization gaps
- Add missing permission checks
- Standardize custom action authorization

### Step 7: Secure Sensitive Modules
- Finance, Pastoral, Prayer special handling
- Explicit export permissions
- Dashboard scope fix

### Step 8: Comprehensive Testing
- FK injection tests
- Privilege escalation tests
- Cross-scope tests
- Celery authorization tests

### Step 9: Regression Testing
- Ensure all 144 Phase 0-1 tests pass
- PostgreSQL/Redis/Celery validation

### Step 10: Final Audit & Report
- Security sweep
- Document remaining issues
- Phase 3 completion report

---

## AUDIT SUMMARY

**Authorization Architecture**: 🟡 **GOOD FOUNDATION, SIGNIFICANT GAPS**

**Strengths**:
- ✅ Excellent scoping architecture (`BranchScopedQuerysetMixin`)
- ✅ Database-backed permissions
- ✅ Multi-leader support correct
- ✅ Direct-ID protection working
- ✅ MFA enforcement working

**Critical Gaps**:
- ❌ Roles are hardcoded (not dynamic)
- ❌ FK validation missing in most serializers
- ❌ Celery tasks don't re-validate authorization
- ❌ Ownership fields inadequately protected
- ❌ Incomplete permission catalog

**Risk Level**: **MEDIUM-HIGH**

The existing architecture is sound but incomplete. The `BranchScopedQuerysetMixin` provides excellent GET protection, but POST/PATCH operations have significant validation gaps that could allow cross-branch manipulation.

**Phase 3 Status**: **READY TO PROCEED**

All necessary information gathered. Implementation can begin.

---

**Next Step**: Design dynamic RBAC architecture compatible with existing system.
