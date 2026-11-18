# Migrations Required for Phases 11-15

## Status: PENDING - Python environment not available

To generate these migrations, run:
```bash
# From the chapelflow directory
python manage.py makemigrations members finance
python manage.py makemigrations --check  # Verify no conflicts
python manage.py migrate --plan  # Review migration plan
python manage.py migrate  # Apply migrations
```

## New Models Added

### Phase 11 - Member Engagement (apps/members/models.py)

#### 1. MemberFollowUp Model
- **Fields:**
  - `id`: UUIDField (primary key)
  - `member`: ForeignKey to Member
  - `milestone`: CharField (choices: DAY_7, DAY_30, DAY_90)
  - `assigned_to`: ForeignKey to User (nullable)
  - `scheduled_for`: DateTimeField
  - `completed_at`: DateTimeField (nullable)
  - `reminder_sent_at`: DateTimeField (nullable)
  - `notes`: TextField
  - `created_at`: DateTimeField (auto_now_add)
  - `updated_at`: DateTimeField (auto_now)

- **Constraints:**
  - `unique_together`: ["member", "milestone"]
  - Index on ["member", "scheduled_for"]
  - Index on ["assigned_to", "completed_at"]
  - Index on ["scheduled_for", "completed_at"]

- **Meta:**
  - `db_table`: "member_followup"
  - `ordering`: ["scheduled_for"]

#### 2. EngagementMetrics Model
- **Fields:**
  - `member`: OneToOneField to Member (primary key)
  - `services_attended_30d`: IntegerField (default=0)
  - `services_attended_90d`: IntegerField (default=0)
  - `last_service_date`: DateField (nullable)
  - `attendance_rate_30d`: DecimalField (max_digits=5, decimal_places=2, default=0.00)
  - `events_attended_30d`: IntegerField (default=0)
  - `events_attended_90d`: IntegerField (default=0)
  - `last_event_date`: DateField (nullable)
  - `volunteer_assignments_active`: IntegerField (default=0)
  - `volunteer_assignments_completed`: IntegerField (default=0)
  - `last_volunteer_date`: DateField (nullable)
  - `giving_count_30d`: IntegerField (default=0)
  - `giving_count_90d`: IntegerField (default=0)
  - `last_giving_date`: DateField (nullable)
  - `engagement_score`: IntegerField (default=0, 0-100 range)
  - `days_since_last_activity`: IntegerField (default=0)
  - `last_calculated_at`: DateTimeField (auto_now)

- **Meta:**
  - `db_table`: "member_engagement_metrics"
  - Index on ["engagement_score"]
  - Index on ["days_since_last_activity"]

### Phase 14 - Financial Reconciliation (apps/finance/models.py)

#### 3. FinancialPeriod Model
- **Fields:**
  - `id`: UUIDField (primary key)
  - `branch`: ForeignKey to Branch (PROTECT)
  - `name`: CharField(max_length=100)
  - `period_start`: DateField
  - `period_end`: DateField
  - `status`: CharField(max_length=10, choices: OPEN/CLOSED/LOCKED)
  - `closed_by`: ForeignKey to User (nullable, SET_NULL)
  - `closed_at`: DateTimeField (nullable)
  - `locked_by`: ForeignKey to User (nullable, SET_NULL)
  - `locked_at`: DateTimeField (nullable)
  - `created_at`: DateTimeField (auto_now_add)
  - `updated_at`: DateTimeField (auto_now)

- **Constraints:**
  - `unique_together`: ["branch", "period_start", "period_end"]
  - Index on ["branch", "status"]
  - Index on ["period_start", "period_end"]

- **Meta:**
  - `db_table`: "finance_period"
  - `ordering`: ["-period_start"]

## Migration Dependencies

The new migrations will depend on:
- Latest members app migration (currently 0008_phase3_add_constraints)
- Latest finance app migration (check apps/finance/migrations/)
- accounts.User model (for ForeignKey relationships)
- organizations.Branch model (for ForeignKey relationships)

## Potential Issues to Check

1. **Circular Import**: MemberFollowUp references User via assigned_to
2. **Signal Registration**: Ensure apps/members/apps.py ready() is called
3. **Existing Data**: No existing data migration needed (all new tables)
4. **Foreign Key ON_DELETE**: All use appropriate cascades (PROTECT for branch, SET_NULL for users)

## Post-Migration Verification

After applying migrations, verify:
```bash
# Check migration status
python manage.py showmigrations members finance

# Verify table creation
python manage.py dbshell
\dt member_*
\dt finance_period
\q

# Run tests
pytest apps/members/tests/ -v
pytest apps/finance/tests/ -v
```

## Rollback Plan

If migrations fail:
```bash
# Rollback members
python manage.py migrate members 0008_phase3_add_constraints

# Rollback finance
python manage.py migrate finance <previous_migration_number>

# Fix issues and regenerate
python manage.py makemigrations members finance
```
