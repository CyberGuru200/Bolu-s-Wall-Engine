"""Controlled catalogue import (Phase 6C).

The manifest produced in Phase 6B is the only input. Nothing here reads the
frontend at runtime, and nothing is imported automatically: an import happens
only when a caller explicitly invokes :func:`apply_import`.

Safety properties, in the order they are enforced:

1. The manifest is fully validated (structure, slugs, taxonomy, image bytes,
   hashes, dimensions, path containment) before anything is written.
2. A database safety gate refuses anything that is not a reachable, fully
   migrated MySQL database.
3. Slug conflicts abort the run before the first write.
4. All writes happen inside one transaction.
5. Image files are tracked as they are stored. A transaction rollback does not
   undo filesystem writes, so they are deleted explicitly if the run fails.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from pathlib import Path

from django.conf import settings
from django.core.files.base import ContentFile
from django.db import DatabaseError, connections, transaction
from django.db.migrations.executor import MigrationExecutor

from apps.catalog.models import Category, Tag
from apps.core.slugs import normalize_slug
from apps.wallpapers.catalogue import (
    PUBLIC_SUBDIR,
    ManifestError,
    _resolve_inside,
    _same_title,
    load_manifest,
    validate_manifest,
)
from apps.wallpapers.models import Wallpaper

SQLITE_ENGINES = {"django.db.backends.sqlite3"}
MYSQL_ENGINE = "django.db.backends.mysql"

CATEGORY_SLUG_MAX_LENGTH = 120
TAG_SLUG_MAX_LENGTH = 90


class ImportAborted(Exception):
    """The import stopped before or during writing. Nothing was committed."""


class DatabaseNotSuitable(ImportAborted):
    """The configured database is not a usable MySQL application database."""


@dataclass
class ImportOutcome:
    created: list[str] = field(default_factory=list)
    updated: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    conflicts: list[dict] = field(default_factory=list)
    files_written: list[str] = field(default_factory=list)
    files_removed: list[str] = field(default_factory=list)
    database: dict = field(default_factory=dict)

    def as_dict(self) -> dict:
        return {
            "created": len(self.created),
            "updated": len(self.updated),
            "skipped": len(self.skipped),
            "conflicts": len(self.conflicts),
            "files_written": len(self.files_written),
            "files_removed_after_failure": len(self.files_removed),
            "conflict_details": self.conflicts,
        }


# --------------------------------------------------------------------------
# Database safety gate
# --------------------------------------------------------------------------


def check_database_gate(*, using: str = "default", allow_test_database: bool = False) -> dict:
    """Return a description of the target database, or raise.

    Refuses to continue when the database is not MySQL, is unreachable, has
    pending migrations, or is the SQLite test harness without an explicit,
    test-only opt-in.

    The returned description never includes a password.
    """

    connection = connections[using]
    settings_dict = connection.settings_dict
    engine = settings_dict.get("ENGINE", "")
    using_test_harness = bool(getattr(settings, "USING_SQLITE_TEST_HARNESS", False))

    if using_test_harness and not allow_test_database:
        raise DatabaseNotSuitable(
            "This process is running on the SQLite test harness "
            "(config.settings.test). A real import must run against the "
            "configured MySQL application database. Refusing to write."
        )

    if allow_test_database and not using_test_harness:
        raise DatabaseNotSuitable(
            "--allow-test-database is only accepted when the SQLite test "
            "harness is active. Refusing to write to a real database with a "
            "test-only flag."
        )

    if using_test_harness:
        accepted_engines = SQLITE_ENGINES
    else:
        accepted_engines = {MYSQL_ENGINE}

    if engine not in accepted_engines:
        raise DatabaseNotSuitable(
            f"Refusing to import into database engine {engine!r}. "
            f"Expected {sorted(accepted_engines)}."
        )

    try:
        connection.ensure_connection()
    except Exception as exc:  # noqa: BLE001 - any driver error is fatal here
        raise DatabaseNotSuitable(
            "The configured database is not reachable: "
            f"{exc.__class__.__name__}: {exc}"
        ) from exc

    pending = _pending_migrations(connection)
    if pending:
        raise DatabaseNotSuitable(
            "Refusing to import before migrations are applied. Unapplied: "
            + ", ".join(sorted(pending))
        )

    return {
        "engine": engine,
        "name": str(settings_dict.get("NAME", "")),
        "host": str(settings_dict.get("HOST", "")),
        "port": str(settings_dict.get("PORT", "")),
        "test_database": using_test_harness,
        "migrations_applied": True,
    }


def _pending_migrations(connection) -> list[str]:
    """Migration labels that have not been applied to ``connection``."""

    executor = MigrationExecutor(connection)
    plan = executor.migration_plan(executor.loader.graph.leaf_nodes())
    # ``migration_plan`` yields (migration, backwards?) pairs.
    return [f"{migration.app_label}.{migration.name}" for migration, _backwards in plan]


# --------------------------------------------------------------------------
# Plane data preparation
# --------------------------------------------------------------------------


def _asset_bytes(path: Path) -> bytes:
    """Read an image asset. Patched by tests to simulate a mid-run failure."""

    return path.read_bytes()


def _storage():
    return Wallpaper._meta.get_field("image").storage


def _category_for(record: dict) -> Category:
    data = record["category"]
    slug = normalize_slug(data["name"], max_length=CATEGORY_SLUG_MAX_LENGTH)
    if slug != data["slug"]:
        raise ImportAborted(
            f"Category slug mismatch for {data['name']!r}: manifest "
            f"{data['slug']!r}, expected {slug!r}."
        )
    existing = Category.objects.filter(slug=slug).first()
    if existing:
        return existing
    by_name = Category.objects.filter(name__iexact=data["name"]).first()
    if by_name:
        return by_name
    return Category.objects.create(name=data["name"], slug=slug)


def _tag_for(tag: dict) -> Tag:
    slug = normalize_slug(tag["name"], max_length=TAG_SLUG_MAX_LENGTH)
    if slug != tag["slug"]:
        raise ImportAborted(
            f"Tag slug mismatch for {tag['name']!r}: manifest {tag['slug']!r}, "
            f"expected {slug!r}."
        )
    existing = Tag.objects.filter(slug=slug).first()
    if existing:
        return existing
    by_name = Tag.objects.filter(name__iexact=tag["name"]).first()
    if by_name:
        return by_name
    return Tag.objects.create(name=tag["name"], slug=slug)


def _apply_fields(wallpaper: Wallpaper, record: dict, category: Category) -> None:
    license_block = record["license"]
    attribution = record.get("attribution") or {}
    image = record["image"]

    wallpaper.title = record["title"]
    wallpaper.slug = record["slug"]
    wallpaper.description = record.get("description", "")
    wallpaper.category = category
    wallpaper.source_url = record.get("source_url", "")
    wallpaper.author = attribution.get("author", "")
    wallpaper.collection = attribution.get("collection", "")
    wallpaper.license_name = license_block.get("name", "")
    wallpaper.license_url = license_block.get("url", "")
    wallpaper.license_status = Wallpaper.LicenseStatus.DOCUMENTED
    wallpaper.width = image.get("width")
    wallpaper.height = image.get("height")
    wallpaper.file_size = image.get("file_size")
    # The image is uploaded, never an external hotlink.
    wallpaper.image_url = ""
    wallpaper.thumbnail_url = ""


def _store_image(wallpaper: Wallpaper, record: dict, repo_root: Path) -> str | None:
    """Attach the verified asset to the model and write it to storage.

    Returns the storage name so a failed run can delete it again.
    """

    image = record["image"]
    path = _resolve_inside(repo_root, repo_root / PUBLIC_SUBDIR, image["source_path"])
    data = _asset_bytes(path)

    digest = hashlib.sha256(data).hexdigest()
    if digest != image["sha256"]:
        raise ImportAborted(
            f"Image changed after validation: {image['source_path']} "
            f"(expected {image['sha256'][:12]}…, read {digest[:12]}…)."
        )

    wallpaper.image.save(Path(image["source_path"]).name, ContentFile(data), save=False)
    return wallpaper.image.name or None


# --------------------------------------------------------------------------
# Import
# --------------------------------------------------------------------------


def plan_conflicts(manifest: dict, existing: dict[str, Wallpaper]) -> list[dict]:
    """Slugs that already exist with a different title. Never overwrite these."""

    conflicts = []
    for record in manifest["records"]:
        row = existing.get(record["slug"])
        if row is None:
            continue
        if not _same_title(row.title, record["title"]):
            conflicts.append(
                {
                    "slug": record["slug"],
                    "manifest_title": record["title"],
                    "existing_title": row.title,
                    "reason": "slug-collision-with-unrelated-title",
                }
            )
    return conflicts


def apply_import(
    manifest: dict,
    *,
    repo_root: Path,
    allow_test_database: bool = False,
    update_existing: bool = False,
    using: str = "default",
) -> ImportOutcome:
    """Create the manifest's records. Raises :class:`ImportAborted` on failure.

    ``update_existing`` must be passed explicitly; without it a record whose
    slug already exists is skipped rather than modified.
    """

    repo_root = Path(repo_root).resolve()

    result = validate_manifest(manifest, repo_root=repo_root)
    if not result.ok:
        raise ImportAborted(
            "Manifest validation failed: "
            + "; ".join(problem.message for problem in result.errors[:5])
        )

    database = check_database_gate(using=using, allow_test_database=allow_test_database)

    existing = {row.slug: row for row in Wallpaper.objects.using(using).all()}
    conflicts = plan_conflicts(manifest, existing)
    if conflicts:
        raise ImportAborted(
            "Slug conflict with existing records; nothing was written: "
            + "; ".join(
                f"{item['slug']} (existing {item['existing_title']!r})"
                for item in conflicts
            )
        )

    outcome = ImportOutcome(conflicts=conflicts, database=database)
    storage = _storage()
    written: list[str] = []

    try:
        with transaction.atomic(using=using):
            for record in manifest["records"]:
                row = existing.get(record["slug"])

                if row is not None and not update_existing:
                    outcome.skipped.append(record["slug"])
                    continue

                category = _category_for(record)

                if row is None:
                    wallpaper = Wallpaper()
                    _apply_fields(wallpaper, record, category)
                    image_name = _store_image(wallpaper, record, repo_root)
                    if image_name:
                        written.append(image_name)
                    wallpaper.status = Wallpaper.Status.PUBLISHED
                    _full_clean_or_abort(wallpaper)
                    wallpaper.save()
                    wallpaper.tags.set([_tag_for(tag) for tag in record["tags"]])
                    outcome.created.append(record["slug"])
                else:
                    _apply_fields(row, record, category)
                    if not _matches_existing_file(row, record):
                        image_name = _store_image(row, record, repo_root)
                        if image_name:
                            written.append(image_name)
                    _full_clean_or_abort(row)
                    row.save()
                    row.tags.set([_tag_for(tag) for tag in record["tags"]])
                    outcome.updated.append(record["slug"])
    except Exception as exc:
        for name in written:
            try:
                storage.delete(name)
                outcome.files_removed.append(name)
            except Exception:  # noqa: BLE001 - cleanup must not mask the cause
                pass
        if isinstance(exc, ImportAborted):
            raise
        raise ImportAborted(f"Import failed and was rolled back: {exc}") from exc

    outcome.files_written = list(written)
    return outcome


def _matches_existing_file(wallpaper: Wallpaper, record: dict) -> bool:
    """True when the stored upload already has the manifest asset's bytes.

    The storage is read through a separate handle: touching the field's cached
    file object would leave it closed and break the model validators that run
    later in the same transaction.
    """

    if not wallpaper.image:
        return False
    expected = record["image"]["sha256"]
    try:
        with wallpaper.image.storage.open(wallpaper.image.name, "rb") as handle:
            stored = hashlib.sha256(handle.read()).hexdigest()
    except Exception:  # noqa: BLE001 - a missing file means "store it again"
        return False
    return stored == expected


def _full_clean_or_abort(wallpaper: Wallpaper) -> None:
    try:
        wallpaper.full_clean()
    except Exception as exc:  # noqa: BLE001 - convert to a clear abort
        raise ImportAborted(
            f"Record {wallpaper.slug!r} failed model validation: {exc}"
        ) from exc


# --------------------------------------------------------------------------
# Convenience helpers used by the command and tests
# --------------------------------------------------------------------------


def load_and_validate(manifest_path: Path, *, repo_root: Path) -> dict:
    manifest = load_manifest(manifest_path)
    result = validate_manifest(manifest, repo_root=repo_root)
    if not result.ok:
        raise ManifestError(
            "Manifest validation failed: "
            + "; ".join(problem.message for problem in result.errors)
        )
    return manifest


def describe_database(*, using: str = "default") -> dict:
    """Best-effort, read-only description of the configured database.

    Never raises and never connects for writing; used by the dry run to make
    clear whether a real application database is present.
    """

    connection = connections[using]
    settings_dict = connection.settings_dict
    engine = settings_dict.get("ENGINE", "")
    info = {
        "engine": engine,
        "name": str(settings_dict.get("NAME", "")),
        "host": str(settings_dict.get("HOST", "")),
        "port": str(settings_dict.get("PORT", "")),
        "test_harness": bool(getattr(settings, "USING_SQLITE_TEST_HARNESS", False)),
        "application_database": engine == MYSQL_ENGINE
        and not getattr(settings, "USING_SQLITE_TEST_HARNESS", False),
        "reachable": False,
        "error": None,
        "pending_migrations": [],
    }

    try:
        connection.ensure_connection()
        info["reachable"] = True
    except Exception as exc:  # noqa: BLE001 - reported, never raised
        info["error"] = f"{exc.__class__.__name__}: {exc}"
        return info

    try:
        info["pending_migrations"] = _pending_migrations(connection)
    except DatabaseError as exc:
        info["error"] = f"{exc.__class__.__name__}: {exc}"

    return info
