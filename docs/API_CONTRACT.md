# ChapelFlow API contract

The authentication, student attendance, community, leadership, and notification routes below are implemented by the integrated TypeScript API. Other product-module routes remain frontend integration contracts until their backend modules are implemented.

| Capability              | Proposed method and path                                 | Request                                      | Response                                         | Auth / permission                               |
| ----------------------- | -------------------------------------------------------- | -------------------------------------------- | ------------------------------------------------ | ----------------------------------------------- |
| Login                   | `POST /auth/login`                                       | `{ identifier, password }`                   | `{ data: User }` plus HttpOnly session cookie    | Public, rate-limited                            |
| Logout                  | `POST /auth/logout`                                      | Empty                                        | `204`                                            | Authenticated                                   |
| Current user            | `GET /auth/me`                                           | None                                         | `{ data: User }`                                 | Authenticated                                   |
| Register                | `POST /auth/register`                                    | Account, profile, membership, consent fields | Pending administrator approval                   | Public, rate-limited                            |
| Leader account setup    | `POST /auth/setup-password`                              | `{ token, password }`                        | Active user plus HttpOnly session cookie         | Public, rate-limited, single-use token          |
| Password recovery       | `POST /auth/forgot-password`                             | `{ identifier }`                             | Generic accepted response                        | Public, rate-limited                            |
| Password reset          | `POST /auth/reset-password`                              | `{ token, password }`                        | `204`                                            | Public, rate-limited, single-use token          |
| Email verification      | `POST /auth/verify-email`                                | `{ token }`                                  | Verification status                              | Public, rate-limited, single-use token          |
| OTP verification        | `POST /auth/verify-otp`                                  | `{ identifier, code }`                       | Verification status                              | Public, rate-limited                            |
| Change password         | `POST /auth/change-password`                             | Current and new passwords                    | `204`                                            | Authenticated                                   |
| Members                 | `GET /members`                                           | Query pagination and filters                 | `PagedResponse<Member>`                          | `members:read`                                  |
| Member mutations        | `POST /members`, `PATCH /members/:id`                    | Authorized member fields                     | Member record                                    | `members:write`                                 |
| Member lifecycle        | `POST /members/:id/archive\|restore`                     | None                                         | `204`                                            | `members:write`, audited                        |
| Approve student         | `POST /members/:id/approve`                              | None                                         | Active student account                           | `members:write`, pending students only, audited |
| Registration options    | `GET /public/communities`                                | Optional community type                      | Active unit and fellowship records               | Public                                          |
| My communities          | `GET /communities`                                       | None                                         | Accessible communities and unread counts         | Authenticated, record-scoped                    |
| Community workspace     | `GET /communities/:slug`                                 | None                                         | Overview, leaders, access capabilities           | Active member, scoped leader, or overseer       |
| Community chat          | `GET/POST /communities/:slug/messages`                   | Search/history or validated message          | Message records                                  | Active member; posting follows community rule   |
| Message moderation      | `DELETE /communities/:slug/messages/:id`                 | None                                         | `204`                                            | Scoped leader or community manager              |
| Community announcements | `GET/POST /communities/:slug/announcements`              | List or announcement fields                  | Announcement records                             | Read scoped; write scoped leader/manager        |
| Community events        | `GET/POST /communities/:slug/events`                     | List or event fields                         | Community event records                          | Read scoped; write scoped leader/manager        |
| Community members       | `GET /communities/:slug/members`                         | None                                         | Scoped member directory                          | Scoped leader or community manager              |
| Membership status       | `PATCH /communities/:slug/members/:id`                   | `{ status }`                                 | Updated membership                               | Scoped leader or community manager, audited     |
| Community stream        | `GET /communities/:slug/stream`                          | SSE subscription                             | Authorized community events                      | Access revalidated while connected              |
| Leadership directory    | `GET /communities/leadership/directory`                  | None                                         | Active and vacant leadership positions           | Authenticated                                   |
| Manage communities      | `GET/POST/PATCH /admin/communities`                      | Community configuration                      | Community records                                | `community:manage`, audited                     |
| Manage leadership       | `GET /admin/leadership`, `POST /admin/leadership/assign` | Filters or assignment/transfer               | Assignment with preserved history                | `leadership:manage`, audited                    |
| Provision leader        | `POST /admin/accounts`                                   | Name, identifier, optional position          | Expiring one-time setup path                     | `leadership:manage`; no password returned       |
| Notifications           | `GET /notifications`, `PATCH /notifications/:id/read`    | None                                         | User-scoped notifications/read state             | Current user only                               |
| Chapel announcement     | `GET/POST /notifications/chapel-announcements`           | List or announcement fields                  | Chapel-wide announcement                         | Read authenticated; write `chapel:announce`     |
| Current attendance      | `GET /attendance/sessions/current`                       | Active branch scope                          | Session and recent records                       | `attendance:read`                               |
| Attendance session      | `POST /attendance/sessions`                              | Service, venue, branch, open/close times     | Session record                                   | `attendance:write`                              |
| Attendance check-in     | `POST /attendance/sessions/:id/check-ins`                | QR token or member identifier                | Result and safe member summary                   | Authenticated / kiosk grant                     |
| Attendance QR           | `GET /attendance/sessions/:id/qr`                        | None                                         | Time-limited image data, reference, expiry       | `attendance:read`; backend rotates token        |
| Attendance correction   | `PATCH /attendance/records/:id`                          | Status and required reason                   | Updated record and audit reference               | `attendance:write`                              |
| Student pass            | `GET /attendance/pass`                                   | None                                         | Own identity, signed rotating QR, active session | Authenticated student, ownership enforced       |
| Student history         | `GET /attendance/history/me`                             | None                                         | Own attendance records                           | Authenticated student, ownership enforced       |
| Active scanner session  | `GET /attendance/sessions/active`                        | None                                         | Active service, own recent scans, count          | `attendance:scan`                               |
| Usher QR scan           | `POST /attendance/scan`                                  | `{ token, sessionId, idempotencyKey }`       | Recorded or duplicate result                     | `attendance:scan`, rate-limited                 |
| Manual attendance       | `POST /attendance/manual`                                | Identifier, session, reason, idempotency key | Recorded or duplicate result                     | `attendance:manual`, audited                    |
| Activate session        | `PATCH /attendance/sessions/:id/activate`                | None                                         | Active session state                             | `attendance:write`, audited                     |
| Close session           | `PATCH /attendance/sessions/:id/close`                   | None                                         | Closed session state                             | `attendance:write`, audited                     |
| List sessions           | `GET /attendance/sessions`                               | Optional status filter                       | Scheduled/active/closed sessions                 | `attendance:write`                              |
| Events                  | `GET/POST /events`                                       | Filters or event form                        | Page or event record                             | Read public/authorized; write `events:write`    |
| Event registration      | `POST /events/:id/registrations`                         | Registration answers                         | Confirmation / waitlist state                    | Authenticated or public token                   |
| Cancel registration     | `DELETE /events/:id/registrations/me`                    | None                                         | `204`                                            | Authenticated, current-user scope               |
| Finance                 | `GET/POST /finance/transactions`                         | Scoped filters or transaction                | Permission-filtered record                       | `finance:read/write`                            |
| Broadcasts              | `POST /communications/broadcasts`                        | Channel, audience, content, schedule         | Draft or confirmation summary                    | `communication:write` plus confirm step         |
| Send broadcast          | `POST /communications/broadcasts/:id/send`               | None                                         | `204`                                            | `communication:write`, confirmed and audited    |
| Worker assignments      | `GET /worker-assignments`, `POST /rosters`               | Filters or roster assignments                | Page or roster                                   | `workers:read/write`                            |
| Worker acknowledgement  | `POST /worker-assignments/:id/acknowledge`               | None                                         | `204`                                            | Assignee or `workers:write`                     |
| Worker leave            | `POST /worker-leave-requests`                            | Dates and reason                             | `204`                                            | Current worker                                  |
| Assets                  | `GET/POST /assets`                                       | Filters or asset details                     | Page or asset                                    | `assets:read` plus backend write permission     |
| Asset movement          | `POST /assets/:id/movements`                             | Movement type and custody details            | `204`                                            | `assets:write`, audited                         |
| Media                   | `GET/POST /media`                                        | Filters or validated media metadata          | Page or media record                             | `media:write`                                   |
| CMS                     | `GET/POST /cms/content`                                  | Filters or content fields                    | Page or content record                           | `cms:write`                                     |
| Publish content         | `POST /cms/content/:id/publish`                          | None                                         | `204`                                            | `cms:write`, confirmed and audited              |
| Branches                | `GET/POST /branches`                                     | Filters or branch fields                     | Page or branch                                   | `branches:manage`                               |
| Analytics               | `GET /analytics/:module`                                 | Branch and date range                        | Series, totals, textual summary                  | `analytics:read`                                |
| Audit                   | `GET /audit-events`                                      | Authorized filters                           | Redacted paged events                            | `audit:read`                                    |
| Public CMS              | `GET /public/content/:slug`                              | None                                         | Published content sections                       | Public; published fields only                   |
| Public detail           | `GET /public/:kind/:id`                                  | Kind is events, sermons, or news             | Published detail sections                        | Public or visibility-scoped                     |
| Account sessions        | `GET /auth/sessions`                                     | None                                         | Active sessions                                  | Authenticated; current-user scope               |
| Revoke session          | `DELETE /auth/sessions/:id`                              | None                                         | `204`                                            | Authenticated; current-user scope               |
| Privacy preferences     | `GET/PATCH /account/privacy-preferences`                 | Channel preferences                          | Preferences or `204`                             | Authenticated; current-user scope               |
| Data requests           | `POST /account/data-export-requests`                     | None                                         | Request reference                                | Authenticated; current-user scope               |
| Deletion requests       | `POST /account/deletion-requests`                        | Reason                                       | Request reference                                | Authenticated; policy review required           |

