"""Environment parsing helpers shared by all settings modules.

Values are read from the process environment. A local backend/.env file is
loaded before settings are evaluated by manage.py, wsgi.py, asgi.py, and
config/settings/base.py; real environment variables always win.
"""

import os
from urllib.parse import urlsplit

from django.core.exceptions import ImproperlyConfigured

TRUE_VALUES = {"1", "true", "yes", "on"}
FALSE_VALUES = {"0", "false", "no", "off"}


def env(name, default=None, *, required=False, strip=True):
    """Return a string setting, optionally requiring it to be present."""
    raw = os.environ.get(name)
    if raw is None:
        if required:
            raise ImproperlyConfigured(
                f"{name} is required. Copy backend/.env.example to backend/.env "
                "and set a non-empty value."
            )
        return default
    value = raw.strip() if strip else raw
    if required and not value:
        raise ImproperlyConfigured(
            f"{name} must not be empty. Set it in backend/.env or the process "
            "environment."
        )
    return value


def env_bool(name, default=False):
    """Parse common truthy/falsy strings, rejecting ambiguous values."""
    raw = os.environ.get(name)
    if raw is None or not raw.strip():
        return default
    value = raw.strip().lower()
    if value in TRUE_VALUES:
        return True
    if value in FALSE_VALUES:
        return False
    raise ImproperlyConfigured(
        f"{name} must be one of: true, false, 1, 0, yes, no, on, off."
    )


def env_int(name, default):
    raw = os.environ.get(name)
    if raw is None or not raw.strip():
        return default
    try:
        return int(raw)
    except ValueError as exc:
        raise ImproperlyConfigured(f"{name} must be an integer.") from exc


def env_list(name, default=()):
    """Parse a comma-separated list.

    An unset variable uses ``default``. An explicitly empty variable means an
    empty list, so CORS can be deliberately disabled.
    """
    raw = os.environ.get(name)
    if raw is None:
        return tuple(default)
    return tuple(item.strip() for item in raw.split(",") if item.strip())


def validate_origins(name, origins):
    """Validate explicit browser origins used by CORS and CSRF settings.

    Wildcards are intentionally rejected: credentials must never be allowed
    for an arbitrary origin. Each value must be a bare http(s) origin with no
    path, query, fragment, or embedded credentials.
    """
    validated = []
    for origin in origins:
        if not origin or "*" in origin:
            raise ImproperlyConfigured(
                f"{name} must contain explicit origins; wildcards are not allowed."
            )
        parts = urlsplit(origin)
        if (
            parts.scheme not in {"http", "https"}
            or not parts.netloc
            or parts.path not in {"", "/"}
            or parts.query
            or parts.fragment
            or parts.username
            or parts.password
        ):
            raise ImproperlyConfigured(
                f"{name} contains an invalid origin. Use a bare value such as "
                "http://localhost:5173 (no path, query, fragment, or credentials)."
            )
        normalized = f"{parts.scheme.lower()}://{parts.netloc.lower()}"
        if normalized not in validated:
            validated.append(normalized)
    return tuple(validated)
