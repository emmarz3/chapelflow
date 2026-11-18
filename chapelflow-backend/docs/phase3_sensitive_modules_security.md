# Phase 3: Sensitive Modules Security Hardening

## Overview

This document covers additional security controls for the most sensitive modules in ChapelFlow CUC:
- **Finance** - Giving, pledges, payments (PII + financial data)
- **Pastoral** - Pastoral cases, notes (highly confidential counseling data)
- **Prayer** - Prayer requests, notes (private spiritual matters)

**Security Principle**: Sensitive data requires defense-in-depth beyond standard RBAC.

---

## Security Controls Matrix

| Module | Permission Class | MFA Required | Object-Level Checks | Audit Logging | Data Masking |
|--------|-----------------|--------------|---------------------|---------------|--------------|
| Finance | IsFinanceAuthorized | ✅ YES | ❌ No (branch-scope sufficient) | ✅ YES | 🟡 Partial (last 4 digits) |
| Pastoral | IsPastoralAuthorized | ❌ No | ✅ YES (assigned_to/member) | ✅ YES | ❌ No |
| Prayer | IsAuthenticated | ❌ No | 🟡 Queryset-level | ✅ YES | ❌ No |

**Legend**:
- ✅ Implemented and verified
- 🟡 Partial implementation
- ❌ Not implemented (gap identified)

---

## Finance Module Security

### Current Implementation

#### IsFinanceAuthorized Permission Class
```python
class IsFinanceAuthorized(BasePermission):
    def has_permission(self, request, view):
        user = request.user
        return bool(
            user and user.is_authenticated and user.is_active
            and user.role in Roles.FINANCE_ACCESS_ROLES
            and user_has_completed_required_mfa(user)
        )
```

**Strengths**:
- ✅ Requires MFA for all finance operations
- ✅ Role-based access (FINANCE_ACCESS_ROLES only)
- ✅ Applied to all Finance ViewSets

**Gaps**:
- ❌ No object-level permission checks (relies on BranchScopedQuerysetMixin)
- ❌ No rate limiting on sensitive queries
- 🟡 Payment webhook endpoint is AllowAny (mitigated by signature verification)

### Finance Access Roles

From `common/constants/roles.py`:
```python
FINANCE_ACCESS_ROLES = {
    Roles.SUPER_ADMIN,
    Roles.CHAPLAIN,
    Roles.FINANCE_OFFICER,
}
```

**Analysis**: Appropriately restricted. Only org-wide or finance-specific roles.

### Audit Trail

Finance operations are logged via:
- `apps.audit.services.log_action()` (automatic via signals)
- Manual logging in services for critical operations

**Verified**:
- ✅ Giving creation logged
- ✅ Pledge creation/updates logged
- ✅ Payment status changes logged (webhooks)
- ✅ Reconciliation operations logged

### Data Protection

**PII in Finance Models**:
- `Giving.member` (FK to Member with full PII)
- `Payment.member` (FK to Member)
- `Pledge.member` (FK to Member)

**Current Protection**:
- ✅ Branch-scoped queryset filtering
- ✅ MFA required
- ✅ Serializers validate FK scope
- ❌ No field-level masking in responses

**Recommendation**: Consider masking member names in list views (show only in detail views with explicit permission check).

### Finance Webhook Security

**PaymentWebhookView**:
- Permission: `AllowAny` (gateways cannot authenticate as ChapelFlow users)
- Security: Cryptographic signature verification via `process_webhook()`
- Idempotency: Replay protection via `idempotency_key`

**Status**: ✅ SECURE (standard pattern for payment gateways)

---

## Pastoral Module Security

### Current Implementation

#### IsPastoralAuthorized Permission Class
```python
class IsPastoralAuthorized(BasePermission):
    """
    Pastoral records are the most sensitive data in the system.
    Access limited to:
      - the member the case is about
      - staff in Roles.PASTORAL_ACCESS_ROLES
      - staff explicitly assigned to the case
    """
    
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.is_active)
    
    def has_object_permission(self, request, view, obj):
        user = request.user
        if user.role in Roles.PASTORAL_ACCESS_ROLES:
            return True
        assigned_to = getattr(obj, "assigned_to_id", None)
        if assigned_to and assigned_to == user.id:
            return True
        member = getattr(obj, "member", None)
        if member and getattr(member, "user_id", None) == user.id:
            return True
        return False
```

**Strengths**:
- ✅ Object-level permission checks
- ✅ Three-tier access (pastoral staff, assigned, self)
- ✅ Custom queryset filtering in PastoralCaseViewSet

