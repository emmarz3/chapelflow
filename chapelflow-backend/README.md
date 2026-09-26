# ChapelFlow CUC — University Edition Backend

Django + Django REST Framework backend for ChapelFlow CUC, a University
Chapel management platform. This is the **University Edition** — the
general Church Edition will be developed later, on the same codebase.

This backend has been **built, migrated, and smoke-tested against a real
PostgreSQL + Redis stack** (not just written) — see [Testing](#testing) and
[Known limitations](#known-limitations--what-to-check-before-production)
for what's actually been verified versus what still needs review.

## Phase 0 status (University Edition alignment)

This backend was originally built as a general Church Edition system and
has since gone through a **Phase 0 audit + remediation** against the
University Edition specification. See `docs/legacy_role_migration.md`
and `docs/university_structure.md` for the two biggest structural changes.
Summary of what changed and what's still open is in the Phase 0 report
(ask for it, or see the end of this README's [Known limitations](#known-limitations--what-to-check-before-production)
section).

## Architecture

```
                    CHAPELFLOW CUC
                         │
          ┌──────────────┴──────────────┐
          │                             │
       FRONTEND                    DJANGO ADMIN
 HTML/CSS/JS/PWA                  Internal Admin
          │
          │ HTTPS / REST  (/api/v1/...)
          ▼
    Django REST Framework
          │
    ┌─────┼──────────────────────────────┐
    │     │                              │
JWT Auth RBAC + Branch/Org Scoping Business Logic (services.py per app)
    │     │                              │
    └─────┼──────────────────────────────┘
          │
      Django ORM
          │
          ▼
      PostgreSQL
          │
    ┌─────┼─────────────┐
    │     │             │
 Redis  Celery      Cloud Storage
(cache) (async)    (Cloudinary/S3/local, pluggable)
```

20 Django apps under `apps/`: `accounts`, `organizations`, `university`,
`members`, `visitors`, `households`, `ministries`, `groups`, `events`,
`attendance`, `finance`, `communications`, `notifications`, `prayer`,
`pastoral`, `volunteers`, `reports`, `uploads`, `audit`, `dashboard`.

Two independent hierarchies hang off `Member` (see
`docs/university_structure.md` for the full picture and why they're kept
separate): the **academic** side (`apps.university`: University → College
→ Department) and the **Chapel** side (`apps.organizations` Branch +
`apps.ministries` Group: Fellowship / Unit / Ministry).

## Role model (University Edition)

Current roles: `SUPER_ADMIN`, `CHAPLAIN`, `CHAPEL_ADMIN`,
`FELLOWSHIP_LEADER`, `UNIT_HEAD`, `MINISTRY_GROUP_LEADER`, `MEMBER`,
`VISITOR`. **"Staff Community" is not a role** — it's a Member
classification (`Member.community`), alongside `STUDENT`.

Legacy roles (`PASTOR`, `FINANCE_OFFICER`, `COMMUNITY_LEADER`,
`MINISTRY_LEADER`, `DEPARTMENT_LEADER`, `UNIT_LEADER`, `VOLUNTEER`) remain
valid on existing rows but are no longer assignable to new users. See
`docs/legacy_role_migration.md` for the full migration plan — some
mappings were safe to automate, others were deliberately left for manual
review rather than guessed at.

Chaplain gets organization/university-wide read scope (every branch under
their own Organization), Chapel Admin is branch-scoped, Super Admin is
global. Chaplain never receives Super Admin's system-configuration access
— it's a permission grant, not a superuser flag.

Fellowship Leader / Unit Head / Ministry-Group Leader are scoped to only
the Group(s) they actively lead, sourced from `apps.groups.GroupMembership`
(`role=LEADER`), not the legacy single `Group.leader` FK — so a Fellowship,
Unit, or Ministry can have more than one active leader and every one of
them is correctly scoped (`common/permissions/scoping.py::led_group_ids`).

## MFA (spec section 18)

`POST /api/v1/auth/mfa/enroll/` generates a TOTP secret + `otpauth://`
provisioning URI (+ base64 QR code if the `qrcode` package is installed —
degrades gracefully to URI-only if not). `POST /api/v1/auth/mfa/confirm/`
validates a 6-digit code and flips `User.mfa_enabled`. Any role listed in
`settings.MFA_ENFORCED_ROLES` is blocked from every RBAC-protected
endpoint (`common.permissions.rbac.HasRolePermission` /
`IsFinanceAuthorized`) until `mfa_enabled` is `True` — including Super
Admin, if Super Admin is in that list; this check runs before the Super
Admin bypass on purpose. The enroll/confirm endpoints themselves stay
reachable throughout (`IsAuthenticated` only), so a blocked user can
always complete setup. `MFA_ENFORCED_ROLES` is `[]` in `config/settings/test.py`
by default so it doesn't affect unrelated fixtures; `tests/accounts/test_mfa.py`
exercises enforcement explicitly via `@override_settings`.

`POST /api/v1/auth/mfa/reset/` `{"user_id": "...", "reason": "..."}` —
administrative reset for a user who lost their authenticator device.
Chapel Admin or Super Admin only (`common.permissions.rbac.IsChapelAdminOrSuperAdmin`);
a Chapel Admin may only reset users in their own branch (a cross-branch
attempt 404s, not 403 — consistent with this codebase's direct-ID
handling elsewhere, so it never confirms another branch's user exists).
Resets `MFADevice.confirmed` and `User.mfa_enabled` back to `False` and
writes an `AuditAction.MFA_RESET` entry; the user re-enrolls normally via
`/mfa/enroll/` afterward (which issues a brand new secret regardless).

## Member creation (mandatory rule)

**Normal administrators cannot create Member records manually** —
`POST /api/v1/members/` is blocked for every role, including Super Admin.
The only two ways a Member is created:
1. Public self-registration — `POST /api/v1/auth/register/` (creates
   User + Member together, atomically).
2. Staff-assisted conversion from a Visitor record —
   `POST /api/v1/visitors/{id}/convert/` (see the Visitor pipeline below).

Historical bulk import remains available as an explicitly separate
data-migration workflow: `POST /api/v1/members/import/`.

## Visitor / first-timer pipeline

`apps.visitors` implements the full spec pipeline: public
`POST /api/v1/visitors/first-timer-form/` (no auth) → staff-logged
follow-ups (`POST /api/v1/visitors/{id}/follow-up/`) → optional conversion
to a full Member (`POST /api/v1/visitors/{id}/convert/`). This is separate
from `apps.attendance.VisitorAttendance`, which only records a check-in —
the two are now linked via `VisitorAttendance.visitor_record` but track
different things.

## Multi-leader groups & the deprecated `leader` field

`apps.ministries.Group.leader` (a single FK) is **deprecated** — see its
`help_text` and the `Group` class docstring — but intentionally not
dropped yet (schema-change risk; see `docs/university_structure.md` for
the removal plan). `GroupSerializer` exposes both: `leader` (deprecated,
still writable for backward compatibility with existing integrations) and
`leaders` (the real, read-only, multi-leader-capable listing, built
purely from active `apps.groups.GroupMembership` rows via
`apps.groups.serializers.active_leader_memberships()`). New code should
always read/write `leaders`/`GroupMembership`, never `leader`.

## Reports: multi-format export engine

`apps.reports.services` implements real CSV, Excel (`openpyxl`), and PDF
(`reportlab`) exporters — `export_report_rows(export_format, rows, title)`
dispatches to the right one and raises `ValueError` for anything else
(no silent fallback to CSV, which was the previous bug: `run_report_job`
used to hardcode CSV regardless of what `ReportJob.export_format` said).
`GET /api/v1/reports/jobs/formats/` reports exactly which formats are
implemented, sourced from the same `REPORT_EXPORTERS` dict `run_report_job`
uses — the two can't drift out of sync.

## Communications: delivery-state tracking

`apps.notifications.NotificationStatus` now has five states: `PENDING`,
`SENT`, `DELIVERED`, `FAILED`, `STUBBED`. Stub SMS/push providers
(`apps/notifications/providers.py`) return `{"status": "stubbed", ...}`,
and `deliver_notification` now checks for that and marks `STUBBED` rather
than `SENT` — this was the exact bug the prior README warned about
("Do not mark an SMS/push delivery as 'sent' when the provider is only
stubbed") and has now been fixed, not just documented as a risk.
`mark_notification_delivered()` is a webhook-ready handler for providers
that confirm delivery asynchronously (only transitions `SENT` → `DELIVERED`,
never touches `STUBBED`/`FAILED`/`PENDING`). Every `Notification` fanned
out from an `Announcement` is now linked via `source_announcement`, so
`GET /api/v1/communications/announcements/{id}/delivery-status/` can roll
up real per-status counts for that campaign.

## Security model (read this before adding a new endpoint)

Every endpoint touching organization-sensitive data combines two independent
layers — **both are required, neither substitutes for the other**:

1. **RBAC** — `common/permissions/rbac.py`. `HasRolePermission` checks the
   requesting user's role against a `permission_action_map` each ViewSet
   declares, backed by a DB-editable `RolePermission` table (seeded by
   `scripts/seed_roles.py`).
2. **Branch scoping** — `common/permissions/scoping.py`. `BranchScopedQuerysetMixin`
   filters querysets so a non-super-admin only ever sees rows in their own
   branch. **A user cannot bypass this by editing an ID in a URL** — the
   record is filtered out of the queryset entirely, so direct-ID access
   returns `404`, not `403` (a `403` would itself leak that the record
   exists in another branch).

**Important gotcha (we hit this bug and fixed it during development):** if a
ViewSet mixes in `BranchScopedQuerysetMixin` but then defines its own
`get_queryset()`, Python's method resolution means the subclass's version
wins outright and the mixin's filtering is **silently never applied** — a
real branch-isolation bypass. To make this structurally impossible, the
mixin now exposes `get_queryset()` itself (always applies the filter) and
expects subclasses to override `get_base_queryset()` instead for
`select_related`/`prefetch_related`/custom joins. If you add a new
branch-scoped ViewSet, use `get_base_queryset()`, never `get_queryset()`.

Pastoral records (`apps/pastoral`) get an additional, stricter layer:
`IsPastoralAuthorized` re-checks access at the object level on every single
retrieve/update/destroy, on top of queryset filtering, because this is the
most sensitive data in the system.

## Setup

### Bootstrap the single Super Admin

Set `SUPER_ADMIN_EMAIL` and `SUPER_ADMIN_PASSWORD` as environment variables.
On Render, clear any custom **Docker Command** override in the dashboard so
the Dockerfile command runs migrations and bootstraps the admin and chapel at
container startup. Locally, run `python manage.py bootstrap_super_admin`.
The command is idempotent for that email and refuses to create a second Super
Admin or proceed when it finds conflicting records. It never reads credentials
from source control.

For a local test run without PostgreSQL, set `CHAPELFLOW_TEST_SQLITE=1` before
running Django tests. CI and production-like test runs still use `DATABASE_URL`.

### Option A — Docker (recommended)

```bash
cp .env.example .env
docker compose up --build
```

This starts Postgres, Redis, the Django app (migrates + collects static +
gunicorn), a Celery worker, and Celery beat.

### Option B — Local Python environment

Requires Python 3.12+, PostgreSQL, and Redis running locally.

```bash
cp .env.example .env
pip install -r requirements.txt --break-system-packages   # or use a venv

# Create the DB (adjust to your local Postgres setup)
createuser chapelflow --pwprompt   # password: chapelflow
createdb chapelflow -O chapelflow

python manage.py migrate
python scripts/seed_roles.py        # grants role -> permission mappings
python scripts/seed_demo_data.py    # demo org/branch/users, password: ChangeMe123!

python manage.py runserver
```

In a separate terminal, for background jobs (imports, reports, notifications):

```bash
celery -A config worker --loglevel=info
```

### Creating an admin account manually

```bash
python manage.py createsuperuser  # prompts for email + password; role=SUPER_ADMIN automatically
```

## Authentication

Two login flows, both hitting `POST /api/v1/auth/login/`:

**Students/members** (matriculation number):
```json
{"matric_no": "SWE/2024/005", "password": "..."}
```

**Staff/admins** (email):
```json
{"email": "admin@example.com", "password": "..."}
```

Matric numbers are validated against `MATRIC_NUMBER_REGEX` (default
`^[A-Z]{2,6}/[0-9]{2,4}/[0-9]{3,6}$`, configurable via `.env` since real
institutional formats vary) and normalized to uppercase on save and on
login, so `swe/2024/005` and `SWE/2024/005` are the same account.

Response:
```json
{
  "success": true,
  "message": "Login successful.",
  "data": {
    "access": "...", "refresh": "...",
    "user": {"id": "...", "matric_no": "...", "role": "...", "branch": "...", ...}
  }
}
```

Use `Authorization: Bearer <access>` on subsequent requests. Refresh via
`POST /api/v1/auth/refresh/`, logout (blacklists the refresh token) via
`POST /api/v1/auth/logout/`.

## API surface

All endpoints are under `/api/v1/`. Full interactive docs (OpenAPI/Swagger)
at `/api/docs/` once the server is running. Key groups:

| Area | Base path |
|---|---|
| Auth | `/api/v1/auth/` |
| Organizations/Branches | `/api/v1/organizations/`, `/api/v1/branches/` |
| Members | `/api/v1/members/` (+ `/import/`, `/{id}/regenerate-qr/`) |
| Households | `/api/v1/households/` |
| Ministries/Groups | `/api/v1/groups-catalog/`, `/api/v1/group-memberships/` |
| Events | `/api/v1/events/`, `/api/v1/event-registrations/` |
| Attendance | `/api/v1/attendance/qr-check-in/`, `/manual/`, `/check-in/`, `/sync/`, `/sessions/`, `/records/` |
| Finance | `/api/v1/giving/`, `/pledges/`, `/payments/`, `/payments/webhook/<provider>/` |
| Communications | `/api/v1/communications/announcements/` |
| Notifications | `/api/v1/notifications/` |
| Prayer | `/api/v1/prayer/requests/`, `/notes/` |
| Pastoral | `/api/v1/pastoral/cases/`, `/notes/` |
| Volunteers | `/api/v1/volunteers/profiles/`, `/assignments/` |
| Reports | `/api/v1/reports/jobs/` (async — returns a job, poll for `file_url`) |
| Dashboard | `/api/v1/dashboard/admin/`, `/pastor/`, `/finance/`, `/member/` |
| Uploads | `/api/v1/uploads/upload/` |
| Audit | `/api/v1/audit/logs/` (read-only) |

Every response follows `{"success": bool, "message": str, "data": ..., "errors"?: {...}}`.
Paginated list responses add a `"pagination"` block.

## Testing

```bash
python -m pytest tests/ -v
```

109 tests currently cover the security-critical guarantees the spec calls
out explicitly, including three Phase 0 passes of additions:

- **`tests/accounts/test_auth.py`** — matric number normalization/validation,
  case-insensitive login, invalid credentials return a clean `400` (not a
  `500`), inactive accounts can't log in.
- **`tests/members/test_branch_isolation.py`** — a branch admin cannot list
  or fetch-by-ID another branch's members (regression test for the bug
  described above), super admin sees everything, an admin with no branch
  assigned sees nothing (fail closed), unauthorized roles can't create members.
- **`tests/members/test_phase0_member_lifecycle.py`** — manual member
  creation is blocked for every role including Super Admin (even with
  `MEMBERS_CREATE` granted); the import-CSV path remains available as the
  separate migration workflow; public self-registration creates User+Member
  atomically; deactivate/reactivate/merge all write an audit trail.
- **`tests/members/test_chaplain_scope.py`** — Chaplain sees every branch in
  their own Organization; Chapel Admin remains scoped to their own branch only.
- **`tests/university/test_structure.py`** — University/College/Department
  is genuinely separate from Chapel Groups; reads are public (needed for
  registration-form dropdowns), writes require system-config permission.
- **`tests/visitors/test_visitor_pipeline.py`** — the full Visitor →
  First-Timer Form → Follow-Up → Optional Conversion pipeline; branch
  isolation on visitor records; a visitor can't be converted twice.
- **`tests/accounts/test_mfa.py`** — enrollment returns a secret +
  provisioning URI, re-enrollment issues a fresh secret; confirmation with
  a valid TOTP code enables MFA, a wrong/malformed code doesn't; a role in
  `MFA_ENFORCED_ROLES` is blocked from RBAC-protected endpoints until MFA
  is completed (including Super Admin, if listed) but can always still
  reach enroll/confirm.
- **`tests/members/test_multi_leader_scoping.py`** — a Fellowship Leader
  sees only the Fellowship(s) they actively lead via `GroupMembership`,
  not `Group.leader`; two independent leaders of the same Group both see
  it (proves multi-leader support); a role's Group-type restriction is
  enforced (a Unit Head's Fellowship leadership doesn't leak through);
  Chapel Admin is unaffected by leader-scoping.
- **`tests/members/test_phase0_endpoint_sweep.py`** — direct-ID access to
  another branch's Giving/EventRegistration/Upload record 404s (not 403,
  avoiding existence leakage); pledges and uploads list-scope correctly;
  the new public events endpoint needs no auth and excludes non-public
  events; the ordinary events list still requires auth+permission.
- **`tests/accounts/test_mfa.py`** administrative-reset additions —
  Chapel Admin resets a user's MFA within their own branch; a cross-branch
  reset attempt 404s; Super Admin can reset across branches; a plain
  Member gets 403; the reset writes an audit log entry; the full loop
  (enrolled → admin reset → user re-enrolls → confirms → regains access)
  works end to end.
- **`tests/groups/test_leader_deprecation.py`** — `GroupSerializer.leaders`
  is built purely from active `GroupMembership` rows, never from the
  deprecated `leader` FK (proven by deliberately setting `leader` to an
  unrelated member and confirming it never appears in `leaders`); inactive
  `GroupMembership` leadership rows are excluded; the shared
  `active_leader_memberships()` helper matches the serializer's own logic.
- **`tests/reports/test_export_formats.py`** — CSV/Excel/PDF exporters
  produce real, parseable output (a genuine `openpyxl`-readable workbook,
  a PDF with the actual `%PDF` file signature, not stubs); `ReportJob`
  end-to-end for all three `export_format` values via the real
  `StorageService`; an unknown report type fails the job cleanly with
  `FAILED` + an error message, not a silent CSV fallback.
- **`tests/communications/test_delivery_states.py`** — a real (locmem)
  email send is marked `SENT`; stubbed SMS/push sends are marked
  `STUBBED`, never `SENT`; `mark_notification_delivered` only transitions
  `SENT` → `DELIVERED`, never touches `STUBBED`; the per-Announcement
  delivery-status rollup aggregates correctly and respects branch scoping.
- **`tests/attendance/test_attendance.py`** — QR check-in creates a record;
  a duplicate check-in for the same member+session returns the *same*
  record instead of creating a second one; invalid QR tokens are rejected;
  offline sync is idempotent under replay (same `client_record_id` twice →
  `synced` then `already_synced`, never two rows).
- **`tests/integration/test_pastoral_privacy.py`** — an unrelated member
  can't list or fetch another member's pastoral case; the member the case
  is about can see it; the assigned pastor can see it; any pastoral-access
  role in the branch can see it (oversight); a finance officer cannot.
- **`tests/finance/test_payments.py`** — members can't reach finance
  endpoints; invalid webhook signatures are rejected; valid webhooks
  confirm the payment; a replayed webhook (gateways redeliver) is a safe
  idempotent no-op, not a duplicate charge.

Run with real Postgres, not sqlite (settings force `config.settings.test`,
which still expects `DATABASE_URL` — a local Postgres instance is required).
All 109 tests + migrations were verified in this session against a real
Postgres 16 + Redis instance, not just written.

## Operational endpoints (health / readiness)

Three unauthenticated endpoints for infra/orchestrators, added in Phase 1
(`common/health.py`) — none of them return connection strings, hostnames,
or credentials, even on failure:

- `GET /health/` and `GET /liveness/` — pure liveness. No dependency I/O
  at all (verified by `tests/common/test_health.py`, which asserts the
  database is never even queried) — this is what the Docker
  `HEALTHCHECK` hits, and what a dumb uptime monitor should hit. It must
  stay meaningful even when Postgres or Redis is having a bad moment.
- `GET /readiness/` — checks Postgres, Redis, and Celery-broker
  reachability; returns `200` with `{"status": "ok", "checks": {...}}` or
  `503` with the same shape naming which component is down. **Scope
  limit, stated plainly:** the Celery check only proves the broker socket
  is reachable, not that a worker is running or keeping up with the
  queue — real worker monitoring needs Flower/Celery events, which this
  endpoint doesn't attempt.

Deployment-readiness checks (`common/checks.py`) run via
`python manage.py check --deploy` — deliberately scoped to what's
project-specific (storage/email/payment/SMS credentials) rather than
duplicating Django's own built-in `--deploy` checks for `SECRET_KEY`,
`DEBUG`, and `ALLOWED_HOSTS` emptiness, which already cover those. Plain
`manage.py check` (what CI and local dev run constantly) is unaffected —
these only fire under `--deploy`.

## Storage & payment provider abstraction

`apps/uploads/storage.py` and `apps/finance/services.py` implement the
StorageService and PaymentService abstractions called for in the spec —
switching `STORAGE_PROVIDER=local|cloudinary|s3` or adding a new payment
gateway touches only these files, never call sites elsewhere in the codebase.
The large-CSV-import path (`apps/members/views.py` + `apps/members/tasks.py`)
now also goes through `StorageService` rather than a local temp file, fixing
a Phase 0 bug where the Celery worker (separate filesystem from the web
container) couldn't read a path written to the web container's `/tmp`.

## Known limitations / what to check before production

This was built and smoke-tested in an extended session against a real (but
disposable) database. Before shipping to real users:

- **Phase 1 scoping sweep found and fixed a real cross-branch data leak**:
  `AuditLogViewSet` had no branch scoping at all, so any `CHAPEL_ADMIN`
  (a branch-scoped role that holds `AUDIT_VIEW` by default) could read
  every branch's audit trail — MFA-reset reasons, financial actions,
  role changes — system-wide. Fixed by scoping through the acting user's
  branch (`user__branch`); AuditLog has no branch FK of its own, so this
  doesn't (and can't, without a bigger feature) attribute an action to
  the branch of the *resource* it touched, only to the branch of the
  *actor* who performed it. Five more viewsets had the same
  duplicated-hand-rolled-scoping root cause, minus the leak (they
  under-scoped Chaplain to a single branch instead of their whole
  Organization, rather than over-exposing anyone): `BranchViewSet`,
  `VolunteerProfileViewSet`, `VolunteerAssignmentViewSet`,
  `AttendanceRecordViewSet`, `VisitorAttendanceViewSet`. All six are now
  on `BranchScopedQuerysetMixin` (extended with an `id`-self-lookup mode
  for the Branch-is-the-model case) and covered by
  `tests/audit,organizations,volunteers,attendance/test_branch_isolation.py`.
  The dashboard app (`apps/dashboard/views.py`) has the same
  Chaplain-under-scoping pattern in `_branch_qs_or_all` — found, but
  deliberately left for the Phase 3 Chaplain-visibility pass rather than
  fixed here, since dashboards are custom aggregation views, not
  `ModelViewSet.get_queryset()` duplication, and Phase 3 already owns
  verifying Chaplain's dashboard visibility.
- **drf-spectacular can't generate a schema for 21 existing plain
  `APIView`s** across `apps/accounts`, `apps/attendance`,
  `apps/dashboard`, `apps/finance`, and `apps/uploads` (no
  `serializer_class` / `@extend_schema`, so `/api/schema/` silently
  falls back to a generic shape for each). Pre-existing, not introduced
  this round — found during the Phase 1 Swagger/OpenAPI audit and not
  fixed here (real fix is ~20 files' worth of explicit response
  serializers); the 2 new health views added this round do have proper
  `@extend_schema` responses so as not to add to the count.
- **MFA enrollment/confirmation/administrative reset are all implemented**
  (`POST /api/v1/auth/mfa/enroll/` + `/confirm/` + `/reset/`) and enforced
  for any role in `MFA_ENFORCED_ROLES` via `common.permissions.rbac`. Still
  worth checking before go-live: the `qrcode` package must actually be
  installed in production for the base64 QR image (it degrades to
  URI-only otherwise, which most authenticator apps also accept via
  manual entry).
- **Endpoint audit sweep (spec section 10) completed for finance,
  communications, reports, events, and uploads** — found and fixed two
  real gaps: `EventRegistrationViewSet` had a hand-rolled `get_queryset()`
  missing Chaplain org-wide scope, and `apps/uploads` had no RBAC
  permission check and no `get_object()`-protected detail route at all.
  Both are now on the shared `BranchScopedQuerysetMixin`. Finance,
  communications, and reports had no such gaps — they already used the
  mixin correctly and have no custom `get_object()` overrides to audit.
- **Multi-leader scoping implemented, `Group.leader` formally deprecated** —
  Fellowship Leader / Unit Head / Ministry-Group Leader scope off
  `apps.groups.GroupMembership` (`role=LEADER`), not the legacy single
  `Group.leader` FK, so a Group can have more than one active leader.
  `Group.leader` is marked deprecated in its own `help_text` and the
  `Group` docstring, kept only for backward compatibility, and its
  removal plan is documented in `docs/university_structure.md` — the
  column is intentionally not dropped yet.
- **Report export formats are real, not just claimed** — CSV, Excel
  (`openpyxl`), and PDF (`reportlab`) all produce genuine, parseable
  output; `apps.reports.services.export_report_rows` is what
  `run_report_job` actually calls, so the `GET .../formats/` endpoint and
  the real behavior can't drift apart the way CSV-always-regardless-of-
  `export_format` did before this was fixed.
- **Communications delivery states are now accurate** — stub SMS/push
  sends are marked `STUBBED`, never `SENT`; a `DELIVERED` state and a
  webhook-ready `mark_notification_delivered()` handler exist for when a
  real provider is wired up; per-`Announcement` delivery rollups are
  available via `GET .../delivery-status/`.
- **Tier 2 legacy role migrations require manual review** — run
  `python scripts/migrate_legacy_roles.py --report-tier-2` and resolve the
  CSV before removing `Roles.LEGACY_CHOICES` from the codebase. Verified
  idempotent (`--apply-tier-1` run twice migrates 0 users the second time)
  and non-mutating (`--report-tier-2` writes only a CSV) in this session.
  See `docs/legacy_role_migration.md`.
- **SMS and push notification providers are still stubs** (`apps/notifications/providers.py`)
  that log instead of sending — now correctly tracked as `STUBBED` rather
  than lying about it as `SENT`, but still not real sends. Wire up your
  actual SMS vendor (Termii, Africa's Talking, etc.) and FCM/APNs before
  relying on these channels.
- **The matric number regex is a sensible default, not a guarantee** — confirm
  it matches your actual institution(s)' format before onboarding real students;
  it's configurable via `MATRIC_NUMBER_REGEX` in `.env` without a code change.
- **Payment webhook signature verification is implemented for Paystack and
  Flutterwave** and covered by tests, but has not been tested against a real
  sandbox account from either provider — verify against their actual test
  webhooks before going live.
- **No rate-limit tuning done beyond sensible defaults** (`auth`: 10/min,
  `sync`: 30/min, `reports`: 20/min in `REST_FRAMEWORK.DEFAULT_THROTTLE_RATES`) —
  revisit under real load.
- **Frontend integration is not started.** This backend was built without
  the actual ChapelFlow frontend repository; connecting it requires
  inspecting the real frontend's expected request/response shapes and
  likely adjusting some serializer field names to match.

## Environment variables

See `.env.example` for the full list with defaults. Never commit a real `.env`.
