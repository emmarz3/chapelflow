# Phase 11 Migration Specification

**Status**: BLOCKED - Cannot generate migrations without Django environment  
**Blocker**: `ModuleNotFoundError: No module named 'django'`

---

## Required Migration: `members.0009_phase11_engagement_followup`

### Models to Create

#### 1. MemberFollowUp

```python
operations = [
    migrations.CreateModel(
        name='MemberFollowUp',
        fields=[
            ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True)),
            ('milestone', models.CharField(
                max_length=10,
                choices=[
                    ('DAY_7', '7-Day Follow-Up'),
                    ('DAY_30', '30-Day Follow-Up'),
                    ('DAY_90', '90-Day Follow-Up'),
                ],
                help_text='Which follow-up milestone (7/30/90 days)'
            )),
            ('scheduled_for', models.DateTimeField(help_text='When this follow-up is due')),
            ('completed_at', models.DateTimeField(
                null=True, blank=True,
                help_text='When follow-up was completed'
            )),
            ('notes', models.TextField(
                blank=True,
                help_text='Follow-up notes (what was discussed, next steps)'
            )),
            ('reminder_sent_at', models.DateTimeField(
                null=True, blank=True,
                help_text='When reminder was sent. Prevents duplicate reminders (idempotency).'
            )),
            ('created_at', models.DateTimeField(auto_now_add=True)),
            ('updated_at', models.DateTimeField(auto_now=True)),
            
            # Foreign Keys
            ('member', models.ForeignKey(
                'members.Member',
                on_delete=models.CASCADE,
                related_name='follow_ups',
                help_text='Member being followed up'
            )),
            ('assigned_to', models.ForeignKey(
                'accounts.User',
                null=True, blank=True,
                on_delete=models.SET_NULL,
                related_name='member_follow_up_assignments',
                help_text='Staff member assigned to complete this follow-up'
            )),
        ],
        options={
            'db_table': 'members_follow_up',
            'ordering': ['scheduled_for'],
        },
    ),
    
    # Indexes
    migrations.AddIndex(
        model_name='memberfollowup',
        index=models.Index(fields=['scheduled_for', 'completed_at'], name='members_fo_schedul_idx'),
    ),
    migrations.AddIndex(
        model_name='memberfollowup',
        index=models.Index(fields=['assigned_to', 'completed_at'], name='members_fo_assigne_idx'),
    ),
    migrations.AddIndex(
        model_name='memberfollowup',
        index=models.Index(fields=['reminder_sent_at'], name='members_fo_reminde_idx'),
    ),
    
    # Unique constraint
    migrations.AddConstraint(
        model_name='memberfollowup',
        constraint=models.UniqueConstraint(
            fields=['member', 'milestone'],
            name='unique_member_milestone'
        ),
    ),
]
```

#### 2. EngagementMetrics

```python
operations += [
    migrations.CreateModel(
        name='EngagementMetrics',
        fields=[
            # Primary key (OneToOne with Member)
            ('member', models.OneToOneField(
                'members.Member',
                on_delete=models.CASCADE,
                related_name='engagement_metrics',
                primary_key=True
            )),
            
            # Attendance metrics
            ('services_attended_30d', models.IntegerField(
                default=0,
                help_text='Services attended in last 30 days'
            )),
            ('services_attended_90d', models.IntegerField(
                default=0,
                help_text='Services attended in last 90 days'
            )),
            ('last_service_date', models.DateField(
                null=True, blank=True,
                help_text='Date of most recent service attendance'
            )),
            ('attendance_rate_30d', models.DecimalField(
                max_digits=5, decimal_places=2,
                default=0,
                help_text='Attendance rate in last 30 days (0-100%)'
            )),
            
            # Event participation
            ('events_attended_30d', models.IntegerField(
                default=0,
                help_text='Events attended in last 30 days'
            )),
            ('events_attended_90d', models.IntegerField(
                default=0,
                help_text='Events attended in last 90 days'
            )),
            ('last_event_date', models.DateField(
                null=True, blank=True,
                help_text='Date of most recent event attendance'
            )),
            
            # Volunteering
            ('volunteer_assignments_active', models.IntegerField(
                default=0,
                help_text='Currently active volunteer assignments'
            )),
            ('volunteer_assignments_completed', models.IntegerField(
                default=0,
                help_text='Total volunteer assignments completed (all time)'
            )),
            ('last_volunteer_date', models.DateField(
                null=True, blank=True,
                help_text='Date of most recent volunteer activity'
            )),
            
            # Giving (optional - may be disabled for privacy)
            ('giving_count_30d', models.IntegerField(
                default=0,
                help_text='Number of gifts in last 30 days'
            )),
            ('giving_count_90d', models.IntegerField(
                default=0,
                help_text='Number of gifts in last 90 days'
            )),
            ('last_giving_date', models.DateField(
                null=True, blank=True,
                help_text='Date of most recent giving'
            )),
            
            # Overall engagement
            ('engagement_score', models.IntegerField(
                default=0,
                help_text='Overall engagement score (0-100)'
            )),
            ('days_since_last_activity', models.IntegerField(
                default=0,
                help_text='Days since any recorded activity'
            )),
            
            # Metadata
            ('last_calculated_at', models.DateTimeField(
                auto_now=True,
                help_text='When metrics were last calculated'
            )),
        ],
        options={
            'db_table': 'members_engagement_metrics',
        },
    ),
    
    # Indexes
    migrations.AddIndex(
        model_name='engagementmetrics',
        index=models.Index(fields=['engagement_score'], name='members_en_engagem_idx'),
    ),
    migrations.AddIndex(
        model_name='engagementmetrics',
        index=models.Index(fields=['days_since_last_activity'], name='members_en_days_si_idx'),
    ),
]
```

