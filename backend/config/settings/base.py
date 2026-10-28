"""Shared Django settings for every environment.

Environment-specific values live in development.py and production.py.
Nothing in this file should contain real credentials.
"""

import os
from pathlib import Path

from corsheaders.defaults import default_headers
from django.core.exceptions import ImproperlyConfigured
from dotenv import load_dotenv

from config.env import env, env_bool, env_int, env_list, validate_origins

BASE_DIR = Path(__file__).resolve().parents[2]
load_dotenv(BASE_DIR / ".env")

SECRET_KEY = env("DJANGO_SECRET_KEY", required=True)
SECRET_KEY_FALLBACKS = list(env_list("DJANGO_SECRET_KEY_FALLBACKS"))

# Defaults are deliberately safe; development.py opts into DEBUG explicitly.
DEBUG = False
ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.sites",
    # django-allauth: headless JSON API only (no server-rendered account pages).
    "allauth",
    "allauth.account",
    "allauth.socialaccount",
    "allauth.socialaccount.providers.google",
    "allauth.headless",
    "rest_framework",
    "corsheaders",
    "apps.core",
    "apps.wallpapers",
    "apps.catalog",
    "apps.library",
    "apps.accounts",
    "apps.api",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    # Required by django-allauth for account/social login state.
    "allauth.account.middleware.AccountMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

# MySQL is the application database. Environment variables only; no defaults
# for the database name or user. DB_PASSWORD may be empty only for local
# development, which production.py rejects.
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.mysql",
        "NAME": env("DB_NAME", required=True),
        "USER": env("DB_USER", required=True),
        "PASSWORD": os.environ.get("DB_PASSWORD", ""),
        "HOST": env("DB_HOST", "127.0.0.1"),
        "PORT": env("DB_PORT", "3306"),
        "CONN_MAX_AGE": env_int("DB_CONN_MAX_AGE", 60),
        "OPTIONS": {
            "charset": "utf8mb4",
            "connect_timeout": env_int("DB_CONNECT_TIMEOUT", 10),
            "init_command": "SET sql_mode='STRICT_TRANS_TABLES'",
        },
        "TEST": {
            "CHARSET": "utf8mb4",
            "COLLATION": "utf8mb4_unicode_ci",
        },
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": (
            "django.contrib.auth.password_validation."
            "UserAttributeSimilarityValidator"
        )
    },
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = env("DJANGO_TIME_ZONE", "UTC")
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

# Uploaded wallpaper and category images are stored on disk (or later, an
# object-storage backend). MySQL stores only the relative path. Django serves
# these files during development through config/urls.py; production must serve
# MEDIA_ROOT separately.
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

# Upload limits are enforced by model validators and can be tuned per
# environment. Values are bytes.
WALLPAPER_IMAGE_MAX_BYTES = env_int("WALLPAPER_IMAGE_MAX_BYTES", 15 * 1024 * 1024)
WALLPAPER_THUMBNAIL_MAX_BYTES = env_int(
    "WALLPAPER_THUMBNAIL_MAX_BYTES", 5 * 1024 * 1024
)
CATEGORY_IMAGE_MAX_BYTES = env_int("CATEGORY_IMAGE_MAX_BYTES", 5 * 1024 * 1024)

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# --- Authentication ------------------------------------------------------
# django-allauth supplies the account/social plumbing and its Headless app
# exposes a JSON API. Its built-in JWT token strategy issues and validates the
# access/refresh tokens used by the React frontend, so no separate JWT package
# or hand-written token code is involved.
AUTHENTICATION_BACKENDS = [
    "django.contrib.auth.backends.ModelBackend",
    "allauth.account.auth_backends.AuthenticationBackend",
]

SITE_ID = env_int("DJANGO_SITE_ID", 1)

ACCOUNT_ADAPTER = "apps.accounts.adapters.AccountAdapter"
SOCIALACCOUNT_ADAPTER = "apps.accounts.adapters.SocialAccountAdapter"
# Public password signup is closed by default. Google is the self-service
# signup path; staff accounts are created with `createsuperuser`.
ACCOUNT_ALLOW_PASSWORD_SIGNUP = env_bool("AUTH_ALLOW_PASSWORD_SIGNUP", False)
ACCOUNT_LOGIN_METHODS = {"username"}
ACCOUNT_SIGNUP_FIELDS = ["email*", "username*", "password1*", "password2*"]
ACCOUNT_EMAIL_VERIFICATION = "optional"
ACCOUNT_UNIQUE_EMAIL = True

