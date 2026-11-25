# ChapelFlow advertising rollout

The advertising screens and moderation API deploy with the application. Paid checkout remains disabled until `PAYSTACK_SECRET_KEY` is configured on `chapelflow-api` in Railway. Use the key for the Paystack account designated to receive chapel ad revenue, after the chapel and account owner agree on revenue, refunds and ad policy. Never commit a key.

Paystack sends one integration webhook to `https://chapelflow-api-production.up.railway.app/api/v1/payments/webhook/paystack/`. The existing giving endpoint now routes signed ad events to the advertising handler. Do not replace this URL with the ads-only alias or giving webhooks will stop. Recurring plans are created on first checkout at ₦3,000 and ₦7,500 monthly. Checkout is restricted to card and direct debit, which Paystack supports for subscriptions. Payment verification, idempotent renewals and failed invoice handling are server-side. Do a live low-value test only after the account owner has reviewed payment settings.

Set `SCENDEY_WAITLIST_URL` on the Railway API to the HTTPS Scendey `/api/join` endpoint to send consented, paid advertisers to its brand waitlist. The Scendey endpoint sends its own verification email. Without this variable, consent is recorded but no Scendey signup is attempted. Check Scendey email delivery before turning this on. If the variable is added after advertisers subscribed, enqueue `apps.advertising.tasks.sync_scendey_waitlist` for any opted-in, unsynced paid campaign.

The first-month ₦2,000 founding offer is not enabled: Paystack's simple monthly plan charges the same amount each renewal. A first-month discount requires a separate one-time charge followed by a scheduled full-price subscription with explicit renewal consent, which should be tested against a live Paystack sandbox before advertising it.

The ads show in the public homepage and events page only for approved campaigns with a verified, unexpired paid period. Admin path: `/app/admin/advertising`; advertiser path: `/app/advertise`. No ads appear on auth, attendance, giving or pastoral care screens.
