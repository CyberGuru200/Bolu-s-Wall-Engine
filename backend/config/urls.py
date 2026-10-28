"""Root URL configuration.

Phase 4 exposes the health check, the read-only catalogue API, the
authenticated library and profile endpoints, django-allauth Headless
authentication (``/_allauth/``), the OAuth provider callbacks (``/accounts/``),
Django admin, and uploaded media files in development.
"""

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include("apps.core.urls")),
    path("api/v1/", include("apps.api.urls")),
    # JSON sign-in, token refresh, logout, and provider flows.
    path("_allauth/", include("allauth.headless.urls")),
    # OAuth provider redirect/callback routes (no allauth HTML account pages).
    path("accounts/", include("allauth.urls")),
]

if settings.DEBUG:
    # Development only: serve uploaded images so admin previews work. In
    # production, the web server (or object storage) must serve MEDIA_ROOT.
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
