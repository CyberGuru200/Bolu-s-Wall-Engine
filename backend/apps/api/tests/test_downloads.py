from django.core.cache import cache
from rest_framework.settings import api_settings
from rest_framework.test import APITestCase

from apps.wallpapers.models import Wallpaper

from .utils import image_upload, make_category, make_wallpaper


class DownloadApiTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.category = make_category("Anime")
        cls.external = make_wallpaper(
            "External", category=cls.category, download_count=4
        )
        cls.uploaded = make_wallpaper(
            "Uploaded", category=cls.category, image=image_upload(), image_url=""
        )
        cls.draft = make_wallpaper(
            "Draft", category=cls.category, status=Wallpaper.Status.DRAFT
        )
        cls.archived = make_wallpaper(
            "Archived", category=cls.category, status=Wallpaper.Status.ARCHIVED
        )
        cls.hidden_category = make_category("Hidden", is_active=False)
        cls.hidden = make_wallpaper("Hidden", category=cls.hidden_category)

    def url(self, slug):
        return f"/api/v1/wallpapers/{slug}/download/"

    def test_download_increments_the_counter(self):
        response = self.client.post(self.url(self.external.slug))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["download_count"], 5)
        self.external.refresh_from_db()
        self.assertEqual(self.external.download_count, 5)

    def test_each_request_increments_by_exactly_one(self):
        for expected in range(1, 6):
            response = self.client.post(self.url(self.external.slug))
            self.assertEqual(response.data["download_count"], 4 + expected)

        self.external.refresh_from_db()
        self.assertEqual(self.external.download_count, 9)

    def test_external_download_url_is_returned_unchanged(self):
        response = self.client.post(self.url(self.external.slug))

        self.assertEqual(response.data["image_source"], "external")
        self.assertEqual(
            response.data["download_url"],
            "https://images.example.com/wallpaper.jpg",
        )
        # JSON, not a redirect: no Location header and no 3xx status.
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("Location", response)

    def test_uploaded_download_url_is_absolute(self):
        response = self.client.post(self.url(self.uploaded.slug))

        self.assertEqual(response.data["image_source"], "uploaded")
        self.assertTrue(
            response.data["download_url"].startswith(
                "http://testserver/media/wallpapers/"
            )
        )

    def test_unpublished_wallpapers_cannot_be_downloaded(self):
        for wallpaper in (self.draft, self.archived, self.hidden):
            with self.subTest(slug=wallpaper.slug):
                response = self.client.post(self.url(wallpaper.slug))
                self.assertEqual(response.status_code, 404)

        self.draft.refresh_from_db()
        self.archived.refresh_from_db()
        self.hidden.refresh_from_db()
        self.assertEqual(self.draft.download_count, 0)
        self.assertEqual(self.archived.download_count, 0)
        self.assertEqual(self.hidden.download_count, 0)

    def test_unknown_slug_returns_404(self):
        self.assertEqual(
            self.client.post(self.url("does-not-exist")).status_code, 404
        )

    def test_get_is_not_allowed(self):
        response = self.client.get(self.url(self.external.slug))

        self.assertEqual(response.status_code, 405)
        self.external.refresh_from_db()
        self.assertEqual(self.external.download_count, 4)

    def test_anonymous_downloads_are_allowed(self):
        response = self.client.post(self.url(self.external.slug))

        self.assertEqual(response.status_code, 200)

    def test_counter_cannot_go_negative(self):
        self.external.download_count = 0
        self.external.save(update_fields=["download_count"])

        response = self.client.post(self.url(self.external.slug))

        self.assertEqual(response.data["download_count"], 1)


class DownloadThrottleTests(APITestCase):
    """Throttling is best-effort abuse control, not verified analytics."""

    def setUp(self):
        cache.clear()
        self.category = make_category("Throttle")
        self.wallpaper = make_wallpaper("Throttled", category=self.category)
        self.original_rate = api_settings.DEFAULT_THROTTLE_RATES.get("downloads")
        api_settings.DEFAULT_THROTTLE_RATES["downloads"] = "2/minute"

    def tearDown(self):
        api_settings.DEFAULT_THROTTLE_RATES["downloads"] = self.original_rate
        cache.clear()

    def test_requests_above_the_configured_rate_return_429(self):
        url = f"/api/v1/wallpapers/{self.wallpaper.slug}/download/"

        self.assertEqual(self.client.post(url).status_code, 200)
        self.assertEqual(self.client.post(url).status_code, 200)
        blocked = self.client.post(url)

        self.assertEqual(blocked.status_code, 429)
        self.assertIn("detail", blocked.data)

        self.wallpaper.refresh_from_db()
        # Rejected requests are not counted.
        self.assertEqual(self.wallpaper.download_count, 2)
