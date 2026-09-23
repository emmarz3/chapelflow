# ChapelFlow remaining-work documentation

**Reviewed:** September 9, 2026  
**Scope:** React frontend, Django API (`chapelflow-backend`), deployment, and
the requirements recorded in the repository's phase/audit documents.

## How to read this document

This is the authoritative working backlog derived from the available project
evidence. It is not a verbatim copy of historical chat prompts: those prompt
transcripts are not stored in this workspace. Where a phase report describes a
requirement, it is treated as **prompt/phase evidence**. Where the current code
contains an explicit gap, it is treated as **code evidence**.

Task labels:

- **[CODE]** Current source code shows the work is incomplete.
- **[AUDIT]** A phase requirement is implemented or claimed, but has not been
  proven at runtime; complete it by executing the stated acceptance checks.
- **[OPS]** Requires infrastructure, credentials, chapel policy, or another
  decision outside source code.
- **[DONE]** Implemented and verified by the focused acceptance tests.

Items explicitly excluded: abstract base-class methods in `StorageService` and
`PaymentService`, normal `PENDING` model values, and development fallbacks that
are deliberately used only outside production.

## Release gate — must complete before production

| ID | Type | Remaining task | Evidence | Completion criteria |
| --- | --- | --- | --- | --- |
| RG-01 | [DONE] | Remove the insecure Django `SECRET_KEY` fallback. | `config/settings/base.py`; verified September 18, 2026 | Production startup fails if `SECRET_KEY` is absent or equals the development value; focused production/deployment checks pass (`14 passed`). |
| RG-02 | [AUDIT] | Run the production-PostgreSQL parallel-worker rehearsal for the now retryable, atomic, idempotent scheduled reconciliation. | Implementation and focused retry/idempotency tests completed September 18, 2026 | Parallel PostgreSQL workers create no duplicate reconciliation results or alerts; focused SQLite checks currently pass. |
| RG-03 | [OPS] | Implement encrypted, off-site PostgreSQL backups, retention, restore instructions, and regular restore tests. Define RPO/RTO. | Phase 19/20 audits | Scheduled backup succeeds; a restore drill meets the approved RPO/RTO. |
| RG-04 | [OPS] | Configure production dependencies: PostgreSQL, Redis, object storage, SMTP, Paystack/Flutterwave, Termii, FCM, maps, livestream, and approved upload scanning. | `.env.example`; `docs/PRODUCTION_CHECKLIST.md` | Readiness passes and each enabled provider is tested in sandbox/production-safe mode. |
| RG-05 | [AUDIT] | Execute Django checks, migrations, the full test suite, security tests, performance tests, and the frontend's API-mode contract/e2e tests. | Phase 20 reports record these as unexecuted | CI stores passing results; migration check is clean; failed-path tests are included. |
| RG-06 | [AUDIT] | Perform a production-like release rehearsal and rollback rehearsal. | Phase 20 deployment audit | Fresh environment deploys, migrates, starts web/Celery, serves readiness, processes a job/upload, and rolls back safely. |
| RG-07 | [AUDIT] | Verify the critical security paths against running services. | Phase 18/20 audits | Tests cover login/MFA/token rotation, rate limits, RBAC, mass assignment, IDOR/cross-branch access, webhook signatures, uploads, and pastoral privacy. |

## Required backend implementation work

| ID | Type | Phase / area | Remaining task | Acceptance criteria |
| --- | --- | --- | --- | --- |
| BE-01 | [CODE] | Phase 15 — reports | Add retry/backoff, idempotent completion handling, bounded execution, progress reporting, and chunking for large report jobs. | Transient storage/provider failure retries; completed jobs are not regenerated; large fixtures do not exhaust worker memory. |
| BE-02 | [DONE] | Member import | Notify the requesting user with the import result summary. | Implemented and verified September 18, 2026: success, fatal failure, and revoked-permission paths notify only the requesting user; focused tests pass. |
| BE-03 | [CODE] | Prayer | Build consent-based public-prayer broadcasting: preference, audience scope, unsubscribe behaviour, and delivery queue. | Only opted-in, authorized fellowship recipients receive PUBLIC requests; private/pastoral details never fan out. |
| BE-04 | [AUDIT] | Phase 2 — account security | Add account lockout/progressive protection for repeated failed logins and MFA recovery codes if these are still required by the agreed specification. | Brute-force and lost-device tests pass without enabling account enumeration. |
| BE-05 | [AUDIT] | Phase 4 — members | Test member merge, duplicate prevention, transfers, and household boundaries with every linked record type. | Giving, attendance, registrations, volunteer and group records remain correct; cross-branch links are rejected. |
| BE-06 | [AUDIT] | Phase 5 — visitors | Verify visitor conversion and follow-up automation; add automatic follow-up creation/analytics only where the agreed phase requirement requires them. | Duplicate submission, conversion, reminder, and conversion-rate tests pass. |
| BE-07 | [AUDIT] | Phase 6 — groups | Verify leadership transfer and hierarchy constraints. | Ineligible leader assignments and invalid/cyclic hierarchy changes are rejected. |
| BE-08 | [AUDIT] | Phase 7 — events | Verify recurrence generation, capacity/waitlist transitions, reminders, and concurrent registration. | Concurrent registration cannot exceed capacity or duplicate a member registration. |
| BE-09 | [AUDIT] | Phase 8 — attendance | Verify QR expiry, device authentication, offline reconciliation, manual check-in, and concurrent scans. | Expired/replayed tokens are denied and duplicate attendance rows cannot be created. |
| BE-10 | [AUDIT] | Phase 9 — volunteers | Verify availability conflict detection, assignment notifications, roster lifecycle, and skills matching. | Conflicting assignments are rejected and state transitions/audit records are correct. |
| BE-11 | [AUDIT] | Phase 10 — communications | Verify targeting, communication preference enforcement, real SMS/FCM delivery, failure/retry handling, and provider delivery callbacks. | No recipient outside the permitted audience is contacted; configured providers transition notifications correctly. |
| BE-12 | [AUDIT] | Phase 11 — engagement | Verify engagement calculation and refresh/reminder schedules; document the metric refresh policy. | Expected sample data produces correct metrics and reminders run exactly once. |
| BE-13 | [AUDIT] | Phase 12/14 — finance | Test webhooks and all money-changing paths under concurrency; add row locks/constraints wherever a measured race remains. | Duplicate gateway events and parallel updates never alter a confirmed payment or balance incorrectly. |
| BE-14 | [AUDIT] | Phase 13 — privacy | Run visibility and cross-branch tests for prayer and pastoral records. | PUBLIC/CHURCH/LEADERSHIP/PRIVATE policies are enforced for list and direct-ID access. |
| BE-15 | [AUDIT] | Phase 16/17 — dashboards and branches | Validate dashboard metric accuracy, authorization, aggregation, performance, and branch-transfer isolation. | Known fixture totals match output and unauthorized branches are never disclosed. |

