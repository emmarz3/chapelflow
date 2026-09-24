# ChapelFlow

Chapel management platform for Chrisland University Chapel, Abeokuta. The repository contains a React/Vite frontend and a Django REST Framework backend. Django is the only supported backend.

## Run locally

Requirements: Node.js 22+ and Python 3.12+.

```bash
npm install
npm run dev
```

On a fresh local database, open `http://localhost:5173/setup/admin` to create
the single Super Admin. The account is signed in immediately and redirected to
the full dashboard. This one-time browser setup is disabled outside local
development and closes after the first Super Admin exists.

This starts Django and the frontend together. Install backend requirements in `chapelflow-backend` first (preferably in a virtual environment); `scripts/dev-django.mjs` uses `.venv` when present. Configure `chapelflow-backend/.env` with a local PostgreSQL `DATABASE_URL` and the other Django settings.

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
- `chapelflow-backend`: Django REST Framework API, authentication, RBAC, attendance, migrations, and management commands
- `e2e`: Playwright journeys for desktop and mobile

The endpoint catalogue and role/permission matrix are documented in [`docs/API_CONTRACT.md`](docs/API_CONTRACT.md). Deployment checks and external-provider dependencies are tracked in [`docs/PRODUCTION_CHECKLIST.md`](docs/PRODUCTION_CHECKLIST.md).

Authentication assumes secure HttpOnly cookies. No authentication token is stored in `localStorage`; only the non-sensitive theme preference is persisted there. Backend authorization remains authoritative.

Attendance uses Django attendance sessions, student passes, usher checkpoints, and audited corrections. Backend authorization and branch scope remain authoritative.

In production, public student registrations remain inactive until a chapel administrator verifies and approves them from the member directory. Approval is server-authorized and audited; ushers cannot approve accounts.

Production routes fetch backend-authorized content and show explicit loading, empty, and error states. Preview fixtures are reachable only when `VITE_DATA_MODE=demo` is intentionally configured. Demo authentication stores only a preview role in session storage and is excluded from API mode.

## Required environment

- `VITE_BACKEND=django`: only supported backend; set at frontend build time
- `VITE_API_BASE_URL`: backend API origin/path, set at frontend build time
- `VITE_DATA_MODE=api`: production data mode, set at frontend build time
- `VITE_INSTITUTION_NAME`, `VITE_PRIVACY_CONTACT`, `VITE_SUPPORT_CONTACT`, `VITE_MAP_URL`, `VITE_LIVESTREAM_URL`: optional frontend build-time values
- Backend runtime variables such as `DATABASE_URL`, `SECRET_KEY`, `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS`, `PUBLIC_BACKEND_URL`, `SUPER_ADMIN_EMAIL`, and `SUPER_ADMIN_PASSWORD` belong on the Django service. See [`chapelflow-backend/.env.example`](chapelflow-backend/.env.example).

## Deployment

Deploy the backend as a Docker web service using `chapelflow-backend/Dockerfile` and the frontend as a static site. Set `SUPER_ADMIN_EMAIL` and `SUPER_ADMIN_PASSWORD` on the backend service. The Dockerfile runs migrations and both bootstrap commands at container startup. Clear any Render **Docker Command** override so Render uses the Dockerfile `CMD`. Set frontend `VITE_BACKEND=django`, `VITE_DATA_MODE=api`, and `VITE_API_BASE_URL` before the static-site build; `VITE_*` values are embedded at build time. Configure the frontend rewrite for `/api/*` to the backend and `/*` to `/index.html`.

Redis is optional on the Render free plan. If `REDIS_URL` is unset, the backend uses in-memory caching and an in-memory Celery broker, and runs tasks synchronously; `/readiness/` reports Redis and Celery as `not configured`. Set `REDIS_URL` to use Redis-backed caching and queuing.

The generated campus-chapel hero is stored at `public/chapel-hero.png`. It contains no text or logos and should be replaced with approved institutional photography when available.
