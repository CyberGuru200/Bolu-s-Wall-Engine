from django.conf import settings
from django.test import override_settings
from django.urls import reverse
from rest_framework.test import APIClient, APITestCase
from rest_framework.throttling import ScopedRateThrottle

from apps.api.pagination import StandardPagination
from apps.api.views import (
    CategoryViewSet,
    LikeListCreateView,
    SavedWallpaperListCreateView,
    TagViewSet,
    WallpaperViewSet,
)

from .utils import make_category, make_user, make_wallpaper


class ApiRoutingTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.category = make_category("Routing")
        cls.wallpaper = make_wallpaper("Routed", category=cls.category)

    def test_reverse_names_resolve(self):
        self.assertEqual(reverse("api:category-list"), "/api/v1/categories/")
        self.assertEqual(reverse("api:tag-list"), "/api/v1/tags/")
        self.assertEqual(reverse("api:wallpaper-list"), "/api/v1/wallpapers/")
        self.assertEqual(reverse("api:like-list"), "/api/v1/library/likes/")
        self.assertEqual(reverse("api:saved-list"), "/api/v1/library/saved/")
        self.assertEqual(
            reverse("api:like-detail", kwargs={"slug": "routed"}),
            "/api/v1/library/likes/routed/",
        )

    def test_router_root_describes_public_collections(self):
        response = self.client.get("/api/v1/")

        self.assertEqual(response.status_code, 200)
        self.assertIn("categories", response.data)
        self.assertIn("tags", response.data)
        self.assertIn("wallpapers", response.data)

    def test_health_endpoint_is_still_available_outside_v1(self):
        response = self.client.get("/api/health/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["status"], "ok")

    def test_browsable_api_renders_in_development(self):
        response = self.client.get(
            "/api/v1/wallpapers/", HTTP_ACCEPT="text/html"
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("text/html", response["Content-Type"])

    def test_catalogue_endpoints_are_public_and_read_only(self):
        for view in (CategoryViewSet, TagViewSet, WallpaperViewSet):
            with self.subTest(view=view.__name__):
                view_set = view()
                self.assertEqual(
                    [permission.__name__ for permission in view_set.permission_classes],
                    ["AllowAny"],
                )

    def test_library_endpoints_require_authentication(self):
        for view in (LikeListCreateView, SavedWallpaperListCreateView):
            with self.subTest(view=view.__name__):
                self.assertEqual(
                    [
                        permission.__name__
                        for permission in view.permission_classes
                    ],
                    ["IsAuthenticated"],
                )

    def test_jwt_is_the_primary_authentication_mechanism(self):
        self.assertEqual(
            settings.REST_FRAMEWORK["DEFAULT_AUTHENTICATION_CLASSES"],
            (
                "allauth.headless.contrib.rest_framework.authentication."
                "JWTTokenAuthentication",
                "rest_framework.authentication.SessionAuthentication",
            ),
        )

    def test_no_basic_or_remote_token_authentication_is_configured(self):
        configured = " ".join(
            settings.REST_FRAMEWORK["DEFAULT_AUTHENTICATION_CLASSES"]
        ).lower()

        for forbidden in ("basic", "rest_framework.authtoken", "oauth2_provider"):
            self.assertNotIn(forbidden, configured)

    def test_pagination_defaults_and_cap(self):
        self.assertEqual(settings.API_PAGE_SIZE, 24)
        self.assertEqual(settings.API_MAX_PAGE_SIZE, 60)

        paginator = StandardPagination()
        self.assertEqual(paginator.page_size, 24)
        self.assertEqual(paginator.max_page_size, 60)
        self.assertEqual(paginator.page_size_query_param, "page_size")

    @override_settings(API_PAGE_SIZE=5, API_MAX_PAGE_SIZE=8)
    def test_pagination_settings_are_configurable(self):
        paginator = StandardPagination()

        self.assertEqual(paginator.page_size, 5)
        self.assertEqual(paginator.max_page_size, 8)

    def test_download_throttle_is_configured(self):
        self.assertIn("downloads", settings.REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"])

        action = WallpaperViewSet.download
        self.assertEqual(action.kwargs["throttle_classes"], [ScopedRateThrottle])
        self.assertEqual(WallpaperViewSet.throttle_scope, "downloads")


class AuthenticationBehaviourTests(APITestCase):
    def setUp(self):
        self.user = make_user("session-user")
        self.category = make_category("Auth")
        self.wallpaper = make_wallpaper("Auth wall", category=self.category)

    def test_missing_credentials_return_a_bearer_challenge(self):
        response = self.client.get("/api/v1/library/likes/")

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response["WWW-Authenticate"], "Bearer")
        self.assertIn("detail", response.data)

    def test_session_authenticated_writes_require_csrf(self):
        csrf_client = APIClient(enforce_csrf_checks=True)
        csrf_client.force_login(self.user)

        response = csrf_client.post(
            "/api/v1/library/likes/",
            {"wallpaper": self.wallpaper.slug},
            format="json",
        )

        self.assertEqual(response.status_code, 403)
        self.assertIn("detail", response.data)

    def test_authenticated_session_can_use_the_library(self):
        self.client.force_login(self.user)

        response = self.client.post(
            "/api/v1/library/likes/",
            {"wallpaper": self.wallpaper.slug},
            format="json",
        )

        self.assertEqual(response.status_code, 201)


class ErrorHandlingTests(APITestCase):
    def test_unknown_route_returns_404(self):
        self.assertEqual(self.client.get("/api/v1/nope/").status_code, 404)

    def test_unknown_wallpaper_slug_returns_404(self):
        self.assertEqual(
            self.client.get("/api/v1/wallpapers/nope/").status_code, 404
        )

    def test_validation_errors_are_structured(self):
        user = make_user("error-user")
        self.client.force_authenticate(user)

        response = self.client.post(
            "/api/v1/library/saved/", {"wallpaper": ""}, format="json"
        )

        self.assertEqual(response.status_code, 400)
        self.assertIsInstance(response.data, dict)
        self.assertIn("wallpaper", response.data)

    def test_error_body_contains_no_traceback(self):
        response = self.client.get("/api/v1/wallpapers/?ordering=secret_field")

        self.assertEqual(response.status_code, 400)
        body = response.content.decode().lower()
        self.assertNotIn("traceback", body)
        self.assertNotIn("secret_key", body)
