# Bolu’s Wall Engine

A wallpaper discovery app with an approved React 19 + Vite 7 frontend and a Django 5.2 + MySQL backend. The frontend has an editorial homepage, image-filled glass-style cards, combined search/category filtering, curated collections, details with source/license attribution, and downloads. It runs either on its bundled 56-record catalogue with browser-local likes/saves, or against the Django API with Google sign-in and a server-backed library when `VITE_API_BASE_URL` is set.

**Catalog status:** **56 records** — the original 24 preserved byte-for-byte, plus 32 documented works from the official KDE Plasma wallpaper collection (16 CC BY-SA 4.0, 16 LGPLv3). Every addition records its artist, license, pinned source, and file hash. See [the reconstruction report](docs/DESIGN_RECONSTRUCTION.md) and [per-image sources](docs/IMAGE_SOURCES.md). The earlier [correction report](docs/CORRECTION_REVIEW.md) documents the unavailable-56 investigation and is now historical.

The previous 56-record catalog and original reference design were not available. This is a careful reconstruction from the written brief, not a claim of exact restoration.

## Backend (Phases 3–6C)

A Django 5.2 LTS backend lives in [`backend/`](backend/README.md) with a versioned REST API at `/api/v1/`. Phase 2 added the `Category`, `Tag`, `Wallpaper`, `Like`, and `SavedWallpaper` models, migrations, uploaded/external image handling, and Django Admin. Phase 3 added read-only catalogue endpoints, search/filter/ordering/pagination, a download-count endpoint, and per-user like/saved endpoints. Phase 4 added Google sign-in through django-allauth Headless, rotating JWTs, a profile endpoint, and account management; the full reference is [`backend/API.md`](backend/API.md). Phase 5 connects the approved React app to those endpoints. The 56-record frontend catalogue still has not been imported into the database.

```bash
cd backend
python -m venv .venv
# Windows: .\.venv\Scripts\Activate.ps1
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
# Copy .env.example to .env, then fill in the database values.
python manage.py check
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

Before `migrate`, create the MySQL database and user with the `CREATE DATABASE` /
`CREATE USER` / `GRANT` statements in
[backend step 5](backend/README.md#5-create-the-mysql-database-windows). The
server is expected at `127.0.0.1:3306` with `utf8mb4`. `manage.py check` runs
without a connection; `manage.py check --database default` is the real test.

See the [backend setup guide](backend/README.md) for Windows PowerShell commands, MySQL database creation, migrations, admin usage, tests, and production notes, and [the API reference](backend/API.md) for endpoints and parameters. MySQL is configured as the application database. No MySQL server was available in this workspace, so migrations and the tests have not run against MySQL; they ran through the documented SQLite test harness instead. The frontend connects to the API when `VITE_API_BASE_URL` is set; see [Phase 5 integration](docs/PHASE5_API_INTEGRATION.md).

## Catalogue manifest and import (Phases 6B–6C)

The 32 added wallpapers are already present as files in
`Front End Project/public/wallpapers/kde/`, and the frontend renders them
directly — no database is needed to see them. Publishing them through the API is
a separate, optional step.

- **Manifest.** `backend/catalogue/manifest.json` is generated from the
  frontend's own data modules by `tools/catalogue/build_manifest.mjs`; it records
  each image's path, SHA-256, byte size, dimensions, category, tags, artist,
  collection, licence, and pinned source. Regenerate or check it from the
  repository root:

  ```bash
  node tools/catalogue/build_manifest.mjs          # rewrite
  node tools/catalogue/build_manifest.mjs --check  # fail if stale
  ```

  The file is generated — never hand-edit it. Only the 32 records with verified
  local images are in it; the 24 external Pexels records are deliberately
  excluded.

- **Schema.** Migration `wallpapers/0002` adds two optional columns, `author`
  and `collection` (blank by default, max 200 characters), so credited works
  keep their attribution. Existing rows are unaffected.

- **Import.** The command is a dry run unless `--apply` is passed:

  ```bash
  cd backend
  python manage.py import_catalogue          # validate everything, write nothing
  python manage.py import_catalogue --apply  # MySQL only, all-or-nothing
  ```

  `--apply` refuses to run unless the target is a reachable, fully migrated
  MySQL database; it never falls back to SQLite. A conflict (an existing slug
  whose title differs) aborts the run before anything is written, and a failure
  mid-run rolls back both the rows and the copied files. `--update-existing`
  overwrites records only when the slug *and* title match.

  **No import has been run against a real database, and the migration has never
  been applied to MySQL.** See
  [Phase 6C](docs/PHASE6C_SCHEMA_AND_IMPORT.md) for the safety gate, conflict
  policy, and rollback behaviour, and
  [Phase 6B](docs/PHASE6B_CATALOGUE_IMPORT.md) for how the manifest was built.

## Run locally

Use Node.js 22.12+ (tested with Node 22.22.3) and npm.

```bash
cd "Front End Project"
npm ci
npm run dev
```

Vite serves on port 5173 by default. The development and preview servers bind to `0.0.0.0`; the Arena preview host is allowed.

With no `VITE_API_BASE_URL`, the app runs entirely on its bundled catalogue and browser-local likes/saves — no backend, database, or credentials are needed. To use the Django API and Google sign-in, copy `Front End Project/.env.example` to `.env.local`, set `VITE_API_BASE_URL` (for example `http://127.0.0.1:8000`) and `VITE_GOOGLE_CLIENT_ID`, allow the Vite origin in the backend's `CORS_ALLOWED_ORIGINS`, and start the backend separately. The [integration guide](docs/PHASE5_API_INTEGRATION.md) documents the token flow, refresh behaviour, field adapters, and limitations. The OAuth client secret never belongs in a `VITE_*` variable.

