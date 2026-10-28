# Frontend ↔ Django API integration (Phase 5)

The React app can run against the Django API or against its bundled catalogue.
The mode is chosen at build/start time by `VITE_API_BASE_URL`:

| `VITE_API_BASE_URL` | Data source | Likes/saves | Downloads |
| --- | --- | --- | --- |
| unset/empty | `src/data/` bundle, 56 records | `localStorage` (`bwe:liked`, `bwe:saved`) | direct image URL |
| set | `/api/v1/` | Django library endpoints, Bearer token | `POST …/download/` then the returned URL |

A failed API request is **never** replaced by bundled data: the catalogue area
shows the error and a retry button. The fallback exists only when the variable
is absent, so production misconfiguration cannot silently show stale content.

## Configuration

1. Start the backend (MySQL for a real deployment; the SQLite harness is fine
   for local checks):

   ```bash
   cd backend
   source .venv/bin/activate
   python manage.py migrate
   python manage.py runserver 0.0.0.0:8000
   ```

2. Allow the Vite origin in the backend `.env`. The development defaults
   already contain both common origins:

   ```text
   CORS_ALLOWED_ORIGINS=http://localhost:5173,http://127.0.0.1:5173
   CSRF_TRUSTED_ORIGINS=http://localhost:5173,http://127.0.0.1:5173
   CORS_ALLOW_CREDENTIALS=False
   ```

   Wildcards are rejected at startup. Add the deployed SPA origin explicitly.

3. Create `Front End Project/.env.local` (Git-ignored):

   ```text
   VITE_API_BASE_URL=http://127.0.0.1:8000
   VITE_GOOGLE_CLIENT_ID=1234567890-abc.apps.googleusercontent.com
   ```

   `Front End Project/.env.example` documents the same two variables. Only
   public values belong here: **never** put `GOOGLE_OAUTH_CLIENT_SECRET`,
   database credentials, or JWT keys in a `VITE_*` variable — Vite inlines
   them into the public bundle.

4. Run the frontend:

   ```bash
   cd "Front End Project"
   npm ci
   npm run dev
   ```

   Remove `VITE_API_BASE_URL` (or leave it empty) to return to the bundled
   catalogue. Restart Vite after changing env files; env values are read at
   server start/build time.

### Google OAuth setup

1. In Google Cloud Console create an OAuth 2.0 **Web application** client.
2. Add the SPA origins (`http://localhost:5173`, and the production origin) to
   *Authorized JavaScript origins*.
3. Put the client ID and secret in `backend/.env`:
   `GOOGLE_OAUTH_CLIENT_ID`, `GOOGLE_OAUTH_CLIENT_SECRET`. The secret stays on
   the server.
4. Put the **same client ID** in `VITE_GOOGLE_CLIENT_ID`.
5. The SPA uses Google Identity Services and the ID-token flow
   (`provider_token`). The OAuth redirect flow is not used because its state
   lives in a server session the SPA never receives.

No Google credentials exist in this workspace, so the button renders an
explicit “not configured” note when the variable is empty, and all provider
responses in tests are mocked. Sign-in has **not** been exercised against real
Google; complete the steps above and verify manually before release.

## Authentication and refresh behaviour

1. GIS returns a Google ID token (`credential`) to the page.
2. The app posts it to `/_allauth/app/v1/auth/provider/token`:

   ```json
   {
     "provider": "google",
     "process": "login",
     "token": { "id_token": "<google id token>", "client_id": "<public client id>" }
   }
   ```

3. allauth verifies the token and answers `200` with application tokens in
   `meta` (`access_token`, `refresh_token`, `session_token`). The Google ID
   token is **never** used as the API token.
4. The app calls `GET /api/v1/auth/me/` with `Authorization: Bearer <access>`
   and displays the profile.
5. Any authenticated request that returns `401` triggers exactly one
   `POST /_allauth/app/v1/tokens/refresh` with `{"refresh_token": …}`. Success
   replaces both tokens (rotation) and the call is retried once. Failure clears
   the session, shows “Your session expired”, opens the sign-in dialog, and
   returns the UI to the guest state; there is no retry loop.
6. Sign-out calls `DELETE /_allauth/app/v1/auth/session` with
   `X-Session-Token`. allauth answers `401` even though it destroys the
   session; the client ignores that response and clears local state either way.
   A subsequent request with the old access token returns `401`.

Token storage: both JWTs and the session token live only in a module-level
in-memory store. They are not written to `localStorage`, `sessionStorage`, or
cookies, and are never logged. Trade-offs:

- A page reload signs the user out; there is no silent re-login.
- Same-page JavaScript (including a successful XSS) can still read in-memory
  values. This is not a claim that browser storage is secure — it is a
  deliberate choice to avoid persistence in this phase.
- Because `CORS_ALLOW_CREDENTIALS=False`, the SPA does not rely on cookies.

## Field mapping

The API and the approved UI model differ. `src/lib/adapters.js` performs the
mapping; components were not rewritten.

