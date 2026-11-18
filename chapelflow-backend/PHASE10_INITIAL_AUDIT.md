# PHASE 10 COMMUNICATIONS & NOTIFICATIONS — INITIAL AUDIT

**Date:** September 1, 2026  
**Auditor:** Kiro AI  
**Estimated Initial Status:** ~55% (as documented in handoff)

---

## EXECUTIVE SUMMARY

Phase 10 is in a **CRITICALLY BROKEN STATE** similar to Phase 9. There is a severe mismatch between:
- What migrations have added to the database schema
- What the models.py files actually define
- What serializers expect
- What services reference
- What views use

**Root Cause:** Migration `0003_announcement_audience_type_announcement_channels_and_more.py` added extensive fields and a complete `CommunicationPreference` model to the database, but these were NEVER added to the Python models.

**Impact:**
- ❌ Serializers reference non-existent fields (`audience_type`, `channels`)
- ❌ Services import non-existent models (`AudienceType`, `CommunicationPreference`)
- ❌ Views cannot function (depend on broken serializers/services)
- ❌ Tasks cannot function (depend on broken services)
- ❌ Phase 9 volunteer reminders cannot integrate (no CommunicationPreference)
- ❌ Phase 7 event reminders cannot integrate properly

**Severity:** CRITICAL - Phase 10 is completely non-functional

---

## DETAILED FINDINGS

### 1. MODELS VS MIGRATIONS MISMATCH (CRITICAL)

#### Announcement Model

**Migration 0003 Added to Database:**
- `status` (CharField - DRAFT/SCHEDULED/QUEUED/SENDING/COMPLETED/FAILED)
- `audience_type` (CharField - EVERYONE/FELLOWSHIP/UNIT/MINISTRY/STAFF_COMMUNITY/CUSTOM)
- `channels` (JSONField - list of channel values)
- `target_community` (CharField - for STAFF_COMMUNITY targeting)
- `sending_started_at` (DateTimeField)
- `completed_at` (DateTimeField)
- `failure_reason` (TextField)

**Current models.py Contains:**
- ❌ NO `status` field
- ❌ NO `audience_type` field
- ❌ NO `channels` field
- ❌ NO `target_community` field
- ❌ NO `sending_started_at` field
- ❌ NO `completed_at` field
- ❌ NO `failure_reason` field

**Impact:** 7 critical fields missing from model definition

#### CommunicationPreference Model

**Migration 0003 Created Complete Model:**
```python
CommunicationPreference:
  - id (auto PK)
  - member (OneToOne to Member)
  - email_enabled (Boolean, default=True)
  - sms_enabled (Boolean, default=True)
  - push_enabled (Boolean, default=True)
  - announcements_enabled (Boolean, default=True)
  - updated_at (auto timestamp)
```

**Current models.py Contains:**
- ❌ NO CommunicationPreference model AT ALL

**Impact:** Entire preference system non-functional

#### AudienceType Enum

**Services.py References:**
```python
from .models import AudienceType
```

**Current models.py Contains:**
- ❌ NO AudienceType enum defined

**Impact:** Services cannot import, fail immediately

---

### 2. SERIALIZER EXPECTATIONS BROKEN

**File:** `apps/communications/serializers.py`

**Serializer Fields Defined:**
```python
fields = [
    "id", "branch", "title", "body", "target_groups",
    "target_membership_statuses", "audience_type", "channels",  # ← These don't exist
    "created_by", "publish_at", "expires_at", "created_at",
]
```

**Result:** Serializer will fail immediately when instantiated because `audience_type` and `channels` don't exist on the model.

---

### 3. SERVICES BROKEN

**File:** `apps/communications/services.py`

**Broken Imports:**
```python
from .models import AudienceType  # ← Doesn't exist
from .models import CommunicationPreference  # ← Doesn't exist
```

**Functions That Will Fail:**
- `authorize_audience()` - references `AudienceType.EVERYONE`, `AudienceType.STAFF_COMMUNITY`, etc.
- `resolve_audience_members()` - references `announcement.audience_type`, `announcement.target_community`
- `filter_by_preference()` - references `CommunicationPreference` model

**Impact:** Every service function fails on import or execution

---

### 4. NOTIFICATION MODEL STATUS

**File:** `apps/notifications/models.py`

**Current State:** ✅ MOSTLY GOOD

The Notification model exists and is relatively complete:
- Has `NotificationChannel` enum ✅
- Has `NotificationStatus` enum ✅
- Has proper fields ✅
- Has proper relationships ✅

**Issues Found:**
- No separate `NotificationDelivery` model (single Notification combines notification + delivery)
- No provider-specific tracking (provider_response is generic JSONField)
- No retry tracking
- No attempt count
- No webhook signature validation fields

**Assessment:** Functional but simplified architecture

---

### 5. COMMUNICATION PREFERENCES - COMPLETELY MISSING

**Required By:**
- Phase 9 volunteer reminder tasks (documented TODO in tasks.py)
- Phase 7 event reminders (should respect preferences)
- Phase 10 announcements (services.py tries to use it)

