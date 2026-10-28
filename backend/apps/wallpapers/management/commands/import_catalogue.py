"""Catalogue import command.

Default behaviour is a dry run: the manifest is validated and a projection is
reported, but nothing is written. An actual import requires ``--apply`` and a
reachable, fully migrated MySQL application database.

    python manage.py import_catalogue                    # dry run
    python manage.py import_catalogue --json-report out.json
    python manage.py import_catalogue --apply            # real import (MySQL only)
    python manage.py import_catalogue --apply --update-existing

``--allow-test-database`` exists only so the automated test suite can exercise
the write path against its throwaway SQLite database; it is refused unless the
SQLite test harness is actually active.
"""

from __future__ import annotations

import json
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import DatabaseError

from apps.wallpapers.catalogue import (
    MANIFEST_VERSION,
    ExistingRecord,
    ManifestError,
    check_source_integrity,
    integrity_counts,
    load_manifest,
    plan_import,
    summarize,
    validate_manifest,
)
from apps.wallpapers.catalogue_import import (
    DatabaseNotSuitable,
    ImportAborted,
    apply_import,
    describe_database,
)
from apps.wallpapers.models import Wallpaper

REPO_ROOT = Path(settings.BASE_DIR).resolve().parent
DEFAULT_MANIFEST = Path(settings.BASE_DIR) / "catalogue" / "manifest.json"


