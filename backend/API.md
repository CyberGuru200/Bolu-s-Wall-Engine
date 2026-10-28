# API reference (Phase 4)

Base URL in local development: `http://127.0.0.1:8000`

All responses are JSON. Local timezone is UTC; timestamps are ISO 8601 with
`Z`.

```
/api/health/                 liveness probe (no database access)
/api/v1/                     browseable index of the public collections
/api/v1/categories/          active categories
/api/v1/tags/                tags used by published wallpapers
/api/v1/wallpapers/          published wallpapers
/api/v1/wallpapers/popular/  all-time download ranking (not "trending")
/api/v1/library/likes/       the signed-in user's likes
/api/v1/library/saved/       the signed-in user's saved wallpapers
/api/v1/auth/me/             the signed-in user's profile
/_allauth/app/v1/            sign-in, tokens, logout, provider config (JSON)
```

Wallpapers are identified by **slug**, not by database primary key. Numeric
primary keys are not exposed by the public API.

## Public endpoints

| Method | Path | Authentication | Purpose |
| --- | --- | --- | --- |
| `GET` | `/api/health/` | None | Confirm Django is running |
| `GET` | `/api/v1/` | None | List the public collection URLs |
| `GET` | `/api/v1/categories/` | None | Active categories, ordered by name |
| `GET` | `/api/v1/categories/{slug}/` | None | One active category |
| `GET` | `/api/v1/tags/` | None | Tags with at least one published wallpaper |
| `GET` | `/api/v1/tags/{slug}/` | None | One public tag |
| `GET` | `/api/v1/wallpapers/` | None | Published wallpapers |
| `GET` | `/api/v1/wallpapers/{slug}/` | None | One published wallpaper |
| `GET` | `/api/v1/wallpapers/popular/` | None | Published wallpapers by download count |
| `POST` | `/api/v1/wallpapers/{slug}/download/` | None | Count a download and return its URL |

Category and tag endpoints are read-only. `POST`, `PUT`, `PATCH`, and `DELETE`
return `405 Method Not Allowed`; only Django Admin can change catalogue data.

### Visibility rules

A wallpaper is public only when **both** conditions hold:

- `status = published`;
- its category is active (`is_active = true`).

Draft, archived, and inactive-category wallpapers return `404` on detail,
download, like, and save routes, and never appear in lists, search, filters,
categories, tags, the popular ranking, or library responses.

A tag is public only when a published wallpaper in an active category uses it.
Category and tag `wallpaper_count` values count published wallpapers only.

### `GET /api/v1/categories/`

```json
{
  "count": 4,
  "next": null,
  "previous": null,
  "results": [
    {
      "name": "Anime",
      "slug": "anime",
      "description": "Animated and illustrated artwork.",
      "image_url": null,
      "image_source": null,
      "wallpaper_count": 6
    }
  ]
}
```

`image_url` is the uploaded image's absolute URL when a category image exists,
otherwise the configured external URL. `image_source` is `"uploaded"`,
`"external"`, or `null`.

### `GET /api/v1/tags/`

```json
{
  "count": 2,
  "next": null,
  "previous": null,
  "results": [
    {"name": "city", "slug": "city", "wallpaper_count": 3},
    {"name": "neon", "slug": "neon", "wallpaper_count": 5}
  ]
}
```

### `GET /api/v1/wallpapers/`

```json
{
  "count": 2,
  "next": null,
  "previous": null,
  "results": [
    {
      "slug": "neon-tokyo",
      "title": "Neon Tokyo",
      "description": "Night streets and glowing signs.",
      "category": {"name": "Anime", "slug": "anime"},
      "tags": [
        {"name": "city", "slug": "city"},
        {"name": "neon", "slug": "neon"}
      ],
      "author": "",
      "collection": "",
      "url": "https://images.example.com/neon.jpg?w=1200",
      "thumbnail_url": "https://images.example.com/neon.jpg?w=1200",
      "image_source": "external",
      "orientation": "landscape",
      "width": 2560,
      "height": 1440,
      "published_at": "2026-10-20T13:16:57.254155Z",
      "download_count": 10
    },
    {
      "slug": "uploaded-sample",
      "title": "Uploaded Sample",
      "description": "",
      "category": {"name": "Nature", "slug": "nature"},
      "tags": [],
      "author": "Example Artist",
      "collection": "Example Collection",
      "url": "http://127.0.0.1:8000/media/wallpapers/2026/10/abc123.png",
      "thumbnail_url": "http://127.0.0.1:8000/media/wallpapers/2026/10/abc123.png",
      "image_source": "uploaded",
      "orientation": "landscape",
      "width": 2560,
      "height": 1440,
      "published_at": "2026-10-20T13:16:57.251434Z",
      "download_count": 3
    }
  ]
}
```

