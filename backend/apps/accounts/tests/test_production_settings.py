"""Production settings must fail closed and must not rely on secrets in code.

Each case imports ``config.settings.production`` in a subprocess because it
validates the environment at import time.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase

BASE_DIR = Path(settings.BASE_DIR)

SUCCESS_SCRIPT = """
import json
import django

django.setup()
from django.conf import settings

print(json.dumps({
    "DEBUG": settings.DEBUG,
    "ALLOWED_HOSTS": settings.ALLOWED_HOSTS,
    "SECURE_SSL_REDIRECT": settings.SECURE_SSL_REDIRECT,
    "SESSION_COOKIE_SECURE": settings.SESSION_COOKIE_SECURE,
    "CSRF_COOKIE_SECURE": settings.CSRF_COOKIE_SECURE,
    "SECURE_HSTS_SECONDS": settings.SECURE_HSTS_SECONDS,
    "CORS_ALLOW_ALL_ORIGINS": settings.CORS_ALLOW_ALL_ORIGINS,
    "CORS_ALLOWED_ORIGINS": list(settings.CORS_ALLOWED_ORIGINS),
    "CORS_ALLOW_CREDENTIALS": settings.CORS_ALLOW_CREDENTIALS,
    "SOCIALACCOUNT_PROVIDERS": settings.SOCIALACCOUNT_PROVIDERS,
    "HEADLESS_TOKEN_STRATEGY": settings.HEADLESS_TOKEN_STRATEGY,
    "HEADLESS_ONLY": settings.HEADLESS_ONLY,
    "ACCOUNT_ALLOW_PASSWORD_SIGNUP": settings.ACCOUNT_ALLOW_PASSWORD_SIGNUP,
    "SECRET_KEY_LENGTH": len(settings.SECRET_KEY),
}))
"""


def production_env(**overrides):
    env = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith(
            ("DJANGO_", "DB_", "CORS_", "CSRF_", "GOOGLE_OAUTH_", "AUTH_")
        )
    }
    env.update(
        {
            "DJANGO_SETTINGS_MODULE": "config.settings.production",
            "DJANGO_SECRET_KEY": "s" * 64,
            "DJANGO_ALLOWED_HOSTS": "api.example.com",
            "DB_NAME": "bolu_wall_engine",
            "DB_USER": "bolu_app",
            "DB_PASSWORD": "production-password",
            "CORS_ALLOWED_ORIGINS": "https://app.example.com",
            "CSRF_TRUSTED_ORIGINS": "https://app.example.com",
            "PYTHONPATH": str(BASE_DIR),
        }
    )
    env.update(overrides)
    return env


def run_production(script=SUCCESS_SCRIPT, **overrides):
    return subprocess.run(
        [sys.executable, "-c", script],
        cwd=BASE_DIR,
        env=production_env(**overrides),
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )


class ProductionSettingsTests(SimpleTestCase):
    def test_production_imports_with_hardened_defaults(self):
        result = run_production()

        self.assertEqual(result.returncode, 0, result.stderr)
        data = json.loads(result.stdout)

        self.assertFalse(data["DEBUG"])
        self.assertEqual(data["ALLOWED_HOSTS"], ["api.example.com"])
        self.assertTrue(data["SECURE_SSL_REDIRECT"])
        self.assertTrue(data["SESSION_COOKIE_SECURE"])
        self.assertTrue(data["CSRF_COOKIE_SECURE"])
        self.assertEqual(data["SECURE_HSTS_SECONDS"], 31536000)
        self.assertFalse(data["CORS_ALLOW_ALL_ORIGINS"])
        self.assertEqual(data["CORS_ALLOWED_ORIGINS"], ["https://app.example.com"])
        self.assertFalse(data["CORS_ALLOW_CREDENTIALS"])
        self.assertGreaterEqual(data["SECRET_KEY_LENGTH"], 50)

    def test_production_keeps_the_allauth_jwt_stack(self):
        result = run_production()

        self.assertEqual(result.returncode, 0, result.stderr)
        data = json.loads(result.stdout)
        self.assertTrue(data["HEADLESS_ONLY"])
        self.assertEqual(
            data["HEADLESS_TOKEN_STRATEGY"],
            "allauth.headless.tokens.strategies.jwt.JWTTokenStrategy",
        )
        self.assertFalse(data["ACCOUNT_ALLOW_PASSWORD_SIGNUP"])
        self.assertEqual(data["SOCIALACCOUNT_PROVIDERS"], {})

    def test_production_refuses_debug(self):
        result = run_production(DJANGO_DEBUG="true")

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("DJANGO_DEBUG must be false", result.stderr)

    def test_production_refuses_a_weak_secret(self):
        result = run_production(DJANGO_SECRET_KEY="short")

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("at least 50 characters", result.stderr)

    def test_production_refuses_wildcard_hosts(self):
        result = run_production(DJANGO_ALLOWED_HOSTS="*")

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("explicit production hostnames", result.stderr)

    def test_production_refuses_an_empty_database_password(self):
        result = run_production(DB_PASSWORD="")

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("DB_PASSWORD is required", result.stderr)

    def test_production_refuses_a_half_configured_google_client(self):
        result = run_production(GOOGLE_OAUTH_CLIENT_ID="client-only")

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Set both GOOGLE_OAUTH_CLIENT_ID", result.stderr)

    def test_production_rejects_wildcard_cors_origins(self):
        result = run_production(CORS_ALLOWED_ORIGINS="https://*.example.com")

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("wildcards are not allowed", result.stderr)
