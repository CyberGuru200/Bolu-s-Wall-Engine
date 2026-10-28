# Frontend reconstruction: editorial gallery and 56-wallpaper catalog

## Status

**Design reconstructed from the written requirements. Catalog completed with 32 documented works.**

- Target and actual catalog: **56 records** (the original 24 plus 32 additions).
- Original 24 records: byte-for-byte unchanged (`6b36c389…8ab013`).
- Added works: 32 distinct, licensed KDE Plasma wallpapers, each with artist, license, pinned source URL, and file hash.
- No placeholders, generated images, invented popularity data, or copied Offscreen assets.
- No backend, commits, or pushes.
- The previous 56-record catalog and reference image were unavailable. This is a **careful reconstruction** from the written brief, not a claim of exact restoration or a pixel match to the unavailable reference.

## Design work

Kept the existing React/Vite architecture, sidebar navigation, hash views, search, categories, featured section, modals, favorites, downloads, and persistence.

### Homepage

- Editorial masthead with a larger type scale, restrained accent label, and two clear entry points.
- Section intros and kickers that establish hierarchy without marketing copy.
- **In the spotlight**: the existing three featured records, restyled with 20px corners, deeper hover lift, and a restrained image zoom.
- **New to the library**: four of the 32 real additions, with a "View all 32" control that opens a filtered collection view.
- **Collections**: four curated groupings (Quiet minimal, Coastlines, After dark, Illustrated worlds), each built only from real catalog IDs, with a translucent glass count pill.
- **By category**: real category counts, clickable to filter the gallery.
- No "trending", "popular", or fake activity sections. Nothing implies usage data that does not exist.

### Wallpaper cards

- 24px image-filled cards, 4:3, with the image as the dominant surface.
- Layered gradient scrim that deepens behind the text and controls while leaving the upper image clear.
- Title, category pill, and — for sourced additions — artist and license line.
- One translucent glass group for Like/Save/Download plus a glass View button, all at least 42px.
- Refined two-layer shadow, inset hairline border, 4px hover lift, and a subtle 1.035 image scale.
- Keyboard focus rings on every control; reduced motion disables lift, zoom, and transitions.
- Controls are always visible, not hover-dependent.
- The light theme keeps dark scrims over imagery for readability; the surrounding page uses theme tokens. Dark theme uses matching elevated surfaces.

### Detail dialog

- Added a **Source & license** panel for the 32 additions: artist, collection, license link, delivery-copy modification note, original artwork link, and local license text link.
- Existing Like/Save/Download, related wallpapers, tags, descriptions, and focus behavior are intact.

## Files changed

Runtime:

- `Front End Project/src/App.jsx` — aggregate catalog import, editorial homepage sections, collection state, filtering through the existing catalog helper.
- `Front End Project/src/App.css` — editorial layout, collection cards, refined glass cards, provenance panel, responsive rules, and contrast fixes.
- `Front End Project/src/components/WallpaperCard.jsx` — optional artist/license metadata line.
- `Front End Project/src/components/WallpaperDetail.jsx` — provenance panel and accurate full-size link label.
- `Front End Project/src/data/catalog.js` — new aggregate module; original module imported unchanged.
- `Front End Project/src/data/newWallpapers.js` — 32 new records with full provenance.
- `Front End Project/src/data/collections.js` — curated groupings built from real IDs.
- `Front End Project/public/wallpapers/kde/*` — 32 delivered image files.
- `Front End Project/public/licenses/CC-BY-SA-4.0.txt` and `LGPL-3.0.txt` — official license texts.

Preserved exactly:

- `Front End Project/src/data/wallpapers.js` — original 24 records, hash verified unchanged.
- `Front End Project/src/lib/*`, hooks, navigation, modal, actions, image component, routing.
- `Bolu-s-Wall-Engine-main.zip` and the nested original archive.

Tests and docs:

- `Front End Project/tests/catalog-expansion.test.js` — 7 new unit tests (count, preservation, provenance, real file headers and hashes, license texts, categories/search).
- `Front End Project/tests/e2e/catalog-expansion.spec.js` — 5 new browser tests, including decoding all 32 real local images, provenance, a real download, and mobile/theme checks.
- `Front End Project/tests/e2e/gallery.spec.js` — updated expected counts and category totals for 56 records.
- `Front End Project/tests/e2e/glass-cards.spec.js` — scoped card selectors to the main gallery (the homepage now also uses cards) and updated the radius to 24px.
- `docs/IMAGE_SOURCES.md` — per-image artist, license, source path, delivered file, and modification record.
- `README.md` and this report.

## Catalog and image verification

