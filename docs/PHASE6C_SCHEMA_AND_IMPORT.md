# Phase 6C — Schema preparation and controlled catalogue import

Phase 6C adds the two missing credit fields and implements the gated import write
path. **No import has been run against a real database**, and the 32 images have
not been copied into `MEDIA_ROOT`.

- Schema: `backend/apps/wallpapers/models.py`, migration `wallpapers.0002`
- Write path: [`backend/apps/wallpapers/catalogue_import.py`](../backend/apps/wallpapers/catalogue_import.py)
- Command: [`backend/apps/wallpapers/management/commands/import_catalogue.py`](../backend/apps/wallpapers/management/commands/import_catalogue.py)
- Tests: `backend/apps/wallpapers/tests/test_catalogue_import.py`
- Manifest: `backend/catalogue/manifest.json` (unchanged from Phase 6B)

## 1. Schema change

Two optional `CharField`s on `Wallpaper`, placed beside `source_url`:

| Field | Type | Blank | Null | Default | Max length |
| --- | --- | --- | --- | --- | --- |
| `author` | `CharField` | yes | no | `""` | 200 |
| `collection` | `CharField` | yes | no | `""` | 200 |

Migration `0002_wallpaper_author_wallpaper_collection` contains exactly two
`AddField` operations and nothing else. It is additive, so existing rows are
preserved and simply receive `""`. No new table, no changed column, no data
migration. No value is ever inferred: a record whose source states no author
keeps `""`.

Both fields are exposed read-only by the public API (`WallpaperSerializer`, and
therefore the detail serializer) and are editable in the admin's
*Source and licence* fieldset.

### Applying it later

```bash
cd backend
python manage.py migrate            # MySQL application database
python manage.py migrate --plan     # inspect first, if preferred
```

Not run in this phase: nothing was migrated anywhere.

## 2. Import command

```bash
python manage.py import_catalogue                      # dry run (default)
python manage.py import_catalogue --json-report r.json
python manage.py import_catalogue --no-check-database
python manage.py import_catalogue --apply              # real import (MySQL only)
python manage.py import_catalogue --apply --update-existing
```

| Flag | Meaning |
| --- | --- |
| *(none)* | Dry run: validate, report, write nothing |
| `--apply` | Perform the import; requires a reachable, migrated MySQL database |
| `--update-existing` | With `--apply`, refresh records whose slug **and** title match |
| `--allow-test-database` | Test-only; refused unless the SQLite harness is active |
| `--json-report PATH` | Machine-readable report for either mode |

## 3. Order of operations

1. Load the manifest; reject an unsupported `manifest_version`.
2. Validate structure, summary counts, slugs (against Django's own slugify),
   taxonomy, image path containment, file existence, SHA-256, byte size, Pillow
   format, and pixel dimensions.
3. Re-hash the three frontend source modules; a stale manifest is an error.
4. **Database safety gate** (skipped only for a dry run).
5. Compute slug conflicts. Any conflict aborts *before* the first write.
6. Open one `transaction.atomic()` block and write.

## 4. Conflict and update policy

| Situation | Behaviour |
| --- | --- |
| Slug not present | Create the record |
| Slug present, title matches (normalised, case-insensitive) | **Skip** unless `--update-existing`; the existing row is untouched |
| Slug present, title differs | **Abort the whole run**; nothing is written |
| Existing row not named by the manifest | Never touched, never deleted |
| `--update-existing` on a matching record | Refresh metadata; `status`, `published_at`, and `download_count` are preserved |

Hand-edited records are therefore never silently replaced: a first `--apply`
skips them, and overwriting requires the explicit `--update-existing` flag.

## 5. Database safety gate

`check_database_gate()` refuses to write when any of these is true:

- the engine is not `django.db.backends.mysql` (outside the test harness);
- the process is running on `config.settings.test` (SQLite harness) without
  `--allow-test-database`;
- `--allow-test-database` is passed while the harness is *not* active;
- the connection cannot be established;
- any migration is unapplied (checked with `MigrationExecutor.migration_plan`).

The gate returns engine, name, host, port, and harness status — never a password.
The import never runs on startup: there are no `AppConfig.ready()` hooks, no
signals, and no call sites outside the management command.

## 6. Transaction and file cleanup

An `ImageField.save()` writes to storage immediately, so a database rollback
alone would leave orphaned files. `apply_import()` therefore:

1. records every storage name it writes;
2. on any exception, deletes those names from storage, then re-raises;
3. lets the surrounding `transaction.atomic()` roll back all rows, categories,
   and tags.

Verified by tests that fail mid-run and then assert both zero rows and an empty
media directory. A hard process kill (SIGKILL, power loss) can still leave
orphaned files; those are inert and would need a manual sweep.

## 7. Dry-run output difference

The dry run prints the configured engine, database name, host, reachability, and
any unapplied migrations, and labels the target as either
`APPLICATION DATABASE (MySQL)` or `SQLite test harness — not the application
database`. Create/update/skip counts are produced **only** for a reachable MySQL
application database; otherwise it prints `Not computed` plus
"These checks ran WITHOUT application-database access".

## 8. Manifest mapping

| Manifest | Model |
| --- | --- |
| `title` | `title` |
| `slug` | `slug` (never regenerated) |
| `description` | `description` |
| `category.name/slug` | `Category` (reused by slug or name; created only if absent) |
| `tags[]` | `Tag` set on the record |
| `image.source_path` | `image` (bytes copied to storage; `image_url` stays empty) |
| `image.width/height/file_size` | `width` / `height` / `file_size` |
| `source_url` | `source_url` |
| `license.name/url` | `license_name` / `license_url`, always `documented` |
| `attribution.author` | `author` |
| `attribution.collection` | `collection` |
| `status: published` | `status` + `published_at` |

## 9. Limitations

- The write path has only been exercised against ephemeral test databases.
- MySQL DDL for `0002` is unverified; no MySQL server exists here.
- `--update-existing` refreshes every record, not a selected subset.
- When `--update-existing` replaces an image whose bytes changed, the previous
  stored file is deliberately left in place rather than deleted; re-imports of
  unchanged content do not write a second copy.
- Creating categories during an import touches `Category` rows. They are only
  created when absent, and the whole block rolls back with the transaction.
- Everything except `--apply --update-existing` on a matching slug is safe to
  re-run; repeated runs converge on the same state.
