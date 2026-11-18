# Phase 14 Required Migrations

**Date**: 2026-09-01  
**Status**: ⚠️ **BLOCKED** - Cannot generate (Django not installed)

---

## Migration Generation Commands

Once Django environment is available, run:

```bash
# Generate Phase 14 migrations
python manage.py makemigrations finance --name phase14_reconciliation_enhancements

# Apply migrations
python manage.py migrate finance

# Verify migrations
python manage.py showmigrations finance
```

---

## Expected Database Changes

### 1. New Enums/Choices

#### ReconciliationStatus (TextChoices)
- PENDING
- IN_PROGRESS
- RECONCILED
- DISCREPANCY
- APPROVED

#### ReconciliationResultType (TextChoices)
- MATCHED
- UNMATCHED_PAYMENT
- UNMATCHED_GIVING
- AMOUNT_MISMATCH

#### AdjustmentStatus (TextChoices)
- PENDING
- APPROVED
- REJECTED

---

### 2. Model Changes

#### A. Reconciliation Model (MAJOR CHANGES)

**New Fields**:
```sql
ALTER TABLE finance_reconciliation ADD COLUMN id UUID PRIMARY KEY;
ALTER TABLE finance_reconciliation ADD COLUMN status VARCHAR(20) DEFAULT 'PENDING';
ALTER TABLE finance_reconciliation ADD COLUMN difference DECIMAL(16,2) DEFAULT 0;
ALTER TABLE finance_reconciliation ADD COLUMN created_by_id UUID;
ALTER TABLE finance_reconciliation ADD COLUMN created_at TIMESTAMP;
ALTER TABLE finance_reconciliation ADD COLUMN approved_by_id UUID;
ALTER TABLE finance_reconciliation ADD COLUMN approved_at TIMESTAMP;
```

**Modified Fields**:
```sql
ALTER TABLE finance_reconciliation ALTER COLUMN reconciled_at DROP NOT NULL;
ALTER TABLE finance_reconciliation ALTER COLUMN reconciled_at DROP DEFAULT;
```

**New Constraints**:
```sql
ALTER TABLE finance_reconciliation 
  ADD CONSTRAINT unique_reconciliation_per_period 
  UNIQUE (branch_id, period_start, period_end);
```

**New Indexes**:
```sql
CREATE INDEX idx_recon_branch_status ON finance_reconciliation(branch_id, status);
CREATE INDEX idx_recon_period ON finance_reconciliation(period_start, period_end);
CREATE INDEX idx_recon_status_created ON finance_reconciliation(status, created_at);
```

**Foreign Keys**:
```sql
ALTER TABLE finance_reconciliation 
  ADD CONSTRAINT fk_recon_created_by 
  FOREIGN KEY (created_by_id) REFERENCES accounts_user(id) ON DELETE SET NULL;

ALTER TABLE finance_reconciliation 
  ADD CONSTRAINT fk_recon_approved_by 
  FOREIGN KEY (approved_by_id) REFERENCES accounts_user(id) ON DELETE SET NULL;
```

#### B. ReconciliationResult Model (NEW TABLE)

**Table Creation**:
```sql
CREATE TABLE finance_reconciliation_result (
    id UUID PRIMARY KEY,
    reconciliation_id UUID NOT NULL,
    result_type VARCHAR(20) NOT NULL,
    payment_id UUID,
    giving_id UUID,
    expected_amount DECIMAL(14,2),
    actual_amount DECIMAL(14,2),
    difference DECIMAL(14,2) DEFAULT 0,
    notes TEXT,
    created_at TIMESTAMP NOT NULL,
    
    CONSTRAINT fk_result_reconciliation 
      FOREIGN KEY (reconciliation_id) 
      REFERENCES finance_reconciliation(id) 
      ON DELETE CASCADE,
    
    CONSTRAINT fk_result_payment 
      FOREIGN KEY (payment_id) 
      REFERENCES finance_payment(id) 
      ON DELETE SET NULL,
    
    CONSTRAINT fk_result_giving 
      FOREIGN KEY (giving_id) 
      REFERENCES finance_giving(id) 
      ON DELETE SET NULL
);

CREATE INDEX idx_result_reconciliation_type ON finance_reconciliation_result(reconciliation_id, result_type);
CREATE INDEX idx_result_payment ON finance_reconciliation_result(payment_id);
CREATE INDEX idx_result_giving ON finance_reconciliation_result(giving_id);
```

#### C. FinancialAdjustment Model (NEW TABLE)

