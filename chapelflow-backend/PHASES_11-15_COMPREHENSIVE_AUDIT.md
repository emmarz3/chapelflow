# PHASES 11-15 COMPREHENSIVE AUDIT

**Date:** September 1, 2026  
**Scope:** Member Engagement, Giving & Finance, Prayer & Pastoral Care, Finance Reconciliation, Reporting & Export  
**Method:** Source Code Analysis (Following Master Implementation Prompt)

---

## EXECUTIVE SUMMARY

**Audit Principle:** "Actual source code is the source of truth"

This audit inspects existing models, services, views, tasks, and integrations for Phases 11-15 to determine:
1. What IS working
2. What is PARTIALLY implemented
3. What is MISSING
4. What needs SECURITY hardening
5. What needs TESTING

**Critical Finding:** Architecture for all 5 phases EXISTS but with varying completion levels.

---

## GLOBAL DEPENDENCY MAP

### Core Entities (Phases 1-10)
```
User (accounts)
   ├── Member (members)
   │   ├── Branch (organizations)
   │   ├── Fellowship/Unit/Ministry (ministries.Group)
   │   ├── College/Department (university)
   │   └── Household (households)
   ├── Event (events)
   ├── Attendance (attendance)
   ├── Volunteer Assignment (volunteers)
   ├── Announcement (communications)
   └── Notification (notifications)
```

### Phase 11-15 Entities
```
PHASE 11 (Engagement & Follow-Up)
   ├── Visitor (visitors)
   ├── VisitorFollowUp (visitors)
   └── [MISSING] MemberFollowUp
   └── [MISSING] EngagementMetrics
   └── [MISSING] AttendanceFollowUp
   └── [MISSING] InactiveDetection

PHASE 12 (Giving & Finance)
   ├── Giving (finance) ✅
   ├── Payment (finance) ✅
   ├── Pledge (finance) ✅
   ├── GivingCategory (finance) ✅
   ├── Refund (finance) ✅
   └── [PARTIAL] Webhook security

PHASE 13 (Prayer & Pastoral)
   ├── PrayerRequest (prayer) ✅
   ├── PrayerNote (prayer) ✅
   ├── PastoralCase (pastoral) ✅
   ├── PastoralNote (pastoral) ✅
   └── [NEEDS] Privacy enforcement testing

PHASE 14 (Reconciliation)
   ├── Reconciliation (finance) ✅
   ├── FinancialStatement (finance) ✅
   └── [MISSING] Automated reconciliation logic
   └── [MISSING] Mismatch detection
   └── [MISSING] Gateway transaction matching

PHASE 15 (Reporting)
   ├── ReportJob (reports) ✅
   └── [MISSING] Report generators
   └── [MISSING] Export formats (CSV/XLSX/PDF)
   └── [MISSING] Filter security
```

---

## PHASE 11 — MEMBER ENGAGEMENT & FOLLOW-UP

### Current Status: **~30% Complete**

### What EXISTS ✅

#### Visitor Follow-Up (Partial)
**File:** `apps/visitors/models.py`

```python
class Visitor(models.Model):
    # ✅ Core visitor tracking
    # ✅ Status pipeline: NEW → CONTACTED → FOLLOWED_UP → REGISTERED → LAPSED
    # ✅ Conversion tracking (converted_member, converted_at)
    status = models.CharField(choices=VisitorStatus.choices)
    converted_member = models.OneToOneField("members.Member")
    converted_at = models.DateTimeField(null=True)

class VisitorFollowUp(models.Model):
    # ✅ Follow-up tracking
    # ✅ Assignment (assigned_to)
    # ✅ Multiple methods (CALL, SMS, EMAIL, VISIT, WHATSAPP)
    # ✅ Outcomes (PENDING, REACHED, NO_RESPONSE, NOT_INTERESTED)
    # ✅ Reminder tracking (reminder_sent_at for idempotency)
    visitor = models.ForeignKey(Visitor)
    assigned_to = models.ForeignKey(User)
    method = models.CharField(choices=Method.choices)
    outcome = models.CharField(choices=Outcome.choices)
    scheduled_for = models.DateTimeField(null=True)
    completed_at = models.DateTimeField(null=True)
    reminder_sent_at = models.DateTimeField(null=True)  # ✅ Idempotency
```

**Status:** Visitor follow-up architecture is GOOD. Models are well-designed.

---

### What is MISSING ❌

#### 1. ❌ New Member Follow-Up (CRITICAL)
**Requirement:** 7-day, 30-day, 90-day follow-up for new members

