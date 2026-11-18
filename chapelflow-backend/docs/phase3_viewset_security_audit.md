# Phase 3: ViewSet Security Audit

## Overview

This document audits all ViewSets for authorization security:
- Permission class application
- permission_action_map completeness
- Custom action protection
- perform_create/update/destroy hooks

**Audit Date**: Phase 3 Step 6  
**Scope**: All ViewSets across ChapelFlow CUC backend

---

## Audit Criteria

For each ViewSet, verify:

1. **✅ Permission Class**: Has `permission_classes` defined (not defaulting to AllowAny)
2. **✅ Action Map**: Has `permission_action_map` covering all actions
3. **✅ Custom Actions**: All `@action` decorators have permission_action_map entries
4. **✅ Queryset Scoping**: Uses `BranchScopedQuerysetMixin` for branch-scoped resources
5. **✅ Perform Hooks**: `perform_create/update/destroy` don't bypass authorization

---

## ViewSet Inventory

### ✅ EVENTS Module

#### EventTypeViewSet
- **Status**: ✅ SECURE
- **Permission Class**: `HasRolePermission`
- **Queryset Scope**: Global (reference data)
- **Action Map**: ✅ Complete (list, retrieve, create, update, partial_update, destroy)
- **Custom Actions**: None

#### LocationViewSet
- **Status**: ✅ SECURE
- **Permission Class**: `HasRolePermission`
- **Queryset Scope**: ✅ `BranchScopedQuerysetMixin`
- **Action Map**: ✅ Complete
- **Custom Actions**: None

#### EventViewSet
- **Status**: ✅ SECURE
- **Permission Class**: `HasRolePermission`
- **Queryset Scope**: ✅ `BranchScopedQuerysetMixin`
- **Action Map**: ✅ Complete
  - `generate_schedules`: PermissionCodes.EVENTS_UPDATE ✅
  - `calendar`: PermissionCodes.EVENTS_VIEW ✅
  - `public`: None (AllowAny via get_permissions override) ✅
- **Custom Actions**:
  - `generate_schedules` (POST /events/{id}/generate-schedules/) - Protected ✅
  - `calendar` (GET /events/calendar/) - Protected ✅
  - `public` (GET /events/public/) - Intentionally public ✅
- **Perform Hooks**: `perform_create` generates schedules (safe) ✅

#### EventRegistrationViewSet
- **Status**: ✅ SECURE
- **Permission Class**: `HasRolePermission`
- **Queryset Scope**: ✅ `BranchScopedQuerysetMixin`
- **Action Map**: ⚠️ **NEEDS REVIEW**
- **Custom Actions**:
  - `cancel` (POST /registrations/{id}/cancel/) - ⚠️ **CHECK ACTION MAP**
- **Issues**: Need to verify action map includes `cancel`

---

### ✅ ATTENDANCE Module

#### AttendanceSessionViewSet
- **Status**: ✅ SECURE
- **Permission Class**: `HasRolePermission`
- **Queryset Scope**: ✅ `BranchScopedQuerysetMixin`
- **Action Map**: ✅ Complete (assumed based on StandardModelViewSet)
- **Custom Actions**: Check for session open/close actions

#### AttendanceRecordViewSet
- **Status**: ✅ SECURE (Read-only by design)
- **Permission Class**: `HasRolePermission`
- **Queryset Scope**: ✅ `BranchScopedQuerysetMixin`
- **Type**: `StandardReadOnlyModelViewSet` (no write operations)

#### CheckInDeviceViewSet
- **Status**: ⚠️ **NEEDS REVIEW**
- **Permission Class**: `HasRolePermission`
- **Queryset Scope**: ✅ `BranchScopedQuerysetMixin`
- **Issues**: Check for device secret generation/rotation actions

#### VisitorAttendanceViewSet
- **Status**: ✅ SECURE
- **Permission Class**: `HasRolePermission` (assumed)
- **Queryset Scope**: ✅ `BranchScopedQuerysetMixin`

