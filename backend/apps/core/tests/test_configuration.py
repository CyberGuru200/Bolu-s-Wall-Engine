import os
from unittest.mock import patch

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.test import SimpleTestCase

from config.env import env, env_bool, env_int, env_list, validate_origins


class EnvironmentHelperTests(SimpleTestCase):
    def test_wildcard_origins_are_rejected(self):
        with self.assertRaises(ImproperlyConfigured):
            validate_origins("TEST_ORIGINS", ("*",))
        with self.assertRaises(ImproperlyConfigured):
            validate_origins("TEST_ORIGINS", ("https://*.example.com",))

    def test_origins_must_be_bare_http_origins(self):
        for value in (
            "example.com",
            "ftp://example.com",
            "https://example.com/path",
            "https://example.com?query=1",
            "https://user:pass@example.com",
        ):
            with self.subTest(value=value):
                with self.assertRaises(ImproperlyConfigured):
                    validate_origins("TEST_ORIGINS", (value,))

    def test_origins_are_normalized_and_deduplicated(self):
        origins = validate_origins(
            "TEST_ORIGINS",
            (
                "HTTP://LOCALHOST:5173/",
                "http://localhost:5173",
                "https://app.example.com",
            ),
        )
        self.assertEqual(
            origins,
            ("http://localhost:5173", "https://app.example.com"),
        )

    def test_boolean_parsing_rejects_ambiguous_values(self):
        with patch.dict(os.environ, {"TEST_FLAG": "yes"}):
            self.assertTrue(env_bool("TEST_FLAG", False))
        with patch.dict(os.environ, {"TEST_FLAG": "Off"}):
            self.assertFalse(env_bool("TEST_FLAG", True))
        with patch.dict(os.environ, {"TEST_FLAG": "sometimes"}):
            with self.assertRaises(ImproperlyConfigured):
                env_bool("TEST_FLAG", False)

    def test_integer_and_list_parsing(self):
        with patch.dict(os.environ, {"TEST_PORT": "3307"}):
            self.assertEqual(env_int("TEST_PORT", 3306), 3307)
        with patch.dict(os.environ, {"TEST_PORT": "not-a-port"}):
            with self.assertRaises(ImproperlyConfigured):
                env_int("TEST_PORT", 3306)
        with patch.dict(
            os.environ, {"TEST_LIST": " a, b ,, c "}, clear=False
        ):
            self.assertEqual(env_list("TEST_LIST"), ("a", "b", "c"))
        # Explicitly empty is empty, not the default.
        with patch.dict(os.environ, {"TEST_LIST": ""}, clear=False):
            self.assertEqual(env_list("TEST_LIST", ("default",)), ())

    def test_required_values_must_not_be_empty(self):
        with patch.dict(os.environ, {"TEST_REQUIRED": ""}, clear=False):
            with self.assertRaises(ImproperlyConfigured):
                env("TEST_REQUIRED", required=True)


class SettingsTests(SimpleTestCase):
    def test_application_settings_use_mysql(self):
        # Inspect the shipped application settings rather than the active
        # module: when no MySQL server exists, tests run through the explicit
        # config.settings.test harness, which must not weaken the real config.
        from config.settings import development

        database = development.DATABASES["default"]
        self.assertEqual(database["ENGINE"], "django.db.backends.mysql")
        self.assertEqual(database["OPTIONS"]["charset"], "utf8mb4")
        self.assertEqual(database["TEST"]["CHARSET"], "utf8mb4")
        self.assertIn("DB_NAME", os.environ)
        self.assertIn("DB_USER", os.environ)

    def test_sqlite_is_only_used_by_an_explicit_test_harness(self):
        using_harness = getattr(settings, "USING_SQLITE_TEST_HARNESS", False)

        if using_harness:
            self.assertEqual(
                settings.DATABASES["default"]["ENGINE"],
                "django.db.backends.sqlite3",
            )
        else:
            self.assertEqual(
                settings.DATABASES["default"]["ENGINE"],
                "django.db.backends.mysql",
            )

    def test_cors_is_explicit_and_credentials_are_off_by_default(self):
        self.assertFalse(settings.CORS_ALLOW_ALL_ORIGINS)
        self.assertFalse(settings.CORS_ALLOW_CREDENTIALS)
        for origin in settings.CORS_ALLOWED_ORIGINS:
            self.assertNotIn("*", origin)
            self.assertRegex(origin, r"^https?://")

    def test_secret_key_comes_from_the_environment(self):
        self.assertTrue(settings.SECRET_KEY)
        self.assertNotEqual(
            settings.SECRET_KEY,
            "replace-with-a-long-random-secret-key",
        )

    def test_rest_framework_defaults_are_configured(self):
        rest = settings.REST_FRAMEWORK
        self.assertIn(
            "rest_framework.authentication.SessionAuthentication",
            rest["DEFAULT_AUTHENTICATION_CLASSES"],
        )
        self.assertEqual(
            rest["DEFAULT_PERMISSION_CLASSES"],
            ("rest_framework.permissions.IsAuthenticatedOrReadOnly",),
        )
        self.assertEqual(rest["PAGE_SIZE"], 24)