- `url` is the image the client should display: the uploaded file's absolute
  URL when an upload exists, otherwise the configured external URL unchanged.
  Uploaded URLs are absolute when a request context is available.
- `thumbnail_url` is the uploaded thumbnail, then the external thumbnail, then
  the primary image.
- `orientation` is `landscape`, `portrait`, `square`, or `null` when dimensions
  are unknown.
- `description` is an empty string when not set.
- No storage paths, database IDs, statuses, or internal counters other than
  `download_count` are exposed.

### `GET /api/v1/wallpapers/{slug}/`

Returns the same fields plus provenance:

```json
{
  "slug": "neon-tokyo",
  "title": "Neon Tokyo",
  "description": "Night streets and glowing signs.",
  "category": {"name": "Anime", "slug": "anime"},
  "tags": [{"name": "neon", "slug": "neon"}],
  "author": "",
  "collection": "",
  "url": "https://images.example.com/neon.jpg?w=1200",
  "thumbnail_url": "https://images.example.com/neon.jpg?w=1200",
  "image_source": "external",
  "orientation": "landscape",
  "width": 2560,
  "height": 1440,
  "published_at": "2026-10-20T13:16:57.254155Z",
  "download_count": 10,
  "external_image_url": "https://images.example.com/neon.jpg?w=1200",
  "uploaded_image_url": null,
  "external_thumbnail_url": null,
  "uploaded_thumbnail_url": null,
  "source_url": "https://example.com/artist",
  "license": {
    "name": "CC BY-SA 4.0",
    "url": "https://creativecommons.org/licenses/by-sa/4.0/",
    "status": "documented"
  }
}
```

External URLs are returned exactly as stored. The API never fetches them, so a
URL in a response is **not** proof that the image is reachable or licensed.

`author` and `collection` are read-only credit strings of up to 200 characters,
returned by the list, detail, library, and popular responses. They hold only
what a recorded source states; when a record has no documented credit the value
is an empty string `""`, never `null` and never a guess. They come from the
import manifest (`attribution.author`, `attribution.collection`) or from manual
entry in Django Admin.

### `GET /api/v1/wallpapers/popular/`

Same shape as the wallpaper list, ordered by `download_count` descending, then
by newest primary key. This is an **all-time download ranking**, not trending
content: the schema stores no per-day activity or time-windowed view data, so
recent interest cannot be measured. It excludes drafts, archived wallpapers,
and wallpapers in inactive categories.

Because `popular/` is a dynamic route, **`popular` is a reserved wallpaper
slug**: a wallpaper with that slug cannot be retrieved through
`/api/v1/wallpapers/popular/`. Django Admin does not currently prevent it.
`?ordering=-download_count` gives the same ranking without the reserved word.

## Query parameters

Only `/api/v1/wallpapers/` and `/api/v1/wallpapers/popular/` accept filters.
Unknown parameters are ignored.

| Parameter | Applies to | Values | Example |
| --- | --- | --- | --- |
| `search` | list, popular | Case-insensitive text matched against `title` and `description` (max 100 characters) | `?search=neon` |
| `category` | list, popular | Exact category slug | `?category=anime` |
| `tag` | list, popular | Exact tag slug. Repeat for AND semantics; comma-separated values are also accepted | `?tag=neon&tag=city` |
| `orientation` | list, popular | `landscape`, `portrait`, `square` | `?orientation=landscape` |
| `ordering` | list | `published_at`, `download_count`, `title`, each optionally prefixed with `-` | `?ordering=-download_count` |
| `page` | all lists | Page number | `?page=2` |
| `page_size` | all lists | Results per page, capped at `API_MAX_PAGE_SIZE` | `?page_size=12` |

`ordering` is ignored by `/popular/`, which always ranks by downloads. Multiple
ordering fields separated by commas are supported, e.g.
`?ordering=-download_count,title`.

Tag filters use **AND** semantics: `?tag=neon&tag=city` returns wallpapers
carrying both tags. Duplicate rows from the many-to-many join are collapsed, so
a wallpaper appears once.

Unknown ordering fields and unsupported orientations return `400` rather than
being silently ignored. More than 10 tag filters also returns `400`.