| UI field | API source | Notes |
| --- | --- | --- |
| `id` | `slug` | Stable public identifier; numeric PKs are never exposed |
| `category` | `category.name` | Display string |
| `categorySlug` | `category.slug` | Used for server-side category queries |
| `tags` | `tags[].name` | Display strings |
| `tagSlugs` | `tags[].slug` | Used for `tag=` queries |
| `url` (list) | `thumbnail_url`, fallback `url` | Card preview |
| `fullUrl` / detail `url` | `url` | Uploaded or external full image |
| `width` / `height` | `width` / `height` | May be `null`; no aspect ratio then |
| `source.license` / `.licenseUrl` | detail `license.name` / `.url` | Only real licence data |
| `source.licenseStatus` | detail `license.status` | `documented`/`unverified`/`unknown` |
| `source.sourceUrl` | detail `source_url` | Optional original-artwork link |
| `source.author` / `.collection` / `.licenseFile` / `.modified` | — | **Not stored by the backend; never fabricated** (only the bundled records have them) |
| liked/saved sets | `results[].wallpaper.slug` | From `/library/likes/` and `/library/saved/` |
| download | `POST …/{slug}/download/` → `download_url` | File is fetched from that URL, never proxied |

Query mapping (`toWallpaperQuery`) supports the documented parameters:
`search` (trimmed, ≤100), `category` (slug), repeated `tag` (slugs),
`orientation`, and `ordering=title` for the “Title A–Z” sort. The UI’s
“Collection order” is local insertion order and maps to no API parameter.

## Area-by-area behaviour

**Catalogue.** The app loads `/categories/`, `/tags/`, `/wallpapers/`, and
`/wallpapers/popular/`, following `next` links at `page_size=60` (the API’s
maximum) for up to 10 pages (600 records). Loading, empty, error-with-retry,
and broken-image states are rendered. Counts come from the API. The home
spotlight uses the three most-downloaded real records from `/popular/`;
“Recently added” uses `published_at` ordering. Curated collections and the
editorial featured IDs have no API equivalent and are only shown in local
mode — no replacement metadata is invented.

**Search/filtering.** Filtering is applied to the loaded catalogue in the
browser so the approved multi-term AND search over title, category, and tags
keeps working. The backend’s `search` parameter is a single substring over
title/description; using it would change behaviour, so the UI does not send it
per keystroke. The mapping is implemented and unit-tested for callers that
need server filtering.

**Detail.** Opening a card shows the list record immediately and requests
`GET /api/v1/wallpapers/{slug}/`; the licence/source block appears when the
detail arrives (“Loading full details…” meanwhile). If the detail request
fails, the list record stays visible with a notice.

**Library.** After sign-in the app loads both library lists and uses the
returned slugs as the UI state. Toggling calls `POST`/`DELETE` with
`{"wallpaper": "<slug>"}`; the UI updates from the response, and duplicate
in-flight toggles for the same item are ignored. Anonymous clicks open the
sign-in dialog instead of writing a local substitute. `401`s go through the
single refresh path; other failures show an error and leave the server state
unchanged. `bwe:theme` remains local; `bwe:liked`/`bwe:saved` are only used in
local mode.

**Downloads.** The app calls the download endpoint, then fetches the returned
`download_url` as an image blob. “Download started” appears only after the blob
is handed to the browser, so a counted request is not reported as a completed
transfer. `404`, `409` (no image), `429` (throttle), and unreachable-image
errors show explanatory notices plus a link to the image.

## Verification performed

- `npm test` — 34 Node tests, including request construction, bearer headers,
  pagination/envelope handling, error normalisation, query mapping, adapters,
  session refresh/expiry, sign-out, download URL handling, and the lazy GIS
  loader.
- `npm run lint` and `npm run build` (both modes) pass; an API-mode build
  contains the configured base URL and client ID.
- A live Node probe against the Django API (SQLite preview settings, not MySQL)
  exercised categories/tags/wallpapers/popular/detail, the download endpoint
  and counter increment, anonymous `401`, username login, `/auth/me/`, like and
  save create/list/delete, refresh rotation, CORS on the Vite origin, and
  logout invalidating the access token.
- Server-side renders of `App` in both modes produced the expected initial
  states.
- **No browser interaction or visual check was run:** this sandbox has no
  Playwright browser binary and cannot download one. Existing Playwright specs
  were not executed.

## Limitations

- Real Google sign-in, MySQL, and production deployment remain unverified.
- Tokens are lost on reload; there is no persistent login in this phase.
- The UI loads at most 600 wallpapers (10 × 60) and shows a notice when the
  catalogue is larger; a full solution needs server-side paging or filtering
  UI.
- Server-side search would differ from the current multi-term UI search; see
  above.
- External image hosts may block browser `fetch` (CORS), in which case the
  download fails with a link to open the image directly. This is not a proxy
  failure.
- Google Identity Services does not report closing the account popup as a
  cancellation event. No request is made and the button returns to its idle
  state, but no cancellation message can be shown.
- Browser-local likes/saves from bundled mode are not imported into an account;
  the two libraries are intentionally separate.
- Download throttling is server-configured (`API_DOWNLOAD_THROTTLE_RATE`,
  default 60/minute); the UI only reports `429`.
- The API-mode spotlight is a download ranking, not editorial curation, and is
  labelled as general spotlight rather than trending.
