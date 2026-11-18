# ChapelFlow Technical Audit

**Audit status:** Phase 0 static repository inspection; no production systems or data accessed.  
**Date:** 2026-11-05

## Architecture observed

| Area | Evidence | Finding |
|---|---|---|
| Frontend | Root `package.json`, `src/main.tsx`, `src/app/App.tsx` | React 19 + TypeScript + Vite; React Router 7; TanStack Query; Vitest and Playwright scripts; PWA plugin and GSAP are dependencies. `AuthProvider` owns session bootstrap and cookie-based API login. |
| Backend | `chapelflow-backend/requirements.txt`, `config/urls.py` | Django REST Framework API, split into domain apps; Celery workers and Redis; PostgreSQL via `DATABASE_URL`; Django admin and OpenAPI endpoints. |
| Authentication | `apps/accounts/views.py`, `common/authentication`, `config/settings/base.py` | Custom user model, JWT access/refresh cookies, refresh rotation and blacklist, MFA endpoints, password reset and session revocation. Global DRF permission defaults to `IsAuthenticated`; public endpoints explicitly opt out. |
| Authorization | `common/permissions`, `common/constants/roles.py`, app viewsets | Database-backed role permissions, role constants, branch scoping and per-resource policies exist. Coverage still needs endpoint-by-endpoint runtime verification. |
| Data | `config/settings/base.py`, app models/migrations | PostgreSQL is the configured production database; apps cover accounts, organizations, university, members, visitors, households, ministries/groups, events, attendance, finance, communications, notifications, prayer/pastoral, volunteers, reports, uploads, audit, dashboard, operations and social. |
| Infrastructure | `render.yaml`, `chapelflow-backend/Dockerfile`, `docker-compose.yml`, `vercel.json` | Repository deployment descriptor targets Render web + Celery worker + managed Postgres/Redis; frontend has Vercel configuration. No ECS task/service, ALB, RDS, IAM or Secrets Manager definitions were found. Live cloud configuration was not inspected. |
| Tests | `package.json`, `src/test`, `e2e`, `chapelflow-backend/tests` | Frontend unit/component and Playwright suites; backend Django tests across security, auth, attendance, reports and domain apps. Commands exist; Phase 0 did not execute them. |

## Feature inventory (repository evidence)

- Authentication, institutional accounts, role dashboards and admin routes are implemented in frontend and backend.
- Attendance includes QR, kiosk, usher checkpoints, offline sync, device/session/record endpoints and correction models.
- Prayer requests, pastoral notes and testimonies have backend models and role/privacy checks.
- Announcements and member communication preferences have backend models, API routes and asynchronous dispatch tasks.
- In-app notifications are user-scoped; email/SMS/push delivery depends on configured providers.
- Content moderation workflows exist under operations; exact coverage of all user-generated content needs runtime and route review.
- Media/library and live routes exist in the frontend; this inspection did not establish a first-party sermon/stream backend or confirm any external streaming provider.
- PWA support is configured through Vite; install/offline behavior has not been exercised in a browser.

## Findings and risks

