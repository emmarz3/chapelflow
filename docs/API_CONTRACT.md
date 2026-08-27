# Frontend API contract

No backend was present in the supplied workspace. These integration points are therefore isolated requirements, not claims about existing endpoints. Confirm paths and payloads against the ChapelFlow backend before deployment.

| Capability             | Proposed method and path                   | Request                                      | Response                                      | Auth / permission                            |
| ---------------------- | ------------------------------------------ | -------------------------------------------- | --------------------------------------------- | -------------------------------------------- |
| Login                  | `POST /auth/login`                         | `{ identifier, password }`                   | `{ data: User }` plus HttpOnly session cookie | Public, rate-limited                         |
| Logout                 | `POST /auth/logout`                        | Empty                                        | `204`                                         | Authenticated                                |
| Current user           | `GET /auth/me`                             | None                                         | `{ data: User }`                              | Authenticated                                |
| Register               | `POST /auth/register`                      | Account, profile, membership, consent fields | Verification status                           | Public, rate-limited                         |
| Password recovery      | `POST /auth/forgot-password`               | `{ identifier }`                             | Generic accepted response                     | Public, rate-limited                         |
| Password reset         | `POST /auth/reset-password`                | `{ token, password }`                        | `204`                                         | Public, rate-limited, single-use token       |
| Email verification     | `POST /auth/verify-email`                  | `{ token }`                                  | Verification status                           | Public, rate-limited, single-use token       |
| OTP verification       | `POST /auth/verify-otp`                    | `{ identifier, code }`                       | Verification status                           | Public, rate-limited                         |
| Change password        | `POST /auth/change-password`               | Current and new passwords                    | `204`                                         | Authenticated                                |
| Members                | `GET /members`                             | Query pagination and filters                 | `PagedResponse<Member>`                       | `members:read`                               |
| Member mutations       | `POST /members`, `PATCH /members/:id`      | Authorized member fields                     | Member record                                 | `members:write`                              |
| Member lifecycle       | `POST /members/:id/archive\|restore`       | None                                         | `204`                                         | `members:write`, audited                     |
| Current attendance     | `GET /attendance/sessions/current`         | Active branch scope                          | Session and recent records                    | `attendance:read`                            |
| Attendance session     | `POST /attendance/sessions`                | Service, venue, branch, open/close times     | Session record                                | `attendance:write`                           |
| Attendance check-in    | `POST /attendance/sessions/:id/check-ins`  | QR token or member identifier                | Result and safe member summary                | Authenticated / kiosk grant                  |
| Attendance QR          | `GET /attendance/sessions/:id/qr`          | None                                         | Time-limited image data, reference, expiry    | `attendance:read`; backend rotates token     |
| Attendance correction  | `PATCH /attendance/records/:id`            | Status and required reason                   | Updated record and audit reference            | `attendance:write`                           |
| Events                 | `GET/POST /events`                         | Filters or event form                        | Page or event record                          | Read public/authorized; write `events:write` |
| Event registration     | `POST /events/:id/registrations`           | Registration answers                         | Confirmation / waitlist state                 | Authenticated or public token                |
| Cancel registration    | `DELETE /events/:id/registrations/me`      | None                                         | `204`                                         | Authenticated, current-user scope            |
| Finance                | `GET/POST /finance/transactions`           | Scoped filters or transaction                | Permission-filtered record                    | `finance:read/write`                         |
| Broadcasts             | `POST /communications/broadcasts`          | Channel, audience, content, schedule         | Draft or confirmation summary                 | `communication:write` plus confirm step      |
| Send broadcast         | `POST /communications/broadcasts/:id/send` | None                                         | `204`                                         | `communication:write`, confirmed and audited |
| Worker assignments     | `GET /worker-assignments`, `POST /rosters` | Filters or roster assignments                | Page or roster                                | `workers:read/write`                         |
| Worker acknowledgement | `POST /worker-assignments/:id/acknowledge` | None                                         | `204`                                         | Assignee or `workers:write`                  |
| Worker leave           | `POST /worker-leave-requests`              | Dates and reason                             | `204`                                         | Current worker                               |
| Assets                 | `GET/POST /assets`                         | Filters or asset details                     | Page or asset                                 | `assets:read` plus backend write permission  |
| Asset movement         | `POST /assets/:id/movements`               | Movement type and custody details            | `204`                                         | `assets:write`, audited                      |
| Media                  | `GET/POST /media`                          | Filters or validated media metadata          | Page or media record                          | `media:write`                                |
| CMS                    | `GET/POST /cms/content`                    | Filters or content fields                    | Page or content record                        | `cms:write`                                  |
| Publish content        | `POST /cms/content/:id/publish`            | None                                         | `204`                                         | `cms:write`, confirmed and audited           |
| Branches               | `GET/POST /branches`                       | Filters or branch fields                     | Page or branch                                | `branches:manage`                            |
| Analytics              | `GET /analytics/:module`                   | Branch and date range                        | Series, totals, textual summary               | `analytics:read`                             |
| Audit                  | `GET /audit-events`                        | Authorized filters                           | Redacted paged events                         | `audit:read`                                 |
| Public CMS             | `GET /public/content/:slug`                | None                                         | Published content sections                    | Public; published fields only                |
| Public detail          | `GET /public/:kind/:id`                    | Kind is events, sermons, or news             | Published detail sections                     | Public or visibility-scoped                  |
| Account sessions       | `GET /auth/sessions`                       | None                                         | Active sessions                               | Authenticated; current-user scope            |
| Revoke session         | `DELETE /auth/sessions/:id`                | None                                         | `204`                                         | Authenticated; current-user scope            |
| Privacy preferences    | `GET/PATCH /account/privacy-preferences`   | Channel preferences                          | Preferences or `204`                          | Authenticated; current-user scope            |
| Data requests          | `POST /account/data-export-requests`       | None                                         | Request reference                             | Authenticated; current-user scope            |
| Deletion requests      | `POST /account/deletion-requests`          | Reason                                       | Request reference                             | Authenticated; policy review required        |

