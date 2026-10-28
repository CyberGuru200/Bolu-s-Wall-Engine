from django.conf import settings
from django.test import SimpleTestCase


class HealthCheckTests(SimpleTestCase):
    url = "/api/health/"
    allowed_origin = (
        settings.CORS_ALLOWED_ORIGINS[0]
        if settings.CORS_ALLOWED_ORIGINS
        else None
    )
    rejected_origin = "https://not-allowed.example"

    def require_configured_origin(self):
        if not self.allowed_origin:
            self.skipTest("No CORS origin is configured in this environment.")

    def test_get_returns_simple_json_without_database(self):
        response = self.client.get(self.url, HTTP_ACCEPT="application/json")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/json")
        self.assertEqual(response["Cache-Control"], "no-store")
        self.assertEqual(
            response.json(),
            {"status": "ok", "service": "bolu-wall-engine-api"},
        )

    def test_response_does_not_expose_configuration(self):
        response = self.client.get(self.url, HTTP_ACCEPT="application/json")
        body = response.content.decode().lower()

        self.assertEqual(set(response.json()), {"status", "service"})
        for forbidden in (
            "secret_key",
            "db_password",
            "database",
            "debug",
            "mysql",
            "allowed_hosts",
            "traceback",
        ):
            self.assertNotIn(forbidden, body)

    def test_only_get_is_allowed(self):
        response = self.client.post(self.url, data={})
        self.assertEqual(response.status_code, 405)

    def test_cors_allows_only_the_configured_frontend_origin(self):
        self.require_configured_origin()
        allowed = self.client.get(
            self.url, HTTP_ORIGIN=self.allowed_origin
        )
        self.assertEqual(
            allowed["Access-Control-Allow-Origin"], self.allowed_origin
        )
        # Credentials are disabled by default; explicit origins still apply.
        self.assertNotIn("Access-Control-Allow-Credentials", allowed)

    def test_cors_rejects_an_unconfigured_origin(self):
        self.require_configured_origin()
        response = self.client.get(
            self.url, HTTP_ORIGIN=self.rejected_origin
        )
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("Access-Control-Allow-Origin", response)

    def test_cors_preflight_for_the_frontend_origin(self):
        self.require_configured_origin()
        response = self.client.options(
            self.url,
            HTTP_ORIGIN=self.allowed_origin,
            HTTP_ACCESS_CONTROL_REQUEST_METHOD="GET",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response["Access-Control-Allow-Origin"], self.allowed_origin
        )
