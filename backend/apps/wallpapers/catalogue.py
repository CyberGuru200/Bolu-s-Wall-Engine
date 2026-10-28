"""Read-only validation and planning for the catalogue import manifest.

Phase 6B deliberately contains **no write path**. This module can load a
manifest, prove that every record is safe to import, and describe what an
import *would* do against the database. Nothing here creates, updates, or
deletes a row.

The manifest is generated from the frontend modules by
``tools/catalogue/build_manifest.mjs``. This module is the independent checker:
it re-derives slugs with Django's own ``slugify``, re-hashes the image files,
and decodes them with Pillow rather than trusting the manifest's values.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlsplit

from PIL import Image, UnidentifiedImageError

from apps.core.slugs import normalize_slug
from apps.core.validators import IMAGE_FORMAT_BY_EXTENSION

MANIFEST_VERSION = 1
MANIFEST_KIND = "catalogue-import-manifest"

# The manifest is only ever allowed to read images from this subtree of the
# repository. Anything else (media/, templates, arbitrary absolute paths, or a
# ".." escape) is rejected.
PUBLIC_SUBDIR = Path("Front End Project") / "public"

SLUG_FIELD_MAX_LENGTH = 220
CATEGORY_SLUG_MAX_LENGTH = 120
TAG_SLUG_MAX_LENGTH = 90

ALLOWED_STATUSES = {"draft", "published", "archived"}
ALLOWED_LICENSE_STATUSES = {"documented", "unverified", "unknown"}

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class ManifestError(Exception):
    """The manifest could not be read or is structurally unusable."""


@dataclass(frozen=True)
class Problem:
    level: str  # "error" | "warning"
    message: str
    record: str | None = None

    def as_dict(self) -> dict:
        payload = {"level": self.level, "message": self.message}
        if self.record is not None:
            payload["record"] = self.record
        return payload


@dataclass
class ValidationResult:
    manifest: dict
    problems: list[Problem] = field(default_factory=list)

    @property
    def errors(self) -> list[Problem]:
        return [problem for problem in self.problems if problem.level == "error"]

    @property
    def warnings(self) -> list[Problem]:
        return [problem for problem in self.problems if problem.level == "warning"]

    @property
    def ok(self) -> bool:
        return not self.errors

    def error(self, message: str, record: str | None = None) -> None:
        self.problems.append(Problem("error", message, record))

    def warn(self, message: str, record: str | None = None) -> None:
        self.problems.append(Problem("warning", message, record))


@dataclass(frozen=True)
class ExistingRecord:
    """The minimum an import planner needs to know about a stored row."""

    slug: str
    title: str
    status: str = ""


@dataclass
class ImportPlan:
    create: list[str] = field(default_factory=list)
    update: list[str] = field(default_factory=list)
    skip: list[str] = field(default_factory=list)
    conflict: list[dict] = field(default_factory=list)
    untouched: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "create": len(self.create),
            "update": len(self.update),
            "skip": len(self.skip),
            "conflict": len(self.conflict),
            "untouched_existing": len(self.untouched),
            "conflicts": self.conflict,
        }


def load_manifest(path: Path) -> dict:
    """Read and JSON-decode a manifest, raising :class:`ManifestError`."""

    try:
        raw = Path(path).read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise ManifestError(f"Manifest not found: {path}") from exc
    except OSError as exc:
        raise ManifestError(f"Manifest could not be read: {path} ({exc})") from exc

    try:
        manifest = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ManifestError(f"Manifest is not valid JSON: {path} ({exc})") from exc

    if not isinstance(manifest, dict):
        raise ManifestError("Manifest root must be a JSON object.")
    return manifest


def _resolve_inside(repo_root: Path, public_root: Path, relative_path: str) -> Path:
    """Resolve a repository-relative path and require it inside ``public_root``.

    Manifest paths are stored relative to the repository root so they remain
    readable and reviewable. ``Path.resolve()`` collapses ``..`` and follows
    symlinks, so an escape or a symlink pointing outside the public directory is
    rejected as well.
    """

    if not isinstance(relative_path, str) or not relative_path.strip():
        raise ValueError("source_path is empty")

    candidate = (repo_root / relative_path).resolve()
    root = public_root.resolve()
    if candidate != root and root not in candidate.parents:
        raise ValueError(
            f"source_path is outside {PUBLIC_SUBDIR.as_posix()}/: {relative_path}"
        )
    return candidate


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _extract_fields(manifest: dict) -> tuple[dict, dict]:
    source = manifest.get("source")
    selection = manifest.get("selection")
    return (
        source if isinstance(source, dict) else {},
        selection if isinstance(selection, dict) else {},
    )


def _check_structure(result: ValidationResult, manifest: dict) -> bool:
    if manifest.get("manifest_version") != MANIFEST_VERSION:
        result.error(
            f"Unsupported manifest_version: {manifest.get('manifest_version')!r} "
            f"(expected {MANIFEST_VERSION})."
        )
    if manifest.get("kind") != MANIFEST_KIND:
        result.error(f"Unexpected manifest kind: {manifest.get('kind')!r}.")

    source, selection = _extract_fields(manifest)
    if not source:
        result.error("Manifest is missing its 'source' block.")
    if not selection:
        result.error("Manifest is missing its 'selection' block.")

    records = manifest.get("records")
    if not isinstance(records, list) or not records:
        result.error("Manifest must contain a non-empty 'records' list.")
        return False

    for key in ("categories", "tags"):
        if not isinstance(manifest.get(key), list):
            result.error(f"Manifest '{key}' must be a list.")

    return bool(result.ok)


def _check_summary_counts(result: ValidationResult, manifest: dict) -> None:
    source, selection = _extract_fields(manifest)
    records = manifest.get("records", [])
    excluded = selection.get("excluded_records", [])

    if not isinstance(excluded, list):
        result.error("'selection.excluded_records' must be a list.")
        excluded = []

    if selection.get("selected") != len(records):
        result.error(
            "selection.selected "
            f"({selection.get('selected')!r}) does not match the "
            f"{len(records)} manifest records."
        )
    if selection.get("excluded") != len(excluded):
        result.error(
            "selection.excluded "
            f"({selection.get('excluded')!r}) does not match the "
            f"{len(excluded)} excluded records."
        )

    total = source.get("total_records")
    if isinstance(total, int) and total != len(records) + len(excluded):
        result.error(
            f"source.total_records ({total}) does not equal selected + excluded "
            f"({len(records)} + {len(excluded)})."
        )

    original = source.get("original_records")
    added = source.get("added_records")
    if isinstance(original, int) and isinstance(added, int) and original + added != total:
        result.error(
            "source.original_records + source.added_records "
            f"({original} + {added}) does not equal total_records ({total})."
        )


def _check_slugs(result: ValidationResult, records: list[dict]) -> None:
    seen_slugs: dict[str, str] = {}
    seen_ids: dict[int, str] = {}
    seen_paths: dict[str, str] = {}

    for index, record in enumerate(records):
        label = f"record[{index}]"
        if not isinstance(record, dict):
            result.error("Record is not an object.", label)
            continue

        title = record.get("title")
        slug = record.get("slug")
        source_id = record.get("source_id")

        if not isinstance(title, str) or not title.strip():
            result.error("Record has no title.", label)
            continue

        label = f"record[{index}] id={source_id} {title!r}"

        if not isinstance(source_id, int):
            result.error("source_id must be an integer.", label)
        elif source_id in seen_ids:
            result.error(
                f"Duplicate source_id {source_id} (also used by {seen_ids[source_id]}).",
                label,
            )
        else:
            seen_ids[source_id] = title

        if not isinstance(slug, str) or not slug:
            result.error("Record has no slug.", label)
        else:
            expected = normalize_slug(title, max_length=SLUG_FIELD_MAX_LENGTH)
            if slug != expected:
                result.error(
                    f"Slug {slug!r} does not match Django slugify output {expected!r}.",
                    label,
                )
            if slug in seen_slugs:
                result.error(
                    f"Duplicate slug {slug!r} (also used by {seen_slugs[slug]!r}).",
                    label,
                )
            else:
                seen_slugs[slug] = title
            if len(slug) > SLUG_FIELD_MAX_LENGTH:
                result.error(f"Slug exceeds {SLUG_FIELD_MAX_LENGTH} characters.", label)

        image = record.get("image")
        if not isinstance(image, dict):
            result.error("Record has no image block.", label)
        else:
            source_path = image.get("source_path")
            if isinstance(source_path, str):
                if source_path in seen_paths:
                    result.error(
                        f"Duplicate image source_path {source_path!r} "
                        f"(also used by {seen_paths[source_path]!r}).",
                        label,
                    )
                else:
                    seen_paths[source_path] = title


def _check_text_fields(result: ValidationResult, records: list[dict]) -> None:
    for index, record in enumerate(records):
        label = f"record[{index}] id={record.get('source_id')} {record.get('title')!r}"

        if record.get("status") not in ALLOWED_STATUSES:
            result.error(f"Invalid status {record.get('status')!r}.", label)

        if not isinstance(record.get("description"), str):
            result.error("description must be a string.", label)
        elif not record["description"].strip():
            result.warn("Record has an empty description.", label)

        source_url = record.get("source_url", "")
        if not isinstance(source_url, str):
            result.error("source_url must be a string.", label)
        elif source_url:
            parts = urlsplit(source_url)
            if parts.scheme not in {"http", "https"} or not parts.netloc:
                result.error(f"source_url is not an absolute http(s) URL: {source_url!r}.", label)
            if parts.username or parts.password:
                result.error("source_url must not contain credentials.", label)
        else:
            result.warn("Record has no source_url.", label)

        license_block = record.get("license")
        if not isinstance(license_block, dict):
            result.error("Record has no licence block.", label)
            continue

        status = license_block.get("status")
        name = license_block.get("name") or ""
        url = license_block.get("url") or ""
        if status not in ALLOWED_LICENSE_STATUSES:
            result.error(f"Invalid licence status {status!r}.", label)
        if status == "documented" and not (name or url):
            result.error("Documented licence has neither a name nor a URL.", label)
        if status == "documented" and not url:
            result.warn("Documented licence has no URL.", label)
        if url:
            parts = urlsplit(url)
            if parts.scheme not in {"http", "https"} or not parts.netloc:
                result.error(f"licence URL is not absolute http(s): {url!r}.", label)

        attribution = record.get("attribution")
        if not isinstance(attribution, dict):
            result.warn("Record has no attribution block.", label)
        elif not attribution.get("author"):
            result.warn("No upstream author recorded.", label)


def _check_image(
    result: ValidationResult,
    record: dict,
    repo_root: Path,
    public_root: Path,
) -> None:
    label = f"record id={record.get('source_id')} {record.get('title')!r}"
    image = record.get("image") or {}

    try:
        path = _resolve_inside(repo_root, public_root, image.get("source_path", ""))
    except ValueError as exc:
        result.error(str(exc), label)
        return

    if not path.exists():
        result.error(f"Image file does not exist: {image.get('source_path')}", label)
        return
    if not path.is_file():
        result.error(f"Image path is not a file: {image.get('source_path')}", label)
        return

    expected_hash = image.get("sha256")
    if not isinstance(expected_hash, str) or not _SHA256_RE.match(expected_hash):
        result.error("image.sha256 is not a lowercase SHA-256 hex digest.", label)
    else:
        actual_hash = _sha256(path)
        if actual_hash != expected_hash:
            result.error(
                f"Image sha256 mismatch: manifest {expected_hash[:12]}…, "
                f"file {actual_hash[:12]}….",
                label,
            )

    expected_size = image.get("file_size")
    actual_size = path.stat().st_size
    if expected_size != actual_size:
        result.error(
            f"file_size mismatch: manifest {expected_size!r}, file {actual_size}.",
            label,
        )

    suffix = path.suffix.lower()
    expected_format = IMAGE_FORMAT_BY_EXTENSION.get(suffix)
    if expected_format is None:
        result.error(f"Unsupported image extension {suffix!r}.", label)
        return
    if image.get("format") != expected_format:
        result.error(
            f"image.format {image.get('format')!r} does not match the extension "
            f"({expected_format}).",
            label,
        )

    try:
        with Image.open(path) as handle:
            width, height = handle.size
            actual_format = handle.format
        with Image.open(path) as handle:
            handle.verify()
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        result.error(f"Image cannot be decoded: {exc}", label)
        return

    if actual_format != expected_format:
        result.error(
            f"Image contents are {actual_format!r}, not {expected_format!r}.",
            label,
        )
    if (image.get("width"), image.get("height")) != (width, height):
        result.error(
            "Dimensions mismatch: manifest "
            f"{image.get('width')}x{image.get('height')}, file {width}x{height}.",
            label,
        )
    if width <= 0 or height <= 0:
        result.error("Image has non-positive dimensions.", label)


def _check_taxonomy(result: ValidationResult, manifest: dict) -> None:
    categories = manifest.get("categories", [])
    tags = manifest.get("tags", [])
    records = manifest.get("records", [])

    category_slugs: dict[str, str] = {}
    for index, category in enumerate(categories):
        label = f"category[{index}]"
        if not isinstance(category, dict):
            result.error("Category entry is not an object.", label)
            continue
        name = category.get("name")
        slug = category.get("slug")
        if not isinstance(name, str) or not name.strip():
            result.error("Category has no name.", label)
            continue
        expected = normalize_slug(name, max_length=CATEGORY_SLUG_MAX_LENGTH)
        if slug != expected:
            result.error(
                f"Category slug {slug!r} does not match slugify output {expected!r}.",
                label,
            )
        if slug in category_slugs:
            result.error(f"Duplicate category slug {slug!r}.", label)
        category_slugs[slug] = name

    tag_slugs: dict[str, str] = {}
    for index, tag in enumerate(tags):
        label = f"tag[{index}]"
        if not isinstance(tag, dict):
            result.error("Tag entry is not an object.", label)
            continue
        name = tag.get("name")
        slug = tag.get("slug")
        if not isinstance(name, str) or not name.strip():
            result.error("Tag has no name.", label)
            continue
        expected = normalize_slug(name, max_length=TAG_SLUG_MAX_LENGTH)
        if slug != expected:
            result.error(
                f"Tag slug {slug!r} does not match slugify output {expected!r}.", label
            )
        if slug in tag_slugs:
            result.error(f"Duplicate tag slug {slug!r}.", label)
        tag_slugs[slug] = name

    category_usage: dict[str, int] = {}
    tag_usage: dict[str, int] = {}

    for record in records:
        if not isinstance(record, dict):
            continue
        label = f"record id={record.get('source_id')} {record.get('title')!r}"

        category = record.get("category")
        if not isinstance(category, dict):
            result.error("Record has no category block.", label)
        else:
            slug = category.get("slug")
            if slug not in category_slugs:
                result.error(f"Category {slug!r} is not declared in 'categories'.", label)
            elif category.get("name") != category_slugs[slug]:
                result.error(
                    f"Category name {category.get('name')!r} does not match the "
                    f"declared name {category_slugs[slug]!r}.",
                    label,
                )
            category_usage[slug] = category_usage.get(slug, 0) + 1

        record_tags = record.get("tags")
        if not isinstance(record_tags, list):
            result.error("tags must be a list.", label)
            continue
        seen_on_record: set[str] = set()
        for tag in record_tags:
            if not isinstance(tag, dict):
                result.error("Tag reference is not an object.", label)
                continue
            slug = tag.get("slug")
            if slug in seen_on_record:
                result.error(f"Duplicate tag {slug!r} on one record.", label)
            seen_on_record.add(slug)
            if slug not in tag_slugs:
                result.error(f"Tag {slug!r} is not declared in 'tags'.", label)
            elif tag.get("name") != tag_slugs[slug]:
                result.error(
                    f"Tag name {tag.get('name')!r} does not match the declared "
                    f"name {tag_slugs[slug]!r}.",
                    label,
                )
            tag_usage[slug] = tag_usage.get(slug, 0) + 1

    for category in categories:
        if isinstance(category, dict) and category.get("slug") not in category_usage:
            result.warn(
                f"Category {category.get('slug')!r} is declared but unused.",
                "categories",
            )
    for tag in tags:
        if isinstance(tag, dict) and tag.get("slug") not in tag_usage:
            result.warn(f"Tag {tag.get('slug')!r} is declared but unused.", "tags")


def _check_exclusions(result: ValidationResult, manifest: dict) -> None:
    """Guarantee the excluded external records are described, not imported."""

    selection = manifest.get("selection") or {}
    excluded = selection.get("excluded_records") or []
    records = manifest.get("records") or []

    selected_titles = {record.get("title") for record in records if isinstance(record, dict)}
    selected_slugs = {record.get("slug") for record in records if isinstance(record, dict)}

    for index, entry in enumerate(excluded):
        label = f"excluded[{index}]"
        if not isinstance(entry, dict):
            result.error("Excluded entry is not an object.", label)
            continue
        if not entry.get("reason"):
            result.error("Excluded entry has no reason.", label)
        if entry.get("title") in selected_titles:
            result.error(
                f"Excluded record {entry.get('title')!r} also appears in 'records'.",
                label,
            )
        slug = normalize_slug(entry.get("title", ""), max_length=SLUG_FIELD_MAX_LENGTH)
        if slug in selected_slugs:
            result.error(f"Excluded record slug {slug!r} collides with a selected record.", label)


def validate_manifest(manifest: dict, *, repo_root: Path) -> ValidationResult:
    """Validate a decoded manifest without touching the database."""

    repo_root = Path(repo_root).resolve()
    public_root = repo_root / PUBLIC_SUBDIR
    result = ValidationResult(manifest=manifest)
    if not _check_structure(result, manifest):
        return result

    _check_summary_counts(result, manifest)
    records = [record for record in manifest["records"] if isinstance(record, dict)]

    _check_slugs(result, manifest["records"])
    _check_text_fields(result, records)
    for record in records:
        _check_image(result, record, repo_root, public_root)
    _check_taxonomy(result, manifest)
    _check_exclusions(result, manifest)

    if (manifest.get("summary") or {}).get("categories") not in (None, len(manifest.get("categories", []))):
        result.error("summary.categories does not match 'categories'.")
    if (manifest.get("summary") or {}).get("tags") not in (None, len(manifest.get("tags", []))):
        result.error("summary.tags does not match 'tags'.")

    return result


def plan_import(manifest: dict, existing: list[ExistingRecord]) -> ImportPlan:
    """Classify records against existing rows. Pure; performs no writes.

    Rules:

    * slug absent from the database -> ``create``
    * slug present with the same normalised title -> ``update`` (the same
      record; safe to refresh metadata)
    * slug present with a different title -> ``conflict`` and skipped, because
      the row may be unrelated content that happens to share a slug
    * every existing row not named by the manifest -> ``untouched``
    """

    plan = ImportPlan()
    by_slug: dict[str, ExistingRecord] = {}
    for row in existing:
        by_slug.setdefault(row.slug, row)

    manifest_slugs: set[str] = set()

    for record in manifest.get("records", []):
        slug = record["slug"]
        title = record["title"]
        manifest_slugs.add(slug)

        row = by_slug.get(slug)
        if row is None:
            plan.create.append(slug)
            continue

        if _same_title(row.title, title):
            plan.update.append(slug)
        else:
            plan.conflict.append(
                {
                    "slug": slug,
                    "manifest_title": title,
                    "existing_title": row.title,
                    "reason": "slug-collision-with-unrelated-title",
                }
            )
            plan.skip.append(slug)

    for row in existing:
        if row.slug not in manifest_slugs:
            plan.untouched.append(row.slug)

    return plan


def _same_title(left: str, right: str) -> bool:
    return " ".join((left or "").split()).casefold() == " ".join(
        (right or "").split()
    ).casefold()


def summarize(manifest: dict) -> dict:
    """Counts used by the dry-run report."""

    records = manifest.get("records", [])
    license_counts: dict[str, int] = {}
    status_counts: dict[str, int] = {}
    authors = set()
    collections = set()

    for record in records:
        license_name = (record.get("license") or {}).get("name") or "(none)"
        license_counts[license_name] = license_counts.get(license_name, 0) + 1
        status = record.get("status", "(none)")
        status_counts[status] = status_counts.get(status, 0) + 1
        attribution = record.get("attribution") or {}
        if attribution.get("author"):
            authors.add(attribution["author"])
        if attribution.get("collection"):
            collections.add(attribution["collection"])

    category_counts: dict[str, int] = {}
    for record in records:
        slug = (record.get("category") or {}).get("slug", "(none)")
        category_counts[slug] = category_counts.get(slug, 0) + 1

    return {
        "total_source_records": (manifest.get("source") or {}).get("total_records"),
        "selected_records": len(records),
        "excluded_records": len((manifest.get("selection") or {}).get("excluded_records") or []),
        "categories": len(manifest.get("categories") or []),
        "category_counts": dict(sorted(category_counts.items())),
        "tags": len(manifest.get("tags") or []),
        "license_coverage": dict(sorted(license_counts.items())),
        "status_counts": dict(sorted(status_counts.items())),
        "distinct_authors": len(authors),
        "distinct_collections": len(collections),
    }


def check_source_integrity(
    manifest: dict, *, repo_root: Path
) -> list[Problem]:
    """Confirm the manifest was generated from the current frontend modules.

    If a title, licence, or URL changes in the frontend without regenerating the
    manifest, the import would silently use stale data. This turns that into a
    hard error.
    """

    problems: list[Problem] = []
    source = manifest.get("source") or {}
    modules = source.get("modules") or []
    if not modules:
        problems.append(Problem("error", "Manifest has no source module hashes.", "source"))
        return problems

    for entry in modules:
        relative = entry.get("path") if isinstance(entry, dict) else None
        expected = entry.get("sha256") if isinstance(entry, dict) else None
        if not relative or not expected:
            problems.append(Problem("error", "Source module entry is incomplete.", "source"))
            continue
        path = (repo_root / relative).resolve()
        if repo_root.resolve() not in path.parents and path != repo_root.resolve():
            problems.append(
                Problem("error", f"Source module escapes the repository: {relative}", "source")
            )
            continue
        if not path.is_file():
            problems.append(
                Problem("error", f"Source module is missing: {relative}", "source")
            )
            continue
        actual = _sha256(path)
        if actual != expected:
            problems.append(
                Problem(
                    "error",
                    f"Source module changed since the manifest was generated: "
                    f"{relative} (manifest {expected[:12]}…, file {actual[:12]}…). "
                    "Re-run tools/catalogue/build_manifest.mjs.",
                    "source",
                )
            )

    return problems


def integrity_counts(manifest: dict, *, repo_root: Path) -> dict:
    """Explicit counts for the dry-run report.

    These are computed independently of :func:`validate_manifest` so the report
    can state "0 missing files" rather than relying on the absence of errors.
    """

    repo_root = Path(repo_root).resolve()
    public_root = repo_root / PUBLIC_SUBDIR
    records = [record for record in manifest.get("records", []) if isinstance(record, dict)]

    slugs = [record.get("slug") for record in records if record.get("slug")]
    paths = [
        (record.get("image") or {}).get("source_path")
        for record in records
        if isinstance(record.get("image"), dict)
    ]

    missing_files = []
    for relative in paths:
        try:
            candidate = _resolve_inside(repo_root, public_root, relative)
        except ValueError:
            missing_files.append(relative)
            continue
        if not candidate.is_file():
            missing_files.append(relative)

    def _duplicates(values):
        seen: dict[str, int] = {}
        for value in values:
            seen[value] = seen.get(value, 0) + 1
        return sorted(value for value, count in seen.items() if count > 1)

    missing_required = []
    for record in records:
        license_block = record.get("license") or {}
        required_present = (
            bool(record.get("title"))
            and bool(record.get("slug"))
            and isinstance(record.get("category"), dict)
            and bool((record.get("category") or {}).get("slug"))
            and isinstance(record.get("image"), dict)
            and bool((record.get("image") or {}).get("source_path"))
            and record.get("status") in ALLOWED_STATUSES
            and license_block.get("status") in ALLOWED_LICENSE_STATUSES
        )
        if not required_present:
            missing_required.append(record.get("slug") or f"source_id={record.get('source_id')}")

    exclusion_reasons: dict[str, int] = {}
    for entry in (manifest.get("selection") or {}).get("excluded_records") or []:
        if isinstance(entry, dict):
            reason = entry.get("reason") or "(no reason)"
            exclusion_reasons[reason] = exclusion_reasons.get(reason, 0) + 1

    return {
        "missing_local_files": missing_files,
        "duplicate_slugs": _duplicates(slugs),
        "duplicate_source_paths": _duplicates([path for path in paths if path]),
        "missing_required_fields": missing_required,
        "excluded_by_reason": dict(sorted(exclusion_reasons.items())),
    }
