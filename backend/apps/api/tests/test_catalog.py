from django.test import override_settings
from rest_framework.test import APITestCase

from apps.catalog.models import Category, Tag
from apps.wallpapers.models import Wallpaper

from .utils import make_category, make_tag, make_wallpaper


class CategoryApiTests(APITestCase):
    url = "/api/v1/categories/"

    @classmethod
    def setUpTestData(cls):
        cls.active = make_category("Minimalist")
        cls.also_active = make_category("Anime")
        cls.inactive = make_category("Retired", is_active=False)
        make_wallpaper("Published", category=cls.active)
        make_wallpaper("Draft", category=cls.active, status=Wallpaper.Status.DRAFT)
        make_wallpaper(
            "Archived", category=cls.active, status=Wallpaper.Status.ARCHIVED
        )

    def test_list_returns_only_active_categories_ordered_by_name(self):
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        slugs = [item["slug"] for item in response.data["results"]]
        self.assertEqual(slugs, ["anime", "minimalist"])
        self.assertNotIn("retired", slugs)

    def test_public_payload_has_no_internal_fields(self):
        response = self.client.get(self.url)
        item = response.data["results"][0]

        self.assertEqual(
            set(item),
            {
                "name",
                "slug",
                "description",
                "image_url",
                "image_source",
                "wallpaper_count",
            },
        )
        self.assertNotIn("is_active", item)
        self.assertNotIn("id", item)

    def test_wallpaper_count_counts_only_published_wallpapers(self):
        response = self.client.get(self.url)
        counts = {
            item["slug"]: item["wallpaper_count"]
            for item in response.data["results"]
        }

        self.assertEqual(counts["minimalist"], 1)
        self.assertEqual(counts["anime"], 0)

    def test_detail_is_retrieved_by_slug(self):
        response = self.client.get("/api/v1/categories/minimalist/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["name"], "Minimalist")

    def test_inactive_category_detail_is_not_found(self):
        response = self.client.get("/api/v1/categories/retired/")

        self.assertEqual(response.status_code, 404)

    def test_unknown_category_is_not_found(self):
        self.assertEqual(
            self.client.get("/api/v1/categories/missing/").status_code, 404
        )

    def test_category_image_url_supports_external_values(self):
        make_category("Colored", image_url="https://cdn.example.com/cat.jpg")

        response = self.client.get("/api/v1/categories/")
        item = next(
            entry for entry in response.data["results"] if entry["slug"] == "colored"
        )

        self.assertEqual(item["image_url"], "https://cdn.example.com/cat.jpg")
        self.assertEqual(item["image_source"], "external")

    def test_category_list_is_paginated(self):
        response = self.client.get(self.url)

        self.assertIn("count", response.data)
        self.assertIn("next", response.data)
        self.assertIn("results", response.data)

    @override_settings(API_PAGE_SIZE=1)
    def test_page_size_setting_is_respected(self):
        response = self.client.get(self.url)

        self.assertEqual(len(response.data["results"]), 1)

    def test_public_users_cannot_create_or_change_categories(self):
        payload = {"name": "Hacked", "slug": "hacked"}
        self.assertEqual(self.client.post(self.url, payload).status_code, 405)
        detail = "/api/v1/categories/minimalist/"
        self.assertEqual(self.client.put(detail, payload).status_code, 405)
        self.assertEqual(self.client.patch(detail, payload).status_code, 405)
        self.assertEqual(self.client.delete(detail).status_code, 405)
        self.assertFalse(Category.objects.filter(slug="hacked").exists())


class TagApiTests(APITestCase):
    url = "/api/v1/tags/"

    @classmethod
    def setUpTestData(cls):
        category = make_category("Abstract")
        cls.published_tag = make_tag("neon")
        cls.draft_only_tag = make_tag("unreleased")
        cls.shared_tag = make_tag("blue")

        cls.published = make_wallpaper(
            "Published", category=category, tags=[cls.published_tag, cls.shared_tag]
        )
        cls.other = make_wallpaper(
            "Second", category=category, tags=[cls.shared_tag]
        )
        make_wallpaper(
            "Draft",
            category=category,
            status=Wallpaper.Status.DRAFT,
            tags=[cls.draft_only_tag],
        )

    def test_list_only_returns_tags_used_by_published_wallpapers(self):
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        slugs = [item["slug"] for item in response.data["results"]]
        self.assertEqual(slugs, ["blue", "neon"])
        self.assertNotIn("unreleased", slugs)

    def test_wallpaper_count_uses_published_wallpapers(self):
        response = self.client.get(self.url)
        counts = {
            item["slug"]: item["wallpaper_count"]
            for item in response.data["results"]
        }

        self.assertEqual(counts["blue"], 2)
        self.assertEqual(counts["neon"], 1)

    def test_tag_detail_by_slug(self):
        response = self.client.get("/api/v1/tags/neon/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["name"], "neon")

    def test_tag_used_only_by_drafts_is_not_found(self):
        self.assertEqual(
            self.client.get("/api/v1/tags/unreleased/").status_code, 404
        )

    def test_tags_from_inactive_categories_are_hidden(self):
        hidden = make_category("Hidden", is_active=False)
        hidden_tag = make_tag("hidden-tag")
        make_wallpaper("Hidden wall", category=hidden, tags=[hidden_tag])

        response = self.client.get(self.url)
        slugs = [item["slug"] for item in response.data["results"]]

        self.assertNotIn("hidden-tag", slugs)

    def test_public_users_cannot_create_or_change_tags(self):
        payload = {"name": "hacked", "slug": "hacked"}
        self.assertEqual(self.client.post(self.url, payload).status_code, 405)
        detail = "/api/v1/tags/neon/"
        self.assertEqual(self.client.put(detail, payload).status_code, 405)
        self.assertEqual(self.client.delete(detail).status_code, 405)
        self.assertFalse(Tag.objects.filter(slug="hacked").exists())
