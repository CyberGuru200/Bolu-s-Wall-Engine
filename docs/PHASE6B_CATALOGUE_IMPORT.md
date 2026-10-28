# Phase 6B — Catalogue import manifest and dry run

Phase 6B prepares a safe import of the **32 verified local-image wallpaper
records** from the bundled frontend catalogue into the Django database. It does
not import anything: there is no write path in this phase.

- Manifest: [`backend/catalogue/manifest.json`](../backend/catalogue/manifest.json)
- Generator: [`tools/catalogue/build_manifest.mjs`](../tools/catalogue/build_manifest.mjs)
- Validator/planner: [`backend/apps/wallpapers/catalogue.py`](../backend/apps/wallpapers/catalogue.py)
- Command: [`backend/apps/wallpapers/management/commands/import_catalogue.py`](../backend/apps/wallpapers/management/commands/import_catalogue.py)
- Tests: [`backend/apps/wallpapers/tests/test_catalogue_manifest.py`](../backend/apps/wallpapers/tests/test_catalogue_manifest.py)

## Source of truth

The manifest is generated from the frontend modules — `src/data/catalog.js`,
`wallpapers.js`, and `newWallpapers.js` — by importing them as ES modules.
No title, URL, tag, licence, or dimension is retyped. The manifest records the
SHA-256 of each source module, and the Django command re-hashes those files
before doing anything else, so a frontend edit that was not followed by
regeneration is a hard error rather than stale data.

Regenerate and check:

```bash
node tools/catalogue/build_manifest.mjs          # write backend/catalogue/manifest.json
node tools/catalogue/build_manifest.mjs --check  # fail if the file is stale
```

Output is deterministic: records are ordered by source id, keys are written in a
fixed order, and no timestamps or random values are emitted. Two runs produce
byte-identical files.

## What is selected, and what is not

| Source | Count | Decision |
| --- | --- | --- |
| Local-image records (`/wallpapers/kde/…`) | 32 | Selected; verified files, hashes, dimensions |
| External Pexels records | 24 | **Excluded**; no per-record author or licence metadata, unreachable here |

Excluded records are listed in the manifest with a reason so the exclusion is
reviewable, but they are never converted into import records. The validator
rejects a manifest where an excluded title also appears in the selected set.

Only five categories appear among the 32 records (Abstract 15, Illustration 3,
Minimalist 3, Nature 9, Space 2). Anime and Colored contain only excluded
records, so the manifest does not declare them: the future import will not
create empty categories.

## Manifest record shape

```json
{
  "source_id": 25,
  "title": "Altai",
  "slug": "altai",
  "description": "…",
  "category": { "name": "Nature", "slug": "nature" },
  "tags": [{ "name": "mountains", "slug": "mountains" }],
  "image": {
    "source_path": "Front End Project/public/wallpapers/kde/altai.jpg",
    "public_url": "/wallpapers/kde/altai.jpg",
    "sha256": "…", "file_size": 170441,
    "width": 2560, "height": 1440, "format": "JPEG"
  },
  "source_url": "https://github.com/KDE/…",
  "license": { "name": "CC BY-SA 4.0", "url": "…", "status": "documented", "id": "…", "text_path": "…" },
  "attribution": {
    "author": "Alesya Khoteeva",
    "collection": "KDE Plasma Workspace Wallpapers",
    "upstream": { "commit": "…", "original_path": "…", "original_sha256": "…", "modification": "…" }
  },
  "status": "published"
}
```

Slugs are computed with an exact mirror of Django's `slugify`; the validator
independently recomputes them with `apps.core.slugs.normalize_slug` and rejects
any mismatch. All 32 titles produce unique slugs today (longest 21 characters).

`attribution.author` and `attribution.collection` are preserved in the manifest
because the frontend records them. Phase 6C added optional `author` and
`collection` columns, so the importer can now store them; until an import runs
they live only in the manifest and `docs/IMAGE_SOURCES.md`.