**Missing:**
- No `MemberFollowUp` model
- No follow-up task model for members
- No automatic task generation on member creation
- No periodic task to trigger follow-ups
- No new member onboarding workflow

**Implementation Needed:**
```python
# apps/members/models.py or separate engagement app

class MemberFollowUp(models.Model):
    """
    Follow-up tasks for new members (7/30/90 day milestones)
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    member = models.ForeignKey("members.Member", on_delete=models.CASCADE)
    milestone = models.CharField(
        choices=[
            ('DAY_7', '7-Day Follow-Up'),
            ('DAY_30', '30-Day Follow-Up'),
            ('DAY_90', '90-Day Follow-Up'),
        ]
    )
    assigned_to = models.ForeignKey(User, null=True, on_delete=models.SET_NULL)
    scheduled_for = models.DateTimeField()
    completed_at = models.DateTimeField(null=True)
    notes = models.TextField(blank=True)
    reminder_sent_at = models.DateTimeField(null=True)  # Idempotency
    created_at = models.DateTimeField(auto_now_add=True)
```

#### 2. ❌ Attendance Follow-Up (CRITICAL)
**Requirement:** Flag repeated absence, generate follow-up tasks

**Missing:**
- No absence detection logic
- No configurable threshold
- No follow-up task generation on absence
- No attendance-triggered workflow

**Implementation Needed:**
```python
# apps/attendance/services.py

def detect_repeated_absence(member, threshold_weeks=3):
    """
    Check if member has been absent for threshold_weeks.
    Generate follow-up task if needed.
    """
    from django.utils import timezone
    from datetime import timedelta
    
    cutoff = timezone.now() - timedelta(weeks=threshold_weeks)
    
    recent_attendance = Attendance.objects.filter(
        member=member,
        created_at__gte=cutoff
    ).exists()
    
    if not recent_attendance:
        # Create follow-up task
        create_attendance_follow_up(member)

# Periodic Celery task
@shared_task
def check_attendance_absences():
    """
    Run weekly: detect members with repeated absence
    """
    threshold = getattr(settings, 'ABSENCE_THRESHOLD_WEEKS', 3)
    # ... implementation
```

#### 3. ❌ Engagement Tracking (CRITICAL)
**Requirement:** Track participation in services, events, fellowships, volunteering

**Missing:**
- No `EngagementMetrics` model
- No engagement scoring
- No participation aggregation
- No engagement history

**Design Decision Needed:**
- **Calculated dynamically** vs **materialized view** vs **periodic update**
- Recommend: Materialized with periodic update (performance)

**Implementation Needed:**
```python
# apps/members/models.py or engagement app

class EngagementMetrics(models.Model):
    """
    Materialized engagement metrics per member.
    Updated periodically via Celery task.
    """
    member = models.OneToOneField("members.Member", on_delete=models.CASCADE)
    
    # Attendance metrics
    total_services_attended = models.IntegerField(default=0)
    last_service_date = models.DateField(null=True)
    attendance_rate_30d = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    
    # Event participation
    total_events_attended = models.IntegerField(default=0)
    last_event_date = models.DateField(null=True)
    
    # Volunteering
    total_volunteer_assignments = models.IntegerField(default=0)
    active_volunteer = models.BooleanField(default=False)
    
    # Fellowship participation
    fellowship_attendance_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    
    # Giving (optional - privacy concern)
    total_giving_count = models.IntegerField(default=0)
    last_giving_date = models.DateField(null=True)
    
    # Overall engagement score (0-100)
    engagement_score = models.IntegerField(default=0)
    
    last_calculated_at = models.DateTimeField(auto_now=True)
```

#### 4. ❌ Inactive Member Detection (HIGH)
**Requirement:** Detect inactive members, configurable inactivity period

**Missing:**
- No inactive member detection
- No configurable period
- No flag/status update
- No notification to pastoral team

**Implementation Needed:**
```python
# apps/members/services.py

def detect_inactive_members(branch, inactivity_days=90):
    """
    Find members with no activity for inactivity_days.
    Activity = attendance, events, volunteering, giving.
    """
    from django.utils import timezone
    from datetime import timedelta
    
    cutoff = timezone.now() - timedelta(days=inactivity_days)
    
    # Query members with no recent activity
    inactive = Member.objects.filter(
        branch=branch,
        membership_status=MembershipStatus.ACTIVE
    ).exclude(
        # Has recent attendance
        attendance_records__created_at__gte=cutoff
    ).exclude(
        # Has recent event registration
        event_registrations__created_at__gte=cutoff
    ).exclude(
        # Has recent volunteer assignment
        volunteer_profile__assignments__created_at__gte=cutoff
    ).distinct()
    
    return inactive

# Celery task
@shared_task
def flag_inactive_members():
    """
    Monthly task: detect inactive members and notify pastoral team
    """
    # ... implementation
```

