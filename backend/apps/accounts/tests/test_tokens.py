"""Token acquisition, validation, refresh, and logout behaviour."""

import jwt
from django.conf import settings
from django.test import TestCase

from .utils import HEADLESS, ME_URL, bearer, login, make_user, post_json, tokens_for


class LoginTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = make_user("bolu", email="bolu@example.com")

    def test_login_returns_access_refresh_and_session_tokens(self):
        response = login(self.client)

        self.assertEqual(response.status_code, 200)
        meta = response.json()["meta"]
        self.assertTrue(meta["is_authenticated"])
        for key in ("access_token", "refresh_token", "session_token"):
            self.assertTrue(meta[key])

    def test_access_token_has_the_expected_claims(self):
        meta = tokens_for(self.client)

        payload = jwt.decode(
            meta["access_token"],
            settings.SECRET_KEY,
            algorithms=["HS256"],
        )

        self.assertEqual(payload["token_use"], "access")
        self.assertEqual(payload["sub"], str(self.user.pk))
        self.assertEqual(
            payload["exp"] - payload["iat"],
            settings.HEADLESS_JWT_ACCESS_TOKEN_EXPIRES_IN,
        )

    def test_refresh_token_is_not_accepted_as_an_access_token(self):
        meta = tokens_for(self.client)

        response = self.client.get(ME_URL, **bearer(meta["refresh_token"]))

        self.assertEqual(response.status_code, 401)

    def test_wrong_password_is_rejected_without_tokens(self):
        response = post_json(
            self.client,
            f"{HEADLESS}/auth/login",
            {"username": "bolu", "password": "wrong"},
        )

        self.assertEqual(response.status_code, 400)
        self.assertNotIn("access_token", response.content.decode())


class AccessTokenTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = make_user("bolu")
        cls.other = make_user("visitor")

    def setUp(self):
        self.tokens = tokens_for(self.client)

    def test_valid_token_authenticates_the_profile_endpoint(self):
        response = self.client.get(ME_URL, **bearer(self.tokens["access_token"]))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["username"], "bolu")

    def test_anonymous_request_is_rejected(self):
        response = self.client.get(ME_URL)

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response["WWW-Authenticate"], "Bearer")

    def test_malformed_token_is_rejected(self):
        for value in ("not-a-jwt", "abc.def.ghi", ""):
            with self.subTest(value=value):
                response = self.client.get(ME_URL, **bearer(value))
                self.assertEqual(response.status_code, 401)

    def test_non_bearer_scheme_is_rejected(self):
        response = self.client.get(
            ME_URL, HTTP_AUTHORIZATION=f"Basic {self.tokens['access_token']}"
        )

        self.assertEqual(response.status_code, 401)

    def test_token_signed_with_another_key_is_rejected(self):
        payload = jwt.decode(
            self.tokens["access_token"],
            settings.SECRET_KEY,
            algorithms=["HS256"],
        )
        forged = jwt.encode(
            payload, "attacker-secret-that-is-long-enough-0123456789", algorithm="HS256"
        )

        response = self.client.get(ME_URL, **bearer(forged))

        self.assertEqual(response.status_code, 401)

    def test_expired_token_is_rejected(self):
        payload = jwt.decode(
            self.tokens["access_token"],
            settings.SECRET_KEY,
            algorithms=["HS256"],
        )
        payload["exp"] = payload["iat"] - 1
        payload["iat"] = payload["iat"] - 2
        expired = jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")

        response = self.client.get(ME_URL, **bearer(expired))

        self.assertEqual(response.status_code, 401)

    def test_token_for_another_user_cannot_reuse_a_valid_session(self):
        # Same signed session id, different ``sub``: stateful validation must
        # compare the subject against the session owner.
        payload = jwt.decode(
            self.tokens["access_token"],
            settings.SECRET_KEY,
            algorithms=["HS256"],
        )
        payload["sub"] = str(self.other.pk)
        forged = jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")

        response = self.client.get(ME_URL, **bearer(forged))

        self.assertEqual(response.status_code, 401)

    def test_token_without_a_session_id_is_rejected(self):
        payload = jwt.decode(
            self.tokens["access_token"],
            settings.SECRET_KEY,
            algorithms=["HS256"],
        )
        payload.pop("sid")
        forged = jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")

        response = self.client.get(ME_URL, **bearer(forged))

        self.assertEqual(response.status_code, 401)

    def test_inactive_user_token_is_rejected(self):
        self.user.is_active = False
        self.user.save(update_fields=["is_active"])

        response = self.client.get(ME_URL, **bearer(self.tokens["access_token"]))

        self.assertEqual(response.status_code, 401)


class RefreshTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = make_user("bolu")

    def setUp(self):
        self.tokens = tokens_for(self.client)

    def refresh(self, token):
        return post_json(
            self.client,
            f"{HEADLESS}/tokens/refresh",
            {"refresh_token": token},
        )

    def test_refresh_returns_a_new_access_token(self):
        response = self.refresh(self.tokens["refresh_token"])

        self.assertEqual(response.status_code, 200)
        data = response.json()["data"]
        self.assertNotEqual(data["access_token"], self.tokens["access_token"])
        profile = self.client.get(ME_URL, **bearer(data["access_token"]))
        self.assertEqual(profile.status_code, 200)

    def test_rotation_replaces_the_refresh_token(self):
        response = self.refresh(self.tokens["refresh_token"])

        self.assertEqual(response.status_code, 200)
        rotated = response.json()["data"]["refresh_token"]
        self.assertNotEqual(rotated, self.tokens["refresh_token"])
        self.assertEqual(self.refresh(rotated).status_code, 200)

    def test_rotated_refresh_token_cannot_be_reused(self):
        response = self.refresh(self.tokens["refresh_token"])
        self.assertEqual(response.status_code, 200)

        replay = self.refresh(self.tokens["refresh_token"])

        self.assertEqual(replay.status_code, 400)

    def test_invalid_refresh_token_is_rejected(self):
        self.assertEqual(self.refresh("not-a-token").status_code, 400)

    def test_refresh_token_lifetime_matches_settings(self):
        payload = jwt.decode(
            self.tokens["refresh_token"],
            settings.SECRET_KEY,
            algorithms=["HS256"],
        )

        self.assertEqual(payload["token_use"], "refresh")
        self.assertEqual(
            payload["exp"] - payload["iat"],
            settings.HEADLESS_JWT_REFRESH_TOKEN_EXPIRES_IN,
        )


class LogoutTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = make_user("bolu")

    def setUp(self):
        self.tokens = tokens_for(self.client)

    def logout(self):
        return self.client.delete(
            f"{HEADLESS}/auth/session",
            HTTP_X_SESSION_TOKEN=self.tokens["session_token"],
        )

    def test_logout_invalidates_the_access_token(self):
        self.assertEqual(
            self.client.get(ME_URL, **bearer(self.tokens["access_token"])).status_code,
            200,
        )

        # allauth Headless returns an unauthenticated envelope (401) for the
        # session it just destroyed; the important part is the effect below.
        self.assertEqual(self.logout().status_code, 401)

        response = self.client.get(ME_URL, **bearer(self.tokens["access_token"]))
        self.assertEqual(response.status_code, 401)

    def test_logout_invalidates_the_refresh_token(self):
        self.logout()

        response = post_json(
            self.client,
            f"{HEADLESS}/tokens/refresh",
            {"refresh_token": self.tokens["refresh_token"]},
        )

        self.assertEqual(response.status_code, 400)

    def test_logout_cannot_be_replayed_as_a_valid_session(self):
        self.logout()

        response = self.client.delete(
            f"{HEADLESS}/auth/session",
            HTTP_X_SESSION_TOKEN=self.tokens["session_token"],
        )

        # 410 Gone: the session token no longer resolves to a session.
        self.assertEqual(response.status_code, 410)

    def test_public_catalogue_survives_logout(self):
        self.logout()

        self.assertEqual(self.client.get("/api/v1/wallpapers/").status_code, 200)
