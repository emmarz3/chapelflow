# ChapelFlow advertising rollout

## Advertiser journey

Student and staff members open **Ads & subscriptions** from the dashboard hamburger navigation (path: `/app/advertise`). They choose an active subscription program, submit the brand details, proposed ad category, HTTPS destination and image, and optionally consent to Scendey waitlist updates.

Submitting an application does **not** charge the advertiser. The campaign stays in `PENDING` while every active Super Admin receives an in-app `ADMIN_ALERT` notification linking to the review queue. Super Admin reviews the creative, category and destination, then approves, rejects or requests changes. The advertiser also receives an in-app decision notification. Only `APPROVED` campaigns expose the Paystack checkout action; the backend rejects checkout for every other state. Payment verification is still required before the campaign becomes active or appears in placements.

## Subscription program management

Super Admin manages programs in `/app/admin/advertising` under **Subscription programs**. The manager can create a program, edit its name/description/monthly price/placement profile/placements, and activate or deactivate it. The public advertiser form reads active programs from `GET /api/v1/ads/plans/`; the admin endpoints are `GET/POST /api/v1/ads/admin/programs/` and `PATCH/DELETE /api/v1/ads/admin/programs/:id/`.

The database migration creates two starter programs from the existing fixed plans:
- Campus Brand — ₦3,000/month, homepage and events page.
- Featured Brand — ₦7,500/month, homepage and events page with the existing higher rotation weight.

Programs are deactivated rather than deleted. A campaign snapshots the program name, placements and monthly price when the application is submitted. Paystack monthly plans are versioned by program and price. Editing or deactivating a program therefore affects new applications only; existing campaigns, subscribers and their agreed renewal prices are preserved.

## Billing and approvals

Advertising revenue belongs to the Super Admin, not the Chapel. Advertiser charges, monthly subscriptions, refunds and settlement are processed through the Super Admin's own Paystack account. Configure `ADS_PAYSTACK_SECRET_KEY` on the Railway `chapelflow-api` service with the Super Admin account's secret key; do not reuse the Chapel giving `PAYSTACK_SECRET_KEY`. The ads code uses this dedicated key for plan creation, checkout initialization, transaction verification, and subscription creation/cancellation. Also set `ADS_PAYSTACK_WEBHOOK_SECRET` to the Super Admin Paystack account's mode-specific `whsec_` webhook signing secret from Developers → API configuration → Webhook signing secret. The webhook verifies the current `Paystack-Signature` header using the timestamped raw-body HMAC, with legacy `X-Paystack-Signature` support retained for the transition. Never commit either secret or expose either in frontend code.

Checkout remains fail-closed until the Super Admin records approval of the advertising policy covering revenue ownership, refund/dispute handling and permitted ad categories. The confirmed revenue owner is the Super Admin. Set `ADS_POLICY_APPROVED=true` only after refund/dispute handling and permitted categories are also documented. Never use the Chapel giving account for ads.

Campus Brand starter pricing is ₦3,000/month and Featured Brand is ₦7,500/month. The first 10 approved student advertisers can pay ₦2,000 for month one; later months use the selected program's monthly price. The founding charge is a one-time card payment. After Paystack verifies it, the backend requires a reusable card authorization and creates the full-price monthly subscription with the first renewal one month later. The ad activates only after both steps succeed. If the discounted charge succeeds but Paystack does not return reusable authorization or subscription creation fails, reconcile the charge before asking the advertiser to pay again.

Keep the Chapel giving webhook at `https://chapelflow-api-production.up.railway.app/api/v1/payments/webhook/paystack/` configured in the Chapel giving Paystack dashboard. Configure the Super Admin advertising Paystack account's webhook separately at `https://chapelflow-api-production.up.railway.app/api/v1/ads/paystack/webhook/`. This separation ensures ads settle into the Super Admin's Paystack account and Chapel giving events remain isolated. `FRONTEND_URL` must be the public ChapelFlow origin; callback is `/app/advertise?campaign=<campaign-id>`. Keep both Paystack secrets backend-only.

## Delivery, placements and audit

Super Admin can approve, reject, request changes, pause, resume, revoke, view decision history and payments, or pause all ad display immediately. Payment records are protected from campaign deletion. Rejection, approval and change requests notify the advertiser in-app. New applications and resubmissions notify every active Super Admin in-app.

Sponsored placements are labelled Sponsored and only appear on the campaign's agreed placements, while approved and paid. Featured campaigns retain twice the placement weight. Impressions deduplicate per visitor/ad across placements for 12 hours; clicks deduplicate per visitor/ad for 30 minutes. No sales, clicks or view counts are guaranteed. Images must be verified PNG/JPEG/WebP under 2 MB; URLs require HTTPS. Advertisers must be student/staff members and supply a proposed category.

Scendey opt-in remains separate and unchecked by default. ChapelFlow records accepted wording/timestamp and sends opted-in brand details only after verified ad payment; no ChapelFlow password/account is transferred. Set `SCENDEY_WAITLIST_URL=https://scendey-waitlist-production.up.railway.app/api/join`. Before enabling live opt-ins, confirm Scendey's `/api/join` endpoint accepts the advertiser payload and its email-verification flow works.

## Pilot checklist

1. Record revenue/refund/category rules and set the policy approval flag only after sign-off.
2. Use Paystack test mode for normal plans, founding offer, duplicate webhooks, failed renewals, cancellation and refunds.
3. Verify Super Admin in-app notifications, approval/rejection/change requests, and that pending/rejected ads cannot initialize checkout.
4. Confirm that program price or placement edits affect only new applications and do not alter existing campaign snapshots or Paystack subscriptions.
5. Verify emergency pause and status screens, optional Scendey sync with explicit consent, and the two-month pilot.

This branch contains code and migrations only. It does not deploy to production or make live payments.