---

## Dependencies

This migration depends on:
- `members.0008_*` (previous members migration)
- `accounts.000X_*` (User model must exist for assigned_to FK)

---

## Verification Commands

After migration is generated and applied:

```bash
# Generate migration
python manage.py makemigrations members

# Verify migration
python manage.py sqlmigrate members 0009

# Apply migration
python manage.py migrate members

# Verify tables created
python manage.py dbshell
\dt members_*
\d members_follow_up
\d members_engagement_metrics
```

---

## Rollback Plan

If migration fails or needs to be rolled back:

```bash
# Rollback one migration
python manage.py migrate members 0008

# If tables were partially created, drop them manually
python manage.py dbshell
DROP TABLE IF EXISTS members_engagement_metrics CASCADE;
DROP TABLE IF EXISTS members_follow_up CASCADE;
```

---

## Data Integrity Checks

After migration, verify:

1. **No orphaned follow-ups**: All `member_id` values exist in `members_member`
   ```sql
   SELECT COUNT(*) FROM members_follow_up mf
   LEFT JOIN members_member m ON mf.member_id = m.id
   WHERE m.id IS NULL;
   -- Expected: 0
   ```

2. **No orphaned metrics**: All `member_id` values exist in `members_member`
   ```sql
   SELECT COUNT(*) FROM members_engagement_metrics me
   LEFT JOIN members_member m ON me.member_id = m.id
   WHERE m.id IS NULL;
   -- Expected: 0
   ```

3. **Unique constraint working**: Try to insert duplicate milestone for same member
   ```sql
   -- Should fail with unique constraint violation
   INSERT INTO members_follow_up (id, member_id, milestone, scheduled_for, created_at, updated_at)
   VALUES (gen_random_uuid(), '<existing_member_id>', 'DAY_7', NOW(), NOW(), NOW())
   ON CONFLICT DO NOTHING;
   ```

4. **OneToOne constraint working**: EngagementMetrics can only have one record per member
   ```sql
   -- Should fail with unique constraint violation
   INSERT INTO members_engagement_metrics (member_id, engagement_score, days_since_last_activity, last_calculated_at)
   VALUES ('<existing_member_id>', 0, 0, NOW())
   ON CONFLICT DO NOTHING;
   ```

---

## Post-Migration Tasks

After successful migration:

1. **Backfill follow-ups for existing active members** (optional):
   ```python
   # Run in Django shell
   from apps.members.models import Member, MembershipStatus
   from apps.members.signals import create_new_member_follow_ups
   
   active_members = Member.objects.filter(
       membership_status=MembershipStatus.ACTIVE,
       follow_ups__isnull=True  # No follow-ups yet
   )
   
   for member in active_members:
       create_new_member_follow_ups(
           sender=Member,
           instance=member,
           created=True
       )
   ```

2. **Generate initial engagement metrics**:
   ```bash
   # Run Celery task manually
   python manage.py shell
   >>> from apps.members.tasks import recalculate_engagement_metrics
   >>> recalculate_engagement_metrics()
   ```

3. **Verify Celery beat schedule**:
   ```bash
   celery -A config inspect scheduled
   # Should show:
   # - member-follow-up-reminders (hourly)
   # - recalculate-engagement-metrics (daily)
   # - flag-absent-members (weekly)
   ```

---

## Known Issues & Workarounds

### Issue 1: Large member population backfill

**Problem**: Backfilling follow-ups for 10,000+ existing members may timeout

**Solution**: Use batched approach
```python
from django.db import transaction
from apps.members.models import Member, MembershipStatus

batch_size = 100
members = Member.objects.filter(
    membership_status=MembershipStatus.ACTIVE,
    follow_ups__isnull=True
)

for i in range(0, members.count(), batch_size):
    batch = members[i:i+batch_size]
    with transaction.atomic():
        for member in batch:
            create_new_member_follow_ups(Member, member, True)
    print(f"Processed {i + len(batch)} members")
```

### Issue 2: Engagement metrics calculation timeout

**Problem**: First run of `recalculate_engagement_metrics` may timeout with large dataset

**Solution**: Use chunked processing or Celery chord
```python
# Option A: Add to task (recommended)
from celery import chord, group

@shared_task
def recalculate_engagement_for_member(member_id):
    """Calculate metrics for single member."""
    # ... single member logic ...

@shared_task
def recalculate_engagement_metrics_chunked():
    """Dispatch calculation as parallel tasks."""
    active_members = Member.objects.filter(
        membership_status=MembershipStatus.ACTIVE
    ).values_list('id', flat=True)
    
    # Create parallel tasks
    tasks = group(
        recalculate_engagement_for_member.s(str(member_id))
        for member_id in active_members
    )
    tasks.apply_async()
```

---

## Environment Setup Instructions

To enable migration generation:

```powershell
# Navigate to project
cd "c:\Users\MY PC\Downloads\chapelflow-backend\chapelflow"

# Create virtual environment
python -m venv venv

# Activate
.\venv\Scripts\Activate.ps1

# Install dependencies
pip install -r requirements.txt

# Set environment variables (copy .env.example to .env first)
# Ensure DATABASE_URL, REDIS_URL, etc. are configured

# Generate migrations
python manage.py makemigrations members

# Review generated migration
# File will be: apps/members/migrations/0009_phase11_engagement_followup.py

# Apply migration
python manage.py migrate
```

---

**Status**: Documentation complete. Migration generation requires environment setup.
