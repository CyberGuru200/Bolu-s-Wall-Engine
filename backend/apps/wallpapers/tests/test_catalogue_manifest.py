"""Phase 6B tests: manifest integrity, validation, planning, and safety.

These tests run against freshly created in-memory test databases. They never
import catalogue data: every test asserts that the command left the row count
unchanged.
"""

import json
import shutil
import tempfile
from io import StringIO
from pathlib import Path

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from apps.catalog.models import Category, Tag
from apps.wallpapers.catalogue import (
    ExistingRecord,
    check_source_integrity,
    load_manifest,
    plan_import,
    summarize,
    validate_manifest,
)
from apps.wallpapers.models import Wallpaper

REPO_ROOT = Path(settings.BASE_DIR).resolve().parent
MANIFEST_PATH = Path(settings.BASE_DIR) / "catalogue" / "manifest.json"


def manifest_copy(**overrides):
    manifest = load_manifest(MANIFEST_PATH)
    manifest.update(overrides)
    return manifest


class ManifestIntegrityTests(TestCase):
    def test_manifest_validates_without_errors(self):
        manifest = load_manifest(MANIFEST_PATH)
        result = validate_manifest(manifest, repo_root=REPO_ROOT)
        self.assertTrue(
            result.ok,
            msg="\n".join(problem.message for problem in result.errors),
        )

    def test_source_modules_match_the_manifest(self):
        manifest = load_manifest(MANIFEST_PATH)
        problems = check_source_integrity(manifest, repo_root=REPO_ROOT)
        self.assertEqual(
            problems,
            [],
            msg="\n".join(problem.message for problem in problems),
        )

    def test_manifest_selects_only_the_verified_local_records(self):
        manifest = load_manifest(MANIFEST_PATH)
        summary = summarize(manifest)

        self.assertEqual(summary["total_source_records"], 56)
        self.assertEqual(summary["selected_records"], 32)
        self.assertEqual(summary["excluded_records"], 24)
        self.assertEqual(summary["categories"], 5)
        self.assertEqual(summary["tags"], 62)

        selection = manifest["selection"]
        self.assertEqual(selection["policy"], "verified-local-image-records-only")
        for entry in selection["excluded_records"]:
            self.assertEqual(entry["reason"], "external-url-unverified")

        for record in manifest["records"]:
            self.assertTrue(record["image"]["source_path"].startswith("Front End Project/public/"))
            self.assertFalse(record["source_url"].startswith("https://images.pexels.com"))
            self.assertNotIn("pexels", record["image"]["source_path"].lower())

    def test_category_distribution_matches_the_audit(self):
        manifest = load_manifest(MANIFEST_PATH)
        self.assertEqual(
            summarize(manifest)["category_counts"],
            {
                "abstract": 15,
                "illustration": 3,
                "minimalist": 3,
                "nature": 9,
                "space": 2,
            },
        )

    def test_licence_and_attribution_coverage(self):
        manifest = load_manifest(MANIFEST_PATH)
        summary = summarize(manifest)
        self.assertEqual(
            summary["license_coverage"], {"CC BY-SA 4.0": 16, "LGPLv3": 16}
        )
        self.assertEqual(summary["distinct_authors"], 19)
        self.assertEqual(summary["distinct_collections"], 1)
        for record in manifest["records"]:
            self.assertEqual(record["license"]["status"], "documented")
            self.assertTrue(record["license"]["name"])
            self.assertTrue(record["license"]["url"])
            self.assertTrue(record["attribution"]["author"])

    def test_manifest_is_byte_stable_when_regenerated(self):
        """The generator must be deterministic.

        Skipped gracefully when Node is unavailable; the build is also compared
        across two runs outside the test suite.
        """

        import shutil as _shutil
        import subprocess

        if not _shutil.which("node"):
            self.skipTest("node is not available in this environment")

        builder = REPO_ROOT / "tools" / "catalogue" / "build_manifest.mjs"
        with tempfile.TemporaryDirectory() as tmp:
            first = Path(tmp) / "first.json"
            second = Path(tmp) / "second.json"
            for output in (first, second):
                subprocess.run(
                    ["node", str(builder), "--output", str(output)],
                    check=True,
                    capture_output=True,
                    cwd=REPO_ROOT,
                )
            self.assertEqual(first.read_bytes(), second.read_bytes())
            self.assertEqual(first.read_bytes(), MANIFEST_PATH.read_bytes())


