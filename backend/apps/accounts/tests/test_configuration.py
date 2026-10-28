"""Configuration and URL-level assertions for the Phase 4 auth stack."""

from django.conf import settings
from django.test import SimpleTestCase, TestCase
from django.urls import resolve, reverse

from apps.accounts.adapters import AccountAdapter, SocialAccountAdapter


class AuthenticationConfigurationTests(SimpleTestCase):
    def test_allauth_backends_are_installed(self):
        self.assertEqual(
            settings.AUTHENTICATION_BACKENDS,
            [
                "django.contrib.auth.backends.ModelBackend",
                "allauth.account.auth_backends.AuthenticationBackend",
            ],
        )

    def test_headless_only_mode_is_enabled(self):
        self.assertTrue(settings.HEADLESS_ONLY)
        self.assertEqual(settings.HEADLESS_CLIENTS, ("app",))
        self.assertIn(
            "socialaccount_login_error", settings.HEADLESS_FRONTEND_URLS
        )

    def test_jwt_token_strategy_is_allauths(self):
        # No custom JWT code: allauth Headless issues and validates the tokens.
        self.assertEqual(
            settings.HEADLESS_TOKEN_STRATEGY,
            "allauth.headless.tokens.strategies.jwt.JWTTokenStrategy",
        )
        self.assertEqual(settings.HEADLESS_JWT_AUTHORIZATION_HEADER_SCHEME, "Bearer")
        self.assertTrue(settings.HEADLESS_JWT_ROTATE_REFRESH_TOKEN)
        self.assertTrue(settings.HEADLESS_JWT_STATEFUL_VALIDATION_ENABLED)
        self.assertEqual(settings.HEADLESS_JWT_ALGORITHM, "HS256")

    def test_token_lifetimes_are_configured(self):
        self.assertEqual(settings.HEADLESS_JWT_ACCESS_TOKEN_EXPIRES_IN, 15 * 60)
        self.assertEqual(
            settings.HEADLESS_JWT_REFRESH_TOKEN_EXPIRES_IN, 7 * 24 * 60 * 60
        )
        self.assertGreater(
            settings.HEADLESS_JWT_REFRESH_TOKEN_EXPIRES_IN,
            settings.HEADLESS_JWT_ACCESS_TOKEN_EXPIRES_IN,
        )

    def test_session_outlives_the_refresh_token(self):
        self.assertGreaterEqual(
            settings.SESSION_COOKIE_AGE,
            settings.HEADLESS_JWT_REFRESH_TOKEN_EXPIRES_IN + 24 * 60 * 60,
        )

    def test_drf_uses_allauth_jwt_then_session_authentication(self):
        self.assertEqual(
            settings.REST_FRAMEWORK["DEFAULT_AUTHENTICATION_CLASSES"],
            (
                "allauth.headless.contrib.rest_framework.authentication."
                "JWTTokenAuthentication",
                "rest_framework.authentication.SessionAuthentication",
            ),
        )

    def test_password_signup_is_closed_but_social_signup_is_open(self):
        self.assertFalse(settings.ACCOUNT_ALLOW_PASSWORD_SIGNUP)
        self.assertFalse(AccountAdapter().is_open_for_signup(None))
        self.assertTrue(SocialAccountAdapter().is_open_for_signup(None, None))

    def test_login_is_by_username(self):
        self.assertEqual(settings.ACCOUNT_LOGIN_METHODS, {"username"})

    def test_google_signup_never_auto_connects_an_existing_account(self):
        self.assertTrue(settings.SOCIALACCOUNT_AUTO_SIGNUP)
        self.assertFalse(settings.SOCIALACCOUNT_EMAIL_AUTHENTICATION)
        self.assertFalse(settings.SOCIALACCOUNT_EMAIL_AUTHENTICATION_AUTO_CONNECT)
        self.assertTrue(settings.ACCOUNT_UNIQUE_EMAIL)

    def test_google_credentials_are_not_configured_without_environment(self):
        # Tests never provide GOOGLE_OAUTH_CLIENT_ID, so Google is simply
        # unavailable instead of being faked with placeholder credentials.
        self.assertEqual(settings.SOCIALACCOUNT_PROVIDERS, {})

    def test_cors_is_an_explicit_allowlist_without_credentials(self):
        self.assertFalse(settings.CORS_ALLOW_ALL_ORIGINS)
        self.assertNotIn("*", settings.CORS_ALLOWED_ORIGINS)
        self.assertFalse(settings.CORS_ALLOW_CREDENTIALS)
        self.assertIn("x-session-token", settings.CORS_ALLOW_HEADERS)
        self.assertIn("authorization", settings.CORS_ALLOW_HEADERS)

    def test_site_id_is_present_for_social_apps(self):
        self.assertEqual(settings.SITE_ID, 1)


class AuthUrlTests(TestCase):
    def test_me_route_is_reversible(self):
        self.assertEqual(reverse("api:me"), "/api/v1/auth/me/")
        self.assertEqual(resolve("/api/v1/auth/me/").url_name, "me")

    def test_headless_config_endpoint_is_served(self):
        response = self.client.get("/_allauth/app/v1/config")

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["status"], 200)
        self.assertIn("account", body["data"])
        self.assertIn("socialaccount", body["data"])

    def test_headless_config_reports_closed_password_signup(self):
        body = self.client.get("/_allauth/app/v1/config").json()

        self.assertFalse(body["data"]["account"]["is_open_for_signup"])
        self.assertEqual(body["data"]["account"]["login_methods"], ["username"])

    def test_classic_allauth_pages_are_not_served(self):
        for path in (
            "/accounts/login/",
            "/accounts/signup/",
            "/accounts/password/reset/",
        ):
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path).status_code, 404)

    def test_google_login_view_is_disabled_in_headless_only_mode(self):
        # The URL exists so the OAuth callback can be mounted, but the
        # interactive login view is disabled by HEADLESS_ONLY.
        self.assertEqual(self.client.get("/accounts/google/login/").status_code, 404)

    def test_google_callback_route_is_mounted(self):
        self.assertEqual(
            resolve("/accounts/google/login/callback/").url_name,
            "google_callback",
        )
