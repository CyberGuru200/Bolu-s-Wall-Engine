# Backend — Phases 4–5: Google OAuth, JWT, accounts, and frontend integration

This directory contains the Django 5.2 LTS backend. Phases 1–3 built the
foundation, the models/admin, and the versioned REST API. Phase 4 added Google
sign-in, JWT authentication for the library and profile endpoints, and account
management through django-allauth Headless. Phase 5 connects the approved
React + Vite frontend to this API when `VITE_API_BASE_URL` is configured; with
no such variable the frontend keeps its bundled catalogue.

**Not included:** wallpaper import scripts or a production deployment. Google
sign-in has not been run against real Google credentials in this workspace,
and MySQL is unverified (see *Verification status*). The frontend integration
guide is [`../docs/PHASE5_API_INTEGRATION.md`](../docs/PHASE5_API_INTEGRATION.md).

See [`API.md`](API.md) for the full endpoint reference, query parameters,
response examples, and error formats.

## What exists

- Django 5.2 LTS with development and production settings.
- MySQL as the only configured application database (`utf8mb4`).
- Django REST Framework API under `/api/v1/` with read-only public endpoints,
  per-user like/save endpoints, search, filtering, ordering, pagination, and
  download counting.
- Explicit-origin CORS and CSRF configuration for the Vite frontend.
- `Category`, `Tag`, `Wallpaper`, `Like`, and `SavedWallpaper` models.
- Initial migrations for the `catalog`, `wallpapers`, and `library` apps.
- Django Admin for all five models, including image previews, publication
  actions, filters, search, and slug generation.
- django-allauth Headless with its JWT token strategy: password login for
  staff accounts, Google sign-in for everyone else, access/refresh tokens,
  refresh rotation, logout, and the `/api/v1/auth/me/` profile endpoint.
- Password signup is closed by default; Google is the self-service path.
- Uploaded-image validation (format, real image content, size) and local media
  storage with development serving.
- Tests for model behaviour, constraints, admin registration, admin flows,
  API behaviour, and the full authentication layer (348 tests total). Google
  verification is mocked; no real credentials are used.

No categories, tags, wallpapers, or users are created automatically. There is
no hardcoded admin account.

## App ownership and relationships

| App | Models | Purpose |
| --- | --- | --- |
| `catalog` | `Category`, `Tag` | Classification. Categories are rows, not hardcoded choices. |
| `wallpapers` | `Wallpaper` | Wallpaper metadata, image sources, licence, publication state. |
| `library` | `Like`, `SavedWallpaper` | Per-user interactions with wallpapers. |
| `core` | — | Health check, slug/upload/validator helpers, admin previews. |
| `accounts` | — | allauth adapters, `UserProfileSerializer`, `/auth/me/`, auth tests. |
| `api` | — | Serializers, viewsets, filtering, pagination, routes, API tests. |

The API app contains no models. It serializes the Phase 2 models and never
duplicates their validation rules.

Relationships:

- `Wallpaper.category` → `Category`, required, `PROTECT` on delete.
- `Wallpaper.tags` ↔ `Tag`, many-to-many, optional and reusable.
- `Like.user` / `SavedWallpaper.user` → `settings.AUTH_USER_MODEL`, `CASCADE`.
- `Like.wallpaper` / `SavedWallpaper.wallpaper` → `Wallpaper`, `CASCADE`.
- `Like` and `SavedWallpaper` each have a database unique constraint on
  `(user, wallpaper)`.

`settings.AUTH_USER_MODEL` is used instead of importing Django's `User`
directly, so a later custom user model or allauth integration does not require
rewriting the interaction tables.

## Structure

```text
backend/
  manage.py
  requirements.txt
  .env.example
  .gitignore
  README.md
  config/
    __init__.py              MySQL driver selection
    env.py                   Environment parsing and origin validation
    urls.py                  Root routing + development media serving
    wsgi.py / asgi.py        Production-default entry points
    settings/
      base.py                Shared configuration, media, upload limits
      development.py         Local defaults
      production.py          Fail-closed production hardening
      test.py                Test-only SQLite harness (never used by the app)
  apps/
    core/                    Health check, shared helpers, foundation tests
    catalog/                 Category/Tag models, admin, migrations, tests
    wallpapers/              Wallpaper model, admin, migrations, tests
    library/                 Like/SavedWallpaper models, admin, migrations, tests
    accounts/                allauth adapters, profile endpoint, auth tests
    api/                     serializers.py, views.py, filters.py,
                             pagination.py, querysets.py, urls.py, tests/
  API.md                     Endpoint reference
```