class ManifestValidationTests(TestCase):
    def setUp(self):
        self.manifest = load_manifest(MANIFEST_PATH)

    def _validate(self, manifest):
        return validate_manifest(manifest, repo_root=REPO_ROOT)

    def test_duplicate_slug_is_rejected(self):
        manifest = json.loads(json.dumps(self.manifest))
        manifest["records"][1]["slug"] = manifest["records"][0]["slug"]

        result = self._validate(manifest)

        self.assertFalse(result.ok)
        self.assertTrue(
            any("Duplicate slug" in problem.message for problem in result.errors)
        )

    def test_slug_that_disagrees_with_django_slugify_is_rejected(self):
        manifest = json.loads(json.dumps(self.manifest))
        manifest["records"][0]["slug"] = "Not A Slug"

        result = self._validate(manifest)

        self.assertFalse(result.ok)
        self.assertTrue(
            any("does not match Django slugify" in problem.message for problem in result.errors)
        )

    def test_path_escape_is_rejected(self):
        manifest = json.loads(json.dumps(self.manifest))
        manifest["records"][0]["image"]["source_path"] = "../manage.py"

        result = self._validate(manifest)

        self.assertFalse(result.ok)
        self.assertTrue(
            any("outside Front End Project/public" in problem.message for problem in result.errors)
        )

    def test_path_outside_public_directory_is_rejected(self):
        manifest = json.loads(json.dumps(self.manifest))
        manifest["records"][0]["image"]["source_path"] = "backend/manage.py"

        result = self._validate(manifest)

        self.assertFalse(result.ok)
        self.assertTrue(
            any("outside Front End Project/public" in problem.message for problem in result.errors)
        )

    def test_missing_file_is_rejected(self):
        manifest = json.loads(json.dumps(self.manifest))
        manifest["records"][0]["image"]["source_path"] = (
            "Front End Project/public/wallpapers/kde/does-not-exist.jpg"
        )

        result = self._validate(manifest)

        self.assertFalse(result.ok)
        self.assertTrue(
            any("does not exist" in problem.message for problem in result.errors)
        )

    def test_image_hash_mismatch_is_rejected(self):
        manifest = json.loads(json.dumps(self.manifest))
        manifest["records"][0]["image"]["sha256"] = "0" * 64

        result = self._validate(manifest)

        self.assertFalse(result.ok)
        self.assertTrue(
            any("sha256 mismatch" in problem.message for problem in result.errors)
        )

    def test_dimension_mismatch_is_rejected(self):
        manifest = json.loads(json.dumps(self.manifest))
        manifest["records"][0]["image"]["width"] = 123

        result = self._validate(manifest)

        self.assertFalse(result.ok)
        self.assertTrue(
            any("Dimensions mismatch" in problem.message for problem in result.errors)
        )

    def test_excluded_record_cannot_also_be_imported(self):
        manifest = json.loads(json.dumps(self.manifest))
        manifest["selection"]["excluded_records"][0]["title"] = manifest["records"][0]["title"]

        result = self._validate(manifest)

        self.assertFalse(result.ok)
        self.assertTrue(
            any("also appears in 'records'" in problem.message for problem in result.errors)
        )

    def test_undeclared_tag_is_rejected(self):
        manifest = json.loads(json.dumps(self.manifest))
        manifest["records"][0]["tags"].append({"name": "not-declared", "slug": "not-declared"})

        result = self._validate(manifest)

        self.assertFalse(result.ok)
        self.assertTrue(
            any("is not declared" in problem.message for problem in result.errors)
        )

    def test_stale_source_hash_is_rejected(self):
        manifest = json.loads(json.dumps(self.manifest))
        manifest["source"]["modules"][0]["sha256"] = "0" * 64

        problems = check_source_integrity(manifest, repo_root=REPO_ROOT)

        self.assertTrue(problems)
        self.assertIn("changed since the manifest was generated", problems[0].message)

    def test_documented_licence_without_name_or_url_is_rejected(self):
        manifest = json.loads(json.dumps(self.manifest))
        manifest["records"][0]["license"] = {
            "name": "",
            "url": "",
            "status": "documented",
            "id": "",
            "text_path": "",
        }

        result = self._validate(manifest)

        self.assertFalse(result.ok)
        self.assertTrue(
            any("neither a name nor a URL" in problem.message for problem in result.errors)
        )


