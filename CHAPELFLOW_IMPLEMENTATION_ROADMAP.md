# ChapelFlow Implementation Roadmap

**Basis:** Phase 0 repository inspection, 2026-11-05. Priority follows the supplied launch policy; execution status is not implied by this plan.

| Priority / phase | Work | Acceptance evidence |
|---|---|---|
| P0 / Phase 1 | Confirm deployed origin and provider; audit auth, role/permission mappings, object ownership and MFA; enforce request-branch matching for prayer assignments; verify privileged audit events and auth revocation. | Focused Django authorization tests pass for allow/deny cases; staging login, token expiry/revocation, and admin-role boundaries verified. |
| P0 / Phase 1 | Secure report exports: private provider uploads, short-lived authorized downloads, requester-scoped report history, and revoke already-public exported objects. | Unit/API tests pass; staging proves unauthorized job access fails, direct public URLs fail, and old report objects are inaccessible. |
| P0 / Phase 9 | Reconcile Render deployment configuration with actual launch target (AWS requested in prompt); verify secret storage, database access, backup/restore, health checks, media durability and rollback. | Live non-production deployment evidence, backup restore rehearsal, and operator-reviewed rollback steps. |
| P0 / Phase 8 | Run focused backend auth/prayer/attendance/report/security tests, frontend tests, typecheck/lint/build and critical browser flows; address failures. | Actual commands and results recorded; no skipped failing critical tests. |
| P1 / Phase 2 | Map personal data; verify prayer visibility/anonymous behavior, access and retention; minimize sensitive logs/API output. | Privacy access matrix and API tests; no identity exposed to unauthorized community users. |
| P1 / Phase 3 | Verify reporting and moderation coverage for each user-generated content module, state transitions, moderator scope and audit trail. | API/UI report-to-resolution flow tests across roles and branches. |
| P1 / Phase 4 | Verify notification preference defaults, channel-specific opt-outs, task enforcement, retries and provider failure states. | Unit/integration tests for opted-in/out members and provider unavailable behavior. |
| P1 / Phase 5 | Audit mobile performance using real build and representative devices; fix only measured launch-impacting bottlenecks. | Reproducible baseline/after measurements and tested critical mobile flows. |
| P1 / Phase 6 | Keyboard, screen reader semantics, focus, contrast, reduced motion and form/error accessibility review. | Automated checks plus documented manual keyboard/screen-reader journeys. |
| P1 / Phase 7 | Verify attendance/auth/stream/database failure behavior and request correlation; check deployment health/readiness. | Failure-path tests and observable recovery behavior in staging. |
| P2 / Phases 8-10 | Broaden regression, operational visibility and launch acceptance across roles; document remaining risks and support ownership. | Completed critical journeys and evidence-based launch checklist/report. |

**Phase 3 implemented locally (2026-11-06):** Abuse reporting and branch-scoped moderation now cover Upper Room posts and media, comments, group messages, group resource links and announcements, visible prayer requests, and testimonies. The reviewer workflow, action audit trail, reporter privacy, author feedback, server-side hide/restore, submission limits, and media validation are documented in `CHAPELFLOW_MODERATION_GUIDE.md`. Verification: 50 affected Django tests, 42 frontend API tests, Django system check, migration drift check, and production frontend build passed. Live deployment validation remains part of the separate launch work.

**Phase 4 implemented locally (2026-11-06):** The in-app centre, per-user topic and channel settings, quiet hours, live-service targeting, server-side opt-outs, delivery states, and idempotent fan-out are described in `CHAPELFLOW_NOTIFICATION_GUIDE.md`. Verification: 78 affected Django tests and 132 frontend tests passed; Django check, migration drift check, and production frontend build passed. A broader 156-test legacy Django run had 30 failures: two import test expectations were updated for on-commit delivery and now pass; the remaining failures involve older pastoral routes, visitor validation, group API expectations, and volunteer scope/API expectations. Browser push remains disabled until device subscriptions and permission handling are implemented. Provider and deployed-browser checks remain launch validation work.

## Immediate execution order

1. Confirm the real production hosting target and review current environment settings without exposing secrets.
2. Run focused tests for authentication, permissions, prayer privacy, attendance, reports and communications; capture actual results.
3. Fix confirmed P0 access-control, privacy, deployment or data-integrity defects with regression tests.
4. Verify each P1 feature only where the module exists and its provider/environment is available.
5. Complete production/staging operations evidence before making any launch recommendation.

## Constraints and unresolved decisions

- The repository describes Render and Vercel; the prompt describes AWS. The live target must be established before deployment work.
- Cloud credentials and production state were not available during Phase 0; no infrastructure mutation is authorized by this audit.
- Existing backend phase reports are historical evidence only and must be reconciled with current source and executable tests.
- Report export code now protects newly generated Cloudinary/S3 exports at the API boundary; previously generated Cloudinary public assets require provider-side revocation. The Supabase storage adapter cannot safely host private report exports yet and fails closed for those jobs.
- Phase 0 and Phase 1 are signed off. Phase 1 source work and local verification completed on 2026-11-05: the focused backend security run passed 189 tests (1 skipped), frontend tests passed 125 tests, `npm run build` succeeded, and Django `check` reported no issues. Provider-side verification of the live origin/settings and legacy public report objects remains a deployment launch gate tracked under Phase 9; it does not block repository Phase 2 work.
- Phase 2 is active. Privacy fixes cover staff-only prayer notes, requester consent before community sharing, sensitive login logs, persistent offline attendance identifiers, and user-visible privacy request status. Deletion requests now expose the user-selected 30-day action deadline, but institutional exceptions and a safe completion process remain open; see `CHAPELFLOW_PRIVACY_AND_DATA_PROTECTION.md`.
- Phase 2 includes the reported post-registration sign-in failure. The localhost loop in VS Code's embedded phone preview was reproduced: login returned 200, but `SameSite=Lax` cookies were blocked in the cross-site frame and the app returned to `/login`. Local Django now issues secure partitioned cookies on Python versions that support them; embedded and normal-browser login tests pass, including protected session reads. On 2026-11-06 the live Render API still returned HTTP 503 with `x-render-routing: suspend-by-user`. The suspended API must be resumed and live login retested before Phase 2 sign-off. Vercel SPA route fallback was also added for that separate deployment target.
- The launch date in the supplied prompt is Sunday, 2026-11-08. Do not defer a confirmed critical security/privacy fix for cosmetic work.