**Gaps**:
- ❌ No MFA requirement (most sensitive data!)
- ❌ No additional checks for write operations (create/update/delete)
- ❌ PastoralNote inherits but doesn't verify parent case authorization

### Pastoral Access Roles

```python
PASTORAL_ACCESS_ROLES = {
    Roles.SUPER_ADMIN,
    Roles.CHAPLAIN,
    Roles.CHAPEL_ADMIN,
}
```

**Analysis**: Appropriately restricted to senior staff.

### Queryset Security

**PastoralCaseViewSet.get_queryset()**:
```python
def get_queryset(self):
    qs = PastoralCase.objects.select_related("branch", "member", "assigned_to").prefetch_related("notes")
    user = self.request.user

    if user.role in Roles.GLOBAL_SCOPE_ROLES:
        return qs
    if user.role in Roles.PASTORAL_ACCESS_ROLES:
        return qs.filter(branch_id=user.branch_id) if user.branch_id else qs.none()

    # Any other role: only cases assigned to them, or about themselves.
    from django.db.models import Q
    return qs.filter(Q(assigned_to=user) | Q(member__user=user))
```

**Status**: ✅ SECURE - Properly restricts visibility

### Critical Security Gaps

1. **NO MFA for Pastoral Access**
   - **Risk**: HIGH
   - **Impact**: Unauthorized access to highly sensitive counseling records
   - **Fix**: Add `user_has_completed_required_mfa(user)` to `IsPastoralAuthorized.has_permission()`

2. **PastoralNote doesn't verify parent case access**
   - **Risk**: MEDIUM
   - **Impact**: Could create notes on cases user shouldn't access
   - **Fix**: Verify case access in `PastoralNoteSerializer.validate_case()`

---

## Prayer Module Security

### Current Implementation

**Permission Class**: `IsAuthenticated` (default)

**Queryset Filtering**:
```python
def get_queryset(self):
    qs = PrayerRequest.objects.select_related("branch", "member", "assigned_to").prefetch_related("notes")
    user = self.request.user

    if user.role in Roles.GLOBAL_SCOPE_ROLES or user.role in Roles.PASTORAL_ACCESS_ROLES:
        if user.role in Roles.GLOBAL_SCOPE_ROLES:
            return qs
        return qs.filter(branch_id=user.branch_id) if user.branch_id else qs.none()

    # Ordinary members: own requests OR public (non-private) requests OR assigned requests
    from django.db.models import Q
    own_member_filter = Q(member__user=user)
    return qs.filter(
        Q(branch_id=user.branch_id) & (own_member_filter | Q(is_private=False) | Q(assigned_to=user))
    )
```

**Status**: ✅ SECURE - Privacy filtering works correctly

### Privacy Model

- `is_private=True`: Only visible to creator, pastoral staff, and assigned staff
- `is_private=False`: Visible to all members in the same branch

**Verified**: ✅ Queryset properly enforces privacy

### Gaps

1. **No dedicated permission class**
   - **Risk**: LOW (IsAuthenticated is acceptable for prayer)
   - **Fix**: Consider creating `IsPrayerAuthorized` for clarity

2. **No MFA requirement**
   - **Risk**: LOW (less sensitive than pastoral cases)
   - **Status**: Acceptable for current requirements

---

## Celery Tasks Authorization Audit

### High-Risk Tasks (Need Re-validation)

#### 1. `bulk_import_members_task(file_url, requesting_user_id)`
**Location**: `apps/members/tasks.py`

**Current Implementation**:
```python
@shared_task
def bulk_import_members_task(file_url, requesting_user_id):
    # Fetches User by id, processes CSV
```

**Security Gap**: ❌ **Does NOT re-validate that requesting_user still has permission**

**Risk**: HIGH
- User could trigger import, then have permissions revoked
- Task runs hours later with stale authorization

**Fix Required**:
```python
@shared_task
def bulk_import_members_task(file_url, requesting_user_id):
    from apps.accounts.models import User
    from common.constants.roles import PermissionCodes
    
    user = User.objects.get(id=requesting_user_id)
    
    # Phase 3: Re-validate permission at task execution time
    if not user.has_perm_code(PermissionCodes.MEMBERS_CREATE):
        logger.error(f"User {user.id} no longer has members.create permission")
        return {"error": "Permission denied"}
    
    # Continue with import...
```

#### 2. `run_report_job(job_id)`
**Location**: `apps/reports/tasks.py`

**Current Implementation**:
```python
@shared_task
def run_report_job(job_id):
    from .models import ReportJob
    job = ReportJob.objects.select_related("requested_by").get(id=job_id)
    # Generates report
```

