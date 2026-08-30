# ChapelFlow

Production-oriented chapel management platform for Chrisland University Chapel, Abeokuta. The repository contains the React/PWA frontend and a TypeScript/PostgreSQL API for secure student QR attendance.

## Run locally

Requirement: Node.js 22+.

```bash
npm install
npm run dev
```

This starts the frontend and API together. Local development uses an embedded persistent PostgreSQL-compatible database in `.chapelflow-data`, runs migrations automatically, and approves local student registrations immediately so they can sign in. These conveniences are disabled in production.

To start either process separately:

```bash
npm run dev:server
npm run dev:web
```

Use `VITE_DATA_MODE=demo` only for the explicit static preview dataset and role switcher. Full-stack development and production use `VITE_DATA_MODE=api`.

## Checks

```bash
npm run typecheck
npm run lint
npm test
npm run test:e2e
npm run build
```

## Architecture

- `src/app`: route composition and guards
- `src/components`: accessible reusable UI primitives
- `src/features`: public, authentication, shell, and product feature pages
- `src/lib/api.ts`: credentialed, abortable API client and normalized errors
- `src/lib/permissions.ts`: centralized role/permission defaults
- `src/lib/fixtures.ts`: development-only preview data
- `src/services/chapelflow.ts`: typed feature contracts for every production module
- `src/types`: shared API/domain types
- `server`: Express API, authentication, QR security, RBAC, attendance workflows, migrations, and seed scripts
- `e2e`: Playwright journeys for desktop and mobile

The proposed endpoint catalogue and role/permission matrix are documented in [`docs/API_CONTRACT.md`](docs/API_CONTRACT.md). Production-readiness and external-provider dependencies are tracked in [`docs/PRODUCTION_CHECKLIST.md`](docs/PRODUCTION_CHECKLIST.md).

Authentication assumes secure HttpOnly cookies. No authentication token is stored in `localStorage`; only the non-sensitive theme preference is persisted there. Backend authorization remains authoritative.

Student passes use short-lived HMAC-signed tokens bound to the active attendance session. Attendance writes derive the usher from the server session, record an audit event, use an idempotency key, and enforce `UNIQUE(attendance_session_id, student_id)` in PostgreSQL.

In production, public student registrations remain inactive until a chapel administrator verifies and approves them from the member directory. Approval is server-authorized and audited; ushers cannot approve accounts.

Production routes fetch backend-authorized content and show explicit loading, empty, and error states. Preview fixtures are reachable only when `VITE_DATA_MODE=demo` is intentionally configured. Demo authentication stores only a preview role in session storage and is excluded from API mode.

## Required environment

- `VITE_API_BASE_URL`: backend API origin/path
- `VITE_DATA_MODE`: `api` for production or explicitly `demo` for preview
- `VITE_INSTITUTION_NAME`: display name override
- `VITE_PRIVACY_CONTACT`: approved privacy contact, currently intentionally blank
- `VITE_SUPPORT_CONTACT`: approved support contact
- `VITE_MAP_URL`: approved chapel map/location URL
- `VITE_LIVESTREAM_URL`: configured stream provider URL
- `DATABASE_URL`: PostgreSQL connection string
- `APP_ORIGIN`: exact trusted frontend origin
- `PORT`: API port, default `8000`
- `CHAPELFLOW_SESSION_SECRET`: at least 32 random characters
- `CHAPELFLOW_QR_SIGNING_SECRET`: a different secret of at least 32 random characters
- `CHAPELFLOW_ADMIN_USERNAME` / `CHAPELFLOW_ADMIN_EMAIL` / `CHAPELFLOW_ADMIN_NAME` / `CHAPELFLOW_ADMIN_PASSWORD`: initial super-administrator seed
- `CHAPELFLOW_USHER_01_USERNAME` / `CHAPELFLOW_USHER_01_PASSWORD`: first restricted usher seed
- `CHAPELFLOW_USHER_02_USERNAME` / `CHAPELFLOW_USHER_02_PASSWORD`: second restricted usher seed

## Deployment

Production requires PostgreSQL 15+ and a completed `.env` based on `.env.example`. Run `npm run build`, `npm run db:migrate`, and `npm run db:seed`, then start the compiled API with `npm run server`. Serve `dist` with SPA fallback and reverse-proxy `/api` to the API process. Use HTTPS, persistent PostgreSQL, secure environment variables, backups, and the exact production `APP_ORIGIN`. The seed is idempotent and preserves existing administrator and usher passwords.

The generated campus-chapel hero is stored at `public/chapel-hero.png`. It contains no text or logos and should be replaced with approved institutional photography when available.