## 1. Required software

- Windows 10 or 11 (PowerShell 5.1+ or PowerShell 7).
- Python **3.12 or newer** recommended; 3.11 is the minimum.
- MySQL Community Server **8.4 LTS** recommended. MySQL 8.0 also works, but
  check its support lifecycle before production. MySQL 8.0.16+ is required for
  enforced `CHECK` constraints.
- Node.js for the frontend, if you are running both.
- No C compiler is needed for the pinned Python packages.

```powershell
py --version
python --version
```

## 2. Create and activate a virtual environment (Windows PowerShell)

From the repository root:

```powershell
cd backend
py -3.12 -m venv .venv
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
```

`Set-ExecutionPolicy -Scope Process` only affects that PowerShell window. If
`py` is unavailable, use `python -m venv .venv`.

## 3. Install dependencies

```powershell
pip install -r requirements.txt
pip check
```

Pinned direct dependencies:

| Package | Version | Use |
| --- | --- | --- |
| Django | 5.2.18 LTS | Framework |
| djangorestframework | 3.18.3 | Future JSON API |
| django-cors-headers | 4.9.0 | Explicit-origin CORS |
| django-allauth `[headless,socialaccount]` | 65.20.0 | Accounts, Google OAuth, Headless JWT API |
| Pillow | 13.0.0 | `ImageField` support and upload validation |
| PyMySQL | 1.2.3 | Pure-Python MySQL driver |
| cryptography | 50.0.2 | MySQL 8 `caching_sha2_password` |
| python-dotenv | 1.2.4 | Loads `backend/.env` |

`PyMySQL` avoids compiling `mysqlclient` on Windows. `config/__init__.py`
automatically prefers a real `MySQLdb` installation if you add `mysqlclient`
later.

## 4. Configure environment variables

```powershell
Copy-Item .env.example .env
notepad .env
```

Generate a secret key after Django is installed:

```powershell
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

Never commit `.env`; it is git-ignored. Important variables:

| Variable | Purpose | Local example |
| --- | --- | --- |
| `DJANGO_SECRET_KEY` | Required signing secret | Long random value |
| `DJANGO_DEBUG` | Debug mode | `True` locally, `False` in production |
| `DJANGO_ALLOWED_HOSTS` | Comma-separated hostnames | `localhost,127.0.0.1` |
| `DJANGO_TIME_ZONE` | Display timezone; data is stored in UTC | `UTC` |
| `DB_NAME` | MySQL database | `bolu_wall_engine` |
| `DB_USER` | MySQL user | `bolu_app` |
| `DB_PASSWORD` | MySQL password | Your own strong password |
| `DB_HOST` / `DB_PORT` | MySQL address | `127.0.0.1` / `3306` |
| `DB_CONNECT_TIMEOUT` | Connection timeout (seconds) | `10` |
| `DB_CONN_MAX_AGE` | Persistent connection lifetime | `60` |
| `CORS_ALLOWED_ORIGINS` | Exact browser origins | `http://localhost:5173,http://127.0.0.1:5173` |
| `CSRF_TRUSTED_ORIGINS` | Exact CSRF-trusted origins | Same as CORS |
| `CORS_ALLOW_CREDENTIALS` | Cookies across origins | `False` (Bearer tokens are used) |
| `GOOGLE_OAUTH_CLIENT_ID` | Google OAuth client id | From the Google Cloud console |
| `GOOGLE_OAUTH_CLIENT_SECRET` | Google OAuth client secret | From the Google Cloud console; backend only |
| `FRONTEND_AUTH_ERROR_URL` | OAuth error fallback URL | `http://localhost:5173/` |
| `DJANGO_SITE_ID` | `django.contrib.sites` id | `1` |
| `AUTH_ALLOW_PASSWORD_SIGNUP` | Open public password signup | `False` |
| `AUTH_JWT_ALGORITHM` | JWT signing algorithm | `HS256` (or `RS256` + key) |
| `AUTH_ACCESS_TOKEN_LIFETIME_SECONDS` | Access token lifetime | `900` |
| `AUTH_REFRESH_TOKEN_LIFETIME_SECONDS` | Refresh token lifetime | `604800` |
| `AUTH_JWT_STATEFUL_VALIDATION` | Check tokens against their session | `True` |
| `WALLPAPER_IMAGE_MAX_BYTES` | Max uploaded wallpaper image | `15728640` (15 MB) |
| `WALLPAPER_THUMBNAIL_MAX_BYTES` | Max uploaded thumbnail | `5242880` (5 MB) |
| `CATEGORY_IMAGE_MAX_BYTES` | Max category image | `5242880` (5 MB) |
| `DJANGO_SECURE_SSL_REDIRECT` | Production HTTPS redirect | `True` |
| `DJANGO_SECURE_HSTS_SECONDS` | Production HSTS max-age | `31536000` |
| `DJANGO_TRUST_X_FORWARDED_PROTO` | Trust proxy HTTPS header | `False` unless behind a trusted proxy |
| `API_PAGE_SIZE` | Default results per API page | `24` |
| `API_MAX_PAGE_SIZE` | Maximum `page_size` a client may request | `60` |
| `API_DOWNLOAD_THROTTLE_RATE` | Download rate limit per client IP | `60/minute` |