### Examples

```bash
# Search titles and descriptions
curl "http://127.0.0.1:8000/api/v1/wallpapers/?search=tokyo"

# Landscape anime wallpapers, most downloaded first
curl "http://127.0.0.1:8000/api/v1/wallpapers/?category=anime&orientation=landscape&ordering=-download_count"

# Wallpapers that use both tags
curl "http://127.0.0.1:8000/api/v1/wallpapers/?tag=neon&tag=city"

# Second page, 12 per page
curl "http://127.0.0.1:8000/api/v1/wallpapers/?page=2&page_size=12"
```

### Pagination

Every list response uses the same envelope:

```json
{
  "count": 56,
  "next": "http://127.0.0.1:8000/api/v1/wallpapers/?page=2",
  "previous": null,
  "results": []
}
```

Defaults: 24 results per page, hard cap 60. Both are configurable with
`API_PAGE_SIZE` and `API_MAX_PAGE_SIZE`. A page beyond the end returns `404`.

## Authenticated endpoints

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/api/v1/library/likes/` | List the current user's likes |
| `POST` | `/api/v1/library/likes/` | Like a wallpaper |
| `GET` | `/api/v1/library/likes/{slug}/` | Check whether the current user liked it |
| `DELETE` | `/api/v1/library/likes/{slug}/` | Remove the like |
| `GET` | `/api/v1/library/saved/` | List the current user's saved wallpapers |
| `POST` | `/api/v1/library/saved/` | Save a wallpaper |
| `GET` | `/api/v1/library/saved/{slug}/` | Check whether the current user saved it |
| `DELETE` | `/api/v1/library/saved/{slug}/` | Remove the save |

### How authentication works

Authentication is provided by **django-allauth Headless** (`HEADLESS_ONLY`),
using its built-in **JWT token strategy**. There is no custom JWT code and no
hardcoded development token. The React app talks to the `app` client under
`/_allauth/app/v1/` and sends `Authorization: Bearer <access_token>` to the
library and profile endpoints.

DRF's authentication classes are, in order:

1. `allauth.headless.contrib.rest_framework.authentication.JWTTokenAuthentication`
2. `rest_framework.authentication.SessionAuthentication` (Django Admin and the
   browseable API only; CSRF still applies)

Access tokens are signed with HS256 by default (RS256/RS384/RS512 are supported
through `AUTH_JWT_ALGORITHM` plus `AUTH_JWT_PRIVATE_KEY`). The access token is
valid for 15 minutes and the refresh token for 7 days. Both lifetimes are
configurable. Refresh tokens rotate: every successful refresh returns a new
refresh token and invalidates the previous one. Access tokens are also checked
against the server-side session they were issued from
(`AUTH_JWT_STATEFUL_VALIDATION=true`), so logging out invalidates outstanding
access tokens immediately.

The public catalogue never requires authentication; library and profile
endpoints always use `request.user`. A user ID in the body or query string is
ignored.

### Authentication endpoints

| Method | Path | Authentication | Purpose |
| --- | --- | --- | --- |
| `GET` | `/_allauth/app/v1/config` | None | Supported login methods and social providers |
| `POST` | `/_allauth/app/v1/auth/login` | None | Sign in with username and password |
| `POST` | `/_allauth/app/v1/auth/provider/token` | None | Sign in with a Google ID token |
| `POST` | `/_allauth/app/v1/auth/provider/redirect` | None | Begin a browser OAuth redirect |
| `POST` | `/_allauth/app/v1/auth/provider/signup` | `X-Session-Token` | Complete a pending social signup |
| `GET` | `/_allauth/app/v1/auth/session` | Bearer or `X-Session-Token` | Current session status |
| `DELETE` | `/_allauth/app/v1/auth/session` | `X-Session-Token` | Log out and invalidate the session |
| `GET` | `/_allauth/app/v1/account/providers` | Bearer | Connected social accounts |
| `POST` | `/_allauth/app/v1/tokens/refresh` | Refresh token in the body | Exchange a refresh token for a new pair |
| `GET` | `/api/v1/auth/me/` | Bearer | The current user's own profile |

Password **signup** is closed (`AUTH_ALLOW_PASSWORD_SIGNUP=false`). Google is
the self-service signup path; staff accounts are created with
`manage.py createsuperuser`.

#### `POST /_allauth/app/v1/auth/login`

```json
{"username": "bolu", "password": "..."}
```

```json
{
  "status": 200,
  "data": {
    "user": {"id": 1, "display": "bolu", "email": "bolu@example.com",
             "has_usable_password": true, "username": "bolu"},
    "methods": [{"method": "password", "at": 1760000000.0}]
  },
  "meta": {
    "is_authenticated": true,
    "session_token": "...",
    "access_token": "eyJ...",
    "refresh_token": "eyJ..."
  }
}
```

The `access_token`/`refresh_token` pair appears only on the response that
completes authentication. `meta.session_token` can also appear on a provisional
response while a social signup is pending; keep it only for that flow. After
authentication the JWT pair is sufficient.

#### `POST /_allauth/app/v1/tokens/refresh`

```json
{"refresh_token": "eyJ..."}
```

Returns `200` with `data.access_token` and the rotated
`data.refresh_token`. A reused, expired, revoked, or malformed refresh token
returns `400` with no token material. After logout, refresh requests fail with
`400` because the session and its stored refresh-token identifiers are gone.

#### `DELETE /_allauth/app/v1/auth/session`

Send the `session_token` from login in the `X-Session-Token` header. The call
destroys the server-side session, which invalidates both the access token and
the refresh token. allauth answers this request with `401` and an
unauthenticated envelope even though the logout succeeded; treat the session as
closed and discard the tokens. This is current allauth Headless behaviour, and
it is covered by the test suite rather than worked around.

#### `GET /api/v1/auth/me/`

```json
{
  "id": 1,
  "username": "bolu",
  "email": "bolu@example.com",
  "display_name": "Bolu Adeyemi",
  "date_joined": "2026-10-20T12:00:00Z",
  "has_usable_password": false,
  "likes_count": 12,
  "saved_count": 4,
  "providers": ["google"]
}
```

Only the caller's own profile is returned; there is no user-id parameter.
Sensitive fields (`is_staff`, `is_superuser`, password hashes, permissions,
tokens) are never serialized.

### Google sign-in

Google is configured from the environment only
(`GOOGLE_OAUTH_CLIENT_ID`, `GOOGLE_OAUTH_CLIENT_SECRET`). With neither set,
Google is simply unavailable and no provider is advertised; setting only one is
a startup error.

The supported SPA flow is **Google Identity Services (GIS) plus a provider
token**:

1. The React app loads `https://accounts.google.com/gsi/client`.
2. After the user chooses an account, Google returns an **ID token**
   (`credential`).