## Checks

Run these from `Front End Project`:

```bash
npm test                 # Node's built-in test runner: catalog, provenance, image files
npm run lint             # ESLint, including React rules
npm run verify:catalog   # Python 3: compare catalog bytes with original ZIP
npm run build            # Existing Vite single-file JS/CSS build

`verify:catalog` needs Python 3 and works on Windows and macOS/Linux: the npm
script calls a small Node wrapper that probes `py -3`, `python`, then `python3`
(Windows first) and runs the check with whichever is a real Python 3. Point it
at a specific interpreter with `BWE_PYTHON` if needed, for example
`$env:BWE_PYTHON = "C:\Python312\python.exe"` in PowerShell. It reads
`Bolu-s-Wall-Engine-main.zip`, so keep that archive.
npx playwright install chromium
npm run test:e2e          # Browser flows, responsive layouts, and axe audits
npm run preview          # Serve the production build
```

`npm run test:e2e` starts Vite if needed. With a preinstalled Chromium, set `PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH` instead of downloading Playwright’s browser. The browser tests intercept Pexels requests with a deterministic **test-only image fixture**. They test successful loads/downloads as well as explicitly failed requests; they do not establish availability of the external Pexels sources.

## Source layout

```text
Front End Project/
  src/
    main.jsx                  React entry point (preserved)
    App.jsx                   Views and frontend state
    App.css                   Layout, components, and light/dark tokens
    index.css                 Existing Tailwind import/reset (preserved)
    components/               Navigation, cards, images, actions, dialogs
    data/wallpapers.js         Original 24 records, byte-for-byte unchanged
    data/newWallpapers.js      32 added records with provenance
    data/catalog.js            Aggregate 56-record catalog
    data/collections.js        Curated groupings built from real IDs
    hooks/useLocalPreference.js
    lib/catalog.js            Pure filtering, categories, sorting, ID helpers
    lib/api.js                JSON API client, pagination, structured errors
    lib/adapters.js           API → UI field mapping and query parameters
    lib/session.js            In-memory JWT session, refresh, library calls
    lib/appApi.js             API-mode wiring from VITE_* configuration
    lib/google.js             Lazy Google Identity Services loader
    lib/download.js           Image blob download (direct or API-returned URL)
    hooks/useCatalogue.js     Bundled catalogue or paginated API load
    hooks/useSession.js       React subscription to the session store
  public/wallpapers/kde/      Delivered copies of the 32 added images
  public/licenses/            CC BY-SA 4.0 and LGPLv3 license texts
  tests/                      Unit, browser, and accessibility checks
  scripts/verify_catalog.py   Verification against the original archive
```

