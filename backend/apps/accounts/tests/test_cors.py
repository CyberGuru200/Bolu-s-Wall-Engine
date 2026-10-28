"""CORS behaviour for the browser-facing API."""

from django.conf import settings
from django.test import override_settings
from rest_framework.test import APITestCase

ALLOWED_ORIGIN = "https://app.example.com"
DENIED_ORIGIN = "https://evil.example.net"


@override_settings(
    CORS_ALLOWED_ORIGINS=[ALLOWED_ORIGIN],
    CORS_ALLOW_CREDENTIALS=False,
)
class CorsTests(APITestCase):
    def test_allowed_origin_is_echoed_on_simple_requests(self):
        response = self.client.get("/api/v1/wallpapers/", HTTP_ORIGIN=ALLOWED_ORIGIN)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Access-Control-Allow-Origin"], ALLOWED_ORIGIN)

    def test_disallowed_origin_gets_no_cors_permission(self):
        response = self.client.get("/api/v1/wallpapers/", HTTP_ORIGIN=DENIED_ORIGIN)

        self.assertEqual(response.status_code, 200)
        self.assertNotIn("Access-Control-Allow-Origin", response)

    def test_wildcard_is_never_used(self):
        response = self.client.get("/api/v1/wallpapers/", HTTP_ORIGIN=ALLOWED_ORIGIN)

        self.assertFalse(settings.CORS_ALLOW_ALL_ORIGINS)
        self.assertNotEqual(response["Access-Control-Allow-Origin"], "*")

    def test_preflight_allows_authorization_and_session_token_headers(self):
        response = self.client.options(
            "/api/v1/library/likes/",
            HTTP_ORIGIN=ALLOWED_ORIGIN,
            HTTP_ACCESS_CONTROL_REQUEST_METHOD="POST",
            HTTP_ACCESS_CONTROL_REQUEST_HEADERS=(
                "authorization,content-type,x-session-token"
            ),
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Access-Control-Allow-Origin"], ALLOWED_ORIGIN)
        allowed_headers = response["Access-Control-Allow-Headers"].lower()
        self.assertIn("authorization", allowed_headers)
        self.assertIn("x-session-token", allowed_headers)
        self.assertIn("content-type", allowed_headers)
        self.assertIn("POST", response["Access-Control-Allow-Methods"])

    def test_preflight_from_a_disallowed_origin_is_not_authorized(self):
        response = self.client.options(
            "/api/v1/library/likes/",
            HTTP_ORIGIN=DENIED_ORIGIN,
            HTTP_ACCESS_CONTROL_REQUEST_METHOD="POST",
            HTTP_ACCESS_CONTROL_REQUEST_HEADERS="authorization",
        )

        self.assertNotIn("Access-Control-Allow-Origin", response)

    def test_credentials_are_not_allowed_by_default(self):
        response = self.client.get("/api/v1/wallpapers/", HTTP_ORIGIN=ALLOWED_ORIGIN)

        self.assertFalse(settings.CORS_ALLOW_CREDENTIALS)
        self.assertNotIn("Access-Control-Allow-Credentials", response)
