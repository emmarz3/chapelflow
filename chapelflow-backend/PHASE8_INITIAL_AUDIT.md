# PHASE 8 INITIAL AUDIT REPORT
# Contributions, Donations & Financial Transaction Management

**Audit Date**: 2026-08-30  
**Auditor**: Phase 8 Implementation Agent  
**Scope**: Complete financial system security and functionality review

---

## EXECUTIVE SUMMARY

**Status**: 🟡 **SUBSTANTIAL EXISTING IMPLEMENTATION WITH CRITICAL SECURITY GAPS**

The ChapelFlow CUC repository contains a **comprehensive finance app** (`apps/finance/`) with:
- ✅ Giving, Payment, Pledge models (authoritative financial records)
- ✅ Payment gateway integration (Paystack, Flutterwave)
- ✅ Webhook security (HMAC signature verification)
- ✅ Branch-scoped authorization
- ✅ DecimalField for exact money arithmetic
- ✅ Controlled enums for status/source

**CRITICAL GAPS**:
- 🔴 **Mass assignment vulnerabilities** in GivingSerializer
- 🔴 **No self-service member endpoints** (members can't view own history)
- 🔴 **No immutability protection** on completed transactions
- 🔴 **Missing validation**: amount > 0, cross-branch member assignment
- 🔴 **Incomplete refund/reversal workflow**
- 🔴 **No event/group contribution tracking** (Phase 6/5 integration missing)
- 🔴 **Limited security test coverage** (no attack matrix)

---

## 1. EXISTING ARCHITECTURE

### 1.1 Models (`apps/finance/models.py`)

#### ✅ **GivingCategory** (Controlled Types)
```python
class GivingCategory(models.Model):
    name = CharField(max_length=100, unique=True)
    description = CharField(max_length=255, blank=True)
    is_active = BooleanField(default=True)
```

**Assessment**: ✅ **GOOD**
- Controlled category system (Tithe, Offering, Building Fund, etc.)
- Unique constraint on name
- Soft-delete via is_active flag

#### ✅ **Giving** (Authoritative Financial Record)
```python
class Giving(models.Model):
    id = UUIDField(primary_key=True, default=uuid.uuid4)
    branch = ForeignKey("organizations.Branch", PROTECT)
    member = ForeignKey("members.Member", null=True, blank=True, SET_NULL)
    category = ForeignKey(GivingCategory, PROTECT)
    
    amount = DecimalField(max_digits=14, decimal_places=2)  ✅
    currency = CharField(max_length=3, default="NGN")
    source = CharField(max_length=20, choices=GivingSource.choices)
    
    payment = OneToOneField("Payment", null=True, blank=True, SET_NULL)
    
    given_at = DateTimeField()
    recorded_by = ForeignKey(User, null=True, blank=True, SET_NULL)
    note = CharField(max_length=500, blank=True)
    created_at = DateTimeField(auto_now_add=True)
```

**Assessment**: 🟡 **MOSTLY GOOD, GAPS EXIST**

**Strengths**:
- ✅ UUID primary key (non-predictable)
- ✅ DecimalField(14, 2) for exact arithmetic
- ✅ Branch FK for organizational scope
- ✅ OneToOne Payment link (online giving)
- ✅ recorded_by audit trail
- ✅ Indexes on (branch, given_at) and (member, category)
- ✅ PROTECT on critical FKs (branch, category)
- ✅ SET_NULL on member (handles member deletion gracefully)

**Gaps**:
- ❌ **No event FK** (can't track event-specific contributions)
- ❌ **No group/fellowship/unit FK** (can't track organizational giving)
- ❌ **No amount validation** (amount > 0 constraint missing)
- ❌ **No status field** (can't distinguish draft/confirmed/voided)
- ❌ **member nullable** but no explicit anonymous giving logic
- ❌ **given_at writable** (should be server-controlled for staff recordings)

#### ✅ **Payment** (Gateway Transaction)
```python
class Payment(models.Model):
    id = UUIDField(primary_key=True, default=uuid.uuid4)
    branch = ForeignKey("organizations.Branch", PROTECT)
    member = ForeignKey("members.Member", null=True, blank=True, SET_NULL)
    
    provider = CharField(max_length=20, choices=[...])
    provider_reference = CharField(max_length=100, unique=True)  ✅
    amount = DecimalField(max_digits=14, decimal_places=2)  ✅
    currency = CharField(max_length=3, default="NGN")
    status = CharField(max_length=15, choices=PaymentStatus.choices)
    
    raw_webhook_payload = JSONField(null=True, blank=True)
    idempotency_key = CharField(max_length=150, unique=True, null=True)
    created_at = DateTimeField(auto_now_add=True)
    confirmed_at = DateTimeField(null=True, blank=True)
```

**Assessment**: ✅ **EXCELLENT**

**Strengths**:
- ✅ Unique provider_reference (prevents duplicates)
- ✅ Unique idempotency_key (replay protection)
- ✅ Status enum (PENDING/SUCCESSFUL/FAILED/REFUNDED)
- ✅ raw_webhook_payload for audit
- ✅ confirmed_at timestamp
- ✅ No sensitive payment data stored (no CVV, card numbers)
- ✅ Index on (provider, provider_reference)

**Gaps**:
- 🟡 **No CheckConstraint** for amount > 0
- 🟡 **status writable** (should be webhook-only via service)

#### ✅ **Pledge**
```python
class Pledge(models.Model):
    id = UUIDField(primary_key=True, default=uuid.uuid4)
    branch = ForeignKey("organizations.Branch", PROTECT)
    member = ForeignKey("members.Member", CASCADE)
    category = ForeignKey(GivingCategory, PROTECT)
    
    amount_pledged = DecimalField(max_digits=14, decimal_places=2)
    amount_fulfilled = DecimalField(max_digits=14, decimal_places=2, default=0)
    start_date = DateField()
    end_date = DateField(null=True, blank=True)
    is_active = BooleanField(default=True)
    
    @property
    def balance(self):
        return self.amount_pledged - self.amount_fulfilled
```

**Assessment**: ✅ **GOOD**

**Strengths**:
- ✅ Separate pledge tracking from actual giving
- ✅ balance property (calculated, not stored)
- ✅ amount_fulfilled read-only tracking

**Gaps**:
- ❌ **No validation**: amount_fulfilled <= amount_pledged
- ❌ **amount_fulfilled writable** (should be service-controlled)

#### 🟡 **FinancialStatement / Reconciliation**
**Assessment**: 🟡 **MODELS EXIST, NO LOGIC**
- Models defined but no generation service
- No Celery tasks for statement generation
- Marked as deferred enhancement

---

### 1.2 Serializers (`apps/finance/serializers.py`)

#### 🔴 **GivingSerializer** - CRITICAL SECURITY GAPS

**Current Implementation**:
```python
class GivingSerializer(ScopedFKValidationMixin, serializers.ModelSerializer):
    class Meta:
        fields = [
            "id", "branch", "member", "category", "amount", "currency",
            "source", "payment", "given_at", "recorded_by", "note", "created_at",
        ]
        read_only_fields = ["id", "recorded_by", "created_at"]
    
    def validate_branch(self, branch):
        return self.validate_branch_fk(branch)
    
    def validate_member(self, member):
        if member:
            return self.validate_member_fk(member)
        return member
    
    def validate_payment(self, payment):
        if payment:
            return self.validate_related_branch_fk(payment, 'payment')
        return payment
```

**Assessment**: 🔴 **CRITICAL MASS ASSIGNMENT VULNERABILITIES**

**Vulnerabilities**:
1. ❌ **branch writable** → User can assign to unauthorized branch
2. ❌ **member writable** → User can create giving for another member
3. ❌ **given_at writable** → Client controls transaction timestamp
4. ❌ **payment writable** → User can link arbitrary payment
5. ❌ **No amount validation** → Negative/zero amounts possible
6. ❌ **No cross-branch validation** → member.branch != giving.branch

**Attack Scenarios**:
```json
// Attack 1: Assign to privileged branch
POST /api/v1/giving/
{
  "branch": "<other-branch-id>",
  "member": "<own-member-id>",
  "amount": 1000,
  "category": "<id>",
  "source": "CASH",
  "given_at": "2026-08-30T10:00:00Z"
}

// Attack 2: Create giving for another member
POST /api/v1/giving/
{
  "branch": "<attacker-branch>",
  "member": "<victim-member-id>",  // ← Different member
  "amount": 999999,
  "category": "<id>",
  "source": "CASH",
  "given_at": "2026-08-30T10:00:00Z"
}

// Attack 3: Backdated transaction
{
  "given_at": "2020-01-01T00:00:00Z"  // ← Fabricated date
}
```

**Required Fixes**:
1. ✅ Make `branch` read_only (derive from request.user.branch or recorded_by.branch)
2. ✅ Make `member` read_only for self-service, validate scope for staff
3. ✅ Make `given_at` server-controlled (use timezone.now() or require approval)
4. ✅ Make `payment` read_only (webhook-controlled)
5. ✅ Add `validate_amount()` → amount > 0
6. ✅ Add `validate()` → member.branch == giving.branch

#### 🟡 **PledgeSerializer**
**Similar Issues**:
- ❌ branch writable
- ❌ member writable
- ✅ amount_fulfilled read_only (correct)

#### 🟡 **PaymentSerializer**
**Assessment**: 🟡 **PARTIALLY SECURE**
- ✅ status read_only (webhook-only)
- ❌ branch/member writable (should be server-controlled)

---

### 1.3 Views (`apps/finance/views.py`)

#### ✅ **GivingViewSet**
```python
class GivingViewSet(BranchScopedQuerysetMixin, StandardModelViewSet):
    serializer_class = GivingSerializer
    permission_classes = [IsFinanceAuthorized]  ✅
    filterset_fields = ["branch", "member", "category", "source"]
    
    def get_base_queryset(self):
        return Giving.objects.select_related("branch", "member", "category", "payment")
    
    def perform_create(self, serializer):
        serializer.save(recorded_by=self.request.user)  ✅
```

**Assessment**: 🟡 **PARTIAL SECURITY**

**Strengths**:
- ✅ BranchScopedQuerysetMixin (list/retrieve filtered)
- ✅ IsFinanceAuthorized (MFA + FINANCE_ACCESS_ROLES)
- ✅ recorded_by auto-set
- ✅ select_related (N+1 prevention)

**Gaps**:
- ❌ **No self-service endpoint** (members can't view own history)
- ❌ **No /me/giving/** or similar
- ❌ **Relies on serializer validation** (which is broken)
- ❌ **No branch auto-assignment** in perform_create

#### 🔴 **PaymentWebhookView**
```python
@method_decorator(csrf_exempt, name="dispatch")
class PaymentWebhookView(APIView):
    permission_classes = [AllowAny]  ✅ Required for webhooks
    authentication_classes = []
    
    def post(self, request, provider):
        try:
            payment = process_webhook(provider, request)
        except WebhookVerificationError as exc:
            return error_response(str(exc), status=400)
        return success_response(...)
```

**Assessment**: ✅ **EXCELLENT SECURITY**
- ✅ AllowAny + csrf_exempt (required for gateway webhooks)
- ✅ Signature verification in process_webhook()
- ✅ All state changes in secure service

---

### 1.4 Services (`apps/finance/services.py`)

#### ✅ **Webhook Processing**
```python
def process_webhook(provider_key: str, request) -> Payment:
    # 1. Verify HMAC signature
    if not service.verify_webhook_signature(request):
        raise WebhookVerificationError("Invalid webhook signature.")
    
    # 2. Parse event
    event = service.parse_webhook_event(payload)
    
    # 3. Idempotent update
    with transaction.atomic():
        payment = Payment.objects.select_for_update().filter(
            provider_reference=event["reference"]
        ).first()
        
        # Already terminal? No-op (idempotent)
        if payment.status in (SUCCESSFUL, FAILED, REFUNDED):
            return payment
        
        # Update status
        payment.status = event["status"]
        payment.raw_webhook_payload = payload
        if event["status"] == SUCCESSFUL:
            payment.confirmed_at = timezone.now()
        payment.save(...)
```

**Assessment**: ✅ **EXCELLENT**

**Strengths**:
- ✅ HMAC signature verification (Paystack SHA512, Flutterwave secret)
- ✅ hmac.compare_digest (timing-attack safe)
- ✅ select_for_update (race condition safe)
- ✅ Idempotency (terminal state check)
- ✅ transaction.atomic (consistency)
- ✅ Structured logging

**Gaps**:
- 🟡 No explicit replay timestamp validation (relies on idempotency)
- 🟡 Amount verification not enforced (event["amount"] not compared to payment.amount)

---

### 1.5 Permissions (`common/permissions/rbac.py`)

#### ✅ **IsFinanceAuthorized**
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

**Assessment**: ✅ **EXCELLENT**
- ✅ MFA required
- ✅ FINANCE_ACCESS_ROLES = {SUPER_ADMIN, CHAPEL_ADMIN, FINANCE_OFFICER}
- ✅ Applied to all finance viewsets

**Gap**:
- ❌ **No object-level permission** (all finance users see all branch data within scope)

---

### 1.6 Tests (`tests/finance/test_payments.py`)

**Existing Coverage**:
1. ✅ Member cannot access finance records (403)
2. ✅ Finance officer can access (200)
3. ✅ Invalid webhook signature rejected (400)
4. ✅ Valid webhook confirms payment
5. ✅ Replayed webhook is idempotent
6. ✅ Unknown reference rejected (400)

**Assessment**: 🟡 **PARTIAL COVERAGE**

**Missing Tests**:
- ❌ Mass assignment attacks (branch/member substitution)
- ❌ Amount validation (negative, zero, NaN)
- ❌ Cross-branch member assignment
- ❌ Self-service giving history access
- ❌ Financial aggregation scope leaks
- ❌ Refund workflow
- ❌ Pledge fulfillment logic
- ❌ Concurrent webhook delivery
- ❌ Dashboard authorization
- ❌ Report scope enforcement

---

## 2. CRITICAL SECURITY GAPS

### 🔴 **Gap 1: Mass Assignment - Branch Substitution**
**Severity**: CRITICAL  
**Attack**:
```python
# User from Branch A
POST /api/v1/giving/
{"branch": "<branch-b-id>", "amount": 1000, ...}
```
**Impact**: User assigns giving to unauthorized branch  
**Root Cause**: GivingSerializer.branch not read_only  
**Fix**: Server-derive branch from request.user.branch

---

### 🔴 **Gap 2: Mass Assignment - Member Substitution**
**Severity**: CRITICAL  
**Attack**:
```python
# User creates giving for another member
POST /api/v1/giving/
{"member": "<victim-id>", "amount": 999999, ...}
```
**Impact**: Fabricated financial records for other members  
**Root Cause**: GivingSerializer.member not read_only  
**Fix**: Self-service must derive member from request.user.member_profile

---

### 🔴 **Gap 3: No Self-Service Endpoint**
**Severity**: HIGH  
**Issue**: Members cannot view their own giving history  
**Impact**: Members have no transparency into their contributions  
**Fix**: Implement `/api/v1/me/giving/` endpoint

---

### 🔴 **Gap 4: No Amount Validation**
**Severity**: HIGH  
**Attack**:
```python
POST /api/v1/giving/
{"amount": -1000, ...}  # Negative
{"amount": 0, ...}      # Zero
```
**Impact**: Invalid financial records  
**Fix**: Add validate_amount() → amount > 0

---

### 🔴 **Gap 5: No Cross-Branch Member Validation**
**Severity**: HIGH  
**Attack**:
```python
# Branch A user
POST /api/v1/giving/
{
  "branch": "<branch-a-id>",
  "member": "<branch-b-member-id>",  // ← Cross-branch
  "amount": 1000
}
```
**Impact**: Member assigned to wrong branch's financial records  
**Fix**: Validate member.branch == giving.branch

---

### 🔴 **Gap 6: No Immutability Protection**
**Severity**: HIGH  
**Issue**: Completed giving records can be modified via PATCH  
**Attack**:
```python
PATCH /api/v1/giving/<id>/
{"amount": 999999}  # Alter historical transaction
```
**Impact**: Financial record tampering  
**Fix**: Implement status field + immutability logic

---

### 🔴 **Gap 7: No Event/Group Integration**
**Severity**: MEDIUM  
**Issue**: Cannot track event-specific or group-specific contributions  
**Impact**: Phase 6 (Events) and Phase 5 (Groups) integration incomplete  
**Fix**: Add optional event/group/fellowship/unit FKs to Giving

---

### 🔴 **Gap 8: Incomplete Refund Workflow**
**Severity**: MEDIUM  
**Issue**: PaymentStatus.REFUNDED exists but no refund logic  
**Impact**: Cannot process refunds properly  
**Fix**: Implement refund service with validation

---

### 🔴 **Gap 9: Dashboard Aggregation Unclear**
**Severity**: MEDIUM  
**Issue**: FinanceDashboardView uses `_branch_qs_or_all()` helper  
**Risk**: Aggregation might leak cross-branch totals  
**Fix**: Audit and verify pre-filtered aggregation

---

### 🔴 **Gap 10: Limited Security Test Coverage**
**Severity**: MEDIUM  
**Issue**: Only 6 tests, no attack matrix  
**Impact**: Security regressions not detected  
**Fix**: Implement 10-scenario attack matrix

---

## 3. POSITIVE FINDINGS

### ✅ **Excellent Foundation**
1. ✅ Decimal arithmetic (no floats for money)
2. ✅ Webhook security (HMAC verification)
3. ✅ Idempotency (replay protection)
4. ✅ Branch scoping (BranchScopedQuerysetMixin)
5. ✅ MFA enforcement (IsFinanceAuthorized)
6. ✅ No sensitive payment data stored
7. ✅ UUID primary keys (non-predictable)
8. ✅ Audit trail (recorded_by, created_at)
9. ✅ Transaction safety (select_for_update, atomic)
10. ✅ Controlled enums (GivingSource, PaymentStatus)

---

## 4. PHASE 8 IMPLEMENTATION PLAN

### **Task 2-5: Model & Validation Hardening**
1. Add Giving.status field (DRAFT/CONFIRMED/VOIDED)
2. Add Giving.event FK (optional, Phase 6 integration)
3. Add Giving.group FK (optional, Phase 5 integration)
4. Add CheckConstraint: amount > 0
5. Add validate_amount() in serializers
6. Add validate() cross-branch check

### **Task 6-7: Authorization Hardening**
1. Make GivingSerializer.branch read_only
2. Make GivingSerializer.member read_only
3. Make GivingSerializer.given_at server-controlled
4. Implement MemberGivingHistoryView (/me/giving/)
5. Add branch auto-assignment in perform_create

### **Task 8-9: Financial Integrity**
1. Implement immutability protection (status-based)
2. Implement refund service
3. Add Refund model (track reversals)
4. Add pledge fulfillment validation

### **Task 10: Reports & Privacy**
1. Audit dashboard aggregation
2. Implement scope-safe reports
3. Add member giving summary

### **Task 11: Security Test Matrix**
1. Member substitution attack
2. Branch substitution attack
3. Amount manipulation attack
4. Cross-branch assignment attack
5. Direct-ID access attack
6. Report scope bypass attack
7. Refund abuse attack
8. Over-refund attack
9. Webhook replay attack
10. Dashboard aggregation leak

### **Task 12: Phase 0-7 Integration**
1. Verify Phase 4 (Members) integration
2. Implement Phase 5 (Groups) contribution tracking
3. Implement Phase 6 (Events) contribution tracking
4. Verify audit logging integration

---

## 5. ACCEPTANCE CRITERIA

Phase 8 is **COMPLETE** only when:

### Financial Model
- [x] Giving is authoritative financial record
- [x] DecimalField for exact arithmetic
- [ ] Status field implemented (DRAFT/CONFIRMED/VOIDED)
- [ ] Amount validation (> 0)
- [ ] Event/group FKs added

### Authorization
- [x] IsFinanceAuthorized permission
- [x] BranchScopedQuerysetMixin
- [ ] Serializer mass assignment fixed
- [ ] Self-service endpoint implemented
- [ ] Cross-branch validation

### Payment Security
- [x] Webhook signature verification
- [x] Idempotency protection
- [x] No sensitive data stored
- [ ] Amount verification in webhooks

### Financial Integrity
- [ ] Immutability protection
- [ ] Refund workflow
- [ ] Reversal tracking
- [ ] Pledge fulfillment validation

### Testing
- [x] Basic webhook tests
- [ ] 10-scenario attack matrix
- [ ] Financial integrity tests
- [ ] Concurrency tests

### Integration
- [x] Phase 4 (Members) compatible
- [ ] Phase 5 (Groups) contributions
- [ ] Phase 6 (Events) contributions
- [x] Audit logging

---

## 6. RECOMMENDATION

**VERDICT**: 🟡 **PHASE 8 PARTIALLY COMPLETE — CRITICAL HARDENING REQUIRED**

The existing finance app provides an **excellent foundation** with correct decimal arithmetic, webhook security, and branch scoping. However, **critical mass assignment vulnerabilities** and **missing self-service endpoints** must be fixed before production use.

**Priority Order**:
1. 🔴 **CRITICAL**: Fix GivingSerializer mass assignment (Tasks 6-7)
2. 🔴 **CRITICAL**: Implement self-service endpoints (Task 7)
3. 🔴 **HIGH**: Add amount validation (Task 5)
4. 🔴 **HIGH**: Implement immutability protection (Task 9)
5. 🟡 **MEDIUM**: Add event/group integration (Task 12)
6. 🟡 **MEDIUM**: Implement refund workflow (Task 9)
7. 🟡 **MEDIUM**: Complete security test matrix (Task 11)

**Estimated Effort**: 8-12 hours of focused security hardening

---

## APPENDIX A: CURRENT ENDPOINTS

### Finance Endpoints
- `GET /api/v1/giving/` - List giving (finance staff only)
- `POST /api/v1/giving/` - Record giving (finance staff only)
- `GET /api/v1/giving/<id>/` - Retrieve giving
- `PATCH /api/v1/giving/<id>/` - Update giving ⚠️
- `DELETE /api/v1/giving/<id>/` - Delete giving ⚠️

- `GET /api/v1/pledges/` - List pledges
- `POST /api/v1/pledges/` - Create pledge
- `PATCH /api/v1/pledges/<id>/` - Update pledge

- `GET /api/v1/payments/` - List payments (read-only)
- `GET /api/v1/payments/<id>/` - Retrieve payment

- `POST /api/v1/payments/webhook/<provider>/` - Webhook (AllowAny)

- `GET /api/v1/dashboard/finance/` - Finance dashboard

### Missing Endpoints
- ❌ `GET /api/v1/me/giving/` - Member giving history
- ❌ `GET /api/v1/me/pledges/` - Member pledge history
- ❌ `POST /api/v1/giving/<id>/refund/` - Refund giving
- ❌ `POST /api/v1/giving/<id>/void/` - Void giving

---

## APPENDIX B: DATABASE SCHEMA

### Giving Table (`finance_giving`)
```sql
CREATE TABLE finance_giving (
    id UUID PRIMARY KEY,
    branch_id BIGINT NOT NULL REFERENCES organizations_branch(id) ON DELETE PROTECT,
    member_id UUID REFERENCES members_member(id) ON DELETE SET NULL,
    category_id BIGINT NOT NULL REFERENCES finance_giving_category(id) ON DELETE PROTECT,
    payment_id UUID REFERENCES finance_payment(id) ON DELETE SET NULL,
    
    amount NUMERIC(14, 2) NOT NULL,
    currency VARCHAR(3) NOT NULL DEFAULT 'NGN',
    source VARCHAR(20) NOT NULL,
    
    given_at TIMESTAMP WITH TIME ZONE NOT NULL,
    recorded_by_id BIGINT REFERENCES accounts_user(id) ON DELETE SET NULL,
    note VARCHAR(500),
    created_at TIMESTAMP WITH TIME ZONE NOT NULL,
    
    -- Missing: status, event_id, group_id, CHECK (amount > 0)
);

CREATE INDEX idx_giving_branch_given_at ON finance_giving(branch_id, given_at);
CREATE INDEX idx_giving_member_category ON finance_giving(member_id, category_id);
```

### Payment Table (`finance_payment`)
```sql
CREATE TABLE finance_payment (
    id UUID PRIMARY KEY,
    branch_id BIGINT NOT NULL REFERENCES organizations_branch(id) ON DELETE PROTECT,
    member_id UUID REFERENCES members_member(id) ON DELETE SET NULL,
    
    provider VARCHAR(20) NOT NULL,
    provider_reference VARCHAR(100) NOT NULL UNIQUE,
    idempotency_key VARCHAR(150) UNIQUE,
    
    amount NUMERIC(14, 2) NOT NULL,
    currency VARCHAR(3) NOT NULL DEFAULT 'NGN',
    status VARCHAR(15) NOT NULL,
    
    raw_webhook_payload JSONB,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL,
    confirmed_at TIMESTAMP WITH TIME ZONE
);

CREATE INDEX idx_payment_provider_reference ON finance_payment(provider, provider_reference);
```

---

**End of Phase 8 Initial Audit Report**
