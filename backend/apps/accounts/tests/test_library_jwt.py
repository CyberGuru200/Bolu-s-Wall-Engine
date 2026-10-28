"""End-to-end JWT authentication against the six library endpoints."""

from rest_framework.test import APITestCase

from apps.api.tests.utils import make_category, make_wallpaper
from apps.library.models import Like, SavedWallpaper

from .utils import ME_URL, api_client_for, make_user

LIKES = "/api/v1/library/likes/"
SAVED = "/api/v1/library/saved/"


def detail(base, slug):
    return f"{base}{slug}/"


class JwtLibraryTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.category = make_category("Auth")
        cls.wallpaper = make_wallpaper("Neon Tokyo", category=cls.category)
        cls.other_wallpaper = make_wallpaper("Quiet Peaks", category=cls.category)
        cls.user = make_user("bolu")
        cls.other = make_user("visitor")

    def test_anonymous_requests_are_rejected_on_every_route(self):
        for url in (
            LIKES,
            detail(LIKES, self.wallpaper.slug),
            SAVED,
            detail(SAVED, self.wallpaper.slug),
        ):
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 401)
                self.assertEqual(
                    self.client.post(
                        url, {"wallpaper": self.wallpaper.slug}, format="json"
                    ).status_code,
                    401,
                )
                self.assertEqual(self.client.delete(url).status_code, 401)

    def test_bearer_token_authenticates_like_crud(self):
        client = api_client_for(self.user)

        created = client.post(LIKES, {"wallpaper": self.wallpaper.slug}, format="json")
        self.assertEqual(created.status_code, 201)
        self.assertTrue(
            Like.objects.filter(user=self.user, wallpaper=self.wallpaper).exists()
        )

        duplicate = client.post(
            LIKES, {"wallpaper": self.wallpaper.slug}, format="json"
        )
        self.assertEqual(duplicate.status_code, 200)

        listed = client.get(LIKES)
        self.assertEqual(listed.data["count"], 1)

        status = client.get(detail(LIKES, self.wallpaper.slug))
        self.assertTrue(status.data["exists"])

        self.assertEqual(
            client.delete(detail(LIKES, self.wallpaper.slug)).status_code, 204
        )
        self.assertFalse(
            Like.objects.filter(user=self.user, wallpaper=self.wallpaper).exists()
        )

    def test_bearer_token_authenticates_saved_crud(self):
        client = api_client_for(self.user)

        created = client.post(SAVED, {"wallpaper": self.wallpaper.slug}, format="json")
        self.assertEqual(created.status_code, 201)
        self.assertTrue(
            SavedWallpaper.objects.filter(
                user=self.user, wallpaper=self.wallpaper
            ).exists()
        )
        self.assertEqual(client.get(SAVED).data["count"], 1)
        self.assertTrue(
            client.get(detail(SAVED, self.wallpaper.slug)).data["exists"]
        )
        self.assertEqual(
            client.delete(detail(SAVED, self.wallpaper.slug)).status_code, 204
        )

    def test_users_are_isolated_from_each_other(self):
        Like.objects.create(user=self.user, wallpaper=self.wallpaper)
        SavedWallpaper.objects.create(user=self.user, wallpaper=self.wallpaper)
        other_client = api_client_for(self.other)

        self.assertEqual(other_client.get(LIKES).data["count"], 0)
        self.assertEqual(other_client.get(SAVED).data["count"], 0)
        self.assertFalse(
            other_client.get(detail(LIKES, self.wallpaper.slug)).data["exists"]
        )
        self.assertFalse(
            other_client.get(detail(SAVED, self.wallpaper.slug)).data["exists"]
        )

        # Deleting through another user's token must not touch the owner's row.
        other_client.delete(detail(LIKES, self.wallpaper.slug))
        other_client.delete(detail(SAVED, self.wallpaper.slug))
        self.assertTrue(
            Like.objects.filter(user=self.user, wallpaper=self.wallpaper).exists()
        )
        self.assertTrue(
            SavedWallpaper.objects.filter(
                user=self.user, wallpaper=self.wallpaper
            ).exists()
        )

    def test_client_supplied_user_ids_are_ignored(self):
        client = api_client_for(self.user)

        created = client.post(
            LIKES,
            {"wallpaper": self.wallpaper.slug, "user": self.other.pk},
            format="json",
        )

        self.assertEqual(created.status_code, 201)
        self.assertTrue(
            Like.objects.filter(user=self.user, wallpaper=self.wallpaper).exists()
        )
        self.assertFalse(Like.objects.filter(user=self.other).exists())

    def test_expired_mode_is_not_required_for_public_catalogue(self):
        self.assertEqual(self.client.get("/api/v1/wallpapers/").status_code, 200)
        self.assertEqual(self.client.get("/api/v1/categories/").status_code, 200)
        self.assertEqual(self.client.get("/api/v1/tags/").status_code, 200)

    def test_jwt_can_read_the_profile_and_library_together(self):
        client = api_client_for(self.user)

        self.assertEqual(client.get(ME_URL).status_code, 200)
        client.post(LIKES, {"wallpaper": self.wallpaper.slug}, format="json")
        self.assertEqual(client.get(ME_URL).data["likes_count"], 1)
        self.assertEqual(client.get(LIKES).data["count"], 1)