# Headless-only: no allauth HTML pages. `allauth.urls` is still mounted so the
# OAuth provider callback routes exist.
HEADLESS_ONLY = True
HEADLESS_CLIENTS = ("app",)
# In headless-only mode allauth refuses to guess where to send a browser after
# an OAuth error. "/" is a safe same-origin fallback; point this at the SPA's
# login error route when the frontend is integrated.
HEADLESS_FRONTEND_URLS = {
    "socialaccount_login_error": env("FRONTEND_AUTH_ERROR_URL", "/"),
}
HEADLESS_TOKEN_STRATEGY = (
    "allauth.headless.tokens.strategies.jwt.JWTTokenStrategy"
)
HEADLESS_JWT_AUTHORIZATION_HEADER_SCHEME = "Bearer"
HEADLESS_JWT_ROTATE_REFRESH_TOKEN = True
# Validating access tokens against their Django session makes logout and
# session expiry effective immediately. The cost is one session lookup per
# authenticated request.
HEADLESS_JWT_STATEFUL_VALIDATION_ENABLED = env_bool(
    "AUTH_JWT_STATEFUL_VALIDATION", True
)

AUTH_JWT_ALGORITHM = env("AUTH_JWT_ALGORITHM", "HS256").upper()
if AUTH_JWT_ALGORITHM not in {
    "HS256",
    "HS384",
    "HS512",
    "RS256",
    "RS384",
    "RS512",
}:
    raise ImproperlyConfigured(
        "AUTH_JWT_ALGORITHM must be HS256, HS384, HS512, RS256, RS384, or RS512."
    )
# PEM data for RS*. Newlines may be written as literal \n in .env.
AUTH_JWT_PRIVATE_KEY = env("AUTH_JWT_PRIVATE_KEY", "").replace("\\n", "\n")
if AUTH_JWT_ALGORITHM.startswith("RS") and not AUTH_JWT_PRIVATE_KEY:
    raise ImproperlyConfigured(
        "AUTH_JWT_PRIVATE_KEY (PEM) is required when AUTH_JWT_ALGORITHM is RS*."
    )
HEADLESS_JWT_ALGORITHM = AUTH_JWT_ALGORITHM
HEADLESS_JWT_PRIVATE_KEY = AUTH_JWT_PRIVATE_KEY

HEADLESS_JWT_ACCESS_TOKEN_EXPIRES_IN = env_int(
    "AUTH_ACCESS_TOKEN_LIFETIME_SECONDS", 15 * 60
)
HEADLESS_JWT_REFRESH_TOKEN_EXPIRES_IN = env_int(
    "AUTH_REFRESH_TOKEN_LIFETIME_SECONDS", 7 * 24 * 60 * 60
)
if HEADLESS_JWT_ACCESS_TOKEN_EXPIRES_IN <= 0:
    raise ImproperlyConfigured(
        "AUTH_ACCESS_TOKEN_LIFETIME_SECONDS must be greater than zero."
    )
if (
    HEADLESS_JWT_REFRESH_TOKEN_EXPIRES_IN
    < HEADLESS_JWT_ACCESS_TOKEN_EXPIRES_IN
):
    raise ImproperlyConfigured(
        "AUTH_REFRESH_TOKEN_LIFETIME_SECONDS must be greater than or equal to "
        "AUTH_ACCESS_TOKEN_LIFETIME_SECONDS."
    )

# Refresh tokens are stored in the server-side Django session, so the session
# must outlive them. Keep at least the Django default of 14 days.
SESSION_COOKIE_AGE = max(
    14 * 24 * 60 * 60, HEADLESS_JWT_REFRESH_TOKEN_EXPIRES_IN + 24 * 60 * 60
)