The repository initially contained `Bolu-s-Wall-Engine-main.zip`, which contains `Front End Project.zip`. The original source was inspected and unpacked into its existing `Front End Project` folder. Both nested archives remain untouched; bundled `node_modules` were not extracted. Install dependencies from the working lockfile instead.

## Frontend behavior

- Hash navigation: `#home`, `#explore`, `#categories`, `#liked`, `#saved`; browser back/forward works between views.
- Search matches title, category, and optional future tags; category and collection filters combine with it.
- Category counts come from the catalog (or the current local collection).
- In bundled mode, local preferences use `bwe:liked`, `bwe:saved`, and `bwe:theme` in browser storage, and the profile is a **guest/local collection**. In API mode, likes and saves come from the authenticated user's server-side library, so anonymous heart/bookmark clicks open sign-in rather than writing a local substitute; `bwe:theme` stays local.
- The theme initially follows the operating-system preference; an explicit selection persists.
- In bundled mode, downloads fetch the **existing source URL** as an image blob. In API mode, the app calls `POST /api/v1/wallpapers/{slug}/download/` and downloads the returned `download_url`; the file is never proxied. Errors, blocked cross-origin requests, and non-image responses expose an original-image link with browser-saving instructions.
- The original 24 records keep their external Pexels URLs unchanged; those hosts are unreachable from this sandbox, so those cards show the built-in fallback here. The 32 added images are local copies and were verified to load and download.
- Curated collections use only real catalog IDs and are shown in bundled mode, where that editorial data exists. No trending section is invented: API mode's spotlight is the all-time download ranking from `/wallpapers/popular/`, not a time-windowed trend.
- Existing original URLs request 1200 × 627 crops. Added images ship at their recorded dimensions (up to 2560 × 1600). The app does not label anything as 4K or invent missing metadata.
- Bundled added-image attribution: the detail dialog shows artist, collection, license, modification status, original-artwork link, and a local license-text link. API records show the licence, source URL, and — since Phase 6C — the `author`/`collection` values the backend stores; this frontend build renders the licence and source URL only. `docs/IMAGE_SOURCES.md` is the redistribution manifest.

## Deployment note

`npm run build` inlines JS/CSS into `dist/index.html`, but wallpaper images and license texts remain separate files. Publish the whole `dist` directory, not only the HTML file.

## Where things stand

| Area | Status |
| --- | --- |
| Frontend | Complete; 34 unit tests, lint, and production build pass. Bundled catalogue verified byte-for-byte against the original archive. |
| Backend | Complete through Phase 6C; 348 tests pass under the SQLite test harness. |
| MySQL | Configured as the application database but **never connected** in this workspace: no server was available, so no migration, test, or import has run against MySQL. |
| Google OAuth | Implemented and unit-tested with mocked verification; **no real Google credentials were used**. |
| Catalogue import | Dry run and write path tested only against throwaway test databases; **no records imported**, no images copied into `MEDIA_ROOT`. |
| Windows | PowerShell instructions are written but were **not executed on Windows**; every check reported here ran on Linux. |

Further reading: [frontend review](docs/FRONTEND_REVIEW.md),
[design reconstruction](docs/DESIGN_RECONSTRUCTION.md),
[per-image sources](docs/IMAGE_SOURCES.md),
[backend guide](backend/README.md), [API reference](backend/API.md),
[Phase 5 integration](docs/PHASE5_API_INTEGRATION.md),
[Phase 6B manifest](docs/PHASE6B_CATALOGUE_IMPORT.md), and
[Phase 6C schema and import](docs/PHASE6C_SCHEMA_AND_IMPORT.md).