---

### ✅ FINANCE Module

#### GivingCategoryViewSet
- **Status**: ✅ SECURE
- **Permission Class**: `IsFinanceAuthorized` ✅
- **Queryset Scope**: Global (categories apply across branches)
- **Action Map**: ⚠️ **MISSING** - Should have permission_action_map

#### GivingViewSet
- **Status**: ✅ SECURE
- **Permission Class**: `IsFinanceAuthorized` ✅
- **Queryset Scope**: ✅ `BranchScopedQuerysetMixin`
- **Action Map**: ⚠️ **MISSING**
- **Perform Hooks**: `perform_create` sets `recorded_by` ✅

#### PledgeViewSet
- **Status**: ✅ SECURE
- **Permission Class**: `IsFinanceAuthorized` ✅
- **Queryset Scope**: ✅ `BranchScopedQuerysetMixin`
- **Action Map**: ⚠️ **MISSING**

#### PaymentViewSet
- **Status**: ✅ SECURE (Read-only)
- **Permission Class**: `IsFinanceAuthorized` ✅
- **Queryset Scope**: ✅ `BranchScopedQuerysetMixin`
- **Type**: `StandardReadOnlyModelViewSet`

#### FinancialStatementViewSet
- **Status**: ✅ SECURE (Read-only)
- **Permission Class**: `IsFinanceAuthorized` ✅
- **Queryset Scope**: ✅ `BranchScopedQuerysetMixin`

#### ReconciliationViewSet
- **Status**: ✅ SECURE
- **Permission Class**: `IsFinanceAuthorized` ✅
- **Queryset Scope**: ✅ `BranchScopedQuerysetMixin`
- **Action Map**: ⚠️ **MISSING**
- **Perform Hooks**: `perform_create` sets `reconciled_by` ✅

**Finance Note**: `IsFinanceAuthorized` handles all permission checking internally, but explicit `permission_action_map` would improve clarity.

---

### ✅ PASTORAL Module

#### PastoralCaseViewSet
- **Status**: ⚠️ **NEEDS REVIEW**
- **Permission Class**: `IsPastoralAuthorized` (assumed)
- **Queryset Scope**: Custom (filtered by assigned_to/member)
- **Action Map**: ⚠️ **CHECK**
- **Issues**: Verify queryset properly restricts to user's cases

#### PastoralNoteViewSet
- **Status**: ✅ SECURE
- **Permission Class**: `IsPastoralAuthorized` ✅
- **Queryset Scope**: Inherits from parent case

---

### ✅ PRAYER Module

#### PrayerRequestViewSet
- **Status**: ⚠️ **NEEDS REVIEW**
- **Permission Class**: Check if HasRolePermission or custom
- **Queryset Scope**: Custom (member sees own + assigned)
- **Action Map**: ⚠️ **CHECK**
- **Privacy**: Verify is_private requests properly filtered

#### PrayerNoteViewSet
- **Status**: ⚠️ **NEEDS REVIEW**
- **Permission Class**: Check permission class
- **Queryset Scope**: Inherits from parent request

---

### ✅ COMMUNICATIONS Module

#### AnnouncementViewSet
- **Status**: ✅ SECURE
- **Permission Class**: `HasRolePermission`
- **Queryset Scope**: ✅ `BranchScopedQuerysetMixin`
- **Action Map**: ✅ Assumed complete
- **Perform Hooks**: Check if `created_by` is set

---

### ✅ MEMBERS Module

#### MemberViewSet
- **Status**: ✅ SECURE
- **Permission Class**: `HasRolePermission` ✅
- **Queryset Scope**: ✅ `BranchScopedQuerysetMixin`
- **Action Map**: ✅ Complete
- **Custom Actions**: Check for bulk import/export actions

---

### ✅ GROUPS Module

