# ChapelFlow advertising rollout

Campus Brand is ₦3,000/month and Featured Brand is ₦7,500/month. The first 10 approved student advertisers can pay ₦2,000 for month one; later months use the selected plan price. Checkout stays disabled until chapel leadership signs off on revenue ownership, refund/dispute handling and permitted ad categories. Set ADVERTISING_POLICY_APPROVED=true only after that agreement is documented.

The founding charge is a one-time card payment. After Paystack verifies it, the backend requires a reusable card authorization and creates the full-price monthly subscription with the first renewal one month later. The ad activates only after both steps succeed. If the discount charge succeeds but Paystack does not return reusable authorization or subscription creation fails, reconcile the charge before asking the advertiser to pay again.

Keep the shared giving webhook at https://chapelflow-api-production.up.railway.app/api/v1/payments/webhook/paystack/. FRONTEND_URL must be the public ChapelFlow origin; callback is /app/advertise?campaign=<campaign-id>. Keep PAYSTACK_SECRET_KEY backend-only. Super Admin can approve, reject, request changes, pause, resume, revoke, view decision history and payments, or pause all ad display immediately. Payment records are protected from campaign deletion.

Ads are labelled Sponsored and appear only on homepage and events. Featured ads receive twice the placement weight. Impressions deduplicate per visitor/ad across both placements for 12 hours; clicks deduplicate per visitor/ad for 30 minutes. No sales or view counts are guaranteed. Images must be verified PNG/JPEG/WebP under 2 MB; URLs require HTTPS. Advertisers must be student/staff members and supply a proposed category.

Scendey opt-in remains separate and unchecked by default. ChapelFlow records accepted wording/timestamp and sends opted-in brand details only after verified ad payment; no ChapelFlow password/account is transferred. Configure Scendey email verification before enabling SCENDEY_WAITLIST_URL.

Pilot checklist: record revenue/refund/category rules; use Paystack test mode for normal plans, founding offer, duplicate webhooks, failed renewals, cancellation and refunds; confirm emergency pause and status screens; verify optional Scendey sync with explicit consent; run a two-month pilot. This branch does not deploy or make live payments.