**Table Creation**:
```sql
CREATE TABLE finance_adjustment (
    id UUID PRIMARY KEY,
    branch_id UUID NOT NULL,
    financial_period_id UUID,
    giving_id UUID,
    payment_id UUID,
    adjustment_type VARCHAR(100) NOT NULL,
    field_name VARCHAR(100),
    old_value TEXT,
    new_value TEXT,
    amount_delta DECIMAL(14,2),
    reason TEXT NOT NULL,
    status VARCHAR(20) DEFAULT 'PENDING',
    created_by_id UUID,
    created_at TIMESTAMP NOT NULL,
    reviewed_by_id UUID,
    reviewed_at TIMESTAMP,
    rejection_reason TEXT,
    applied_at TIMESTAMP,
    
    CONSTRAINT fk_adjustment_branch 
      FOREIGN KEY (branch_id) 
      REFERENCES organizations_branch(id) 
      ON DELETE PROTECT,
    
    CONSTRAINT fk_adjustment_period 
      FOREIGN KEY (financial_period_id) 
      REFERENCES finance_period(id) 
      ON DELETE PROTECT,
    
    CONSTRAINT fk_adjustment_giving 
      FOREIGN KEY (giving_id) 
      REFERENCES finance_giving(id) 
      ON DELETE SET NULL,
    
    CONSTRAINT fk_adjustment_payment 
      FOREIGN KEY (payment_id) 
      REFERENCES finance_payment(id) 
      ON DELETE SET NULL,
    
    CONSTRAINT fk_adjustment_created_by 
      FOREIGN KEY (created_by_id) 
      REFERENCES accounts_user(id) 
      ON DELETE SET NULL,
    
    CONSTRAINT fk_adjustment_reviewed_by 
      FOREIGN KEY (reviewed_by_id) 
      REFERENCES accounts_user(id) 
      ON DELETE SET NULL
);

CREATE INDEX idx_adjustment_branch_status ON finance_adjustment(branch_id, status);
CREATE INDEX idx_adjustment_period ON finance_adjustment(financial_period_id);
CREATE INDEX idx_adjustment_giving ON finance_adjustment(giving_id);
CREATE INDEX idx_adjustment_payment ON finance_adjustment(payment_id);
CREATE INDEX idx_adjustment_status_created ON finance_adjustment(status, created_at);
```

#### D. FinancialPeriod Model (ENHANCEMENTS)

**Note**: Model already exists, adding save() override with validation

**No new database changes required** - validation in application layer

---

### 3. Audit Model Changes

#### AuditAction Enum Extensions

**New Choices** (added to existing enum):
```python
FINANCIAL_PERIOD_CLOSED = "FINANCIAL_PERIOD_CLOSED"
FINANCIAL_PERIOD_LOCKED = "FINANCIAL_PERIOD_LOCKED"
FINANCIAL_PERIOD_REOPENED = "FINANCIAL_PERIOD_REOPENED"
RECONCILIATION_CREATED = "RECONCILIATION_CREATED"
RECONCILIATION_STARTED = "RECONCILIATION_STARTED"
RECONCILIATION_COMPLETED = "RECONCILIATION_COMPLETED"
RECONCILIATION_APPROVED = "RECONCILIATION_APPROVED"
ADJUSTMENT_CREATED = "ADJUSTMENT_CREATED"
ADJUSTMENT_APPROVED = "ADJUSTMENT_APPROVED"
ADJUSTMENT_REJECTED = "ADJUSTMENT_REJECTED"
ADJUSTMENT_APPLIED = "ADJUSTMENT_APPLIED"
```

**Migration Impact**: TextChoices are Python-level only, no database migration needed

---

## Data Migration Considerations

### Existing Reconciliation Records

If there are existing reconciliation records in the database:

1. **Set default status**: All existing records → `RECONCILED` (assume completed)
2. **Set created_by**: Use `reconciled_by` as fallback
3. **Set created_at**: Use `reconciled_at` as fallback
4. **Calculate difference**: `system_total - bank_total`

**Data Migration Script**:
```python
from django.db import migrations
from decimal import Decimal

def migrate_existing_reconciliations(apps, schema_editor):
    Reconciliation = apps.get_model('finance', 'Reconciliation')
    for recon in Reconciliation.objects.all():
        recon.status = 'RECONCILED'
        recon.created_by = recon.reconciled_by
        recon.created_at = recon.reconciled_at
        recon.difference = Decimal(recon.system_total) - Decimal(recon.bank_total)
        recon.save()

class Migration(migrations.Migration):
    dependencies = [
        ('finance', '0XXX_previous_migration'),
    ]
    
    operations = [
        migrations.RunPython(migrate_existing_reconciliations),
    ]
```

---

## Database Constraints Summary

### Check Constraints