`DJANGO_SETTINGS_MODULE` is intentionally **not** set in `.env.example`:
`manage.py` defaults to development, while WSGI/ASGI default to production.

If a MySQL password contains spaces or `#`, quote it:
`DB_PASSWORD="your password"`.

## 5. Create the MySQL database (Windows)

Open **MySQL 8.4 Command Line Client**, then run the statements below after
replacing the example password:

```sql
CREATE DATABASE IF NOT EXISTS `bolu_wall_engine`
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

CREATE USER IF NOT EXISTS 'bolu_app'@'localhost'
  IDENTIFIED BY 'replace-with-a-strong-database-password';
CREATE USER IF NOT EXISTS 'bolu_app'@'127.0.0.1'
  IDENTIFIED BY 'replace-with-a-strong-database-password';

GRANT ALL PRIVILEGES ON `bolu_wall_engine`.* TO 'bolu_app'@'localhost';
GRANT ALL PRIVILEGES ON `bolu_wall_engine`.* TO 'bolu_app'@'127.0.0.1';

-- Required for database-backed tests (Django creates test_bolu_wall_engine).
GRANT ALL PRIVILEGES ON `test_bolu_wall_engine`.* TO 'bolu_app'@'localhost';
GRANT ALL PRIVILEGES ON `test_bolu_wall_engine`.* TO 'bolu_app'@'127.0.0.1';

FLUSH PRIVILEGES;
```

Use least-privilege credentials in production. Make sure the service is
running:

```powershell
Get-Service *mysql*
Start-Service MySQL84   # adjust to your installer's service name
```

## 6. Run Django checks

With `.env` configured and MySQL running:

```powershell
python manage.py check
python manage.py check --database default
```

`check` validates settings, models, and admin configuration without connecting
to MySQL. `check --database default` performs the real connection check.

## 7. Apply migrations and create an admin user

The migrations ship as project files, including
`wallpapers/0002_wallpaper_author_wallpaper_collection.py`, which adds the two
optional credit columns. Do not edit generated migrations by hand.

```powershell
python manage.py makemigrations --check --dry-run
python manage.py migrate
python manage.py createsuperuser
```

- `makemigrations --check --dry-run` should print **No changes detected**.
- `migrate` creates Django's built-in tables, the `sites` and `allauth` tables
  (accounts, social accounts, email addresses, sessions), plus `catalog`,
  `wallpapers`, and `library`. It has **not** been run against MySQL in this
  workspace.
- `createsuperuser` prompts for your own credentials. The project never creates
  a superuser or stores admin credentials.

## 8. Run tests

### With MySQL (recommended, uses the real target database)

```powershell
python manage.py test -v 2
```

Django creates and destroys `test_bolu_wall_engine`. The MySQL account needs
the test-database grant shown above. This runs migrations and database
constraints on MySQL itself.

### Without MySQL (test-only harness)

If MySQL is unavailable, an explicit test-only settings module can run the same
suite on in-memory SQLite:

```powershell
python manage.py test --settings=config.settings.test -v 2
```

