from django.test import override_settings
from rest_framework.test import APITestCase

from apps.wallpapers.models import Wallpaper

from .utils import EXTERNAL_IMAGE, image_upload, make_category, make_tag, make_wallpaper


class WallpaperVisibilityTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.category = make_category("Anime")
        cls.hidden_category = make_category("Hidden", is_active=False)
        cls.published = make_wallpaper(
            "Neon Tokyo",
            category=cls.category,
            description="Rain, signs, and reflections.",
            width=2560,
            height=1440,
            download_count=7,
        )
        cls.draft = make_wallpaper(
            "Draft piece", category=cls.category, status=Wallpaper.Status.DRAFT
        )
        cls.archived = make_wallpaper(
            "Archived piece", category=cls.category, status=Wallpaper.Status.ARCHIVED
        )
        cls.hidden = make_wallpaper("Hidden piece", category=cls.hidden_category)

    def test_list_returns_only_published_wallpapers(self):
        response = self.client.get("/api/v1/wallpapers/")

        self.assertEqual(response.status_code, 200)
        slugs = [item["slug"] for item in response.data["results"]]
        self.assertEqual(slugs, ["neon-tokyo"])

    def test_draft_and_archived_detail_are_not_found(self):
        for slug in (self.draft.slug, self.archived.slug, self.hidden.slug):
            with self.subTest(slug=slug):
                response = self.client.get(f"/api/v1/wallpapers/{slug}/")
                self.assertEqual(response.status_code, 404)

    def test_published_detail_is_retrieved_by_slug(self):
        response = self.client.get("/api/v1/wallpapers/neon-tokyo/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["title"], "Neon Tokyo")
        self.assertEqual(response.data["category"], {"name": "Anime", "slug": "anime"})

    def test_public_list_exposes_no_internal_fields(self):
        response = self.client.get("/api/v1/wallpapers/")
        item = response.data["results"][0]

        self.assertEqual(
            set(item),
            {
                "slug",
                "title",
                "description",
                "category",
                "tags",
                "author",
                "collection",
                "url",
                "thumbnail_url",
                "image_source",
                "orientation",
                "width",
                "height",
                "published_at",
                "download_count",
            },
        )
        self.assertNotIn("id", item)
        self.assertNotIn("status", item)
        self.assertNotIn("is_active", item)

    def test_detail_requires_public_fields_only(self):
        response = self.client.get("/api/v1/wallpapers/neon-tokyo/")

        for forbidden in ("id", "status", "created_at", "updated_at", "category_id"):
            self.assertNotIn(forbidden, response.data)

    def test_orientation_is_derived_from_real_dimensions(self):
        response = self.client.get("/api/v1/wallpapers/neon-tokyo/")
        self.assertEqual(response.data["orientation"], "landscape")

        portrait = make_wallpaper(
            "Portrait", category=self.category, width=1080, height=1920
        )
        response = self.client.get(f"/api/v1/wallpapers/{portrait.slug}/")
        self.assertEqual(response.data["orientation"], "portrait")

        unknown = make_wallpaper("Unknown size", category=self.category)
        response = self.client.get(f"/api/v1/wallpapers/{unknown.slug}/")
        self.assertIsNone(response.data["orientation"])


class WallpaperImageSerializationTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.category = make_category("Nature")
        cls.uploaded = make_wallpaper(
            "Uploaded art",
            category=cls.category,
            image=image_upload("art.png"),
            image_url="",
            width=1920,
            height=1080,
        )
        cls.external = make_wallpaper(
            "External art",
            category=cls.category,
            image_url="https://images.example.com/external.jpg?w=1200",
            thumbnail_url="https://images.example.com/thumb.jpg",
        )
        cls.both = make_wallpaper(
            "Both sources",
            category=cls.category,
            image=image_upload("both.png"),
        )

    def test_uploaded_image_is_an_absolute_url(self):
        response = self.client.get(f"/api/v1/wallpapers/{self.uploaded.slug}/")

        self.assertEqual(response.data["image_source"], "uploaded")
        self.assertTrue(
            response.data["url"].startswith("http://testserver/media/wallpapers/")
        )
        self.assertEqual(response.data["url"], response.data["uploaded_image_url"])
        self.assertIsNone(response.data["external_image_url"])
        self.assertEqual(response.data["thumbnail_url"], response.data["url"])

    def test_external_url_is_preserved_exactly(self):
        response = self.client.get(f"/api/v1/wallpapers/{self.external.slug}/")

        self.assertEqual(response.data["image_source"], "external")
        self.assertEqual(
            response.data["url"], "https://images.example.com/external.jpg?w=1200"
        )
        self.assertEqual(
            response.data["external_image_url"],
            "https://images.example.com/external.jpg?w=1200",
        )
        self.assertIsNone(response.data["uploaded_image_url"])
        self.assertEqual(
            response.data["thumbnail_url"],
            "https://images.example.com/thumb.jpg",
        )
        self.assertEqual(
            response.data["external_thumbnail_url"],
            "https://images.example.com/thumb.jpg",
        )

    def test_uploaded_image_takes_precedence_when_both_exist(self):
        response = self.client.get(f"/api/v1/wallpapers/{self.both.slug}/")

        self.assertEqual(response.data["image_source"], "uploaded")
        self.assertTrue(
            response.data["url"].startswith("http://testserver/media/wallpapers/")
        )
        self.assertEqual(
            response.data["external_image_url"], EXTERNAL_IMAGE
        )

    def test_list_and_detail_agree_on_the_image_url(self):
        listing = self.client.get("/api/v1/wallpapers/")
        detail = self.client.get(f"/api/v1/wallpapers/{self.uploaded.slug}/")

        item = next(
            entry
            for entry in listing.data["results"]
            if entry["slug"] == self.uploaded.slug
        )
        self.assertEqual(item["url"], detail.data["url"])

    def test_detail_exposes_source_and_licence_provenance(self):
        wallpaper = make_wallpaper(
            "Licensed",
            category=self.category,
            source_url="https://example.com/artist",
            license_name="CC BY-SA 4.0",
            license_url="https://creativecommons.org/licenses/by-sa/4.0/",
            license_status=Wallpaper.LicenseStatus.DOCUMENTED,
        )

        response = self.client.get(f"/api/v1/wallpapers/{wallpaper.slug}/")

        self.assertEqual(response.data["source_url"], "https://example.com/artist")
        self.assertEqual(
            response.data["license"],
            {
                "name": "CC BY-SA 4.0",
                "url": "https://creativecommons.org/licenses/by-sa/4.0/",
                "status": "documented",
            },
        )

    def test_detail_includes_nested_tags(self):
        wallpaper = make_wallpaper(
            "Tagged", category=self.category, tags=[make_tag("neon"), make_tag("city")]
        )

        response = self.client.get(f"/api/v1/wallpapers/{wallpaper.slug}/")

        self.assertEqual(
            response.data["tags"],
            [{"name": "city", "slug": "city"}, {"name": "neon", "slug": "neon"}],
        )


class WallpaperSearchFilterTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.anime = make_category("Anime")
        cls.nature = make_category("Nature")
        cls.neon = make_tag("neon")
        cls.city = make_tag("city")
        cls.mountains = make_tag("mountains")

        cls.one = make_wallpaper(
            "Neon Tokyo",
            category=cls.anime,
            description="Night streets and glowing signs.",
            tags=[cls.neon, cls.city],
            width=2560,
            height=1440,
            download_count=10,
        )
        cls.two = make_wallpaper(
            "Quiet Peaks",
            category=cls.nature,
            description="A calm mountain range at dawn.",
            tags=[cls.mountains],
            width=1440,
            height=2560,
            download_count=40,
        )
        cls.three = make_wallpaper(
            "Square Study",
            category=cls.nature,
            description="Minimal geometry.",
            tags=[cls.neon],
            width=2000,
            height=2000,
            download_count=0,
        )
        make_wallpaper(
            "Neon draft",
            category=cls.anime,
            status=Wallpaper.Status.DRAFT,
            tags=[cls.neon],
            description="Glowing signs, not published.",
        )

    def slugs(self, query=""):
        response = self.client.get(f"/api/v1/wallpapers/{query}")
        self.assertEqual(response.status_code, 200, response.data)
        return [item["slug"] for item in response.data["results"]]

    def test_search_matches_title_case_insensitively(self):
        self.assertEqual(self.slugs("?search=neon"), ["neon-tokyo"])

    def test_search_matches_description(self):
        self.assertEqual(self.slugs("?search=GLOWING"), ["neon-tokyo"])

    def test_search_ignores_drafts(self):
        self.assertNotIn("neon-draft", self.slugs("?search=neon"))

    def test_filter_by_category_slug(self):
        self.assertEqual(
            sorted(self.slugs("?category=nature")), ["quiet-peaks", "square-study"]
        )
        self.assertEqual(self.slugs("?category=anime"), ["neon-tokyo"])

    def test_filter_by_unknown_category_returns_nothing(self):
        self.assertEqual(self.slugs("?category=missing"), [])

    def test_filter_by_tag_slug(self):
        self.assertEqual(
            sorted(self.slugs("?tag=neon")), ["neon-tokyo", "square-study"]
        )

    def test_repeated_tags_use_and_semantics_without_duplicates(self):
        response = self.client.get("/api/v1/wallpapers/?tag=neon&tag=city")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [item["slug"] for item in response.data["results"]], ["neon-tokyo"]
        )

    def test_comma_separated_tags_are_supported(self):
        self.assertEqual(self.slugs("?tag=neon,city"), ["neon-tokyo"])

    def test_orientation_filters(self):
        self.assertEqual(self.slugs("?orientation=landscape"), ["neon-tokyo"])
        self.assertEqual(self.slugs("?orientation=portrait"), ["quiet-peaks"])
        self.assertEqual(self.slugs("?orientation=square"), ["square-study"])

    def test_invalid_orientation_returns_structured_error(self):
        response = self.client.get("/api/v1/wallpapers/?orientation=diagonal")

        self.assertEqual(response.status_code, 400)
        self.assertIn("orientation", response.data)

    def test_ordering_by_download_count(self):
        self.assertEqual(
            self.slugs("?ordering=-download_count"),
            ["quiet-peaks", "neon-tokyo", "square-study"],
        )
        self.assertEqual(
            self.slugs("?ordering=download_count"),
            ["square-study", "neon-tokyo", "quiet-peaks"],
        )

    def test_ordering_by_title_and_publication_date(self):
        self.assertEqual(
            self.slugs("?ordering=title"),
            ["neon-tokyo", "quiet-peaks", "square-study"],
        )
        self.assertEqual(
            self.slugs("?ordering=published_at")[:1], ["neon-tokyo"]
        )

    def test_multiple_ordering_fields(self):
        self.assertEqual(
            self.slugs("?ordering=-download_count,title"),
            ["quiet-peaks", "neon-tokyo", "square-study"],
        )

    def test_multi_field_ordering_uses_the_second_field_on_ties(self):
        make_wallpaper(
            "Zebra Tie",
            category=self.nature,
            download_count=10,
            image_url=EXTERNAL_IMAGE,
        )

        # Both Zebra Tie and Neon Tokyo have 10 downloads; the title decides.
        self.assertEqual(
            self.slugs("?ordering=-download_count,title"),
            ["quiet-peaks", "neon-tokyo", "zebra-tie", "square-study"],
        )

    def test_invalid_ordering_returns_structured_error(self):
        response = self.client.get("/api/v1/wallpapers/?ordering=password")

        self.assertEqual(response.status_code, 400)
        self.assertIn("ordering", response.data)

    def test_search_filters_combine(self):
        self.assertEqual(
            self.slugs("?search=peaks&category=nature"), ["quiet-peaks"]
        )


class WallpaperPaginationTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        category = make_category("Bulk")
        for index in range(30):
            make_wallpaper(f"Wallpaper {index:02d}", category=category)

    def test_default_page_size_and_links(self):
        response = self.client.get("/api/v1/wallpapers/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 30)
        self.assertEqual(len(response.data["results"]), 24)
        self.assertIsNotNone(response.data["next"])
        self.assertIsNone(response.data["previous"])

    def test_page_parameter(self):
        response = self.client.get("/api/v1/wallpapers/?page=2")

        self.assertEqual(len(response.data["results"]), 6)
        self.assertIsNone(response.data["next"])
        self.assertIsNotNone(response.data["previous"])

    def test_page_size_parameter(self):
        response = self.client.get("/api/v1/wallpapers/?page_size=5")

        self.assertEqual(len(response.data["results"]), 5)
        self.assertEqual(response.data["count"], 30)

    @override_settings(API_MAX_PAGE_SIZE=10)
    def test_page_size_is_capped_by_the_configured_maximum(self):
        response = self.client.get("/api/v1/wallpapers/?page_size=500")

        self.assertEqual(len(response.data["results"]), 10)

    def test_invalid_page_returns_not_found(self):
        response = self.client.get("/api/v1/wallpapers/?page=999")

        self.assertEqual(response.status_code, 404)


class PopularWallpaperTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        category = make_category("Ranked")
        cls.top = make_wallpaper(
            "Most downloaded", category=category, download_count=50
        )
        cls.middle = make_wallpaper("Middle", category=category, download_count=5)
        cls.none = make_wallpaper("Never", category=category, download_count=0)
        make_wallpaper(
            "Draft with downloads",
            category=category,
            status=Wallpaper.Status.DRAFT,
            download_count=999,
        )

    def test_popular_endpoint_orders_by_download_count(self):
        response = self.client.get("/api/v1/wallpapers/popular/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [item["slug"] for item in response.data["results"]],
            ["most-downloaded", "middle", "never"],
        )

    def test_popular_endpoint_excludes_unpublished_rows(self):
        response = self.client.get("/api/v1/wallpapers/popular/")
        slugs = [item["slug"] for item in response.data["results"]]

        self.assertNotIn("draft-with-downloads", slugs)

    def test_popular_endpoint_does_not_claim_trending(self):
        response = self.client.get("/api/v1/wallpapers/popular/")

        # No endpoint or field asserts time-windowed popularity.
        self.assertNotIn("trending", str(response.data).lower())
        self.assertNotIn("featured", response.data)
