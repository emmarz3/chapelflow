# Phase 1 — Scendey Waitlist API Contract

**Status:** Repository and source audit complete. No application code or production configuration changed during Phase 1.  
**Audited:** 2026-11-27  
**Scendey repository:** [emmarz3/Scendey-Waitlist](https://github.com/emmarz3/Scendey-Waitlist)  
**Audited Scendey commit:** [681ef0aae6d84e53f35a7011989517ce9c02fa5d](https://github.com/emmarz3/Scendey-Waitlist/commit/681ef0aae6d84e53f35a7011989517ce9c02fa5d)

## 1. Production service

The active Railway production service is online:

- Public origin: `https://scendey-waitlist-production.up.railway.app`
- Public homepage: `/`
- Existing public join routes: `/join?type=brand` and `/join?type=shopper`
- Registration API: `POST /api/join`
- Confirmation API: `POST /api/confirm`
- Resend-verification API: `POST /api/resend-verification`
- Runtime stack: Next.js App Router, TypeScript, Prisma and PostgreSQL.

The homepage and existing shopper join page were opened successfully. Railway reports the Scendey-Waitlist service and its PostgreSQL service online, with the active app deployment successful.

## 2. Registration request

The API accepts JSON. Its schema is a discriminated union on `role`. The only supported role values are `BRAND` and `SHOPPER`.

### Shared fields

| Field | Type / constraint | Required |
|---|---|---|
| `role` | `BRAND` or `SHOPPER` | Yes |
| `email` | Valid email, max 254 chars; normalized to lowercase | Yes |
| `consent` | Boolean; defaults to `false` | No |
| `source` | String, max 100 chars | No |
| `utmSource` | String, max 100 chars | No |
| `utmMedium` | String, max 100 chars | No |
| `utmCampaign` | String, max 100 chars | No |
| `referral` | 8–80 alphanumeric, underscore or hyphen chars | No |
| `invitation` | 8–80 alphanumeric, underscore or hyphen chars | No |

### Brand request

Required: `brandName` (trimmed, 2–100 chars) and `category` (1–60 chars).

Optional: `sellingStatus` (max 80), `handleOrUrl` (max 200), `location` (max 100), `phone` (max 40), and `salesBlocker` (max 1,000).

Example contract (illustrative only; do not submit this as a live registration):

```json
{
  "role": "BRAND",
  "email": "owner@example.com",
  "brandName": "Example Brand",
  "category": "Fashion",
  "handleOrUrl": "@examplebrand",
  "consent": false,
  "source": "CHAPELFLOW"
}
```

### Shopper request

Optional: `name` (trimmed, max 100 chars), `location` (max 100 chars), and `interests` (array of up to 20 strings, each max 60 chars; defaults to an empty array).

Example contract (illustrative only; do not submit this as a live registration):

```json
{
  "role": "SHOPPER",
  "email": "person@example.com",
  "name": "Example Person",
  "interests": ["Fashion", "Technology"],
  "consent": false,
  "source": "CHAPELFLOW"
}
```

The hidden anti-spam field is named `website`. A non-empty value is treated as a bot submission and returns a fake success-shaped response without saving an entry. ChapelFlow must not place a real website, brand URL or user data in this field. Brand URLs belong in `handleOrUrl`.

## 3. Response and error contract

| Situation | HTTP | Response behaviour |
|---|---:|---|
| New entry saved | 201 | `ok: true`, `existing: false`, `delivered: boolean`; a message may explain email delivery failure |
| Email already exists | 200 | `ok: true`, `existing: true`, `delivered: false`; no new entry is created |
| Invalid payload | 400 | `error` and, where applicable, field errors |
| Too many submissions for an email | 429 | Retry after 900 seconds |
| Database / signup failure | 503 | Generic temporary-unavailability message |
| Non-empty anti-spam honeypot | 200 | Fake success-shaped response; no waitlist row is created |

Signup attempts are rate-limited to five per normalized email address per 15 minutes. Email is globally unique across both roles.

**Duplicate behaviour matters:** an existing entry is not updated. The API does not convert an existing `SHOPPER` into a `BRAND`, enrich an existing profile with new brand details, or change its consent/source fields when the email already exists. The existing duplicate response also reveals that an email is registered; Phase 3 should consider a generic public response to reduce email enumeration.

## 4. Email-verification lifecycle

1. `POST /api/join` validates the request and creates a `PENDING` entry.
2. A one-time `VERIFY` token is created and expires after 24 hours.
3. Scendey attempts to send a verification email through its configured email provider.
4. `POST /api/confirm` accepts JSON containing the token. A valid unused token marks the entry `CONFIRMED`, records the verification event and sends the welcome/confirmation email.
5. Expired or previously used tokens are rejected with HTTP 410. Invalid tokens are rejected with HTTP 400.
6. `POST /api/resend-verification` accepts an email and returns a generic response. For a pending entry it invalidates outstanding verification tokens, creates a new one and attempts delivery. It is rate-limited by client and email.

Resend is the default email provider. The application needs server-side `EMAIL_API_KEY` and `EMAIL_FROM`; `EMAIL_API_URL` is optional and defaults to Resend's email API. The Railway service has these variable names present. The secret values and sender-domain verification status were not inspected, and successful delivery was not proven in this audit.

The existing signup UI makes progress/launch-update consent optional. A person can join without opting into marketing updates. This checkbox must not become a mandatory condition of joining. Verification and essential signup-status emails remain part of the confirmation flow.

## 5. Attribution and audience mapping gaps

### Source attribution

The endpoint records a `signup_submitted` analytics event with the supplied `source` regardless of marketing consent. It stores `WaitlistEntry.source` and UTM fields only when `consent: true`. This preserves signup analytics while respecting the user's choice not to receive progress/launch marketing.

For the ChapelFlow general flow, use a fixed server-side source value such as `CHAPELFLOW`, not a caller-controlled value.

### Audience category

The current Scendey schema does **not** support separate `STUDENT`, `STAFF`, `PROFESSIONAL` or `OTHER` role values, nor an `audienceCategory` field.

Recommended mapping after product confirmation:

- Student, staff/professional and other non-brand audiences: `role: SHOPPER`.
- Business/brand audience: `role: BRAND`, with the required brand name and retail category.

If Scendey needs to report or segment Student, Staff/Professional and Other separately, Phase 3 must add a dedicated audience-category field to request validation, Prisma schema/migration and relevant admin/analytics views. Do not overload `role`, the brand `category` field or shopper `interests` to represent a different concept.

The proposed one-size-fits-all full-name field also needs a conditional design decision: `SHOPPER.name` is supported, but the `BRAND` schema does not currently accept a contact person's name. A brand application currently identifies the business through `brandName`.

## 6. Existing ChapelFlow advertiser integration

The existing ChapelFlow Celery task sends:

- `role: BRAND`
- Advertiser email
- `brandName`
- Brand `category`
- `handleOrUrl`
- `consent: true`
- `source: "ChapelFlow advertising"`

These fields match the current Scendey Brand schema. ChapelFlow's API and Celery worker both have a `SCENDEY_WAITLIST_URL` environment variable configured by name. Railway's connected integration redacts variable values, so the exact live value could not be independently checked. The documented target is:

```text
https://scendey-waitlist-production.up.railway.app/api/join
```

**Existing sync issue:** the ChapelFlow task currently treats any response with `ok: true` as a completed sync. Scendey's duplicate response also has `ok: true`, even though it does not update an existing record. An advertiser who previously joined as a Shopper could therefore be marked synced without being represented as a Brand in Scendey. Phase 3 must define and implement a safe reconciliation/upsert or an explicit duplicate outcome before considering that sync reliable.

## 7. Existing automated test coverage

The Scendey package script runs `tests/waitlist-validation.test.ts`. The inspected tests cover brand required fields, Shopper email normalization, optional consent, invalid email and excessive interests. They do not exercise the live API route, database persistence, duplicate-email response, Resend delivery, or the complete verification journey. Phase 5 must add or run route-level/integration tests for those behaviours.

## 8. Phase 1 findings and handoff

### Confirmed

- Correct Scendey repository and current production service identified.
- Public homepage and existing Shopper join page are reachable.
- Exact endpoint and accepted request schema identified from source.
- Duplicate, validation, rate-limit and failure response behaviour inspected.
- Email verification and resend flow inspected.
- Existing ChapelFlow advertiser payload compared against the Scendey schema.
- ChapelFlow's Scendey URL variable names are present on its API and Celery worker services.
- No code or production configuration was changed.

### Not yet proven

- A live JSON POST to `/api/join` was not performed. A real successful POST would create a production waitlist entry and send verification email; no real or synthetic signup was submitted during this audit. The browser inspection tool could not issue a custom JSON POST probe.
- The redacted Railway `SCENDEY_WAITLIST_URL` value was not verified.
- Resend credentials and sender-domain verification were not validated by sending a real email.
- Existing duplicate-record reconciliation has not been implemented.

### Handoff to Phase 2 / Phase 3

Phase 2 can design the public waitlist page, homepage CTA, dashboard card and modal using conditional form fields:
- Non-brand audience: name and email, with optional location/interests.
- Brand audience: email, brand name and brand category; add contact name only if the Scendey schema is extended.

Before Phase 3 finalizes the payload, agree whether Student/Staff/Professional/Other should be persisted as a dedicated audience category. Phase 3 must also close the duplicate-sync issue, preserve optional marketing consent, and implement robust user-facing handling for pending verification, existing registrations, provider failures and retries.

## Source files inspected

- Scendey: `src/app/api/join/route.ts`
- Scendey: `src/lib/validation.ts`
- Scendey: `prisma/schema.prisma`
- Scendey: `src/app/api/confirm/route.ts`
- Scendey: `src/app/api/resend-verification/route.ts`
- Scendey: `src/lib/email.ts`
- Scendey: `src/components/signup-form.tsx`
- ChapelFlow: `chapelflow-backend/apps/advertising/tasks.py`
- ChapelFlow: `chapelflow-backend/apps/advertising/services.py`
- ChapelFlow: `chapelflow-backend/config/settings/base.py`