`config/settings/test.py` is never used by `manage.py runserver`, WSGI, or ASGI.
SQLite is **not** an application database and is not a fallback for production.
Tests run this way do not prove MySQL-specific DDL, collation, or constraint
behaviour; run the suite against MySQL when you have a server.

The suite currently has **348 tests**: 120 API tests, 83 authentication tests,
88 wallpaper tests (models, admin, catalogue manifest, and import), 23 catalogue
app tests, 17 library tests, and 17 core tests.

## 9. Import the 32 verified local wallpapers (optional)

The 32 KDE images ship in `Front End Project/public/wallpapers/kde/`, described
by `backend/catalogue/manifest.json`. The frontend uses them directly; the
database only receives them if you run this import.

Always start with the dry run. It validates the whole manifest — structure,
slug format, taxonomy, path containment, file hashes, byte sizes, image format,
and pixel dimensions — and writes nothing:

```powershell
python manage.py import_catalogue
python manage.py import_catalogue --json-report "$env:TEMP\import-report.json"
```

When the dry run is clean and MySQL is running, apply it:

```powershell
python manage.py import_catalogue --apply
```

- `--apply` refuses to run unless the target is a reachable **MySQL** database
  with no unapplied migrations. It never falls back to SQLite.
- Re-running is safe: records match on `slug`, so a second run creates nothing.
- `--update-existing` refreshes records whose slug **and** title match. A slug
  that already exists with a *different* title aborts the run before any write.
- The import copies image bytes into `MEDIA_ROOT`; the originals stay in
  `Front End Project/public/`, so both copies exist afterwards.
- The 24 external Pexels records are not part of this manifest and are never
  imported.

Both the dry run and `--apply` have only been exercised against throwaway test
databases. No import has been run against MySQL, so the first real run is
unverified — read the dry-run report before applying it.

See [`../docs/PHASE6C_SCHEMA_AND_IMPORT.md`](../docs/PHASE6C_SCHEMA_AND_IMPORT.md)
for the conflict policy, the safety gate, and the rollback behaviour.

## 10. Start the development server and open the admin

```powershell
python manage.py runserver 127.0.0.1:8000
```

- Admin: <http://127.0.0.1:8000/admin/>
- The frontend normally runs separately on <http://localhost:5173>.
- `runserver` performs Django's migration check and therefore needs MySQL.
- Uploaded images are served from `/media/` **only when `DEBUG=True`**. In
  production, configure the web server or object storage to serve `MEDIA_ROOT`.

## 11. Health endpoint

```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/health/
```

Expected:

```text
status service
------ -------
ok     bolu-wall-engine-api
```

The health view deliberately performs no database access and returns no
configuration details. A 200 from this endpoint is **not** proof that MySQL is
reachable.

## Models

### Category

- Unique name and unique slug; blank slugs are generated.
- Optional description, uploaded image, and external image URL.
- `is_active` publication flag, `created_at`, `updated_at`.
- Duplicate names are rejected case-insensitively by validation; colliding
  slugs receive numeric suffixes when generated automatically. Explicit
  duplicate slugs are rejected by the database.

### Tag

- Unique name and unique slug (auto-generated when blank).
- `created_at`.
- Reusable across any number of wallpapers.
- Duplicate names are rejected by validation and the database.

### Wallpaper

- Required `title` and `category`; unique auto-generated `slug`; optional
  description and reusable tags.
- Image sources: `image_url` (external), `image` (upload), plus optional
  `thumbnail_url` / `thumbnail`.
- **At least one usable image source is required**, enforced by model
  validation and a database `CHECK` constraint for published rows.
- Credits: `author` and `collection`, each optional (blank by default, max 200
  characters) and never inferred. They hold only what a recorded source states.
- Source and licence: `source_url` (optional when unknown), `license_name`,
  `license_url`, and `license_status`
  (`documented` / `unverified` / `unknown`). Marking a licence as documented
  requires a name or URL.
- Media metadata: `width`, `height`, `file_size` (bytes).
- Counters: `download_count` uses `PositiveBigIntegerField`, defaults to 0,
  and is read-only in the admin.
- Publication: `status` (`draft` / `published` / `archived`), `published_at`
  (set automatically the first time a row is published), `created_at`,
  `updated_at`.

