# Attendance page adaptation plan

## Existing flows

The frontend attendance page currently expects a separate session lifecycle: a `/current` endpoint, scheduled sessions with an activate action, a session QR endpoint, a check-in feed, and `PATCH` corrections. Its creation form sends title, venue, date, and opening/closing clock times.

Django exposes branch-scoped `AttendanceSession` records at `/api/v1/attendance/sessions/`. A session has `branch`, `label`, `is_open`, `state`, `window_opens_at`, and `window_closes_at`; creation is a normal `POST` and requires a branch. Sessions are created open, with pause/resume/close actions. There is no venue field, activation action, session QR, or admin check-in feed. Attendance records are read from `/api/v1/attendance/records/` and corrected with `POST /api/v1/attendance/records/{id}/correct/`.

The existing Django check-in flow uses a student's attendance pass and an usher's rotating checkpoint token (`/attendance/checkpoint/token/` and `/attendance/student-scan/`). The frontend already has student pass and usher checkpoint pages. Django also exposes redacted scan attempts, but not a live list of check-ins for an admin screen.

## Recommended design

Adapt the page and adapter to the Django model. List sessions scoped to the logged-in user's `branchId`; select a current session when it is open and its configured time window includes the current time (or when it has no window). List its records from the session-filtered records endpoint. Use Django's POST correction action and translate the form fields to the serializer's exact names.

Map service/event name to `label`, and date plus opening/closing times to ISO `window_opens_at` and `window_closes_at`. Send `branch` from the logged-in user's `branchId`. Remove the venue field because Django has no venue property; the page will state that the session is tied to the user's branch. If `branchId` is absent, show a clear message and disable creation.

Do not add Express-style backend endpoints. Remove activation and session-QR controls. Point users to the existing student attendance pass and usher checkpoint scanner for check-ins. Keep the admin live check-in section unavailable with a local explanation because Django has no admin check-in feed; this affects only that section. Session history and record corrections remain usable.