**Security Gap**: ❌ **Does NOT re-validate that requested_by still has permission**

**Risk**: MEDIUM
- User could request report, then lose access
- Report generated with data user shouldn't see

**Fix Required**: Re-validate user permission to the branch/scope at task execution time

#### 3. `dispatch_announcement(announcement_id)`
**Location**: `apps/communications/tasks.py`

**Status**: ✅ LOW RISK
- Announcement already created (validated at creation time)
- Task just dispatches notifications
- No additional authorization needed

### Low-Risk Tasks (Background Processing)

These tasks don't need re-validation (no user-driven authorization):
- `send_due_event_reminders()` - System-triggered
- `flag_members_with_prolonged_absence()` - System-triggered
- `send_pending_follow_up_reminders()` - System-triggered
- `deliver_notification()` - Already authorized notification
- `send_password_reset_email()` - Public endpoint

---

## Fixes Required

### Priority 1: HIGH (Security Vulnerabilities)

1. **Add MFA to Pastoral Access**
   ```python
   # common/permissions/rbac.py - IsPastoralAuthorized
   def has_permission(self, request, view):
       user = request.user
       return bool(
           user and user.is_authenticated and user.is_active
           and user_has_completed_required_mfa(user)  # ADD THIS
       )
   ```

2. **Re-validate Celery Task Authorization**
   - Fix `bulk_import_members_task()`
   - Fix `run_report_job()`

3. **Validate Parent Case Access in PastoralNote**
   ```python
   # apps/pastoral/serializers.py - PastoralNoteSerializer
   def validate_case(self, case):
       # Ensure user can access this case
       from common.permissions.rbac import IsPastoralAuthorized
       permission = IsPastoralAuthorized()
       if not permission.has_object_permission(self.context['request'], None, case):
           raise serializers.ValidationError("You cannot add notes to this case.")
       return case
   ```

### Priority 2: MEDIUM (Defense in Depth)

4. **Add object-level checks to Finance operations**
   - Consider adding `has_object_permission` to `IsFinanceAuthorized`
   - Verify user's branch scope matches resource branch

5. **Create IsPrayerAuthorized permission class**
   - Clarity and consistency
   - Easier to add future requirements (e.g., MFA)

### Priority 3: LOW (Documentation/Clarity)

6. **Document PII handling in serializers**
7. **Add rate limiting to finance endpoints**
8. **Consider field-level masking for sensitive data**

---

## Testing Requirements

### Finance Module Tests

- [ ] Test MFA required for all finance operations
- [ ] Test non-finance roles cannot access (403)
- [ ] Test cross-branch access blocked
- [ ] Test webhook signature verification
- [ ] Test audit logging for all operations

### Pastoral Module Tests

- [ ] Test MFA required (after fix)
- [ ] Test member can only access own cases
- [ ] Test assigned staff can access assigned cases
- [ ] Test pastoral roles can access branch-scoped cases
- [ ] Test PastoralNote validates parent case access
- [ ] Test object-level permission checks

### Prayer Module Tests

- [ ] Test is_private filtering
- [ ] Test member sees own private requests
- [ ] Test member doesn't see others' private requests
- [ ] Test pastoral staff sees all private requests in branch
- [ ] Test public requests visible to all branch members

### Celery Task Tests

- [ ] Test bulk_import_members_task re-validates permission
- [ ] Test run_report_job re-validates permission
- [ ] Test tasks fail gracefully when permission revoked

---

## Completion Criteria

Phase 7 (Secure Sensitive Modules) is complete when:

- [x] Finance module security audited
- [x] Pastoral module security audited
- [x] Prayer module security audited
- [x] Celery tasks audited for authorization gaps
- [ ] HIGH priority fixes applied (MFA, task re-validation, pastoral note validation)
- [ ] MEDIUM priority fixes applied (object-level checks, IsPrayerAuthorized)
- [ ] All sensitive module tests pass
- [ ] Documentation complete

---

## Security Invariants to Verify

After fixes, these must be true:

1. **Finance Invariant**: All finance operations require MFA AND role in FINANCE_ACCESS_ROLES
2. **Pastoral Invariant**: All pastoral access requires MFA AND (pastoral role OR assigned OR self)
3. **Prayer Privacy Invariant**: Private prayer requests never exposed to unauthorized users
4. **Celery Invariant**: Long-running tasks re-validate authorization at execution time
5. **Cross-Branch Invariant**: No sensitive data leaks across branch boundaries

---

**Status**: AUDIT COMPLETE - 3 high priority fixes required  
**Risk Level**: MEDIUM (gaps identified, fixes required before production)  
**Estimated Fix Time**: 2-4 hours
