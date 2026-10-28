"""Local development settings.

Selected by manage.py when DJANGO_SETTINGS_MODULE is not already set.
"""

from config.env import env_bool, env_list, validate_origins

from .base import *  # noqa: F401,F403

DEBUG = env_bool("DJANGO_DEBUG", True)

ALLOWED_HOSTS = list(
    env_list("DJANGO_ALLOWED_HOSTS", ("localhost", "127.0.0.1"))
) or ["localhost", "127.0.0.1"]

CORS_ALLOWED_ORIGINS = validate_origins(
    "CORS_ALLOWED_ORIGINS",
    env_list(
        "CORS_ALLOWED_ORIGINS",
        ("http://localhost:5173", "http://127.0.0.1:5173"),
    ),
)
CSRF_TRUSTED_ORIGINS = validate_origins(
    "CSRF_TRUSTED_ORIGINS",
    env_list("CSRF_TRUSTED_ORIGINS", CORS_ALLOWED_ORIGINS),
)

REST_FRAMEWORK = {
    **REST_FRAMEWORK,  # noqa: F405
    "DEFAULT_RENDERER_CLASSES": (
        "rest_framework.renderers.JSONRenderer",
        "rest_framework.renderers.BrowsableAPIRenderer",
    ),
}
