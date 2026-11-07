# ChapelFlow Privacy and Data Protection

**Status:** Phase 2 source review in progress, 2026-11-06. This is an engineering inventory, not legal advice or institutional approval.

## Data inventory and controls

| Data | Main source/use | Current access and handling | Open control |
|---|---|---|---|
| Account and profile | `accounts.User`, `members.Member`; sign-in, identity, contact and profile fields | Authentication uses secure cookies; profile changes are exposed through scoped account endpoints. Failed-login identifiers remain in access-controlled `LoginHistory`, not application logs after the Phase 2 fix. | Confirm field-level purpose, operator access, retention period and purge rules with the university. |
| Authentication and device history | Password hashes, refresh-token blacklist, login history, IP address and user agent | Passwords are hashed; refresh sessions can be revoked. Login history retains IP/user-agent and attempted identifiers for failed logins. | Define retention and access policy for login history and token blacklist data. |
| Attendance | Session/member check-ins, QR identifiers and correction audit events | Branch-scoped APIs and signed QR tokens; offline check-in identifiers now use tab-scoped storage and older persistent queues are migrated and cleared. | Confirm shared-device handling and retention/purge schedule for attendance, including offline failures. |
| Prayer and pastoral care | Prayer details, privacy level, requester, staff assignment, follow-up notes | Private requests are owner/staff scoped; notes are staff-only and omitted from member responses. Community sharing requires requester consent and pastoral approval; public serialization hides requester and internal staff IDs. Notifications do not include private request details. | Define retention, withdrawal and safeguarding procedures. Community content can still contain identifying details written into the free-text prayer itself. |
| Testimonies and user content | Testimony text, member, reviewer, consent and moderation status | Testimonies require explicit consent and pastoral approval before publication. Prayer content uses a separate consent gate. | Review removal and retention behavior after consent withdrawal; cover all content modules as moderation is audited. |
| Communications | Recipient preferences, announcements and notification records | Preferences are scoped to the signed-in member; prayer notification broadcasts require opt-in and sharing consent. | Define notification delivery/log retention and provider contract controls. |
| Reports and uploads | Membership, attendance, giving exports and media | New report objects are private and API access is requester-scoped; local download URLs are signed/temporary where supported. Legacy public exports and provider configuration remain a deployment launch gate. | Revoke/verify old public objects and check provider access policy in the deployed environment. |
| Privacy requests | Data export and account-deletion request type/status | Authenticated users can create and review their own request statuses. Request reasons are no longer collected or returned. Deletion requests expose a 30-day action deadline to users and operators. | Requests are queued for manual handling; there is no automated export/deletion executor. Authorized university representatives must define retention exceptions and an operational completion process. |
| Browser storage | CSRF cookie, UI preferences, offline attendance queue | Authentication tokens are not stored in browser local storage. The offline queue holds member identifiers in session storage and removes any prior persistent copy. | Review kiosk/tab lifecycle and apply a documented cleanup schedule to failed offline entries. |

## Phase 2 changes

- Member prayer responses no longer include pastoral follow-up note contents.
- Community prayer visibility requires a stored requester consent flag. Staff cannot set consent on the requester's behalf through the API.
- Public prayer responses redact requester and internal assignment identifiers for non-owner community viewers. Public notifications require consent and remain opt-in.
- Failed login logs no longer contain the submitted email or student identifier.
- Offline attendance identifiers no longer remain in persistent local storage; existing copies migrate to session storage and are removed from local storage.
- Users can review their own export/deletion request statuses. The endpoint no longer stores a free-text reason for these requests.
- The requested 30-day deletion deadline is calculated from submission, shown in account settings and the Django admin queue. It is a processing deadline, not automatic erasure. Operators must verify identity, review linked records and exceptions, perform approved deletion/anonymization, and mark completion only after the work is done.
- The register-to-login browser journey passes against Django, including dashboard navigation and session restore. The live Render API was suspended when checked on 2026-11-06, so live sign-in cannot complete until that service is resumed. During an API outage the dashboard now shows a service error and Retry instead of an expired-session redirect. The Vercel SPA rewrite serves `index.html` for direct application routes while preserving its API proxy.

## Policy decisions requiring institutional review

- Approve a data retention schedule for profiles, login history, attendance, prayer/counselling records, notifications, audit events, reports and uploads. The user selected 30 days after a deletion request as the action deadline; this is not a blanket lifetime for all records.
- Define how deletion requests are authenticated, reviewed, completed and communicated, including finance, safeguarding and audit retention exceptions. Do not automatically delete these records until that policy is approved.
- Review the privacy notice and Nigeria Data Protection Act 2023 alignment with authorized university representatives. The application copy is not evidence of legal approval.
- Decide the acceptable lifetime and cleanup behavior for failed offline attendance submissions on shared devices.

## Deletion request handling

An authenticated user submits a request in Account settings and can track its status there. ChapelFlow calculates an action deadline 30 days after submission and shows it to the requester and in the Django admin queue. A duplicate pending request returns the existing request ID. Free-text reasons are not collected.

An authorized operator must verify the request, identify linked prayer, attendance, financial, audit and uploaded records, apply approved retention exceptions, and delete or anonymize eligible records. The operator should record completion only after the work has been verified and communicate the outcome through an approved institutional channel. The current application has no automated deletion executor or export fulfillment process; a displayed deadline alone does not complete a request. The university must approve the retention schedule, exceptions, contact channel and operator procedure before production use.

Local verification on 2026-11-06: the privacy request API test passed, Django `check` reported no issues, the frontend suite passed 128 tests, `npm run build` passed, and the Django browser registration/login/dashboard/session-restore test passed. Phase 2 remains active for the suspended Render API, live login verification, and institutional retention, deletion exception and legal approvals. These decisions must not be invented in code.