Source: official [KDE Plasma Workspace Wallpapers](https://github.com/KDE/plasma-workspace-wallpapers), pinned to commit [`3e4537eb3852a1c769f6fa003e74d06260c266fb`](https://github.com/KDE/plasma-workspace-wallpapers/tree/3e4537eb3852a1c769f6fa003e74d06260c266fb) (2026-10-14).

What was actually done:

1. Read all 38 per-artwork `metadata.json` files through the GitHub API. Each declares its own `KPlugin.License` and author; the repository-level license is `NOASSERTION`, so no blanket license was assumed.
2. Retrieved 38 source images and verified each Git blob SHA-1 against its bytes.
3. Decoded all 38 source images with Pillow; every one decoded successfully.
4. Duplicate screening: no identical file hashes; no perceptual-hash pairs at pHash ≤ 12 or dHash ≤ 10; visual review of 38-image and 32-image contact sheets.
5. Selected 32 distinct artworks: 16 CC BY-SA 4.0, 16 LGPLv3, 19 credited artists.
6. Eleven files are byte-identical to upstream. Twenty-one were resized without cropping to fit within 2560×1600 and re-encoded as JPEG q90; each record states this explicitly as a modification.
7. Stored copies under `public/wallpapers/kde` so the added imagery does not depend on an external hotlink (the environment cannot reach Pexels; GitHub raw fetches are rate-limited and not suitable for runtime display).
8. Recorded SHA-256 for every delivered file; unit tests re-read each file, verify the JPEG/PNG header dimensions, and match the recorded hash.

Accurate categories were used instead of forcing additions into the original four:

| Category | Records |
| --- | --- |
| Anime | 6 (original) |
| Abstract | 21 (6 original + 15 added) |
| Minimalist | 9 (6 original + 3 added) |
| Colored | 6 (original) |
| Nature | 9 (added) |
| Space | 2 (added) |
| Illustration | 3 (added) |

## Verification

| Check | Result |
| --- | --- |
| Actual catalog count | **56**; 56 unique IDs and 56 unique URLs |
| Original 24 preserved | Passed by value and byte hash |
| Added records | 32; unique delivered files, unique upstream paths, unique hashes |
| Added images decode | 32/32 in Node unit tests (headers) and 32/32 in Chromium (`naturalWidth` > 1000) |
| Image-serving HTTP | `/wallpapers/kde/altai.jpg` 200, `/wallpapers/kde/elarun.png` 200 |
| License-containing HTTP | `/licenses/CC-BY-SA-4.0.txt` 200 (18,375 bytes), `/licenses/LGPL-3.0.txt` 200 (7,651 bytes) |
| Unit tests | **13/13 passed** |
| Browser tests | **33/33 passed** (28 existing/updated + 5 new) |
| Accessibility | axe WCAG 2A/2AA audits at 1440 and 375px, light and dark: no violations |
| ESLint | Passed |
| Archive check | `verify:catalog` passed; original hash unchanged |
| Production build | Passed; 44 modules, `dist/index.html` 293.56 kB / 84.49 kB gzip |
| Build assets | `dist/wallpapers/kde` contains 32 images; `dist/licenses` contains 2 license texts |

Rendered inspection performed on the live Vite server (Chromium 156, screenshots retained outside the repository in `/home/user/.cache/bwe-shots/`):

- 1440px light homepage, 1440px dark “New to the library” grid.
- 1440px dark collections section, 1024px light recently-added grid.
- 390px light homepage, 390px dark collections, 390px dark Altai detail dialog.
- 1440px **unmocked** added-image grid: real JPEG/PNG files render; the first card reports `image-loaded`.

These screenshots are what the statements above are based on. The original Pexels artwork still fails in this sandbox, so original 24 cards show the intentional fallback there.

## Remaining limitations

- **The previous catalog and reference design are unavailable.** This reconstruction follows the written brief; it cannot be an exact restoration of the missing 56-record data or reference layout.
- **Original 24 image availability is unverified.** Their unchanged Pexels URLs return `ERR_CONNECTION_CLOSED` in this environment. Their metadata is intact, but their live imagery, cross-origin download behavior, and visual distinctness from the additions could not be checked here. Duplicate screening compares added files against each other, not against the unreachable originals.
- **Downloads for the original 24 remain host-dependent.** Added wallpapers download from the local copy and were verified end to end; original records retain their real failure message and source link when Pexels is unreachable.
- **Eleven added files are unmodified; 21 are delivery resizes.** The originals are linked per record, and `docs/IMAGE_SOURCES.md` states the change. No image was cropped or recolored.
- **Attribution is provided in the detail view and manifest, but not burned into each image.** CC BY-SA 4.0 requires attribution for redistribution; this repository documents artist, license, license text, and source per file. Anyone publishing the app must keep that manifest and the license files with it.
- **Static deployment must ship the whole `dist` directory**, not only `index.html`; the single-file build inlines JS/CSS but imagery and license texts remain separate assets.
- Safari, Firefox, physical mobile devices, and screen-reader software were not tested; Chromium and automated axe audits were.
- The homepage deliberately has no trending/popular section because no genuine usage data exists. Curated collections are editorially selected from real records.