class ImportPlannerTests(TestCase):
    def setUp(self):
        self.manifest = load_manifest(MANIFEST_PATH)

    def test_empty_database_projects_creates_only(self):
        plan = plan_import(self.manifest, [])

        self.assertEqual(len(plan.create), 32)
        self.assertEqual(plan.update, [])
        self.assertEqual(plan.conflict, [])
        self.assertEqual(plan.untouched, [])

    def test_same_slug_and_title_projects_an_update(self):
        plan = plan_import(
            self.manifest,
            [ExistingRecord(slug="altai", title="altai", status="draft")],
        )

        self.assertIn("altai", plan.update)
        self.assertNotIn("altai", plan.create)
        self.assertEqual(len(plan.create), 31)

    def test_same_slug_different_title_is_a_conflict_and_is_not_overwritten(self):
        plan = plan_import(
            self.manifest,
            [ExistingRecord(slug="altai", title="Someone else's wallpaper")],
        )

        self.assertIn("altai", plan.skip)
        self.assertNotIn("altai", plan.update)
        self.assertNotIn("altai", plan.create)
        self.assertEqual(
            plan.conflict[0]["reason"], "slug-collision-with-unrelated-title"
        )

    def test_unrelated_rows_are_reported_untouched(self):
        plan = plan_import(
            self.manifest,
            [ExistingRecord(slug="hand-made-record", title="Hand made")],
        )

        self.assertEqual(plan.untouched, ["hand-made-record"])
        self.assertEqual(len(plan.create), 32)


class ImportCommandSafetyTests(TestCase):
    def setUp(self):
        self.category = Category.objects.create(name="Nature")
        self.tag = Tag.objects.create(name="mountains")
        self.baseline = Wallpaper.objects.count()

    def _run(self, *args):
        out = StringIO()
        call_command("import_catalogue", *args, stdout=out, stderr=StringIO())
        return out.getvalue()

    def test_default_run_is_a_dry_run_and_writes_nothing(self):
        output = self._run("--no-check-database")

        self.assertIn("DRY RUN", output)
        self.assertIn("Selected for import               : 32", output)
        self.assertIn("Excluded                          : 24", output)
        self.assertIn("Validation: no errors", output)
        self.assertIn("Missing local files        : 0", output)
        self.assertIn("Duplicate slugs            : 0", output)
        self.assertIn("Duplicate source paths     : 0", output)
        self.assertIn("Records missing required fields: 0", output)
        self.assertIn("Excluded (external-url-unverified) : 24", output)
        self.assertEqual(Wallpaper.objects.count(), self.baseline)
        self.assertEqual(Category.objects.count(), 1)
        self.assertEqual(Tag.objects.count(), 1)

    def test_apply_is_refused_on_the_test_harness(self):
        """Phase 6C: --apply exists but the database gate refuses the harness."""

        with self.assertRaisesMessage(CommandError, "safety gate"):
            self._run("--apply")

        self.assertEqual(Wallpaper.objects.count(), self.baseline)
        self.assertFalse(Wallpaper.objects.filter(slug="altai").exists())

    def test_json_report_is_written_and_marks_a_dry_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            report_path = Path(tmp) / "report.json"
            self._run("--no-check-database", "--json-report", str(report_path))

            report = json.loads(report_path.read_text(encoding="utf-8"))

        self.assertTrue(report["dry_run"])
        self.assertTrue(report["validation"]["ok"])
        self.assertEqual(report["summary"]["selected_records"], 32)
        self.assertEqual(report["integrity"]["missing_local_files"], 0)
        self.assertEqual(report["integrity"]["duplicate_slugs"], 0)
        self.assertEqual(
            report["integrity"]["excluded_by_reason"],
            {"external-url-unverified": 24},
        )
        self.assertFalse(report["database"]["checked"])

    def test_stale_manifest_is_rejected(self):
        manifest = load_manifest(MANIFEST_PATH)
        manifest["source"]["modules"][0]["sha256"] = "0" * 64

        with tempfile.TemporaryDirectory() as tmp:
            stale_path = Path(tmp) / "stale.json"
            stale_path.write_text(json.dumps(manifest), encoding="utf-8")
            with self.assertRaises(CommandError):
                self._run("--no-check-database", "--manifest", str(stale_path))

        self.assertEqual(Wallpaper.objects.count(), self.baseline)

    def test_dry_run_states_that_no_application_database_was_used(self):
        """Phase 6C: the harness is never presented as an application database."""

        Wallpaper.objects.create(
            title="Different content",
            slug="summer-1am",
            category=self.category,
            image_url="https://images.example.com/other.jpg",
        )
        before = Wallpaper.objects.count()

        report_path = Path(tempfile.mkdtemp()) / "r.json"
        output = self._run("--json-report", str(report_path))

        self.assertIn("SQLite test harness", output)
        self.assertIn("Not computed", output)
        self.assertIn("WITHOUT application-database", output)
        report = json.loads(report_path.read_text(encoding="utf-8"))
        self.assertFalse(report["database"]["application_database"])
        self.assertFalse(report["database"]["checked"])
        self.assertIsNone(report["projection"])

        self.assertEqual(Wallpaper.objects.count(), before)
        self.assertEqual(
            Wallpaper.objects.get(slug="summer-1am").title, "Different content"
        )