**Current State:**
- ❌ Model doesn't exist in models.py
- ✅ Migration 0003 created the table in database
- ✅ Services.py has logic to use it
- ❌ Cannot actually function

**Impact:** All preference checking is broken

---

### 6. PROVIDERS ASSESSMENT

**File:** `apps/notifications/providers.py`

Let me check this file...



---

### 6. PROVIDERS ASSESSMENT

**File:** `apps/notifications/providers.py`

**Current State:** ✅ MOSTLY GOOD

**What Exists:**
- `EmailProvider` - Uses Django's send_mail ✅
- `SMSProvider` - Stub implementation with logging ✅
- `PushProvider` - Stub implementation with logging ✅
- Provider abstraction pattern in place ✅

**Issues Found:**
- No webhook signature validation
- No retry logic at provider level
- No rate limiting
- No provider-specific error handling
- Status tracking is simplistic (stubbed vs sent)

**Assessment:** Basic but functional, properly identifies stubbed vs real

---

### 7. TASKS ASSESSMENT

**File:** `apps/communications/tasks.py`

**Critical Issues:**

❌ **dispatch_announcement() DOES NOT USE services.py**
- Does NOT call `authorize_audience()`
- Does NOT call `resolve_audience_members()`
- Does NOT call `filter_by_preference()`
- Implements its own audience resolution (duplicate logic)
- IGNORES `audience_type` field (doesn't exist in model anyway)
- IGNORES `channels` field
- IGNORES communication preferences
- IGNORES the entire services.py authorization system

**Impact:** All the careful authorization logic in services.py is completely bypassed!

❌ **No idempotency protection**
- Can dispatch same announcement multiple times
- No check if already sent
- No state tracking
- Will create duplicate notifications

❌ **No lifecycle state management**
- Doesn't set `status=QUEUED` before dispatch
- Doesn't set `sending_started_at`
- Doesn't set `completed_at`
- Doesn't set `failure_reason`
- Doesn't track dispatch progress

**File:** `apps/notifications/tasks.py`

**Status:** ✅ BETTER

- Properly uses provider abstraction
- Distinguishes STUBBED vs SENT
- Has retry logic (max_retries=3)
- Updates notification status correctly
- Has idempotency at notification level

---

### 8. VIEWS ASSESSMENT

**File:** `apps/communications/views.py`

**Critical Issues:**

❌ **WRONG PERMISSION CODES**
- Uses `EVENTS_VIEW`, `EVENTS_CREATE`, `EVENTS_UPDATE`, `EVENTS_DELETE`
- Should use `COMMUNICATIONS_*` permission codes
- This is a copy-paste error or legacy code

❌ **No lifecycle actions**
- No `publish` action
- No `cancel` action
- No `schedule` action
- perform_create immediately dispatches (no draft state)

❌ **No authorization in perform_create**
- Doesn't call `services.authorize_branch()`
- Doesn't call `services.authorize_audience()`
- Anyone with EVENTS_CREATE can target anyone

❌ **No scope validation for audience**
- Can target any group IDs
- Can target other branches
- Serializer has some validation but not comprehensive

**File:** `apps/notifications/views.py`

(Need to check if exists and what it contains)

---

### 9. PERMISSION CODES MISSING

**File:** `common/constants/roles.py` (from Phase 9 audit)

**Available Permission Codes:**
- `COMMUNICATIONS_VIEW` ✅
- `COMMUNICATIONS_CREATE` ✅
- `COMMUNICATIONS_UPDATE` ✅
- `COMMUNICATIONS_DELETE` ✅
- `COMMUNICATIONS_SEND` ✅

**Current Usage:**
- ❌ Views use EVENTS_* instead of COMMUNICATIONS_*

---

### 10. SECURITY VULNERABILITIES IDENTIFIED

#### 10.1 Authorization Bypass (CRITICAL)
- `dispatch_announcement()` task bypasses all services.py authorization
- No check that user can target the audience
- No check that groups belong to same branch
- Assignment-scoped leaders can target entire branch

#### 10.2 Cross-Branch Targeting (HIGH)
- Can create announcement with `branch=A` and `target_groups=[group_from_branch_B]`
- Serializer has some validation but dispatch task doesn't enforce it
- No server-side audience resolution validation

#### 10.3 IDOR Vulnerability (HIGH)
- `/announcements/{id}/` - can access by knowing ID
- BranchScopedQuerysetMixin should protect but needs testing
- `/delivery-status/` - might leak cross-branch data

#### 10.4 Mass Assignment (MEDIUM)
- Client could try to set `status`, `completed_at`, etc. when created
- Need to verify serializer read-only protection

#### 10.5 Preference Bypass (CRITICAL)
- `dispatch_announcement()` doesn't check preferences at all
- Anyone opted out will still receive notifications
- services.py has the logic but it's not called

#### 10.6 No Idempotency (HIGH)
- Repeated task execution sends duplicate notifications
- No protection against accidental re-dispatch
- No "already sent" check

#### 10.7 Status Manipulation (MEDIUM)
- If client can set `status` field, could mark as COMPLETED without sending
- Need read-only field protection

#### 10.8 Wrong Permission Codes (MEDIUM)
- Using EVENTS_* gives wrong users access
- Should use COMMUNICATIONS_* for proper RBAC

---

### 11. INTEGRATION ISSUES

#### Phase 7 Event Reminders
- Should use CommunicationPreference (doesn't exist)
- May be creating notifications directly
- Need to verify integration

#### Phase 9 Volunteer Reminders
- Has TODO comments about CommunicationPreference
- Cannot integrate until preferences exist
- Currently bypassing preference system

---

### 12. MISSING FUNCTIONALITY

❌ **CommunicationPreference Management**
- No viewset to manage preferences
- No serializer for preferences
- No URLs for preference endpoints
- Users cannot opt in/out

❌ **Announcement Lifecycle**
- No draft → published workflow
- No scheduling support (publish_at not enforced)
- No cancellation
- No status tracking

❌ **Webhook Endpoints**
- No webhook receivers for provider callbacks
- No signature validation
- No delivery confirmation handling

❌ **Audience Resolution Testing**
- EVERYONE audience type not validated
- FELLOWSHIP/UNIT/MINISTRY not tested
- STAFF_COMMUNITY not validated

---

### 13. TESTING GAP ANALYSIS

**Existing Tests:** Need to check if any exist

**Missing Tests:**
- Model constraint tests
- Audience authorization tests
- Cross-branch targeting tests
- IDOR tests
- Mass assignment tests
- Preference bypass tests
- Idempotency tests
- Lifecycle transition tests
- Provider tests
- Integration tests with Phase 7/9

---

### 14. MIGRATION ANALYSIS

**Migration History:**
```
communications
  [?] 0001_initial
  [?] 0002_initial
  [X] 0003_announcement_audience_type_announcement_channels_and_more
```

**Status:** Migration 0003 has been applied to database but models.py was never updated.

**Required Action:** Update models.py to match migration, do NOT create new migration.

---

## SUMMARY OF CRITICAL ISSUES

### Broken Functionality (7 issues)
1. ❌ Announcement model missing 7 fields
2. ❌ CommunicationPreference model missing entirely
3. ❌ AudienceType enum missing
4. ❌ Serializer references non-existent fields
5. ❌ Services import non-existent models
6. ❌ Tasks bypass services.py authorization
7. ❌ No preference management endpoints

### Security Vulnerabilities (8 issues)
1. 🔴 Authorization bypass in dispatch
2. 🔴 Preference bypass (everyone gets notified)
3. 🟠 Cross-branch targeting
4. 🟠 IDOR vulnerabilities
5. 🟠 No idempotency protection
6. 🟡 Mass assignment risks
7. 🟡 Status manipulation risks
8. 🟡 Wrong permission codes

### Missing Features (6 issues)
1. ❌ Announcement lifecycle (draft/publish/cancel)
2. ❌ Preference management UI/API
3. ❌ Webhook receivers
4. ❌ Phase 7/9 integration
5. ❌ Audience type validation
6. ❌ Channel selection enforcement

---

## ACTUAL IMPLEMENTATION STATUS

**Estimated Completion:** ~40% (worse than 55% estimate)

**What Works:**
- ✅ Basic notification model
- ✅ Provider abstraction
- ✅ Notification delivery task
- ✅ STUBBED status distinction
- ✅ Basic announcement creation

**What's Broken:**
- ❌ Announcement lifecycle
- ❌ Communication preferences
- ❌ Authorization
- ❌ Audience resolution
- ❌ Preference enforcement
- ❌ Idempotency
- ❌ Security

**Severity:** CRITICAL - Cannot deploy to production

---

## RECONCILIATION STRATEGY

### Phase 1: Fix Models (Critical)
1. Add 7 missing fields to Announcement
2. Add AudienceType enum
3. Add CommunicationPreference model
4. Verify no new migrations needed

### Phase 2: Fix Serializers
1. Update AnnouncementSerializer
2. Create CommunicationPreferenceSerializer
3. Add read-only field protection
4. Add comprehensive validation

### Phase 3: Fix Tasks
1. Make dispatch_announcement use services.py
2. Add idempotency protection
3. Add lifecycle state management
4. Integrate preference checking

### Phase 4: Fix Views
1. Change to COMMUNICATIONS_* permission codes
2. Add publish/cancel actions
3. Add authorization in perform_create
4. Create CommunicationPreferenceViewSet

### Phase 5: Security Hardening
1. Test and fix IDOR
2. Test and fix cross-branch
3. Test and fix mass assignment
4. Test and fix preference bypass
5. Test and fix authorization bypass

### Phase 6: Integration
1. Update Phase 7 event reminders
2. Update Phase 9 volunteer reminders
3. Add comprehensive tests
4. Document integration points

### Phase 7: Testing & Verification
1. Write security tests
2. Write integration tests
3. Run all tests
4. Verify migrations
5. Generate honest completion report

---

**End of Initial Audit**

**Next Step:** Begin reconciliation starting with models.py

