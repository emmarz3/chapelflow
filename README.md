# ChapelFlow frontend

Production-oriented React frontend for Chrisland University Chapel, Abeokuta. It includes the institutional public website, authentication and onboarding, permission-aware portal navigation, role-specific dashboards, attendance, members, events, finance, communications, workers, assets, media, CMS, analytics, branches, audit, settings, policies, responsive layouts, dark mode, and PWA support.

## Run locally

```bash
npm install
copy .env.example .env.local
npm run dev
```

Use `VITE_DATA_MODE=demo` for the explicit preview dataset and role switcher. Production should keep `VITE_DATA_MODE=api`; it never silently falls back to fixtures.

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
- `e2e`: Playwright journeys for desktop and mobile

The proposed endpoint catalogue and role/permission matrix are documented in [`docs/API_CONTRACT.md`](docs/API_CONTRACT.md). Production-readiness and external-provider dependencies are tracked in [`docs/PRODUCTION_CHECKLIST.md`](docs/PRODUCTION_CHECKLIST.md).

Authentication assumes secure HttpOnly cookies. No authentication token is stored in `localStorage`; only the non-sensitive theme preference is persisted there. Backend authorization remains authoritative.

Production routes fetch backend-authorized content and show explicit loading, empty, and error states. Preview fixtures are reachable only when `VITE_DATA_MODE=demo` is intentionally configured. Demo authentication stores only a preview role in session storage and is excluded from API mode.

## Required environment

- `VITE_API_BASE_URL`: backend API origin/path
- `VITE_DATA_MODE`: `api` for production or explicitly `demo` for preview
- `VITE_INSTITUTION_NAME`: display name override
- `VITE_PRIVACY_CONTACT`: approved privacy contact, currently intentionally blank
- `VITE_SUPPORT_CONTACT`: approved support contact
- `VITE_MAP_URL`: approved chapel map/location URL
- `VITE_LIVESTREAM_URL`: configured stream provider URL

## Deployment

Serve the built `dist` directory with SPA fallback to `index.html`. Configure HTTPS, CSP, secure cookies, CSRF protection matching the backend, asset caching, and a backend allowlist for the production frontend origin. Review all policy text with institutional legal counsel and configure official contacts before publication.

The generated campus-chapel hero is stored at `public/chapel-hero.png`. It contains no text or logos and should be replaced with approved institutional photography when available.