## Reliability, performance, and operations

| ID | Type | Remaining task | Completion criteria |
| --- | --- | --- | --- |
| OP-01 | [CODE] | Set explicit HTTP timeouts and bounded retries for every external dependency; add circuit breakers where repeated provider failure could exhaust workers. | Simulated slow/failing providers cannot block all workers or cause an unbounded retry loop. |
| OP-02 | [OPS] | Configure graceful Gunicorn and Celery shutdown behaviour. | In-flight work finishes or returns to the queue safely during termination. |
| OP-03 | [AUDIT] | Measure baseline API, query, queue, and report performance; run concurrency/load tests. | P50/P95/P99, capacity, queue depth, and database/worker limits are documented and meet agreed targets. |
| OP-04 | [CODE] | Adopt a measured cache strategy for expensive dashboards/reports with invalidation rules. | Cache keys, TTLs, invalidation, and bypass behaviour are tested. |
| OP-05 | [OPS] | Configure monitoring, structured log retention, alerting, and a post-deploy smoke test. | Alerts fire for failed readiness, backup, queue, error-rate, and provider-delivery thresholds. |
| OP-06 | [OPS] | Publish operational runbooks: installation, configuration, deployment, backup/restore, rollback, monitoring, incident response, and troubleshooting. | A new operator can execute each procedure in a rehearsal. |

## Frontend and product acceptance work

| ID | Type | Remaining task | Completion criteria |
| --- | --- | --- | --- |
| FE-01 | [AUDIT] | Run backend-connected contract tests for every frontend endpoint, field, enum, pagination shape, and normalized error response. | The React API layer passes against a real Django test environment. |
| FE-02 | [OPS] | Replace generated/preview content with approved institutional photography, public copy, contacts, map, and livestream details. | Production values are approved and injected through configuration/CMS. |
| FE-03 | [AUDIT] | Test QR camera/kiosk flows on actual Android/iOS usher devices and low-bandwidth conditions. | Scan, permission denial, offline queue, retry, and fallback/manual check-in are signed off. |
| FE-04 | [AUDIT] | Complete WCAG 2.2 AA acceptance checks. | Keyboard, screen-reader, contrast, zoom, reduced-motion, loading, error, and empty states are verified. |
| FE-05 | [OPS] | Complete the Nigerian legal, privacy, safeguarding, retention, deletion/anonymisation, and identity-verification procedures. | Policy owner approves the procedures and support/privacy contacts are published. |

## Production configuration checklist

- [ ] Set exact HTTPS origins, secure cookies, CSRF trusted origins, CSP, HSTS,
  referrer policy, and permissions policy.
- [ ] Apply migrations and verify database constraints/indexes, especially
  attendance uniqueness and active-session behaviour.
- [ ] Store database, Django, provider, administrator, usher, and signing
  secrets in the deployment secret manager; do not commit them.
- [ ] Run frontend typecheck, lint, unit tests, build, desktop/mobile Playwright,
  Django tests, deployment checks, and migration dry-run in CI.
- [ ] Confirm the chapel's student-identity review process before administrator
  approval of registrations.

## Evidence and known limitations

Primary requirement/audit sources:

- `docs/PRODUCTION_CHECKLIST.md`
- `chapelflow-backend/PHASE20_VERIFICATION_MATRIX.md`
- `chapelflow-backend/PHASE20_FINAL_REPORT.md`

Current-source checks used to prevent stale audit findings from being copied
unchanged:

- `apps/finance/services.py` already uses an atomic transaction and
  `select_for_update()` for payment-webhook processing. The outstanding
  concurrency task is to test all finance paths and harden the scheduled
  reconciliation task.
- `apps/notifications/providers.py` includes Termii and FCM implementations
  but returns `STUBBED` without production credentials. Provider setup and live
  delivery verification therefore remain open.
- `apps/uploads/storage.py` and `apps/finance/services.py` intentionally use
  abstract methods in their base interfaces; those are not missing features.

Historical phase reports can disagree with later reports or current code. When
they do, the current implementation and an executable test take precedence.
