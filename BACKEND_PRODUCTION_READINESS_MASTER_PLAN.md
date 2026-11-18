# ChapelFlow backend production readiness master plan

**Baseline:** 7 November 2026. Scope: Django API, PostgreSQL, Redis, Celery, storage, external providers, and launch operations. This is an execution plan, not a claim that the backend is production ready. Use current code and recorded command output as evidence; older phase reports are historical. The requested deployment paths are Render and AWS. Email, payments, and private durable storage are launch requirements; SMS and push are later features.

## Current evidence

- Local SQLite suite: **850 passed, 1 skipped** before the final disabled-SMS regression test was added. Local PostgreSQL 17 suite: **851 passed, 1 skipped**, including that test. Both runs include two passing subtests. `manage.py check --settings=config.settings.test` passed and `makemigrations --check --dry-run` found no drift with PostgreSQL. GitHub CI on PostgreSQL 16 has been added but has not run remotely.
- A production `check --deploy` with temporary placeholder configuration returned **129 OpenAPI documentation warnings** after registering the cookie/bearer authenticator schema. This is a configuration smoke check with placeholders, not evidence of deployed settings or working providers. The remaining warnings need triage.
- `render.yaml` now separates release migrations/bootstrap from web startup. `infra/aws/` provides ECS API/worker/beat/release tasks, ALB, scoped S3 access, and private media configuration. Neither path has been deployed or validated in its target account. `vercel.json` identifies `https://chapelflow-api-yhqr.onrender.com` as the Vercel frontend's API target. A live `/health/` HEAD request on 7 November returned **503** with `x-render-routing: suspend-by-user`. The supplied Render and Vercel frontend roots both returned **200**, which does not prove the API works.
- A scheduled encrypted PostgreSQL backup workflow exists, but configuration, successful backup runs, restore, retention, and alerting have not been verified here. Prior audit notes say older public report exports may require provider-side revocation.
- Local frontend production build passed after removing SMS/push launch claims. Docker, Terraform, AWS CLI, Render CLI, and a valid GitHub CLI login are unavailable locally, so image and cloud deployment checks remain unverified.
- The local Django/React Playwright integration suite passed **2/2** in Chromium, covering registration, login/session restore, and embedded phone-preview login. It uses local SQLite and does not replace the deployed PostgreSQL/browser journey gate.

## P0 — establish a trustworthy release baseline

1. **Select the production target and launch feature set.** Identify the actual host, API/frontend origins, database, Redis, storage, mail, payment, SMS, and push providers. For each feature, mark *launch required*, *disabled*, or *later*. Record the deployed URL and environment ownership without storing secret values in the repository. **Done when:** there is one approved deployment topology and no UI/API claims a disabled channel works.
2. **Make backend CI authoritative.** Add a workflow using the project's supported Python version and PostgreSQL, plus Redis where integration tests require it. Run Django checks, migration drift check, and the complete backend suite. Keep SQLite as a fast local option, not the sole launch gate. Store test reports and make CI fail on test failures. **Done when:** a clean checkout builds and the full suite passes reproducibly in CI.
3. **Reconcile failing tests with the current API.** Triage every failure by reproducing it against source behavior. Update obsolete campaign tests to the draft → publish → scheduled/queued lifecycle and current routes; fix implementation defects where tests expose real breaks. Replace missing webhook expectations with tests for the supported provider callback flow, or implement that flow if it is launch required. Cover authorization, idempotency, preference opt-outs, and task failure paths. **Done when:** no stale test is silently skipped and both current and legacy test locations pass or obsolete tests are removed with a documented replacement.
4. **Close privacy and access-control launch gaps.** Re-run focused auth, MFA, branch isolation, prayer/pastoral privacy, moderation, attendance, finance, and report-download tests. Finish the privacy deletion/retention decision and safe completion flow tracked in `CHAPELFLOW_PRIVACY_AND_DATA_PROTECTION.md`. Inventory and revoke previously public report exports at the provider, then verify old direct links fail and new downloads require authorized, short-lived access. **Done when:** negative cross-user/cross-branch tests pass, no sensitive export is publicly retrievable, and privacy requests have an operable completion path.

## P0 — deploy and prove the runtime