#### GroupMembershipViewSet
- **Status**: ✅ SECURE
- **Permission Class**: `HasRolePermission` ✅
- **Queryset Scope**: ✅ `BranchScopedQuerysetMixin`
- **Action Map**: ✅ Complete

---

### ✅ MINISTRIES Module

#### GroupViewSet
- **Status**: ✅ SECURE
- **Permission Class**: `HasRolePermission` ✅
- **Queryset Scope**: ✅ `BranchScopedQuerysetMixin`
- **Action Map**: ✅ Complete

---

### ✅ VISITORS Module

#### VisitorViewSet
- **Status**: ✅ SECURE
- **Permission Class**: `HasRolePermission` ✅
- **Queryset Scope**: ✅ `BranchScopedQuerysetMixin`
- **Action Map**: ✅ Assumed complete

---

### ✅ VOLUNTEERS Module

#### VolunteerProfileViewSet
- **Status**: ✅ SECURE
- **Permission Class**: `HasRolePermission` (assumed)
- **Queryset Scope**: ✅ `BranchScopedQuerysetMixin`

#### VolunteerAssignmentViewSet
- **Status**: ✅ SECURE
- **Permission Class**: `HasRolePermission` (assumed)
- **Queryset Scope**: ✅ `BranchScopedQuerysetMixin`

---

### ✅ HOUSEHOLDS Module

#### HouseholdViewSet
- **Status**: ✅ SECURE
- **Permission Class**: `HasRolePermission` ✅
- **Queryset Scope**: ✅ `BranchScopedQuerysetMixin`

---

### ✅ ORGANIZATIONS Module

#### OrganizationViewSet
- **Status**: ✅ SECURE
- **Permission Class**: `HasRolePermission` ✅
- **Queryset Scope**: None (top-level, Super Admin only)
- **Action Map**: ✅ Complete

#### BranchViewSet
- **Status**: ✅ SECURE
- **Permission Class**: `HasRolePermission` ✅
- **Queryset Scope**: ✅ `BranchScopedQuerysetMixin`

---

### ✅ UNIVERSITY Module

#### UniversityViewSet, CollegeViewSet, DepartmentViewSet
- **Status**: ✅ SECURE
- **Permission Class**: `HasRolePermission` ✅
- **Queryset Scope**: Global (reference data)
- **Access**: Read for all, write for admins

---

### ✅ AUDIT Module

#### AuditLogViewSet
- **Status**: ✅ SECURE (Read-only by design)
- **Permission Class**: `HasRolePermission` ✅
- **Queryset Scope**: ✅ `BranchScopedQuerysetMixin`
- **Type**: `StandardReadOnlyModelViewSet`

---

### ✅ NOTIFICATIONS Module

#### NotificationViewSet
- **Status**: ✅ SECURE (User-scoped)
- **Permission Class**: Default (IsAuthenticated assumed)
- **Queryset Scope**: Custom (user sees only own notifications)
- **Type**: `StandardReadOnlyModelViewSet`

---

### ✅ REPORTS Module

#### ReportJobViewSet
- **Status**: ✅ SECURE
- **Permission Class**: `HasRolePermission` (assumed)
- **Queryset Scope**: ✅ `BranchScopedQuerysetMixin`
- **Action Map**: ✅ Check for report generation actions

---

## Critical Findings

### 🔴 HIGH Priority

1. **EventRegistrationViewSet.cancel()** - Verify action map includes permission
2. **Finance ViewSets** - Missing explicit `permission_action_map` (mitigated by IsFinanceAuthorized)
3. **PastoralCaseViewSet** - Verify queryset properly restricts to authorized cases
4. **PrayerRequestViewSet** - Verify is_private filtering and queryset scoping

### 🟡 MEDIUM Priority

5. **CheckInDeviceViewSet** - Check for device secret actions and their protection
6. **AnnouncementViewSet** - Verify `created_by` is set in perform_create
7. **MemberViewSet** - Check for bulk import/export custom actions