3. The app posts
   `{"provider": "google", "process": "login", "token": {"id_token": "<credential>", "client_id": "<GOOGLE_OAUTH_CLIENT_ID>"}}`
   to `/_allauth/app/v1/auth/provider/token`.
4. allauth verifies the token's signature against Google's certificates,
   checks the issuer and audience, and creates or reuses the local user. The
   response contains the JWT pair.

No redirect URI is involved in this flow. In the Google Cloud console create an
OAuth 2.0 client of type **Web application** and add the SPA origins under
*Authorized JavaScript origins* (`http://localhost:5173` locally and the
production origin). The `GoogleProvider` in allauth 65.20 only accepts an
`id_token`; do not send an access token instead.

`POST /_allauth/app/v1/auth/provider/redirect` is also mounted, but under
`HEADLESS_CLIENTS=("app",)` it stores the OAuth state in a server-side session
that is not exposed to a cross-origin SPA, so the callback has no session to
read it from. Do not build the frontend on the redirect flow. If a cookie-based
browser client is added later, register
`https://<api-host>/accounts/google/login/callback/` as an authorized redirect
URI.

When a Google identity's email matches an existing local account, the backend
does **not** link them automatically, even when Google marks the email as
verified. The request returns `401` with a `provider_signup` flow whose
`is_pending` flag is true, and the existing account is left untouched.
Auto-connect is disabled (`SOCIALACCOUNT_EMAIL_AUTHENTICATION=false`,
`..._AUTO_CONNECT=false`), so an account cannot be taken over by creating a
matching Google identity.

### Token storage and CSRF

- Use `Authorization: Bearer`, not cookies. `CORS_ALLOW_CREDENTIALS` stays
  `false`, so the API is not exposed to cross-site cookie requests.
- **Do not store tokens in `localStorage` or `sessionStorage`.** Any XSS can
  read them. Keep the access and refresh tokens in module memory for the
  lifetime of the tab; a page reload requires signing in again. If persistence
  is required later, prefer an HttpOnly refresh cookie with CSRF protection and
  a documented rotation strategy.