All amount fields already have positive constraints (existing):
```sql
-- Already exists
CHECK (amount > 0) ON finance_giving
CHECK (amount > 0) ON finance_payment
CHECK (amount > 0) ON finance_refund
```

**No new CHECK constraints needed** - amounts can be zero or negative in reconciliation differences

### Unique Constraints

1. **Reconciliation**: `(branch_id, period_start, period_end)` - Prevents duplicate reconciliations
2. **FinancialPeriod**: `(branch_id, period_start, period_end)` - Already exists (prevents duplicates)

### Foreign Key Constraints

All foreign keys use appropriate `ON DELETE` behavior:
- **PROTECT**: Critical relationships (branch, period)
- **SET NULL**: User references (created_by, reviewed_by)
- **CASCADE**: Child records (ReconciliationResult)

---

## Index Strategy

### High-Traffic Queries

1. **Reconciliation by branch + status**: 
   ```sql
   SELECT * FROM finance_reconciliation 
   WHERE branch_id = ? AND status = ?
   ```
   **Index**: `idx_recon_branch_status`

2. **Adjustments by branch + status**:
   ```sql
   SELECT * FROM finance_adjustment 
   WHERE branch_id = ? AND status = ?
   ```
   **Index**: `idx_adjustment_branch_status`

3. **Results by reconciliation + type**:
   ```sql
   SELECT * FROM finance_reconciliation_result 
   WHERE reconciliation_id = ? AND result_type = ?
   ```
   **Index**: `idx_result_reconciliation_type`

### Composite Indexes

All composite indexes follow pattern: `(foreign_key, status/type)` for optimal filtering

---

## Migration File Estimate

Expected migration file structure:

```
apps/finance/migrations/
├── 0XXX_phase14_add_reconciliation_status.py      (Reconciliation model changes)
├── 0XXY_phase14_reconciliation_result.py          (New ReconciliationResult table)
├── 0XXZ_phase14_financial_adjustment.py           (New FinancialAdjustment table)
├── 0XYY_phase14_data_migration.py                 (Migrate existing data)
└── 0XYZ_phase14_add_constraints.py                (Add unique constraints + indexes)
```

**Estimated**: 5 migration files

---

## Rollback Strategy

### Safe Rollback Steps

1. **Backup database** before applying migrations
2. **Test migrations** in development first
3. **Apply migrations** during maintenance window
4. **Verify data integrity** after migration

### Rollback Commands

```bash
# Roll back last migration
python manage.py migrate finance 0XXX_previous_migration

# Roll back all Phase 14 migrations
python manage.py migrate finance 0XXX_pre_phase14_migration

# Verify rollback
python manage.py showmigrations finance
```

---

## Post-Migration Verification

### Data Integrity Checks

```sql
-- Check reconciliation statuses
SELECT status, COUNT(*) 
FROM finance_reconciliation 
GROUP BY status;

-- Check adjustment statuses
SELECT status, COUNT(*) 
FROM finance_adjustment 
GROUP BY status;

-- Check reconciliation results
SELECT result_type, COUNT(*) 
FROM finance_reconciliation_result 
GROUP BY result_type;

-- Verify foreign key integrity
SELECT COUNT(*) FROM finance_reconciliation WHERE branch_id IS NULL;  -- Should be 0
SELECT COUNT(*) FROM finance_adjustment WHERE branch_id IS NULL;      -- Should be 0
```

### Index Verification

```sql
-- Check indexes exist
SELECT indexname FROM pg_indexes 
WHERE tablename IN ('finance_reconciliation', 'finance_adjustment', 'finance_reconciliation_result')
ORDER BY tablename, indexname;
```

---

## Blocker Status

⚠️ **BLOCKED**: Cannot generate migrations - Django not installed

**Error**: `ModuleNotFoundError: No module named 'django'`

**Next Steps**:
1. Install Django environment: `pip install django djangorestframework`
2. Run: `python manage.py makemigrations finance --name phase14_reconciliation_enhancements`
3. Review generated migration files
4. Apply: `python manage.py migrate finance`
5. Verify: `python manage.py showmigrations finance`

---

## Estimated Database Impact

| Operation | Rows Affected | Duration Estimate |
|-----------|---------------|-------------------|
| Add Reconciliation fields | Existing rows | < 1 second |
| Create ReconciliationResult table | 0 rows | < 1 second |
| Create FinancialAdjustment table | 0 rows | < 1 second |
| Add indexes | N/A | < 5 seconds |
| Data migration (if needed) | Existing recons | < 10 seconds |

**Total Estimated Downtime**: < 30 seconds

**Recommendation**: Apply during low-traffic period

---

**Status**: ✅ **READY** (awaiting Django environment)