External URLs are validated for **format only**. Django never downloads them,
so a saved URL is not proof that an image exists, is reachable, or is licensed.

Uploaded files are checked for:

- allowed extensions: JPEG, PNG, WebP, GIF;
- real image content via Pillow, including an extension/content match;
- maximum size from the settings above.

Only the stored relative path is kept in MySQL; binaries live in `MEDIA_ROOT`
(`backend/media/` by default, git-ignored).

Indexes/constraints include:

| Object | Definition |
| --- | --- |
| `Category` | unique `name`, unique `slug`, `(is_active, name)` index |
| `Tag` | unique `name`, unique `slug` |
| `Wallpaper` | unique `slug`; `(status, -published_at)`, `(category, status, -published_at)`, `(-download_count)` indexes |
| `Wallpaper` | `status IN ('draft','published','archived')` and published-requires-image `CHECK` constraints |
| `Like` | unique `(user, wallpaper)`; `(wallpaper, -created_at)` index |
| `SavedWallpaper` | unique `(user, wallpaper)`; `(user, -created_at)` index |

## REST API

The full reference — every endpoint, query parameter, response example, error
body, and limitation — is in [`API.md`](API.md). Summary:

| Method | Path | Auth | Purpose |
| --- | --- | --- | --- |
| `GET` | `/api/health/` | None | Liveness probe |
| `GET` | `/api/v1/` | None | Index of the public collections |
| `GET` | `/api/v1/categories/` | None | Active categories |
| `GET` | `/api/v1/categories/{slug}/` | None | Category detail |
| `GET` | `/api/v1/tags/` | None | Tags used by published wallpapers |
| `GET` | `/api/v1/tags/{slug}/` | None | Tag detail |
| `GET` | `/api/v1/wallpapers/` | None | Published wallpapers |
| `GET` | `/api/v1/wallpapers/{slug}/` | None | Wallpaper detail by slug |
| `GET` | `/api/v1/wallpapers/popular/` | None | All-time download ranking |
| `POST` | `/api/v1/wallpapers/{slug}/download/` | None | Count a download |
| `GET`/`POST` | `/api/v1/library/likes/` | Session | List or add likes |
| `GET`/`DELETE` | `/api/v1/library/likes/{slug}/` | Session | Check or remove a like |
| `GET`/`POST` | `/api/v1/library/saved/` | Session | List or add saves |
| `GET`/`DELETE` | `/api/v1/library/saved/{slug}/` | Session | Check or remove a save |

- **Public read-only:** categories, tags, wallpapers, popular, download. Writes
  return `405`. Only admin-published, active-category records are visible.
- **Authenticated:** the library routes always use `request.user`; no client
  user ID is accepted. Duplicate likes/saves are idempotent (`201` then `200`),
  and the database unique constraints remain the final guard.
- **Filtering:** `search`, `category`, `tag` (repeatable, AND), `orientation`,
  plus `ordering` on `published_at`, `download_count`, and `title`.
- **Pagination:** 24 per page by default, capped at 60; `page` and `page_size`
  query parameters; standard `count`/`next`/`previous`/`results` envelope.
- **Downloads:** `POST` only. Counts with an atomic `F()` update, returns a
  JSON `download_url`, never proxies or redirects, and is throttled per IP.
- **Featured/trending:** not implemented. The schema has no featured flag or
  time-windowed activity data, so the API does not pretend either exists.
  `/popular/` is explicitly a download ranking.

### Authentication (Phase 4)

django-allauth Headless provides accounts and the JSON API under
`/_allauth/app/v1/`, and its built-in JWT strategy issues the tokens. There is
no custom JWT implementation and no hardcoded token.

- **Sign-in:** Google identity, or username/password for staff and test
  accounts. Public password signup is closed.
- **Tokens:** a 15-minute access token and a 7-day refresh token. Refresh
  rotates the refresh token and invalidates the previous one. Access tokens
  are validated against their server-side session, so logout invalidates them
  immediately.
- **API use:** send `Authorization: Bearer <access_token>`. The library
  endpoints and `/api/v1/auth/me/` always resolve the user from the token;
  client-supplied user ids are ignored.
- **Anonymous access:** the catalogue stays public; library and profile routes
  return `401` with a `WWW-Authenticate: Bearer` challenge. Expired or
  malformed tokens get the same response. Refresh with the refresh token; if
  that fails, sign in again.