- CSRF applies only to DRF session-authenticated writes (Django Admin and the
  browseable API). Bearer requests carry no cookies and need no CSRF token.
- CORS is an explicit origin allowlist; a wildcard is rejected at startup, and
  `x-session-token` plus `authorization` are the allowed custom headers.

### `POST /api/v1/library/likes/`

Body:

```json
{"wallpaper": "neon-tokyo"}
```

- `201 Created` the first time, returning the like with the nested wallpaper.
- `200 OK` for a duplicate request, returning the existing like. The database
  unique constraint remains the final guard.
- `400` for a missing or invalid slug; `404` if the wallpaper is unknown or not
  published.

```json
{
  "wallpaper": {
    "slug": "neon-tokyo",
    "title": "Neon Tokyo",
    "category": {"name": "Anime", "slug": "anime"},
    "tags": [{"name": "neon", "slug": "neon"}],
    "author": "",
    "collection": "",
    "url": "https://images.example.com/neon.jpg?w=1200",
    "thumbnail_url": "https://images.example.com/neon.jpg?w=1200",
    "image_source": "external",
    "orientation": "landscape",
    "width": 2560,
    "height": 1440,
    "published_at": "2026-10-20T13:16:57.254155Z",
    "download_count": 10
  },
  "liked_at": "2026-10-20T13:17:15.752046Z"
}
```

### `GET /api/v1/library/likes/{slug}/`

```json
{"wallpaper": "neon-tokyo", "liked_at": "2026-10-20T13:17:15.752046Z", "exists": true}
```

`exists` is `false` and `liked_at` is `null` when the signed-in user has not
liked it. The endpoint is scoped to the current user and never reveals other
users' likes.

### `DELETE /api/v1/library/likes/{slug}/`

Returns `204 No Content` whether or not the row existed. Deleting is
idempotent; it never touches another user's row. Unknown or unpublished
wallpapers return `404`.

Saved wallpapers use the identical flow with `saved_at` instead of `liked_at`.

### List responses

```json
{
  "count": 1,
  "next": null,
  "previous": null,
  "results": [
    {
      "wallpaper": {"slug": "neon-tokyo", "title": "Neon Tokyo"},
      "liked_at": "2026-10-20T13:17:15.752046Z"
    }
  ]
}
```

Items whose wallpaper has since been unpublished, archived, or moved to an
inactive category are hidden from the list but keep their database rows.

## Downloads

`POST /api/v1/wallpapers/{slug}/download/`

The endpoint records a download and returns where to fetch the image. It does
**not** stream or proxy the file and never redirects, so there is no
open-redirect path.

```json
{
  "slug": "uploaded-sample",
  "download_count": 4,
  "image_source": "uploaded",
  "download_url": "http://127.0.0.1:8000/media/wallpapers/2026/10/abc123.png",
  "thumbnail_url": "http://127.0.0.1:8000/media/wallpapers/2026/10/abc123.png"
}
```

- Uploaded images: `download_url` is the absolute media URL. In development,
  Django serves `/media/` when `DEBUG=True`. In production the web server or
  object storage must serve that URL; Django does not.
- External images: `download_url` is exactly the stored external URL. The
  client fetches it directly from that host.
- The counter is incremented with a single atomic `F("download_count") + 1`
  update, so concurrent requests cannot lose updates.
- Drafts, archived wallpapers, wallpapers in inactive categories, and unknown
  slugs return `404`. Only `POST` is allowed; `GET` returns `405`.
- Requests are throttled with DRF's scoped rate limit
  `API_DOWNLOAD_THROTTLE_RATE` (default `60/minute`, keyed by client IP).
  Rejected requests return `429` and are not counted.
- Session authentication is deliberately not applied to this action. A signed-in
  browser therefore does not need a CSRF token to record a download; the action
  changes only a counter and returns public URLs.

**Limits of download counts:** counts are best-effort analytics, not verified
transfers. A determined anonymous client can inflate them by repeating
requests from different addresses or waiting out the throttle. The per-process
cache means the configured throttle is not shared across multiple workers.
Treat `download_count` as a relative popularity signal only.

## Errors

DRF's standard structure is used. Validation errors are objects keyed by
field:

```json
{"wallpaper": ["This field is required."]}
```

Other errors use `detail`:

