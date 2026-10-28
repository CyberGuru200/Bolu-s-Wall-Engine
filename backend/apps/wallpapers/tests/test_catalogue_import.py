"""Phase 6C tests: author/collection fields and the gated import write path.

The write path is exercised only against the ephemeral SQLite test database
created by Django's test runner, and only with the explicit
``--allow-test-database`` opt-in. Nothing here touches a real database, real
media storage, or the 24 excluded external records.
"""

import json
import tempfile
from pathlib import Path

from django.conf import settings
from django.core.files.storage import FileSystemStorage
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings

from apps.catalog.models import Category, Tag
from apps.wallpapers import catalogue_import
from apps.wallpapers.catalogue import load_manifest, validate_manifest
from apps.wallpapers.catalogue_import import (
    DatabaseNotSuitable,
    ImportAborted,
    apply_import,
    check_database_gate,
)
from apps.wallpapers.models import Wallpaper

REPO_ROOT = Path(settings.BASE_DIR).resolve().parent
MANIFEST_PATH = Path(settings.BASE_DIR) / "catalogue" / "manifest.json"


def fresh_manifest():
    return load_manifest(MANIFEST_PATH)


def media_entries(root):
    root = Path(root)
    if not root.exists():
        return []
    return sorted(path for path in root.rglob("*") if path.is_file())


class AuthorCollectionSchemaTests(TestCase):
    def setUp(self):
        self.category = Category.objects.create(name="Nature")

    def test_fields_are_optional_and_default_to_empty(self):
        wallpaper = Wallpaper.objects.create(
            title="No credit",
            category=self.category,
            image_url="https://images.example.com/a.jpg",
        )

        wallpaper.refresh_from_db()
        self.assertEqual(wallpaper.author, "")
        self.assertEqual(wallpaper.collection, "")

    def test_existing_records_keep_values_after_migration_shape(self):
        wallpaper = Wallpaper.objects.create(
            title="Credited",
            category=self.category,
            image_url="https://images.example.com/b.jpg",
            author="Alesya Khoteeva",
            collection="KDE Plasma Workspace Wallpapers",
        )

        wallpaper.refresh_from_db()
        self.assertEqual(wallpaper.author, "Alesya Khoteeva")
        self.assertEqual(wallpaper.collection, "KDE Plasma Workspace Wallpapers")

    def test_new_fields_are_nullable_in_practice_but_not_in_storage(self):
        for name in ("author", "collection"):
            field = Wallpaper._meta.get_field(name)
            self.assertTrue(field.blank, name)
            self.assertFalse(field.null, name)
            self.assertEqual(field.get_default(), "", name)
            self.assertEqual(field.max_length, 200, name)

    def test_migration_is_purely_additive(self):
        from importlib import import_module

        migration = import_module(
            "apps.wallpapers.migrations.0002_wallpaper_author_wallpaper_collection"
        )
        added = {
            operation.name
            for operation in migration.Migration.operations
            if operation.__class__.__name__ == "AddField"
        }

        self.assertEqual(added, {"author", "collection"})
        self.assertTrue(
            all(
                operation.__class__.__name__ == "AddField"
                for operation in migration.Migration.operations
            ),
            "the migration must not alter or remove existing fields",
        )

    def test_api_exposes_the_new_fields(self):
        Wallpaper.objects.create(
            title="Credited",
            category=self.category,
            image_url="https://images.example.com/c.jpg",
            author="Alesya Khoteeva",
            collection="KDE Plasma Workspace Wallpapers",
            status=Wallpaper.Status.PUBLISHED,
        )

        response = self.client.get("/api/v1/wallpapers/")
        record = response.json()["results"][0]

        self.assertEqual(record["author"], "Alesya Khoteeva")
        self.assertEqual(record["collection"], "KDE Plasma Workspace Wallpapers")

    def test_fields_appear_in_admin_form(self):
        from django.contrib import admin

        from apps.wallpapers.admin import WallpaperAdmin

        model_admin = WallpaperAdmin(Wallpaper, admin.site)
        fields = [name for fieldset in model_admin.get_fieldsets(None) for name in fieldset[1]["fields"]]

        self.assertIn("author", fields)
        self.assertIn("collection", fields)