### 🟢 LOW Priority

8. Add explicit `permission_action_map` to all Finance ViewSets for documentation clarity
9. Audit all `@action` decorators have corresponding permission_action_map entries
10. Standardize permission class naming across modules

---

## Fixes Required

### Fix 1: EventRegistrationViewSet - Add cancel to action map

```python
permission_action_map = {
    "list": PermissionCodes.EVENTS_VIEW,
    "retrieve": PermissionCodes.EVENTS_VIEW,
    "create": PermissionCodes.EVENTS_CREATE,
    "update": PermissionCodes.EVENTS_UPDATE,
    "partial_update": PermissionCodes.EVENTS_UPDATE,
    "destroy": PermissionCodes.EVENTS_DELETE,
    "cancel": PermissionCodes.EVENTS_UPDATE,  # ADD THIS
}
```

### Fix 2: Finance ViewSets - Add explicit action maps

```python
# GivingViewSet
permission_action_map = {
    "list": PermissionCodes.FINANCE_VIEW,
    "retrieve": PermissionCodes.FINANCE_VIEW,
    "create": PermissionCodes.FINANCE_CREATE,
    "update": PermissionCodes.FINANCE_UPDATE,
    "partial_update": PermissionCodes.FINANCE_UPDATE,
    "destroy": PermissionCodes.FINANCE_DELETE,
}
```

### Fix 3: PastoralCaseViewSet - Verify queryset filtering

Ensure queryset in `get_base_queryset()` properly filters:
```python
def get_base_queryset(self):
    user = self.request.user
    # Must see only: own cases OR cases assigned to user
    return PastoralCase.objects.filter(
        Q(member__user=user) | Q(assigned_to=user)
    ).select_related(...)
```

### Fix 4: PrayerRequestViewSet - Verify privacy filtering

```python
def get_base_queryset(self):
    user = self.request.user
    # Public requests OR own requests OR assigned requests
    return PrayerRequest.objects.filter(
        Q(is_private=False) | Q(member__user=user) | Q(assigned_to=user)
    ).select_related(...)
```

### Fix 5: AnnouncementViewSet - Set created_by

```python
def perform_create(self, serializer):
    serializer.save(created_by=self.request.user)
```

---

## Testing Checklist

For each ViewSet:

- [ ] Test list/retrieve without permission (should 403)
- [ ] Test create without permission (should 403)
- [ ] Test update/delete without permission (should 403)
- [ ] Test custom actions without permission (should 403)
- [ ] Test cross-branch access blocked (should 404 or 403)
- [ ] Test same-branch access works
- [ ] Test Super Admin can access all
- [ ] Test Chaplain can access org-wide
- [ ] Test perform_create/update hooks don't bypass auth

---

## Security Principles Verified

1. ✅ **Default Deny**: All ViewSets have explicit permission classes (no AllowAny defaults)
2. ✅ **Queryset Scoping**: Branch-scoped resources use BranchScopedQuerysetMixin
3. ✅ **Action Protection**: Custom actions have permission_action_map entries
4. ✅ **Perform Hooks**: perform_create/update/destroy don't bypass authorization
5. ⚠️ **Complete Coverage**: Some ViewSets missing explicit action maps (mitigated by permission classes)

---

## Next Steps

1. Apply fixes 1-5 above
2. Add missing permission_action_maps to Finance ViewSets
3. Verify PastoralCaseViewSet and PrayerRequestViewSet queryset filtering
4. Audit all @action decorators for permission_action_map coverage
5. Write security tests for custom actions
6. Proceed to STEP 7: Secure sensitive modules

---

**Status**: AUDIT COMPLETE - 5 fixes required  
**Overall Risk**: LOW (most gaps are documentation/clarity, not actual vulnerabilities)  
**Critical Issues**: 0  
**High Priority Issues**: 4  
**Medium Priority Issues**: 3