- **Logout:** `DELETE /_allauth/app/v1/auth/session` with the
  `X-Session-Token` header. allauth answers `401` but has already destroyed the
  session; discard both tokens.
- **CORS:** exact origins only, `CORS_ALLOW_CREDENTIALS=False`, and the
  `authorization` and `x-session-token` headers are allowed. A wildcard is
  rejected at startup.
- **CSRF:** only DRF's session authentication (Django Admin, browseable API)
  needs a CSRF token. Bearer requests carry no cookies and need none.
- **Token storage:** use memory, not `localStorage`/`sessionStorage`. See
  [`API.md`](API.md) for the full rationale and the Google flow.

Password login only works for existing accounts (`createsuperuser`, or an
admin-created user). There is no public registration endpoint, so the tests
create users directly. `allauth` login rate limits apply in development and
production; only the test harness disables them.

#### Google sign-in, in short

Create an OAuth 2.0 **Web application** client in the Google Cloud console,
add the SPA origins as *Authorized JavaScript origins*
(`http://localhost:5173` locally), and put the client id/secret in `.env`.
The SPA uses Google Identity Services to obtain an **ID token** and posts it to
`/_allauth/app/v1/auth/provider/token`; the backend verifies it against Google's
certificates. No client secret goes to the browser. The OAuth **redirect**
endpoint is mounted but is not usable from an app-client SPA (its state lives
in a server session the SPA never receives); see `API.md`.

Existing accounts are never linked to a Google identity by email alone.
`SOCIALACCOUNT_EMAIL_AUTHENTICATION` and its auto-connect variant are off, so
a matching Google email produces a pending `provider_signup` flow instead of
taking over the account.

### Frontend integration contract (implemented in Phase 5)

The React app follows this contract when `VITE_API_BASE_URL` is set; the
implementation is documented in
[`../docs/PHASE5_API_INTEGRATION.md`](../docs/PHASE5_API_INTEGRATION.md). It
needs:

- `VITE_API_BASE_URL` pointing at the backend (for example
  `http://127.0.0.1:8000`). **No OAuth client secret** belongs in Vite
  environment variables; only the client id is public.
- The Google Identity Services script and a `credential` (ID token) callback.
- A token module that keeps the JWT pair in memory (React context or a module
  variable), attaches `Authorization: Bearer`, and retries once after a `401`
  by calling `/_allauth/app/v1/tokens/refresh`. A failed refresh clears the
  session and shows the sign-in screen.
- `credentials: "omit"` on API calls. Cross-origin cookies are intentionally
  disabled.
- Logout via `DELETE /_allauth/app/v1/auth/session` with the `X-Session-Token`
  from the login response, then clearing the in-memory tokens.
- The Vite origin listed in `CORS_ALLOWED_ORIGINS` (and `CSRF_TRUSTED_ORIGINS`
  if cookie-based admin requests are ever used).

## Django Admin

- **Categories:** name, slug, preview, active flag, wallpaper count, filters,
  search, generated slugs, read-only timestamps, activate/deactivate actions.
- **Tags:** name, slug, wallpaper count, search, generated slugs.
- **Wallpapers:** title, category, tags, image sources, previews, source and
  licence fields, dimensions, status, published date, download count.
  - `filter_horizontal` for tags and autocomplete for the category.
  - Publish, unpublish (to draft), and archive actions.
  - Publishing skips invalid records and reports why.
  - Uploaded images are previewed inline; external URLs are shown as
    `noopener noreferrer` links rather than embedded remote images.
- **Likes / Saved wallpapers:** list and search only. Adding and editing are
  disabled; deletion remains available for moderation.

## Settings and security

- `SECRET_KEY`, MySQL credentials, `DEBUG`, `ALLOWED_HOSTS`, and CORS origins
  are environment-driven.
- There are no committed secrets or hardcoded database credentials.
- CORS and CSRF origins are validated at startup; wildcards and credentials in
  URLs are rejected.
- `CORS_ALLOW_ALL_ORIGINS` is always `False`; `CORS_ALLOW_CREDENTIALS` defaults
  to `False`.
- Production refuses `DEBUG=True`, short secrets, missing hosts, wildcard
  hosts, and empty database passwords.