| ID | Severity | Component | Description / impact | Recommended correction | Verification |
|---|---|---|---|---|---|
| AUD-01 | High | Deployment / operations | `render.yaml` provisions Render, while the requested launch target describes AWS ECS/RDS. No AWS infrastructure-as-code or task/role policy was found. AWS readiness, IAM scope, network boundaries, backup policy and rollback therefore cannot be established from this repo. | Confirm the intended production provider and inspect its deployed configuration. If AWS is the actual target, add/validate deployment definitions and operational evidence before launch; do not infer readiness from optional AWS environment variables. | Inspect live staging configuration, task/service definitions, security groups, IAM, secret source, RDS backups, health checks and rollback procedure. |
| AUD-02 | High | Production configuration | `render.yaml` marks `CORS_ALLOWED_ORIGINS` and `CSRF_TRUSTED_ORIGINS` as manually supplied (`sync: false`); base settings default both to localhost. A missing or incorrect production value can break cookie-authenticated requests or create unsafe cross-origin behavior if misconfigured. | Verify exact production origins and cookie/CSRF behavior in the deployed environment; keep origins explicit and minimal. | Django deployment checks plus browser login/refresh/logout and cross-origin negative tests on staging. |
| AUD-03 | High (fixed in Phase 1) | Prayer request assignment | Generic user-FK validation checked whether the acting pastoral user could access the assignee's branch, rather than whether the assignee belonged to the request's branch. A pastoral user with organization-wide scope could assign care records across branches. | Validate the assignee against the existing request branch (or submitted branch for creation). | Cross-branch assignment regression test rejects the request; privacy/IDOR tests pass. |
| AUD-04 | Medium | User experience / content | Frontend routes include media and live pages, but repository inspection did not confirm a production content/stream provider, backend contract, uptime monitoring or failure behavior. A route alone is not evidence the service works. | Identify the production provider and verify configuration and fallback states; document unavailable dependencies. | Staging end-to-end checks with provider unavailable and available. |
| AUD-05 | Medium | Monitoring / recovery | Django config has request-ID logging and console handlers; deployment descriptor contains health checks, but repository evidence does not establish alerting, durable media/report storage, tested backup restore or incident response. | Verify hosting retention, database backup/restore, media durability and alert destinations; document tested recovery steps. | Restore rehearsal and controlled worker/API failure checks in non-production. |
| AUD-06 | Low | Documentation / auditability | Numerous historical phase reports make strong completion claims alongside explicit gaps and unknowns. They are not a substitute for current test evidence and can mislead launch decisions. | Treat current code and reproducible test/deployment evidence as authoritative; record limitations with dates and commands. | Reconcile current claims against executed CI and staging evidence. |
| AUD-07 | High | Report exports / storage | Report generation uploaded membership, attendance and giving exports through public delivery types for the default Cloudinary and Supabase adapters, then exposed `file_url` in the report serializer. A copied URL could bypass API role and branch checks. | New exports use private storage and short-lived authenticated downloads. Revoke prior public report objects in the provider account before launch. | Storage-adapter and requester-scope tests pass; provider-side revocation and direct-link denial remain unverified. |
| AUD-08 | High (fixed in Phase 2 source) | Prayer privacy / API serialization | Member responses included nested pastoral follow-up notes; public prayer responses exposed requester/internal IDs and community sharing lacked a recorded requester-consent gate. | Restrict notes to pastoral roles, require consent before community visibility/notifications, and redact requester/internal IDs from community responses. | Member/chaplain API regression tests, notification tests and sharing-consent tests. |
| AUD-09 | Medium (fixed in Phase 2 source) | Login logs / browser storage | Failed-login logs included submitted identifiers, and offline attendance identifiers persisted in `localStorage`. | Omit raw identifiers from logs; keep pending attendance identifiers in tab-scoped storage and clear old persistent copies. | Log capture regression and offline queue migration tests. |

## Existing controls observed (static evidence only)

- Production settings reject the known development secret keys, disable `DEBUG`, enable HTTPS redirect, secure cookies, HSTS, nosniff and clickjacking protection.
- DRF defaults to authenticated requests, paginated results and scoped throttling; password validation and short-lived access tokens are configured.
- Refresh token rotation and blacklist support are configured; authentication cookies are the frontend's default API session mechanism.
- Request IDs and audit context middleware are installed; an audit app and audit log calls exist in sensitive flows.
- Notification feed queries are recipient-scoped; announcements dispatch asynchronously and checks communication preferences.
- Report jobs execute asynchronously and recheck branch access before generation.
- Attendance QR service uses signed, expiring tokens and derives the member from the authenticated user for student scans.

These controls have not all been dynamically validated in this phase.

## Phase 0 verification and limits

**Phase 0 sign-off:** Repository architecture and current code/configuration were inspected; all three audit deliverables exist; no production systems or data were accessed or changed. `rtk npm.cmd run build` succeeded (Vite warned that the main JavaScript bundle is 1,059 kB minified); `rtk npm.cmd test` passed 14 files / 125 tests. Phase 0 is complete. Phase 1 source work and local regression verification are complete; provider-side deployment evidence remains a launch gate.

Inspection was limited to repository code/configuration. No live Render/Vercel/AWS account, production database, provider credential, external streaming service, or university deployment was accessed. No production data was modified. Findings that depend on runtime configuration are explicitly marked unverified.
