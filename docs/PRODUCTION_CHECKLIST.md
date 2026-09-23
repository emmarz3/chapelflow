# Production readiness checklist

- Confirm every endpoint, field, enum, pagination format, and error payload against the backend.
- Configure secure HttpOnly session cookies, CSRF handling, trusted origins, and session renewal.
- Replace preview content and the generated hero with approved CMS content and institutional photography.
- Configure official privacy/support contacts; complete Nigerian legal and safeguarding review.
- Connect payment, livestream, email, SMS, WhatsApp, push, maps, and upload providers where approved.
- Enforce backend role, branch, row, field, finance, pastoral-note, and audit permissions.
- Add idempotency and reconciliation rules for attendance, event check-in, and finance mutations.
- Validate file type, size, malware scanning, media captions, and signed upload/download URLs.
- Run the included desktop/mobile Playwright journeys in CI; add backend-connected contract tests when a test API environment exists.
- Set CSP, HSTS, referrer policy, permissions policy, monitoring, backups, retention, and incident procedures.
- Test camera and kiosk flows on target Android tablets and lower-bandwidth mobile devices.
- Verify WCAG 2.2 AA with keyboard, screen reader, contrast, zoom, and reduced-motion checks.
- Provision PostgreSQL, apply `npm run db:migrate`, and verify the attendance uniqueness and partial active-session indexes.
- Store the session, QR signing, initial administrator, and two usher password variables in the deployment secret manager; never commit them.
- Run `npm run db:seed` after migration and confirm both restricted usher accounts can sign in to `/usher/attendance`.
- Reverse-proxy same-origin `/api` traffic to the compiled API and set `APP_ORIGIN` to the exact HTTPS frontend origin.
- Test camera permissions and ZXing scanning on the actual usher Android/iOS devices before the first live service.
- Confirm the chapel administration's identity-verification procedure before approving pending student registrations.