## Validation performed by the command

`validate_manifest()` checks, without touching the database:

- manifest version/kind, and that `selected + excluded == total`;
- unique `source_id`, unique slugs, and slug equality with Django's slugify;
- unique image `source_path`s and uniqueness of every declared category/tag slug;
- every image path resolves **inside** `Front End Project/public` after
  `resolve()`, which rejects `..` escapes and symlinks pointing elsewhere;
- each file exists, is a regular file, and its SHA-256, byte size, Pillow format,
  and pixel dimensions match the manifest;
- required text fields, absolute `http(s)` `source_url`/licence URL, no URLs with
  embedded credentials, valid statuses, and that a `documented` licence carries a
  name or URL (mirroring `Wallpaper.clean()`);
- every record's category and tags are declared, with matching names;
- excluded records are described but never also selected.

## Dry run

```bash
cd backend
python manage.py import_catalogue                  # validate + project, never writes
python manage.py import_catalogue --no-check-database
python manage.py import_catalogue --json-report /tmp/report.json
python manage.py import_catalogue --apply          # Phase 6C: MySQL-gated
```

In Phase 6B `--apply` refused outright. Phase 6C implements the write path; it
is now gated by the MySQL safety check described in
[`PHASE6C_SCHEMA_AND_IMPORT.md`](PHASE6C_SCHEMA_AND_IMPORT.md).

`--json-report` writes the same report as JSON with `"dry_run": true`, the
summary counts, validation errors/warnings, and the database projection.

### Database projection

If a real configured database is reachable, the dry run reads
`(slug, title, status)` from `Wallpaper` and reports create/update/skip/untouched
counts. It never writes. When no application database is available — as in this
workspace — it says so explicitly and reports no counts rather than inventing
them.

## Design of the future write path (Phase 6C, not implemented)

This is the reviewed plan the dry run is preparing for. It is **not** present in
the code.

1. **One transaction.** The whole import runs inside `transaction.atomic()`; any
   unexpected exception rolls back everything.
2. **Validate before writing.** Reuse `validate_manifest()` inside the transaction
   and abort on any error. No partial imports of a broken manifest.
3. **Fixed slugs.** Each record is written with its manifest slug, never a
   generated one, so repeated runs address the same rows.
4. **`update_or_create` keyed on slug.** Existing row with the same slug and the
   same normalised title → update metadata. Same slug but a different title →
   `conflict`: reported and skipped, never overwritten, because it may be
   unrelated content.
5. **Never delete.** No `delete()`, no bulk `update()` over querysets. Rows not
   named by the manifest are untouched and reported as such.
6. **Images copied deliberately.** The manifest's image path is opened and saved
   through `ImageField` (which re-runs the model validators), so media naming,
   format checks, and size limits apply exactly as in the admin. The source file
   stays in the repository; nothing is moved or deleted.
7. **Licence and source.** `source_url`, `license_name`, `license_url`, and
   `license_status="documented"` come straight from each record's recorded
   metadata. No value is inferred for a record that lacks one.
8. **Category/tag upsert.** `get_or_create` on slug for the five declared
   categories and 62 declared tags, then attach tags per record.
9. **Verification.** `Wallpaper.objects.filter(slug__in=manifest_slugs)` must
   match 32 records, then the public API is checked: `count`, category/tag
   counts, `image_source == "uploaded"`, `license.status == "documented"`, and
   the media URLs return `200` with an image content type.
10. **Re-runnability.** A second run should report `created=0, updated=32` and
    leave the total row count unchanged.

## Limitations

- No application database (MySQL or otherwise) exists in this workspace, so
  create/update/skip is not computed against real data.
- The 32 images remain in `Front End Project/public`; the future import copies
  them into `MEDIA_ROOT`. That doubles storage until a storage decision is made.
- Author and collection are storable since Phase 6C (`wallpapers.0002`).
- The 24 Pexels records remain outside this workflow entirely.