---

### Security Assessment: Phase 11

#### ✅ What's Secure
1. Visitor follow-up has `branch` FK (branch scoping)
2. `assigned_to` authorization can be enforced via views
3. `reminder_sent_at` provides idempotency

#### ❌ What Needs Security
1. **Authorization on assignment** - Who can assign follow-ups?
2. **Cross-branch access** - Prevent Branch A accessing Branch B visitors
3. **IDOR protection** - Direct ID access must be prevented
4. **Follow-up privacy** - Sensitive notes must be protected

---

### Testing Needs: Phase 11

**Unit Tests:**
- [ ] Visitor follow-up creation
- [ ] Assignment logic
- [ ] Status transitions
- [ ] Conversion tracking
- [ ] New member follow-up generation (when implemented)
- [ ] Attendance absence detection (when implemented)
- [ ] Engagement scoring (when implemented)
- [ ] Inactive detection (when implemented)

**Security Tests:**
- [ ] IDOR (visitor ID, follow-up ID)
- [ ] Cross-branch access
- [ ] Unauthorized assignment
- [ ] Mass assignment protection
- [ ] Follow-up note privacy

**Integration Tests:**
- [ ] Visitor → Member conversion
- [ ] Follow-up reminder task idempotency
- [ ] Celery task execution
- [ ] Notification integration (Phase 10)

---

## PHASE 12 — GIVING & FINANCE

### Current Status: **~70% Complete**

### What EXISTS ✅

#### Core Models (Well-Designed)
**File:** `apps/finance/models.py`

```python
class Giving(models.Model):
    # ✅ Comprehensive giving model
    # ✅ Decimal fields (not float!) ✅
    # ✅ Status (CONFIRMED/VOIDED) for immutability
    # ✅ Multiple sources (ONLINE/OFFLINE/BANK_TRANSFER/CHECK)
    # ✅ Category FK (tithe, offering, building, etc.)
    # ✅ Event/Group optional FK (Phase 5/6 integration)
    # ✅ Payment OneToOne (online giving)
    # ✅ Check constraint (amount > 0) ✅
    amount = models.DecimalField(max_digits=14, decimal_places=2)  # ✅ SAFE
    status = models.CharField(choices=GivingStatus.choices)
    payment = models.OneToOneField("Payment", null=True)
    
    class Meta:
        constraints = [
            models.CheckConstraint(
                check=models.Q(amount__gt=0),
                name="finance_giving_amount_positive"
            ),
        ]

class Payment(models.Model):
    # ✅ Payment gateway abstraction
    # ✅ Provider (Paystack, Flutterwave)
    # ✅ Reference tracking (provider_reference unique)
    # ✅ Status (PENDING/SUCCESSFUL/FAILED/REFUNDED)
    # ✅ Idempotency key
    # ✅ Webhook payload storage (raw_webhook_payload)
    # ✅ No raw card data stored ✅
    # ✅ Amount validation (> 0)
    provider_reference = models.CharField(max_length=100, unique=True)
    idempotency_key = models.CharField(max_length=150, unique=True, null=True)
    raw_webhook_payload = models.JSONField(null=True)
    
class Pledge(models.Model):
    # ✅ Pledge tracking
    # ✅ Balance calculation
    # ✅ Fulfillment validation
    # ✅ Check constraints (amount_fulfilled <= amount_pledged) ✅
    amount_pledged = models.DecimalField(max_digits=14, decimal_places=2)
    amount_fulfilled = models.DecimalField(max_digits=14, decimal_places=2)
    
    @property
    def balance(self):
        return self.amount_pledged - self.amount_fulfilled

class Refund(models.Model):
    # ✅ Refund tracking
    # ✅ Audit trail (doesn't mutate original)
    # ✅ Payment refund reference
    # ✅ Amount validation
    original_giving = models.ForeignKey(Giving, on_delete=models.PROTECT)
    payment_refund_reference = models.CharField(max_length=150, blank=True)
```

**Assessment:** Models are **EXCELLENT**. Proper use of Decimal, constraints, immutability patterns.

---

### What is MISSING ❌

#### 1. ❌ Payment Gateway Integration (CRITICAL)
**Requirement:** Actually integrate Paystack/Flutterwave

**Current State:** Models exist, but need to check services/views

Let me check services:

<function_calls>
<invoke name="read_file">
<parameter name="path">c:\Users\MY PC\Downloads\chapelflow-backend\chapelflow\apps\finance\services.py