Expected errors use `{ code, message, fieldErrors?, requestId? }` with an appropriate HTTP status. Authentication errors must be generic. Mutations that can duplicate attendance or financial data should accept backend idempotency keys.

All paths above are implemented behind the typed frontend service layer. They remain proposed until matched to the actual ChapelFlow backend; the supplied workspace contains no backend source or OpenAPI specification.

Paged list responses use `{ data: T[], page, pageSize, total }`. Single-record responses use `{ data: T }`. Dates are ISO 8601 strings. The backend must ignore client-supplied branch or actor identifiers that conflict with the authenticated session.

## Role and permission matrix

| Permission area | Super admin | Chapel admin  |     Pastor      |    Worker     |     Member      |
| --------------- | :---------: | :-----------: | :-------------: | :-----------: | :-------------: |
| Dashboard       |     Yes     |      Yes      |       Yes       |      Yes      |       Yes       |
| Members         |   Manage    |    Manage     |      Read       |      No       |    Self only    |
| Attendance      |   Manage    |    Manage     |      Read       |   Own/read    |    Own/read     |
| Events          |   Manage    |    Manage     |     Manage      |     Read      |  Read/register  |
| Finance         |   Manage    |    Manage     |       No        |      No       | Own giving only |
| Communication   |   Manage    |    Manage     | Backend-defined |    Receive    |     Receive     |
| Workers         |   Manage    |    Manage     |      Read       | Own schedule  |       No        |
| Assets          |   Manage    |    Manage     |       No        | Assigned only |       No        |
| CMS / audit     |   Manage    |  Manage/read  |       No        |      No       |       No        |
| Branches        |   Manage    | Active branch |  Active branch  | Active branch |  Active branch  |

The frontend matrix controls presentation only. The backend must enforce every record and field-level authorization decision.
