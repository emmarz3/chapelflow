# Homepage studio

The public homepage is driven by one JSON document that the **Super Admin** edits at
`/app/admin/homepage` (sidebar: Community → Homepage studio). Changes go live as soon as
they are saved.

## What can be edited

| Area | What the Super Admin controls |
| --- | --- |
| Hero & page text | Chapel name, hero title/intro/buttons/photo/caption, the numbers under the title, the countdown target, every section's heading and intro (or hide the section), the welcome pillars and the closing invitation |
| Announcements | The scrolling notice ticker (add, edit, hide, reorder) |
| Services | Sunday, midweek and vigil services: name, venue, minister, time, length, weekly / last-Friday / one-off date. These also drive the calendar, the countdown and the Google / Apple calendar buttons |
| Events | Name, category, dates or weekly repeat, time text, venue, Register or RSVP button, places available and places already taken |
| Sermons | Title, speaker, series, date, length, video / audio / download links, cover image |
| Ministries | Name, icon, description, meeting time |
| Gallery | Caption, sub-caption, photo (URL or upload) |
| Verses | The verse-of-the-day rotation, including a short reflection |
| Contact & social | Address, public email and phone, Facebook, X, Instagram and YouTube (shown in every public page footer) |
| Sign-ups | Event registrations, RSVPs and unit-join requests from visitors, with status, search, CSV export and delete |

Every entry can be **hidden** without deleting it, and lists can be re-ordered. New ministries,
events, services, sermons, photos, verses and announcements are added with the “Add” buttons.
“Restore defaults” returns the site to the built-in sample content (sign-ups are kept).

## How it works

- **Storage:** `operations.HomepageContent` (a single row holding validated JSON plus a `version`)
  and `operations.HomepageRequest` (visitor sign-ups; one per person per programme).
- **Defaults:** until the first save the API returns `content: null` and the React app renders the
  defaults in `src/lib/homepage-content.ts`. The sample names, venues, dates and sermons there are
  placeholders, replace them in the studio. No unverified phone, email or social account is
  published by default.
- **Validation:** `apps/operations/homepage_schema.py` type-checks and length-limits every field,
  drops unknown keys, accepts only `https://`, `http://`, `/path` and (for links) `#anchor`
  addresses, and rejects bad dates, times, icons and duplicate ids. Field errors come back keyed
  by path (for example `events[2].startDate`) and are shown next to the field.
- **Concurrency:** saves send the version they loaded; a stale version returns `409` so two admins
  cannot silently overwrite each other.
- **Audit:** every save, reset and sign-up status change or deletion writes an audit-log entry.

## API

| Method and path | Access | Purpose |
| --- | --- | --- |
| `GET /api/v1/site/homepage/` | Public | Content (or `null`), version, per-event sign-up counts |
| `POST /api/v1/site/homepage/requests/` | Public, throttled, honeypot | Event registration / RSVP or unit-join request. Requires consent; enforces capacity; always answers the same way whether or not the email already signed up |
| `GET` / `PUT` / `DELETE /api/v1/operations/homepage/` | Super Admin | Read, save (`{ content, version }`) or reset |
| `GET /api/v1/operations/homepage/requests/` | Super Admin | Sign-ups (`kind`, `status`, `item`, `search` filters) |
| `PATCH` / `DELETE /api/v1/operations/homepage/requests/<id>/` | Super Admin | Change status / delete |

These routes live under `site/` because `public/<kind>/<slug>/` in the organizations app would
otherwise shadow them.

## Notes

- Places shown as taken = the manual “places already taken” number + online sign-ups.
- Times are West Africa Time (UTC+1, no daylight saving).
- Homepage requests are served by the Django backend through the frontend adapter.