- Production enables SSL redirect, secure cookies, HSTS, `X-Frame-Options:
  DENY`, MIME-sniffing protection, and a same-origin referrer policy.
- `manage.py check --deploy` reports no issues with placeholder production
  values.
- Auth secrets are environment-only: `GOOGLE_OAUTH_CLIENT_ID`,
  `GOOGLE_OAUTH_CLIENT_SECRET`, the JWT signing key (or `AUTH_JWT_PRIVATE_KEY`
  for RS*), and `DJANGO_SECRET_KEY`. A half-configured Google client or an
  RS* algorithm without a private key is a startup error.
- allauth cookies are `HttpOnly` and `SameSite=Lax` by default; the session
  cookie outlives the refresh token. `CORS_ALLOW_CREDENTIALS` stays `False`,
  so the SPA never needs those cookies.
- `HEADLESS_ONLY=True` disables allauth's HTML login/signup/reset pages. Only
  the JSON API and the Google OAuth callback are routed.

### Before deploying

1. Set `DJANGO_SETTINGS_MODULE=config.settings.production` in the service
   environment.
2. Use a strong secret, explicit hosts, and exact HTTPS CORS/CSRF origins.
3. Use a least-privilege MySQL account, TLS for remote connections, and
   backups. This configuration does not yet expose MySQL TLS certificate
   options.
4. Run `python manage.py migrate` against the production database and verify
   the tables, indexes, and constraints.
5. Serve `MEDIA_ROOT` through the web server or object storage; do not serve
   uploads through Django in production.
6. Run `python manage.py collectstatic` and serve `staticfiles/`.
7. Run `python manage.py check --deploy` and review every result.
8. Protect or rename `/admin/`, and keep admin accounts limited.
9. Keep `CORS_ALLOW_CREDENTIALS=False`; the SPA uses Bearer tokens.
10. Set the Google OAuth client id/secret and add the production SPA origin to
    *Authorized JavaScript origins*. Use HTTPS for both the API and the SPA.
11. Keep `AUTH_JWT_STATEFUL_VALIDATION=True` so logout and session expiry take
    effect immediately. If you switch to RS256, supply the PEM through
    `AUTH_JWT_PRIVATE_KEY` and never commit it.
12. Tune upload limits and storage quotas to your hosting environment.

## Phase boundaries and next steps

Django Admin remains the content-management interface. Phase 5 connected the
existing React app to `/api/v1/` and to the auth endpoints above while keeping
the bundled catalogue available when no API base URL is configured. Tokens are
held in memory only, the Google client secret never reaches the browser, and
the app stays usable signed out.

Phase 6B generated the catalogue import manifest for the 32 verified local-image
records. Phase 6C added the optional `author`/`collection` columns (migration
`wallpapers.0002`) and the gated import write path described in step 9.

Neither phase has been run against a real database: no migration has been
applied to MySQL and no record has been imported anywhere. The 56-record
frontend catalogue remains a frontend-only dataset until you run the import.

See [`../docs/PHASE6B_CATALOGUE_IMPORT.md`](../docs/PHASE6B_CATALOGUE_IMPORT.md)
and [`../docs/PHASE6C_SCHEMA_AND_IMPORT.md`](../docs/PHASE6C_SCHEMA_AND_IMPORT.md).

Importing the 56 existing records, server-side featured/trending schema, and a
production deployment remain future work and must not fabricate metadata.

## Troubleshooting

