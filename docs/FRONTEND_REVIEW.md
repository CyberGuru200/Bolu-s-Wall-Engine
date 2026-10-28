# Phase 1 frontend review

**Project:** Bolu’s Wall Engine
**Date:** 14 October 2026
**Scope:** Frontend only. No backend, authentication, database, commits, or pushes.

## 1. Existing architecture discovered

The checkout originally contained a minimal README and `Bolu-s-Wall-Engine-main.zip`. That archive contains `Front End Project.zip`. Before changing files, both archives were inspected in memory.

The application inside the archive uses:

- React 19.2.6 and React DOM, with JavaScript/JSX.
- Vite 7, the React and Tailwind Vite plugins, and `vite-plugin-singlefile`.
- Entry: `index.html` → `src/main.jsx` → `src/App.jsx`.
- Custom `App.css` styles with CSS variables; `index.css` imports Tailwind.
- One gallery page with a large hero, category buttons, an inline card component, responsive grid, skeleton loading, and an empty state.
- A data module containing exactly 24 records, with `id`, `title`, `url`, and `category` fields. Six records belong to each of Anime, Abstract, Minimalist, and Colored.
- Externally hosted Pexels image URLs; no local wallpaper image files, tags, descriptions, or native image dimensions.
- Working category filtering. The original download buttons opened a source image in a new tab rather than downloading a file.
- No existing search, like/save state, detail dialog, theme toggle, profile, tests, or lint configuration. Scripts existed for development, build, and preview only.

The existing source was unpacked into its original `Front End Project` folder. Archived `node_modules` were excluded; dependencies were installed using the original lockfile before compatible dependency updates and test tooling were added. The original archive is untouched.

## 2. Frontend files modified or added

### Original source files changed after extraction

| File under `Front End Project` | Change |
| --- | --- |
| `src/App.jsx` | Frontend views, search/filter state, persistent preferences, navigation, and dialog coordination |
| `src/App.css` | Shared light/dark tokens, editorial gallery styling, responsive layouts, focus/interaction states |
| `index.html` | Page description, theme color, favicon; removed external font requests in favor of a system-font stack |
| `vite.config.js` | Retained original build plugins and alias; added network binding and Arena preview hostname support |
| `package.json` | Added unit, browser, lint, and catalog-verification scripts and development-only test/lint tools |
| `package-lock.json` | Locked added tools and compatible fixes for inherited dependency advisories |

### Added source components and helpers

- `src/components/Navigation.jsx`: desktop/sidebar and mobile navigation, real collection counts.
- `src/components/WallpaperCard.jsx`: reusable image-first card.
- `src/components/WallpaperImage.jsx`: lazy loading, stable proportions, load/error states; optional future dimension metadata.
- `src/components/WallpaperActions.jsx`: shared like/save/download buttons, pressed and busy states.
- `src/components/WallpaperDetail.jsx`: contained source image, available metadata, actions, related wallpapers.
- `src/components/Modal.jsx`: native dialog, Escape/backdrop dismissal, keyboard focus containment and restoration.
- `src/components/Icon.jsx`: lightweight inline SVG icons; no UI/icon package.
- `src/hooks/useLocalPreference.js`: validated local persistence with storage-failure handling.
- `src/lib/catalog.js`: pure data-driven categories, combined filtering, sorting, and ID helpers.
- `src/lib/download.js`: image-blob download with response validation and timeout.
- `public/favicon.svg`: small application icon, not catalog artwork.

### Added checks and documentation

- `eslint.config.js`, `playwright.config.js`
- `tests/catalog.test.js`, `tests/e2e/gallery.spec.js`
- `scripts/verify_catalog.py`
- Root `.gitignore`, expanded root `README.md`, and this review.

**Unchanged after extraction:** `src/main.jsx`, `src/index.css`, and `src/data/wallpapers.js`.

## 3. Features implemented

### Discovery and navigation

- Compact Home page with a discovery heading, featured existing wallpapers, category shortcuts, and the main gallery.
- Home, Explore, Categories, Liked, and Saved views using lightweight hash navigation; browser back/forward supported.
- Search stays available in the top bar. It matches title, category, and optional future tags; all search terms must match the record’s searchable text.
- Search combines with category and liked/saved filtering, with result counts, reset controls, clear search, and dedicated empty states.
- Category labels and counts derive from data rather than a fixed category list.
- Collection order and alphabetical-title sorting; no fabricated popularity/download statistics.
- Mobile navigation with keyboard focus containment, Escape dismissal, focus restoration, and inert background content.
- Skip-to-content and back-to-top links preserve the current view.

### Personal collection and details

- Like/unlike and save/unsave work on both cards and details without accidentally opening a wallpaper.
- Likes and saves persist by record ID in this browser; library counts and views update immediately.
- Guest profile accurately explains local-only storage and links to both collections. It does not imply authentication or account sync.
- Detail dialog shows the supplied image without additional cropping, title, category, actions, original source link, and related wallpapers from the same category.
- Description and tags render only if supplied; none were invented for the existing records.

### Themes, images, and downloads

- Consistent light/dark themes share CSS variables. Initial theme follows system preference; an explicit selection persists.
- Responsive cards with readable titles and always-available action buttons; no mobile hover dependency.
- Responsive grid: four columns at 1440px, three at 1280px, two at 1024/768px, one at 430/390/375px, and five at very wide desktop widths.
- Lazy-loaded catalog/related images, eager featured images, static loading backgrounds, and explicit unavailable-preview fallbacks.
- Source-image blob downloads, disabled controls while a request is pending, success/failure feedback, and a source-image link for blocked/failed downloads.
- Reduced-motion preference support, visible focus states, semantic regions, accessible labels, and live result/action feedback.