# Google OAuth credentials come only from the environment. A half-configured
# client is a startup error instead of a confusing runtime failure.
GOOGLE_OAUTH_CLIENT_ID = env("GOOGLE_OAUTH_CLIENT_ID", "")
GOOGLE_OAUTH_CLIENT_SECRET = env("GOOGLE_OAUTH_CLIENT_SECRET", "")
if bool(GOOGLE_OAUTH_CLIENT_ID) != bool(GOOGLE_OAUTH_CLIENT_SECRET):
    raise ImproperlyConfigured(
        "Set both GOOGLE_OAUTH_CLIENT_ID and GOOGLE_OAUTH_CLIENT_SECRET, or "
        "neither. Google sign-in is unavailable until both are set."
    )

SOCIALACCOUNT_PROVIDERS = {}
if GOOGLE_OAUTH_CLIENT_ID:
    SOCIALACCOUNT_PROVIDERS["google"] = {
        "APP": {
            "client_id": GOOGLE_OAUTH_CLIENT_ID,
            "secret": GOOGLE_OAUTH_CLIENT_SECRET,
            "key": "",
        },
        "SCOPE": ["profile", "email"],
        "OAUTH_PKCE_ENABLED": True,
    }

SOCIALACCOUNT_AUTO_SIGNUP = True
# Never link a Google account to an existing local account merely because the
# email string matches. Google marks addresses as verified, but implicit
# merging is still opt-in and disabled here.
SOCIALACCOUNT_EMAIL_AUTHENTICATION = False
SOCIALACCOUNT_EMAIL_AUTHENTICATION_AUTO_CONNECT = False

# --- API -----------------------------------------------------------------
# JSON only by default. development.py adds the browsable API renderer.
API_PAGE_SIZE = env_int("API_PAGE_SIZE", 24)
API_MAX_PAGE_SIZE = env_int("API_MAX_PAGE_SIZE", 60)

REST_FRAMEWORK = {
    "DEFAULT_RENDERER_CLASSES": ("rest_framework.renderers.JSONRenderer",),
    "DEFAULT_AUTHENTICATION_CLASSES": (
        # Bearer JWT access tokens issued by django-allauth Headless.
        "allauth.headless.contrib.rest_framework.authentication.JWTTokenAuthentication",
        # Kept for Django Admin and the browsable API; CSRF still applies.
        "rest_framework.authentication.SessionAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": (
        "rest_framework.permissions.IsAuthenticatedOrReadOnly",
    ),
    "DEFAULT_PAGINATION_CLASS": "apps.api.pagination.StandardPagination",
    "PAGE_SIZE": API_PAGE_SIZE,
    # Only the download action is throttled for now. Rate limits are
    # best-effort abuse control, not verified download statistics.
    "DEFAULT_THROTTLE_RATES": {
        "downloads": env("API_DOWNLOAD_THROTTLE_RATE", "60/minute"),
    },
    "TEST_REQUEST_DEFAULT_FORMAT": "json",
}

# --- Browser origins -----------------------------------------------------
# No wildcard support by design. CORS_ALLOW_ALL_ORIGINS stays False so that
# credentials can never be combined with an arbitrary origin.
CORS_ALLOW_ALL_ORIGINS = False
CORS_ALLOWED_ORIGINS = validate_origins(
    "CORS_ALLOWED_ORIGINS", env_list("CORS_ALLOWED_ORIGINS")
)
CSRF_TRUSTED_ORIGINS = validate_origins(
    "CSRF_TRUSTED_ORIGINS", env_list("CSRF_TRUSTED_ORIGINS")
)
CORS_ALLOW_CREDENTIALS = env_bool("CORS_ALLOW_CREDENTIALS", False)
# JWT Bearer requests need the Authorization header. X-Session-Token is
# accepted by the allauth Headless app client while a social signup is
# pending.
CORS_ALLOW_HEADERS = (*default_headers, "x-session-token")

# --- Baseline security ---------------------------------------------------
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"
SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = False  # The frontend needs to read the CSRF cookie later.

# --- Logging -------------------------------------------------------------
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "simple": {
            "format": "{levelname} {asctime} {name} {message}",
            "style": "{",
        }
    },
    "handlers": {
        "console": {"class": "logging.StreamHandler", "formatter": "simple"}
    },
    "root": {
        "handlers": ["console"],
        "level": env("DJANGO_LOG_LEVEL", "INFO"),
    },
}