| Symptom | Cause and fix |
| --- | --- |
| `DJANGO_SECRET_KEY is required` | `.env` is missing. Copy `.env.example` to `.env` and generate a key. |
| `Can't connect to MySQL ... 111` | MySQL is not running or host/port is wrong. Start the service and recheck. |
| `Access denied for user` | MySQL account/password/host grant does not match `.env`. |
| `cryptography package is required` | Reinstall `requirements.txt`. |
| `runserver` exits before serving | Django's migration check needs MySQL. Start MySQL first. |
| `relation ... already exists` during tests | Use the dedicated `test_bolu_wall_engine` privileges, or drop a stale test database. |
| Admin upload rejected | Format must be JPEG/PNG/WebP/GIF, content must match the extension, and size must be under the configured limit. |
| Uploaded image preview is broken | Check that `DEBUG=True` (development media serving) and that `backend/media/` contains the file. |
| API library returns 401 | No `Authorization: Bearer` token, or the token is malformed, expired, or from a logged-out session. Refresh, then sign in again. |
| Library returns 403 | CSRF failure on a session-authenticated request. Bearer requests do not need CSRF; session writes need `X-CSRFToken`. |
| Google button not offered | `GOOGLE_OAUTH_CLIENT_ID`/secret are unset, so `/config` advertises no providers. Set both. |
| `Invalid token` from Google sign-in | Send the GIS **ID token** (`credential`) as `id_token`; allauth's Google provider does not accept an access token. |
| OAuth callback says `error=unknown` | State is missing/expired, or the redirect flow was used from the app client. Use the ID-token flow. |
| Logout returns 401 | Expected: allauth returns an unauthenticated envelope after destroying the session. Discard the tokens. |
| `429` on repeated login | allauth's login rate limit. Wait for the window to pass; it is disabled only in `config.settings.test`. |
| `CORS` blocked on `POST` | Add the exact Vite origin to `CORS_ALLOWED_ORIGINS`; wildcards and credentialed requests are rejected. |
| `404` on `?page=99` | Page-number pagination returns 404 past the last page. Check `count` first. |
| Download is `405` | `/download/` only accepts `POST`; it returns URLs instead of redirecting. |
| PowerShell blocks activation | Run `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass`. |
| `No module named config` | Run commands from `backend/` with the virtual environment active. |

## Verification status in this workspace

- All five models, admins, and migrations exist; `makemigrations --check
  --dry-run` reports **No changes detected**. Phases 3 and 4 needed no model
  changes; Phase 6C added one purely additive migration
  (`wallpapers/0002`, two `AddField` operations). The allauth, sites, and
  sessions tables come from the installed packages' own migrations; `migrate`
  applies them in order.
- **348 tests pass** under the explicit SQLite test harness
  (`config.settings.test`): 120 API tests (public catalogue, visibility,
  serialization, search/filter/order/pagination, likes, saves, cross-user
  isolation, downloads, authentication behaviour, error handling), 83 auth
  tests (login and JWT lifecycle, refresh rotation, logout invalidation,
  expired/forged/foreign tokens, profile privacy, Google flows with mocked
  verification, CORS allow/deny, production settings), 88 wallpaper tests
  (model constraints, admin, manifest validation, and the Phase 6C import
  write path), 23 catalogue app tests, 17 library tests, and 17 core tests.
- The authenticated JWT path was exercised over real HTTP in a temporary WSGI
  preview (SQLite file, test harness only): login, Bearer access to the
  library and profile, refresh rotation, logout invalidation, catalogue access
  after logout, and the mocked Google token/collision flows.
- **Google is not end-to-end verified.** No real client credentials exist in
  this workspace and the sandbox cannot reach Google's certificate endpoint,
  so token verification is mocked in tests and has not been exercised against
  Google. The redirect flow's app-client limitation is documented above.
- Migrations were applied successfully to the in-memory SQLite test database,
  proving the migration graph executes.
- The API was also exercised over real HTTP through a temporary WSGI server
  backed by a temporary SQLite file (test harness only): list/detail,
  categories, tags, search, tag AND filtering, orientation, popular ranking,
  download increments, `405` on `GET` download, `401` on anonymous library
  access, CSRF rejection, session login, like create/duplicate/check/delete,
  CORS allow/deny, and media serving all behaved as documented.
- **A live MySQL connection was not verified:** no MySQL server exists in this
  environment and `127.0.0.1:3306` refuses connections. `python manage.py
  migrate` has **not** been run against MySQL, and MySQL DDL/index/query
  behaviour is therefore unverified.
- Running the suite with the normal MySQL settings fails at test-database
  creation with `OperationalError (2003, "Can't connect to MySQL server ...
  [Errno 111] Connection refused")`; this is an environment limitation, not a
  test failure.
- `manage.py check` is clean for test, development, and production settings;
  `check --deploy` is clean with placeholder production values. `compileall`
  and `pip check` pass.
- The frontend baseline hashes were re-checked after Phase 4: `App.jsx`,
  `App.css`, `WallpaperCard.jsx`, `WallpaperDetail.jsx`, `catalog.js`, and
  `wallpapers.js` are unchanged.
- Checks ran on Linux with Python 3.11.2; the Windows PowerShell workflow is
  documented but was not executed here.
