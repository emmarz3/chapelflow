# ChapelFlow performance baseline

**Snapshot date:** 27 November 2026  
**Environment:** Production (Vercel frontend + Railway Django API/PostgreSQL)  
**Purpose:** Establish evidence before the Phase 0–3 performance changes.

## Production observations

The baseline was collected from the current production build and the most recent 501 Railway HTTP request records available during the investigation. These are server-side request durations, not full mobile-device timings and not a representative load test.

| Endpoint | Sample count | Median server duration | 95th percentile | Maximum |
|---|---:|---:|---:|---:|
| `POST /api/v1/auth/login/` | 27 | 336 ms | 478 ms | 921 ms |
| `GET /api/v1/auth/csrf/` | 40 | 4 ms | 49 ms | 93 ms |
| `GET /api/v1/auth/me/` | 38 | 3 ms | 49 ms | 64 ms |
| `GET /api/v1/events/public/` | 38 | 37 ms | 109 ms | 121 ms |
| `GET /api/v1/public/content/sermons/` | 34 | 32 ms | 97 ms | 125 ms |
| `GET /api/v1/site/homepage/` | 34 | 44 ms | 96 ms | 143 ms |
| `GET /api/v1/ads/placement/home/` | 28 | 42 ms | 206 ms | 208 ms |

The API and PostgreSQL services were online with no active Railway service warnings or recent deployment failures. CPU and memory measurements were low over the captured 24-hour window. The API and database each ran one production replica in San Francisco at the time of measurement.

The figures above suggest that server processing alone does not explain the full delay reported by students. Browser startup, asset download/parse, network round trips to the hosted API, and the sequence of frontend requests also need to be measured.

## Frontend baseline

The production build before these changes emitted a JavaScript chunk of approximately **1.28 MB minified (369 KB gzip)**, plus a separate chunk of approximately **717 KB minified (330 KB gzip)** associated with font/PDF functionality. Vite warned about chunks larger than 500 KB.

The application currently:
- Performs a CSRF bootstrap before requesting the current user, even though the current-user request is a safe GET.
- Uses the global authentication loading state for the login submit button.
- Eagerly imports a number of feature modules from the application route registry.
- Precaches all generated JavaScript and CSS matching the broad Workbox glob pattern.

## Browser-side measurement added in Phase 0

`src/lib/performance.ts` adds local diagnostic markers and browser Performance API measurements. It does not send telemetry, credentials, account identifiers, or student data to a server.

In a deployed preview, append `?perf=1` to the page URL and inspect the browser console. The diagnostic report includes:
- Navigation response, DOM-ready and load timings.
- First Contentful Paint and Largest Contentful Paint.
- Cumulative Layout Shift.
- Longest observed interaction candidate and total long-task duration.
- Encoded JavaScript and stylesheet resource sizes.
- Application milestones such as app bootstrap, login form readiness, authentication completion and dashboard readiness.

The interaction value is deliberately labelled a candidate measurement; it is not claimed to be a standards-compliant field INP calculation.

## Measurement protocol

Compare before/after on:
1. First visit with an empty browser cache and no installed service worker.
2. Repeat visit with a warm browser cache.
3. Login route before typing, during submit and after successful authentication.
4. Student dashboard before and after its essential data becomes available.
5. Mobile throttling representative of slow 4G and a mid-range Android device.

Record at least five cold and five warm runs per scenario, report median and 75th/95th percentile where sample size permits, and do not mix browser-cache and service-worker-cache runs.

## Targets for Phases 0–3

These are engineering targets, not achieved results:
- Login form interactive within 2 seconds on the agreed slow-4G test profile.
- Initial application shell visible within 2.5 seconds on that profile.
- At least 30% reduction in initial compressed JavaScript compared with the captured bundle baseline.
- No unnecessary eager download of administration, gallery, analytics, finance, community and PDF feature code on the login route.
- First-time PWA installation precaches the application shell and shared core assets, not every feature chunk.
- Repeat visits cache versioned feature chunks safely without caching authenticated API responses.
