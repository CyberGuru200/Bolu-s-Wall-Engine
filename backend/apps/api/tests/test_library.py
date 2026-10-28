from rest_framework.test import APITestCase

from apps.library.models import Like, SavedWallpaper
from apps.wallpapers.models import Wallpaper

from .utils import make_category, make_user, make_wallpaper


class LibraryApiMixin:
    """Shared assertions for likes and saved wallpapers."""

    model = None
    list_url = None
    detail_url = None
    timestamp_key = None

    @classmethod
    def setUpTestData(cls):
        cls.category = make_category("Anime")
        cls.user = make_user("bolu")
        cls.other_user = make_user("visitor")
        cls.wallpaper = make_wallpaper("Neon Tokyo", category=cls.category)
        cls.other_wallpaper = make_wallpaper("Quiet Peaks", category=cls.category)
        cls.draft = make_wallpaper(
            "Draft piece", category=cls.category, status=Wallpaper.Status.DRAFT
        )

    def detail(self, slug):
        return self.detail_url.format(slug=slug)

    def create(self, slug, **extra):
        return self.client.post(
            self.list_url, {"wallpaper": slug, **extra}, format="json"
        )

    # --- authentication ---------------------------------------------------

    def test_anonymous_access_is_rejected(self):
        # JWT is the first authenticator, so DRF can issue a Bearer challenge.
        self.assertEqual(self.client.get(self.list_url).status_code, 401)
        self.assertEqual(self.create(self.wallpaper.slug).status_code, 401)
        self.assertEqual(
            self.client.get(self.detail(self.wallpaper.slug)).status_code, 401
        )
        self.assertEqual(
            self.client.delete(self.detail(self.wallpaper.slug)).status_code, 401
        )

    # --- creation ---------------------------------------------------------

    def test_create_returns_201_and_the_nested_wallpaper(self):
        self.client.force_authenticate(self.user)

        response = self.create(self.wallpaper.slug)

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["wallpaper"]["slug"], self.wallpaper.slug)
        self.assertIn(self.timestamp_key, response.data)
        self.assertEqual(self.model.objects.filter(user=self.user).count(), 1)

    def test_duplicate_create_is_idempotent(self):
        self.client.force_authenticate(self.user)

        first = self.create(self.wallpaper.slug)
        second = self.create(self.wallpaper.slug)

        self.assertEqual(first.status_code, 201)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(
            self.model.objects.filter(
                user=self.user, wallpaper=self.wallpaper
            ).count(),
            1,
        )

    def test_unpublished_wallpaper_cannot_be_added(self):
        self.client.force_authenticate(self.user)

        response = self.create(self.draft.slug)

        self.assertEqual(response.status_code, 404)
        self.assertFalse(self.model.objects.exists())

    def test_unknown_wallpaper_returns_404(self):
        self.client.force_authenticate(self.user)

        response = self.create("does-not-exist")

        self.assertEqual(response.status_code, 404)

    def test_missing_or_invalid_payload_returns_structured_400(self):
        self.client.force_authenticate(self.user)

        missing = self.client.post(self.list_url, {}, format="json")
        self.assertEqual(missing.status_code, 400)
        self.assertIn("wallpaper", missing.data)

        blank = self.create("")
        self.assertEqual(blank.status_code, 400)
        self.assertIn("wallpaper", blank.data)

    # --- listing ----------------------------------------------------------

    def test_list_returns_only_the_current_users_items(self):
        self.model.objects.create(user=self.user, wallpaper=self.wallpaper)
        self.model.objects.create(user=self.other_user, wallpaper=self.other_wallpaper)
        self.client.force_authenticate(self.user)

        response = self.client.get(self.list_url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(
            response.data["results"][0]["wallpaper"]["slug"], self.wallpaper.slug
        )

    def test_list_is_paginated_and_newest_first(self):
        first = self.model.objects.create(user=self.user, wallpaper=self.wallpaper)
        second = self.model.objects.create(
            user=self.user, wallpaper=self.other_wallpaper
        )
        self.client.force_authenticate(self.user)

        response = self.client.get(self.list_url)

        self.assertIn("count", response.data)
        self.assertEqual(
            [item["wallpaper"]["slug"] for item in response.data["results"]],
            [second.wallpaper.slug, first.wallpaper.slug],
        )

    def test_list_hides_items_for_unpublished_wallpapers(self):
        self.model.objects.create(user=self.user, wallpaper=self.draft)
        self.client.force_authenticate(self.user)

        response = self.client.get(self.list_url)

        self.assertEqual(response.data["count"], 0)

    def test_client_cannot_select_another_users_library(self):
        self.model.objects.create(user=self.other_user, wallpaper=self.wallpaper)
        self.client.force_authenticate(self.user)

        response = self.client.get(f"{self.list_url}?user={self.other_user.pk}")

        self.assertEqual(response.data["count"], 0)

    # --- status -----------------------------------------------------------

    def test_status_is_false_before_and_true_after(self):
        self.client.force_authenticate(self.user)

        before = self.client.get(self.detail(self.wallpaper.slug))
        self.assertEqual(before.status_code, 200)
        self.assertFalse(before.data["exists"])
        self.assertIsNone(before.data[self.timestamp_key])

        self.create(self.wallpaper.slug)
        after = self.client.get(self.detail(self.wallpaper.slug))
        self.assertTrue(after.data["exists"])
        self.assertIsNotNone(after.data[self.timestamp_key])

    def test_status_never_reveals_another_users_item(self):
        self.model.objects.create(user=self.other_user, wallpaper=self.wallpaper)
        self.client.force_authenticate(self.user)

        response = self.client.get(self.detail(self.wallpaper.slug))

        self.assertFalse(response.data["exists"])

    def test_status_for_unpublished_wallpaper_is_404(self):
        self.client.force_authenticate(self.user)

        self.assertEqual(
            self.client.get(self.detail(self.draft.slug)).status_code, 404
        )

    # --- deletion ---------------------------------------------------------

    def test_delete_removes_only_the_current_users_item(self):
        self.model.objects.create(user=self.user, wallpaper=self.wallpaper)
        self.model.objects.create(user=self.other_user, wallpaper=self.wallpaper)
        self.client.force_authenticate(self.user)

        response = self.client.delete(self.detail(self.wallpaper.slug))

        self.assertEqual(response.status_code, 204)
        self.assertTrue(
            self.model.objects.filter(
                user=self.other_user, wallpaper=self.wallpaper
            ).exists()
        )
        self.assertFalse(
            self.model.objects.filter(
                user=self.user, wallpaper=self.wallpaper
            ).exists()
        )

    def test_delete_is_idempotent(self):
        self.client.force_authenticate(self.user)

        self.assertEqual(
            self.client.delete(self.detail(self.wallpaper.slug)).status_code, 204
        )
        self.assertEqual(
            self.client.delete(self.detail(self.wallpaper.slug)).status_code, 204
        )

    def test_delete_cannot_remove_another_users_item(self):
        self.model.objects.create(user=self.other_user, wallpaper=self.wallpaper)
        self.client.force_authenticate(self.user)

        response = self.client.delete(self.detail(self.wallpaper.slug))

        self.assertEqual(response.status_code, 204)
        self.assertTrue(
            self.model.objects.filter(
                user=self.other_user, wallpaper=self.wallpaper
            ).exists()
        )

    def test_delete_for_unpublished_wallpaper_is_404(self):
        self.model.objects.create(user=self.user, wallpaper=self.wallpaper)
        self.client.force_authenticate(self.user)

        self.assertEqual(
            self.client.delete(self.detail(self.draft.slug)).status_code, 404
        )

    # --- input hardening --------------------------------------------------

    def test_client_supplied_user_is_ignored(self):
        self.client.force_authenticate(self.user)

        response = self.create(
            self.wallpaper.slug, user=self.other_user.pk, id=999999
        )

        self.assertEqual(response.status_code, 201)
        self.assertTrue(
            self.model.objects.filter(
                user=self.user, wallpaper=self.wallpaper
            ).exists()
        )
        self.assertFalse(
            self.model.objects.filter(user=self.other_user).exists()
        )


class LikeApiTests(LibraryApiMixin, APITestCase):
    model = Like
    list_url = "/api/v1/library/likes/"
    detail_url = "/api/v1/library/likes/{slug}/"
    timestamp_key = "liked_at"

    def test_two_users_can_like_the_same_wallpaper(self):
        self.client.force_authenticate(self.user)
        self.create(self.wallpaper.slug)
        self.client.force_authenticate(self.other_user)
        self.create(self.wallpaper.slug)

        self.assertEqual(Like.objects.count(), 2)

    def test_duplicate_is_still_blocked_by_the_database_constraint(self):
        Like.objects.create(user=self.user, wallpaper=self.wallpaper)

        from django.db import IntegrityError, transaction

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Like.objects.create(user=self.user, wallpaper=self.wallpaper)


class SavedWallpaperApiTests(LibraryApiMixin, APITestCase):
    model = SavedWallpaper
    list_url = "/api/v1/library/saved/"
    detail_url = "/api/v1/library/saved/{slug}/"
    timestamp_key = "saved_at"

    def test_saving_is_independent_from_liking(self):
        self.client.force_authenticate(self.user)
        self.create(self.wallpaper.slug)

        self.assertEqual(SavedWallpaper.objects.count(), 1)
        self.assertEqual(Like.objects.count(), 0)

    def test_saved_and_liked_collections_are_separate(self):
        Like.objects.create(user=self.user, wallpaper=self.wallpaper)
        self.client.force_authenticate(self.user)

        response = self.client.get(self.list_url)

        self.assertEqual(response.data["count"], 0)