class DatabaseGateTests(TestCase):
    def test_refuses_the_sqlite_test_harness_by_default(self):
        with self.assertRaisesMessage(DatabaseNotSuitable, "SQLite test harness"):
            check_database_gate()

    def test_allows_the_harness_only_with_the_explicit_flag(self):
        info = check_database_gate(allow_test_database=True)

        self.assertTrue(info["test_database"])
        self.assertIn("sqlite", info["engine"])

    def test_flag_is_refused_outside_the_test_harness(self):
        with override_settings(USING_SQLITE_TEST_HARNESS=False):
            with self.assertRaisesMessage(DatabaseNotSuitable, "--allow-test-database"):
                check_database_gate(allow_test_database=True)

    def test_refuses_a_non_mysql_engine(self):
        with override_settings(USING_SQLITE_TEST_HARNESS=False):
            with self.assertRaisesMessage(DatabaseNotSuitable, "Refusing to import into database engine"):
                check_database_gate()

    def test_refuses_when_migrations_are_pending(self):
        from unittest import mock

        with mock.patch.object(
            catalogue_import,
            "_pending_migrations",
            return_value=["wallpapers.0002_wallpaper_author_wallpaper_collection"],
        ):
            with self.assertRaisesMessage(DatabaseNotSuitable, "before migrations are applied"):
                check_database_gate(allow_test_database=True)

    def test_gate_reports_no_password(self):
        info = check_database_gate(allow_test_database=True)
        self.assertNotIn("password", {key.lower() for key in info})