Expected errors use `{ code, message, fieldErrors?, requestId? }` with an appropriate HTTP status. Authentication errors must be generic. Mutations that can duplicate attendance or financial data should accept backend idempotency keys.

All paths are represented behind the typed frontend service layer. Authentication, attendance, community, leadership, and notification paths are implemented under `server/`; unrelated product-module paths remain proposed integration points.

Paged list responses use `{ data: T[], page, pageSize, total }`. Single-record responses use `{ data: T }`. Dates are ISO 8601 strings. The backend must ignore client-supplied branch or actor identifiers that conflict with the authenticated session.

## Role and permission matrix

| Permission area |  Super admin  | Chapel admin  |      Pastor      |      Worker       |      Member       |
| --------------- | :-----------: | :-----------: | :--------------: | :---------------: | :---------------: |
| Dashboard       |      Yes      |      Yes      |       Yes        |        Yes        |        Yes        |
| Members         |    Manage     |    Manage     |       Read       |        No         |     Self only     |
| Attendance      |    Manage     |    Manage     |       Read       |     Own/read      |     Own/read      |
| Events          |    Manage     |    Manage     |      Manage      |       Read        |   Read/register   |
| Finance         |    Manage     |    Manage     |        No        |        No         |  Own giving only  |
| Communication   |    Manage     |    Manage     | Backend-defined  |      Receive      |      Receive      |
| Communities     | Global manage | Global manage | Global oversight | Scoped membership | Scoped membership |
| Workers         |    Manage     |    Manage     |       Read       |   Own schedule    |        No         |
| Assets          |    Manage     |    Manage     |        No        |   Assigned only   |        No         |
| CMS / audit     |    Manage     |  Manage/read  |        No        |        No         |        No         |
| Branches        |    Manage     | Active branch |  Active branch   |   Active branch   |   Active branch   |

The frontend matrix controls presentation only. The backend must enforce every record and field-level authorization decision.

The `attendance_usher` role is intentionally narrower than this general matrix: it receives only `attendance:read`, `attendance:scan`, and `attendance:manual`. It cannot create/activate/close sessions, manage users, view finance, change settings, or access broad analytics.

Community leadership is assignment-scoped and does not grant global administration. `chaplain` and `student_chaplain` can oversee all communities and publish chapel-wide announcements; `super_admin` retains technical configuration and leadership-management authority. A user can hold multiple global roles and multiple dated community leadership assignments.
