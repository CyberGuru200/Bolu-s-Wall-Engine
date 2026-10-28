"""The authenticated profile endpoint."""

from allauth.socialaccount.models import SocialAccount
from django.test import TestCase

from apps.api.tests.utils import make_category, make_wallpaper
from apps.library.models import Like, SavedWallpaper

from .utils import ME_URL, api_client_for, bearer, login, make_user


class MeEndpointTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = make_user(
            "bolu",
            email="bolu@example.com",
            first_name="Bolu",
            last_name="Adeyemi",
        )
        cls.other = make_user("visitor", email="visitor@example.com")
        category = make_category("Anime")
        cls.wallpaper = make_wallpaper("Neon Tokyo", category=category)
        cls.other_wallpaper = make_wallpaper("Quiet Peaks", category=category)
        Like.objects.create(user=cls.user, wallpaper=cls.wallpaper)
        SavedWallpaper.objects.create(user=cls.user, wallpaper=cls.wallpaper)
        Like.objects.create(user=cls.other, wallpaper=cls.other_wallpaper)
        SocialAccount.objects.create(
            user=cls.user,
            provider="google",
            uid="google-sub-1",
            extra_data={},
        )

    def test_anonymous_profile_request_is_rejected(self):
        response = self.client.get(ME_URL)

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response["WWW-Authenticate"], "Bearer")

    def test_profile_is_returned_for_the_token_owner(self):
        client = api_client_for(self.user)

        response = client.get(ME_URL)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["username"], "bolu")
        self.assertEqual(response.data["email"], "bolu@example.com")
        self.assertEqual(response.data["display_name"], "Bolu Adeyemi")
        self.assertTrue(response.data["has_usable_password"])
        self.assertEqual(response.data["likes_count"], 1)
        self.assertEqual(response.data["saved_count"], 1)
        self.assertEqual(response.data["providers"], ["google"])

    def test_profile_exposes_only_safe_fields(self):
        client = api_client_for(self.user)

        response = client.get(ME_URL)

        self.assertEqual(
            set(response.data),
            {
                "id",
                "username",
                "email",
                "display_name",
                "date_joined",
                "has_usable_password",
                "likes_count",
                "saved_count",
                "providers",
            },
        )
        body = response.content.decode()
        for forbidden in (
            "is_superuser",
            "is_staff",
            "last_login",
            "user_permissions",
            "access_token",
            "refresh_token",
            "session_token",
            "eyJ",  # no JWT material in the profile payload
        ):
            self.assertNotIn(forbidden, body)
        self.assertNotIn('"password"', body)
        self.assertNotIn('"groups"', body)

    def test_each_token_sees_only_its_own_profile(self):
        response = api_client_for(self.other).get(ME_URL)

        self.assertEqual(response.data["username"], "visitor")
        self.assertEqual(response.data["likes_count"], 1)
        self.assertEqual(response.data["saved_count"], 0)
        self.assertEqual(response.data["providers"], [])

    def test_client_supplied_user_identifiers_are_ignored(self):
        client = api_client_for(self.user)

        response = client.get(ME_URL, {"user": self.other.pk, "id": self.other.pk})

        self.assertEqual(response.data["id"], self.user.pk)
        self.assertEqual(response.data["username"], "bolu")

    def test_password_login_still_exposes_the_profile(self):
        tokens = login(self.client).json()["meta"]

        response = self.client.get(ME_URL, **bearer(tokens["access_token"]))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["id"], self.user.pk)

    def test_me_is_read_only(self):
        client = api_client_for(self.user)

        for method in ("post", "put", "patch", "delete"):
            with self.subTest(method=method):
                response = getattr(client, method)(ME_URL)
                self.assertEqual(response.status_code, 405)