class Command(BaseCommand):
    help = (
        "Validate the catalogue import manifest and report what an import "
        "would do. The default is a dry run; --apply performs the import "
        "against a reachable MySQL database."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--manifest",
            default=str(DEFAULT_MANIFEST),
            help=f"Path to the manifest JSON (default: {DEFAULT_MANIFEST}).",
        )
        parser.add_argument(
            "--json-report",
            default=None,
            help="Write the report as JSON to this path.",
        )
        parser.add_argument(
            "--no-check-database",
            action="store_true",
            help="Skip the create/update/skip projection in a dry run.",
        )
        parser.add_argument(
            "--apply",
            action="store_true",
            help=(
                "Perform the import. Requires a reachable, fully migrated "
                "MySQL database; refuses everything else."
            ),
        )
        parser.add_argument(
            "--update-existing",
            action="store_true",
            help=(
                "With --apply, refresh records whose slug and title already "
                "match. Without it, existing records are left untouched."
            ),
        )
        parser.add_argument(
            "--allow-test-database",
            action="store_true",
            help=(
                "Test-only: permit --apply against the SQLite test harness. "
                "Ignored (and refused) outside the test harness."
            ),
        )

    def handle(self, *args, **options):
        manifest_path = Path(options["manifest"]).expanduser()
        public_root = REPO_ROOT / "Front End Project" / "public"

        applying = bool(options["apply"])
        self.stdout.write(
            self.style.MIGRATE_HEADING(
                "Catalogue import" if applying else "Catalogue import dry run"
            )
        )
        self.stdout.write(f"Manifest: {manifest_path}")
        self.stdout.write(f"Repository root: {REPO_ROOT}")
        self.stdout.write(f"Public image root: {public_root}")
        self.stdout.write(
            "Mode: APPLY — records will be written"
            if applying
            else "Mode: DRY RUN — no database writes"
        )
        self.stdout.write("")

        try:
            manifest = load_manifest(manifest_path)
        except ManifestError as exc:
            raise CommandError(str(exc)) from exc

        if manifest.get("manifest_version") != MANIFEST_VERSION:
            raise CommandError(
                f"Unsupported manifest_version {manifest.get('manifest_version')!r}; "
                f"expected {MANIFEST_VERSION}."
            )

        result = validate_manifest(manifest, repo_root=REPO_ROOT)
        integrity_problems = check_source_integrity(manifest, repo_root=REPO_ROOT)
        problems = integrity_problems + result.problems
        errors = [problem for problem in problems if problem.level == "error"]
        warnings = [problem for problem in problems if problem.level == "warning"]

        summary = summarize(manifest)
        integrity = integrity_counts(manifest, repo_root=REPO_ROOT)
        self._print_manifest_summary(manifest, summary)
        self._print_integrity(integrity)
        self._print_problems(errors, warnings)

        if errors:
            raise CommandError(
                f"Manifest validation failed with {len(errors)} error(s); "
                "nothing was imported."
            )

        if applying:
            return self._apply(manifest, options, summary, integrity)

        return self._dry_run(manifest, manifest_path, options, summary, integrity, errors, warnings)

    # -- dry run --------------------------------------------------------

    def _dry_run(
        self,
        manifest,
        manifest_path,
        options,
        summary,
        integrity,
        errors,
        warnings,
    ):
        database_info = describe_database()
        self._print_database(database_info)

        projection = {"checked": False, "reason": "not an application database"}
        if options["no_check_database"]:
            projection = {"checked": False, "reason": "--no-check-database was passed."}
        elif self._usable_for_projection(database_info):
            projection = self._projection(manifest)
        else:
            projection = {
                "checked": False,
                "reason": (
                    "no application database access: "
                    f"{database_info.get('error') or 'not a MySQL application database'}"
                ),
            }

        self._print_projection(projection)

        report = {
            "mode": "dry-run",
            "dry_run": True,
            "manifest": str(manifest_path),
            "summary": summary,
            "integrity": {
                **integrity,
                "missing_local_files": len(integrity["missing_local_files"]),
                "duplicate_slugs": len(integrity["duplicate_slugs"]),
                "duplicate_source_paths": len(integrity["duplicate_source_paths"]),
                "missing_required_fields": len(integrity["missing_required_fields"]),
            },
            "validation": {
                "errors": [problem.as_dict() for problem in errors],
                "warnings": [problem.as_dict() for problem in warnings],
                "ok": not errors,
            },
            "database": {
                "engine": database_info["engine"],
                "name": database_info["name"],
                "host": database_info["host"],
                "port": database_info["port"],
                "application_database": database_info["application_database"],
                "test_harness": database_info["test_harness"],
                "reachable": database_info["reachable"],
                "error": database_info["error"],
                "pending_migrations": database_info["pending_migrations"],
                "checked": projection["checked"],
                "reason": projection.get("reason"),
            },
            "projection": projection.get("plan"),
        }

        self._write_json_report(options.get("json_report"), report)
        self.stdout.write("")
        self.stdout.write(
            self.style.SUCCESS(
                "Dry run complete: the manifest is valid and nothing was written."
            )
        )

    @staticmethod
    def _usable_for_projection(database_info) -> bool:
        return bool(
            database_info["application_database"]
            and database_info["reachable"]
            and not database_info["pending_migrations"]
        )

    def _projection(self, manifest):
        try:
            rows = list(
                Wallpaper.objects.values_list("slug", "title", "status")
            )
        except DatabaseError as exc:
            return {
                "checked": False,
                "reason": f"wallpaper table could not be read ({exc.__class__.__name__}: {exc}).",
            }

        plan = plan_import(
            manifest,
            [ExistingRecord(slug=slug, title=title, status=status) for slug, title, status in rows],
        )
        return {
            "checked": True,
            "existing_rows": len(rows),
            "plan": plan.as_dict(),
        }

    # -- apply ----------------------------------------------------------

    def _apply(self, manifest, options, summary, integrity):
        try:
            outcome = apply_import(
                manifest,
                repo_root=REPO_ROOT,
                allow_test_database=options["allow_test_database"],
                update_existing=options["update_existing"],
            )
        except DatabaseNotSuitable as exc:
            raise CommandError(f"Database safety gate refused the import: {exc}") from exc
        except ImportAborted as exc:
            raise CommandError(str(exc)) from exc

        database = outcome.database or {}
        self.stdout.write(self.style.HTTP_INFO("Database"))
        self.stdout.write(f"  Engine  : {database.get('engine')}")
        self.stdout.write(f"  Name    : {database.get('name')}")
        self.stdout.write(f"  Host    : {database.get('host')}:{database.get('port')}")
        if database.get("test_database"):
            self.stdout.write(
                self.style.WARNING(
                    "  NOTE: this was the SQLite test harness (throwaway database)."
                )
            )
        self.stdout.write("")

        self.stdout.write(self.style.HTTP_INFO("Import result"))
        self.stdout.write(f"  Created : {len(outcome.created)}")
        for slug in outcome.created:
            self.stdout.write(f"    + {slug}")
        self.stdout.write(f"  Updated : {len(outcome.updated)}")
        for slug in outcome.updated:
            self.stdout.write(f"    ~ {slug}")
        self.stdout.write(f"  Skipped : {len(outcome.skipped)}")
        self.stdout.write(f"  Files written: {len(outcome.files_written)}")
        self.stdout.write("")

        report = {
            "mode": "apply",
            "dry_run": False,
            "summary": summary,
            "integrity": {
                **integrity,
                "missing_local_files": len(integrity["missing_local_files"]),
                "duplicate_slugs": len(integrity["duplicate_slugs"]),
                "duplicate_source_paths": len(integrity["duplicate_source_paths"]),
                "missing_required_fields": len(integrity["missing_required_fields"]),
            },
            "database": database,
            "result": outcome.as_dict(),
        }
        self._write_json_report(options.get("json_report"), report)

        self.stdout.write("")
        self.stdout.write(
            self.style.SUCCESS(
                f"Import complete: {len(outcome.created)} created, "
                f"{len(outcome.updated)} updated, {len(outcome.skipped)} skipped."
            )
        )

    # -- shared output --------------------------------------------------

    def _write_json_report(self, path, report):
        if not path:
            return
        report_path = Path(path).expanduser()
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        self.stdout.write("")
        self.stdout.write(f"JSON report written: {report_path}")

    def _print_manifest_summary(self, manifest, summary):
        write = self.stdout.write
        selection = manifest.get("selection") or {}
        write(self.style.HTTP_INFO("Source catalogue"))
        write(f"  Total records in source catalogue : {summary['total_source_records']}")
        write(f"  Selected for import               : {summary['selected_records']}")
        write(f"  Excluded                          : {summary['excluded_records']}")
        if selection.get("policy"):
            write(f"  Selection policy                  : {selection['policy']}")
        write("")

        write(self.style.HTTP_INFO("Categories"))
        for slug, count in summary["category_counts"].items():
            write(f"  {slug:<16} {count}")
        write(f"  {'total':<16} {summary['categories']}")
        write("")

        write(self.style.HTTP_INFO("Licences"))
        for name, count in summary["license_coverage"].items():
            write(f"  {name:<20} {count}")
        write(
            f"  distinct authors    {summary['distinct_authors']}   "
            f"collections {summary['distinct_collections']}"
        )
        write(
            f"  tags {summary['tags']}   publication statuses {summary['status_counts']}"
        )
        write("")

    def _print_integrity(self, integrity):
        write = self.stdout.write
        write(self.style.HTTP_INFO("Integrity"))
        write(
            "  Missing local files        : "
            f"{len(integrity['missing_local_files'])}"
        )
        for path in integrity["missing_local_files"]:
            write(f"    missing: {path}")
        write(f"  Duplicate slugs            : {len(integrity['duplicate_slugs'])}")
        for slug in integrity["duplicate_slugs"]:
            write(f"    duplicate: {slug}")
        write(
            "  Duplicate source paths     : "
            f"{len(integrity['duplicate_source_paths'])}"
        )
        for path in integrity["duplicate_source_paths"]:
            write(f"    duplicate: {path}")
        write(
            "  Records missing required fields: "
            f"{len(integrity['missing_required_fields'])}"
        )
        for slug in integrity["missing_required_fields"]:
            write(f"    incomplete: {slug}")
        for reason, count in integrity["excluded_by_reason"].items():
            write(f"  Excluded ({reason}) : {count}")
        write("")

    def _print_database(self, info):
        write = self.stdout.write
        write(self.style.HTTP_INFO("Database"))
        write(f"  Engine  : {info['engine'] or '(not configured)'}")
        write(f"  Name    : {info['name'] or '(not configured)'}")
        write(f"  Host    : {info['host'] or '(default)'}:{info['port']}")

        if info["application_database"]:
            write("  Target  : APPLICATION DATABASE (MySQL)")
        elif info["test_harness"]:
            write("  Target  : SQLite test harness — not the application database")
        else:
            write("  Target  : not a MySQL application database")

        write(f"  Reachable: {'yes' if info['reachable'] else 'no'}")
        if info["error"]:
            write(f"    error: {info['error']}")
        pending = sorted(info["pending_migrations"])
        if pending:
            preview = ", ".join(pending[:5])
            if len(pending) > 5:
                preview += f", … ({len(pending)} total)"
            write(f"  Unapplied migrations: {preview}")
        write("")

    def _print_projection(self, projection):
        write = self.stdout.write
        write(self.style.HTTP_INFO("Import projection"))
        if not projection.get("checked"):
            write(f"  Not computed: {projection.get('reason')}")
            if str(projection.get("reason", "")).startswith("no application database access"):
                write(
                    "  These checks ran WITHOUT application-database access; no "
                    "create/update/skip counts exist."
                )
            write("")
            return

        write(f"  Existing wallpaper rows : {projection['existing_rows']}")
        plan = projection["plan"]
        write(f"  Would create            : {plan['create']}")
        write(f"  Would update            : {plan['update']}")
        write(f"  Would skip (conflict)   : {plan['skip']}")
        write(f"  Existing rows untouched : {plan['untouched_existing']}")
        for conflict in plan["conflicts"]:
            write(
                f"    conflict: {conflict['slug']} — manifest "
                f"{conflict['manifest_title']!r} vs existing "
                f"{conflict['existing_title']!r}"
            )
        write("")

    def _print_problems(self, errors, warnings):
        write = self.stdout.write
        if warnings:
            write(self.style.WARNING(f"Warnings ({len(warnings)})"))
            for problem in warnings:
                location = f" [{problem.record}]" if problem.record else ""
                write(f"  - {problem.message}{location}")
            write("")

        if errors:
            write(self.style.ERROR(f"Errors ({len(errors)})"))
            for problem in errors:
                location = f" [{problem.record}]" if problem.record else ""
                write(f"  - {problem.message}{location}")
            write("")
        else:
            write(self.style.SUCCESS("Validation: no errors."))
            write("")
