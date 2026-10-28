"""Test-only settings used when no MySQL server is available.

This module exists **only** for running the test suite in an isolated
environment. It is never selected automatically by manage.py, WSGI, or ASGI,
and SQLite is never an application database: the shipped
development/production settings remain MySQL-only.

Use the normal settings when MySQL is available so migrations and constraints
run against the real target database:

    python manage.py test

Use this harness only when MySQL cannot be reached:

    python manage.py test --settings=config.settings.test
"""

import tempfile

from .development import *  # noqa: F401,F403

USING_SQLITE_TEST_HARNESS = True

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}

ALLOWED_HOSTS = ["testserver", "localhost", "127.0.0.1"]

# Fast, non-secret hashing for test users only.
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]

# allauth throttles repeated login attempts per IP/username. The suite performs
# many real logins from the same test client address, so the limits are turned
# off here only; development and production keep allauth's defaults.
ACCOUNT_RATE_LIMITS = False

# Uploaded test files go to a temporary directory, never into the repository.
MEDIA_ROOT = tempfile.mkdtemp(prefix="bwe-test-media-")
