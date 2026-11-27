# Scendey Waitlist integration — Phases 3 and 4

Implementation branch: feature/scendey-waitlist-phases-3-4  
Scendey branch: feature/chapelflow-waitlist-integration  
Date: 27 November 2026

## Phase 3 — backend and API integration

- The public ChapelFlow form now calls POST /api/v1/public/scendey-waitlist/.
- The Django backend validates names, email, audience, and the conditional brand fields.
- The backend relays server-to-server to Scendey using the HTTPS URL in SCENDEY_WAITLIST_URL; the Scendey endpoint and any credentials remain server-only.
- Audience values map to existing Scendey roles without changing the meaning of BRAND and SHOPPER.
- The brand/contact name is now stored for BRAND records as well as SHOPPER records.
- Existing advertiser opt-in sync is preserved and now includes audienceCategory BUSINESS and a contact name.
- Scendey remains the sole waitlist database.

## Phase 4 — security, privacy, resilience and validation

- Default marketing consent remains false; opt-in is a separate payload field.
- Transactional verification is not gated by marketing consent.
- A public IP throttle (60/hour), honeypot, HTTPS-only upstream check, bounded upstream timeout, and safe public error handling are in place.
- The public response does not disclose whether an email already exists.
- Scendey's Prisma schema, migration, validation and admin views include audienceCategory.
- Scendey exports and ChapelFlow's existing ad synchronization keep their integration fields.
- Automated tests cover audience mapping, optional consent, invalid business fields, honeypot, provider outage and safe endpoint configuration.

## Local validation

- ChapelFlow frontend: 25 test files, 219 tests passed; production Vite build passed.
- ChapelFlow backend: 9 relay tests passed using the isolated SQLite test settings.
- Scendey: clean npm ci, Prisma schema validation, Prisma Client generation, type-check, 5 validation tests and Next.js production build passed.

## Not done by this change

- No production Prisma migration was applied.
- No Railway/Vercel production variables were edited.
- No real signup or verification email was sent.
- No branch was merged or deployed to production.

The Scendey Prisma migration must be applied before the new Scendey app code is deployed. Deploy Scendey first, then deploy the ChapelFlow backend/Celery worker and finally promote the frontend preview after a controlled end-to-end test.