## 4. Original wallpaper preservation

All **24 original records** retain their exact order, IDs, titles, URLs, categories, comments, and whitespace. The working `wallpapers.js` is **byte-for-byte identical** to the nested archive.

SHA-256:

```text
6b36c389c6dc16b1ac78ac02bfa7e49c86b4993c09ab1137b96f1423818ab013
```

Two independent checks cover preservation:

1. A unit test asserts the original count, unique IDs, and SHA-256.
2. `npm run verify:catalog` directly compares the working file against the unchanged nested ZIP.

Featured and related sections only reference existing records. Browser-test imagery is intercepted in tests and is never substituted into the shipped catalog.

## 5. Tests and build results

Final verification completed successfully after a second review pass.

| Check | Result |
| --- | --- |
| `npm ci` using final lockfile | Passed |
| Existing tests | None were present in the archived project |
| `npm test` | **6/6 passed** |
| `npm run test:e2e` | **24/24 passed** in Chromium 143.0.7499.0 |
| `npm run lint` | Passed |
| `npm run verify:catalog` | Passed; exact original bytes |
| `npm run build` | Passed; 41 modules; generated HTML with inline JS/CSS approximately 243.87 kB, 74.34 kB gzip |
| Production-preview smoke test | Passed: rendering, 24 records, search, details, failed-image fallback; no JavaScript errors |
| `git diff --check` | Passed |
| Additional untracked-source whitespace check | Passed for new/modified frontend files; preserved original data intentionally excluded |
| `npm audit --omit=dev` | **0 production dependency vulnerabilities** |
| Full dependency audit | **3 high-severity development-tool advisories remain** in one inherited dependency chain |

### Browser coverage

- Home, actual successful image load using a deterministic test fixture, categories/counts, alphabetical sorting.
- Combined search/category filtering, no results, reset, and clear-search focus.
- Like/unlike, save/unsave, correct active states, Liked/Saved views, reload persistence.
- Detail image/title, detail actions, related wallpapers, Escape, close-button/backdrop dismissal, focus containment and restoration.
- Actual browser file-download event with a valid image fixture and expected filename.
- Network failure and non-image response handling, actionable source-image fallback, broken previews.
- Light/dark themes, persistent selection, malformed/blocked local storage.
- Category view, guest-profile shortcuts, hash navigation, back/forward behavior.
- Layout and interactive flows at **1440, 1280, 1024, 768, 430, 390, and 375px in both themes**; no page horizontal overflow, expected grid columns, dialogs within viewport bounds.
- Mobile keyboard navigation and transition back to desktop.
- Skip/back-to-top links preserving the current library view.
- Automated axe WCAG A/AA checks on Home, wallpaper detail, and guest profile at **1440 and 375px in both themes**, with **zero detected violations** in these checked states. Automated audits do not constitute a full accessibility certification.

Successful image/download checks use a deterministic SVG fixture intercepted only in Playwright. Real Pexels requests were also retried separately: they fail here with `net::ERR_CONNECTION_CLOSED`. Real failed-download behavior was verified in the live app, not just mocked.

The sandbox’s restricted network prevents normal Playwright browser downloads, so tests used a temporary Chromium installation from an npm-distributed package, with `PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH`. That binary and its libraries are outside the repository and are not application dependencies or deliverables.

## 6. Known limitations

1. **External imagery:** This sandbox does not permit connections to Pexels. Real image availability and successful direct Pexels downloads cannot be verified here. In an unrestricted browser the app requests the original URLs; the host may still impose availability/CORS restrictions. No backend proxy or substitute catalog imagery was introduced.
2. **Source resolution:** Existing URLs request 1200 × 627 crops. Download uses that exact source, not an invented native-resolution/4K file. Gallery proportions reflect these supplied sources; varied masonry/native-ratio layouts await reliable metadata.
3. **Local-only state:** Preferences are per browser, not authenticated, cloud-synced, or guaranteed after browser-data clearing/private browsing. Storage failure retains usable in-memory controls and shows a warning.
4. **Development dependency debt:** The remaining audit chain is `vite-plugin-singlefile` → `micromatch` → `braces`. npm proposes a breaking plugin downgrade. No force fix was applied. There are no reported production dependency vulnerabilities. npm also reports ESLint 9 as unsupported; the React lint-plugin compatibility range currently used should be reviewed before a lint-tool major upgrade.
5. **Browser verification:** Chromium desktop/mobile viewport emulation and automated accessibility checks were run. Real iOS/Android devices, Safari, Firefox, and manual screen-reader testing were not run in this environment.
6. **Discovery scale:** The complete small catalog is filtered locally. Pagination/server querying is intentionally deferred rather than adding a backend during this phase.
7. **Navigation scope:** Views have hashes; individual search/filter selections are local state, not shareable URL parameters. Detail views remain dialogs, not extra routes.

## 7. Decisions for approval

- Review the visual direction and interaction flows in the live frontend preview before beginning any backend work.
- Before deployment, decide whether to retain single-file packaging and resolve its dependency chain, or remove that plugin in favor of Vite’s normal asset output. The existing packaging was intentionally preserved for this phase.
- Recheck the original Pexels sources in an unrestricted browser. If any are permanently unavailable or need higher-resolution sources, approve a separate asset strategy before changing catalog URLs; none have been changed here.

There is no dependency on a backend for this phase. A later approved Django REST Framework/MySQL implementation can replace the local data/preference adapters without replacing the gallery components. No backend development has started.