| Status | Example body | Cause |
| --- | --- | --- |
| `400` | `{"ordering": ["Unsupported ordering field. Use: ..."]}` | Bad query parameter or request body |
| `401` | `{"detail": "Authentication credentials were not provided."}` with `WWW-Authenticate: Bearer` | Missing, malformed, expired, or invalid Bearer token on a library or profile route |
| `403` | `{"detail": "CSRF Failed: CSRF token missing."}` | Session-authenticated write without a CSRF token |
| `404` | `{"detail": "No Wallpaper matches the given query."}` | Unknown slug, draft, archived, or inactive-category wallpaper |
| `404` | `{"detail": "Invalid page."}` | Page number beyond the last page |
| `405` | `{"detail": "Method \"POST\" not allowed."}` | Write to a read-only catalogue route, or `GET` on download |
| `409` | `{"detail": "This wallpaper has no downloadable image source."}` | Defensive guard; publication normally prevents this |
| `429` | `{"detail": "Request was throttled. Expected available in ..."}` | Download throttle exceeded |
| `410` | allauth `{"status": 410}` | A session token was presented for a session that no longer exists |
| `400` | allauth `{"status": 400, "errors": [...]}` | Invalid login, provider token, or refresh token |

Responses never include settings, SQL, file paths, or tracebacks. With
`DEBUG=False` Django also returns a generic 500 page.

## Featured and trending content

There is **no featured endpoint**. The Phase 2 schema has no featured flag,
curation model, or editorial ordering, and inventing one would require a model
change plus admin workflow. A later phase could add a small
`featured_at`/`is_featured` pair, or (better) a curated-collection model that
references wallpapers.

There is **no trending endpoint**. The database stores no per-day views,
download events, or other time-windowed activity, so recent interest cannot be
measured. `GET /api/v1/wallpapers/popular/` is deliberately named and
documented as an all-time download ranking.

## Mapping to the React frontend

The current React app uses `id`, `title`, `url`, `category` (a name string),
`tags` (name strings), and optional `source` metadata. The API deliberately
uses different identifiers and shapes:

| Frontend field | API field | Notes |
| --- | --- | --- |
| `id` | `slug` | Database primary keys are not exposed; `slug` is stable and unique |
| `category` (string) | `category.name` | Filter with `category.slug` |
| `tags` (strings) | `tags[].name` | Filter with `tags[].slug` |
| `url` | `url` | Uploaded absolute URL or preserved external URL |
| `width` / `height` | `width` / `height` | May be `null` |
| `source` | detail `license` + `source_url` | The current frontend build shows licence and source URL; `author`/`collection` are returned by the API but not rendered by it |

The frontend adapter (`Front End Project/src/lib/adapters.js`) implements this
mapping. The API is consumed when `VITE_API_BASE_URL` is set; see
[`../docs/PHASE5_API_INTEGRATION.md`](../docs/PHASE5_API_INTEGRATION.md). With
no base URL the app keeps its bundled catalogue and browser-local library.

## Known limitations

- **Live MySQL is unverified.** The API and authentication suites run through
  the documented SQLite test harness because this workspace has no MySQL
  server. allauth's migrations, `SELECT DISTINCT` joins, and session/collation
  behaviour have not been measured against a real MySQL server.
- Throttling uses Django's default per-process cache. Configure a shared cache
  before relying on limits across workers, and set DRF's `NUM_PROXIES` behind a
  reverse proxy so anonymous limits key on the real client address.
- Download counts are approximate and anonymous-friendly by design.
- External image URLs are format-checked, never fetched. Broken or unlicensed
  external images remain possible.
- No caching headers, ETags, conditional requests, or CDN integration yet.
- No filtering by multiple categories, color, resolution ranges, or licence.
- No featured/trending data exists; see above.
- Google sign-in has not been exercised end-to-end against Google. The suite
  mocks token verification; no `GOOGLE_OAUTH_CLIENT_ID`/secret exists in this
  workspace, and the sandbox cannot reach Google's certificate endpoint. Token
  verification therefore needs one manual check with real credentials before
  release.
- The app-client OAuth redirect flow cannot complete from a pure SPA because
  its state lives in a server-side session that is not handed to the client.
  Use the Google Identity Services ID-token flow; see "Google sign-in".
- Media serving in production is the deployment's responsibility.
- The 56-record frontend catalogue has not been imported; wallpapers must be
  added through Django Admin.
- The API has no write endpoints for wallpapers, categories, or tags, so model
  validation is not exercised through the API; content changes go through
  Django Admin and its forms.
