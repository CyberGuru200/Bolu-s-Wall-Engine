"""Production settings.

Refuses to start with DEBUG enabled, a weak secret, a wildcard host, or no
MySQL password. TLS-related defaults can only be loosened deliberately.
"""

import os

from django.core.exceptions import ImproperlyConfigured

from config.env import env_bool, env_int

from .base import *  # noqa: F401,F403

DEBUG = env_bool("DJANGO_DEBUG", False)
if DEBUG:
    raise ImproperlyConfigured(
        "DJANGO_DEBUG must be false when using config.settings.production."
    )
if len(SECRET_KEY) < 50:  # noqa: F405
    raise ImproperlyConfigured(
        "DJANGO_SECRET_KEY must be at least 50 characters in production."
    )
if not ALLOWED_HOSTS or "*" in ALLOWED_HOSTS:  # noqa: F405
    raise ImproperlyConfigured(
        "DJANGO_ALLOWED_HOSTS must list explicit production hostnames."
    )
if not os.environ.get("DB_PASSWORD"):
    raise ImproperlyConfigured(
        "DB_PASSWORD is required in production; empty MySQL passwords are not allowed."
    )

if not CSRF_TRUSTED_ORIGINS:  # noqa: F405
    CSRF_TRUSTED_ORIGINS = CORS_ALLOWED_ORIGINS  # noqa: F405

# HTTPS and cookie hardening. Terminate TLS at the proxy and forward HTTPS,
# or set DJANGO_SECURE_SSL_REDIRECT=False only for a documented staging case.
SECURE_SSL_REDIRECT = env_bool("DJANGO_SECURE_SSL_REDIRECT", True)
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = env_int("DJANGO_SECURE_HSTS_SECONDS", 31536000)
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True

# Only enable this behind a proxy that overwrites X-Forwarded-Proto.
if env_bool("DJANGO_TRUST_X_FORWARDED_PROTO", False):
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