5. **Configure production safely.** Supply a strong `SECRET_KEY`, exact `ALLOWED_HOSTS`, CORS/CSRF origins, secure cookie settings, `DATABASE_URL`, `REDIS_URL`, and credentials for every launch-required provider via the host's secret store. Use durable private media/report storage. Confirm proxy TLS headers only from the trusted edge. Run `manage.py check --deploy` with deployed settings and review each warning; treat ChapelFlow configuration warnings as release failures where the related feature is enabled. **Done when:** no launch-critical configuration warning remains and login, refresh, logout, CSRF rejection, and cross-origin rejection work from the real frontend origin.
6. **Make deployment and migration repeatable.** Build the Docker image in CI and deploy it to staging. Run migrations exactly once per release instead of relying on each web replica to migrate on startup; verify `bootstrap_*` commands are idempotent. Start and health-check API, worker, and beat; prove scheduled announcements/reminders execute. Rehearse a failed migration/deploy and a rollback using a disposable database. **Done when:** a fresh staging deployment succeeds from a clean database and a rollback procedure has been exercised.
7. **Verify data recovery and monitoring.** Confirm managed database backups or the repository backup workflow actually run, encrypt, retain, and alert on failure. Restore a backup to an isolated database and measure recovery time/data loss. Confirm file storage durability, error reporting, readiness checks, worker lag monitoring, and on-call alert destinations. **Done when:** a dated restore rehearsal and API/worker failure drill produce usable evidence.

## P1 — prove integrations and user journeys

8. **Exercise external providers in staging.** Test email verification/password reset; payment checkout and signed webhooks with provider sandbox accounts; private upload/download; and SMS/FCM only if those channels are launch required. Verify duplicate webhooks, retries, timeouts, and provider outages do not create duplicate financial or notification records. Providers that remain stubbed must be disabled or clearly marked unavailable in the product. **Done when:** each enabled provider has a successful and failure-path staging result.
9. **Run critical end-to-end journeys against PostgreSQL and the deployed frontend.** Cover registration → verification → login → profile, privileged MFA, branch-scoped staff actions, visitor conversion, attendance, giving/reconciliation, announcement publish/schedule/opt-out, moderation, and report export/download. Include a normal browser and the embedded mobile preview if supported. **Done when:** critical paths pass on the deployment topology and a previously recorded live 503/login loop is absent.
10. **Check load and concurrency at expected launch volume.** Measure representative API latency, DB connection use, expensive queries, worker throughput, and concurrent payment/attendance/announcement operations. Add indexes or capacity only for measured bottlenecks. **Done when:** agreed latency/error/queue thresholds hold in staging and concurrency does not duplicate records or cross tenant boundaries.

## P2 — documentation and polish

11. Resolve drf-spectacular authentication/serializer warnings for public API documentation; prioritize endpoints consumed by frontend or external clients. Pin and review dependencies, scan the built image, and record patch decisions. Reconcile older phase reports with current evidence so they do not imply a false launch sign-off.

## Release gate

Do not call the backend ready until **all P0 items** and every P1 item tied to an enabled launch feature are complete. The release record should contain: CI run and full test totals; migration and Docker build results; deployed `check --deploy` output; staging journey results; provider sandbox evidence; backup restore and rollback evidence; unresolved risks with an explicit owner; and the final deployed health/readiness status. Any failed authorization/privacy test, public sensitive export, unverified backup restore, broken core journey, or unavailable API is a no-go.

**Execution order:** 1 → (2, 3, 4 in parallel by workstream) → 5 → 6 → (7, 8, 9) → 10 → release gate. Item 11 can follow once P0/P1 risks are controlled.

## Open release evidence, 7 November 2026

The local code and test baseline is green, but the release gate remains **NO-GO**. The following checks need evidence from the target accounts and institution before either Render or AWS is declared ready:

| Gate | Evidence still required | Owner |
| --- | --- | --- |
| GitHub CI and image | Successful PostgreSQL 16/Redis CI run, Docker build, dependency/image scan; local `gh` authentication is invalid and Docker is unavailable. | Repository owner |
| Render | Resume the suspended API at `chapelflow-api-yhqr.onrender.com`; then verify secret/origin configuration, release migration, web/worker/beat health, browser login and rollback rehearsal. | Render account owner |
| AWS | Account/region/VPC/subnets/certificate, managed PostgreSQL and Redis, Secrets Manager values, `terraform validate/apply`, one-off release task, ECS health, backup/restore and rollback rehearsal. | AWS account owner |
| Providers | SMTP verification/reset, Paystack sandbox checkout and signed duplicate-webhook tests, private storage upload/download, provider outage and retry results. SMS/push remain disabled. | Provider account owner |
| Privacy | Approved retention/deletion exceptions and completion process; inventory and revoke legacy public exports at the storage provider, then verify old links fail. | University privacy owner |
| Operations | Dated restore drill, alert destinations and failure drill, staging browser journeys, and measured latency/queue/concurrency thresholds. | Launch operator |

No secret values belong in this file. Local placeholder `check --deploy` results and passing tests do not satisfy these live gates.