class ImportWriteTests(TestCase):
    def setUp(self):
        self.media_root = tempfile.mkdtemp(prefix="bwe-import-media-")
        self.storage_override = override_settings(
            MEDIA_ROOT=self.media_root,
            USING_SQLITE_TEST_HARNESS=True,
        )
        self.storage_override.enable()
        self.addCleanup(self.storage_override.disable)
        self.manifest = fresh_manifest()

    def _apply(self, **kwargs):
        return apply_import(
            self.manifest,
            repo_root=REPO_ROOT,
            allow_test_database=True,
            **kwargs,
        )

    def test_import_creates_all_selected_records(self):
        outcome = self._apply()

        self.assertEqual(len(outcome.created), 32)
        self.assertEqual(outcome.updated, [])
        self.assertEqual(Wallpaper.objects.count(), 32)
        self.assertEqual(len(outcome.files_written), 32)

    def test_imported_records_preserve_manifest_metadata(self):
        self._apply()

        record = self.manifest["records"][0]
        wallpaper = Wallpaper.objects.get(slug=record["slug"])

        self.assertEqual(wallpaper.title, record["title"])
        self.assertEqual(wallpaper.description, record["description"])
        self.assertEqual(wallpaper.category.name, record["category"]["name"])
        self.assertEqual(
            sorted(tag.slug for tag in wallpaper.tags.all()),
            sorted(tag["slug"] for tag in record["tags"]),
        )
        self.assertEqual(wallpaper.author, record["attribution"]["author"])
        self.assertEqual(wallpaper.collection, record["attribution"]["collection"])
        self.assertEqual(wallpaper.width, record["image"]["width"])
        self.assertEqual(wallpaper.height, record["image"]["height"])
        self.assertEqual(wallpaper.file_size, record["image"]["file_size"])
        self.assertEqual(wallpaper.source_url, record["source_url"])
        self.assertEqual(wallpaper.license_name, record["license"]["name"])
        self.assertEqual(wallpaper.license_url, record["license"]["url"])
        self.assertEqual(wallpaper.license_status, Wallpaper.LicenseStatus.DOCUMENTED)
        self.assertEqual(wallpaper.status, Wallpaper.Status.PUBLISHED)
        self.assertIsNotNone(wallpaper.published_at)
        self.assertTrue(wallpaper.image)
        self.assertEqual(wallpaper.image_url, "")

    def test_no_external_records_are_imported(self):
        self._apply()

        excluded_titles = {
            entry["title"] for entry in self.manifest["selection"]["excluded_records"]
        }
        imported_titles = set(Wallpaper.objects.values_list("title", flat=True))

        self.assertEqual(imported_titles & excluded_titles, set())
        self.assertFalse(Wallpaper.objects.filter(image_url__contains="pexels").exists())

    def test_categories_and_tags_are_not_duplicated(self):
        self._apply()
        self._apply(update_existing=True)

        self.assertEqual(Category.objects.count(), 5)
        self.assertEqual(Tag.objects.count(), 62)
        self.assertEqual(Wallpaper.objects.count(), 32)

    def test_second_run_is_idempotent_and_writes_nothing(self):
        self._apply()
        after_first = media_entries(self.media_root)

        outcome = self._apply()

        self.assertEqual(outcome.created, [])
        self.assertEqual(len(outcome.skipped), 32)
        self.assertEqual(outcome.files_written, [])
        self.assertEqual(Wallpaper.objects.count(), 32)
        self.assertEqual(media_entries(self.media_root), after_first)

    def test_existing_matching_records_are_skipped_without_update_flag(self):
        self._apply()
        Wallpaper.objects.filter(slug="altai").update(description="Hand edited")

        outcome = self._apply()

        self.assertIn("altai", outcome.skipped)
        self.assertEqual(
            Wallpaper.objects.get(slug="altai").description, "Hand edited"
        )

    def test_update_existing_refreshes_only_matching_records(self):
        self._apply()
        Wallpaper.objects.filter(slug="altai").update(
            description="Hand edited", download_count=7
        )

        outcome = self._apply(update_existing=True)

        self.assertIn("altai", outcome.updated)
        wallpaper = Wallpaper.objects.get(slug="altai")
        self.assertEqual(
            wallpaper.description, self.manifest["records"][0]["description"]
        )
        self.assertEqual(wallpaper.status, Wallpaper.Status.PUBLISHED)
        self.assertIsNotNone(wallpaper.published_at)
        # Download counts are user activity, never reset by an import.
        self.assertEqual(wallpaper.download_count, 7)
        self.assertEqual(Wallpaper.objects.count(), 32)

    def test_conflicting_slug_aborts_before_any_write(self):
        category = Category.objects.create(name="Manual")
        Wallpaper.objects.create(
            title="Completely different content",
            slug="altai",
            category=category,
            image_url="https://images.example.com/manual.jpg",
        )
        before = Wallpaper.objects.count()

        with self.assertRaisesMessage(ImportAborted, "Slug conflict"):
            self._apply()

        self.assertEqual(Wallpaper.objects.count(), before)
        self.assertEqual(
            Wallpaper.objects.get(slug="altai").title, "Completely different content"
        )
        self.assertEqual(media_entries(self.media_root), [])

    def test_unrelated_records_are_never_deleted(self):
        category = Category.objects.create(name="Manual")
        Wallpaper.objects.create(
            title="Hand made",
            slug="hand-made",
            category=category,
            image_url="https://images.example.com/manual.jpg",
        )

        self._apply()

        self.assertTrue(Wallpaper.objects.filter(slug="hand-made").exists())
        self.assertEqual(Wallpaper.objects.count(), 33)

    def test_failure_midway_rolls_back_rows_and_files(self):
        original = catalogue_import._asset_bytes
        calls = {"count": 0}

        def failing(path):
            calls["count"] += 1
            if calls["count"] == 5:
                raise OSError("simulated read failure")
            return original(path)

        catalogue_import._asset_bytes = failing
        try:
            with self.assertRaisesMessage(ImportAborted, "rolled back"):
                self._apply()
        finally:
            catalogue_import._asset_bytes = original

        self.assertEqual(Wallpaper.objects.count(), 0)
        self.assertEqual(media_entries(self.media_root), [])

    def test_failed_cleanup_reports_no_orphan_files(self):
        """Files written before the failure must be removed from storage."""

        original = catalogue_import._asset_bytes
        written_before_failure = []

        def failing(path):
            if len(written_before_failure) >= 3:
                raise OSError("simulated failure after storage writes")
            data = original(path)
            written_before_failure.append(path)
            return data

        catalogue_import._asset_bytes = failing
        try:
            with self.assertRaises(ImportAborted):
                self._apply()
        finally:
            catalogue_import._asset_bytes = original

        self.assertEqual(Wallpaper.objects.count(), 0)
        self.assertEqual(media_entries(self.media_root), [])

    def test_invalid_manifest_is_rejected_before_writing(self):
        self.manifest["records"][0]["image"]["sha256"] = "0" * 64

        with self.assertRaisesMessage(ImportAborted, "Manifest validation failed"):
            self._apply()

        self.assertEqual(Wallpaper.objects.count(), 0)

    def test_path_escape_in_manifest_is_rejected(self):
        self.manifest["records"][0]["image"]["source_path"] = "../../manage.py"
        self.manifest["records"][0]["image"]["sha256"] = "0" * 64

        with self.assertRaises(ImportAborted):
            self._apply()

        self.assertEqual(Wallpaper.objects.count(), 0)


class ImportCommandTests(TestCase):
    def setUp(self):
        self.media_root = tempfile.mkdtemp(prefix="bwe-command-media-")
        self.override = override_settings(
            MEDIA_ROOT=self.media_root, USING_SQLITE_TEST_HARNESS=True
        )
        self.override.enable()
        self.addCleanup(self.override.disable)

    def _run(self, *args):
        from io import StringIO

        out = StringIO()
        call_command("import_catalogue", *args, stdout=out, stderr=StringIO())
        return out.getvalue()

    def test_default_is_still_a_dry_run(self):
        output = self._run("--no-check-database")

        self.assertIn("DRY RUN", output)
        self.assertIn("nothing was written", output)
        self.assertEqual(Wallpaper.objects.count(), 0)
        self.assertEqual(media_entries(self.media_root), [])

    def test_apply_without_test_flag_is_refused(self):
        with self.assertRaisesMessage(CommandError, "safety gate"):
            self._run("--apply")

        self.assertEqual(Wallpaper.objects.count(), 0)

    def test_apply_with_test_flag_creates_records(self):
        output = self._run("--apply", "--allow-test-database")

        self.assertIn("Created : 32", output)
        self.assertEqual(Wallpaper.objects.count(), 32)

    def test_apply_json_report_records_the_result(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "apply.json"
            self._run("--apply", "--allow-test-database", "--json-report", str(path))
            report = json.loads(path.read_text(encoding="utf-8"))

        self.assertFalse(report["dry_run"])
        self.assertEqual(report["mode"], "apply")
        self.assertEqual(report["result"]["created"], 32)
        self.assertEqual(report["result"]["skipped"], 0)


class ManifestFieldCoverageTests(TestCase):
    def test_manifest_carries_author_and_collection_for_every_record(self):
        manifest = fresh_manifest()

        for record in manifest["records"]:
            attribution = record.get("attribution") or {}
            self.assertTrue(attribution.get("author"), record["slug"])
            self.assertTrue(attribution.get("collection"), record["slug"])

    def test_manifest_still_validates(self):
        result = validate_manifest(fresh_manifest(), repo_root=REPO_ROOT)
        self.assertTrue(result.ok, [p.message for p in result.errors])
