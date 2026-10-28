"""Shared helpers for the Phase 4 authentication tests."""

import json

from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

HEADLESS = "/_allauth/app/v1"
ME_URL = "/api/v1/auth/me/"

PASSWORD = "correct-horse-battery-staple"

GOOGLE_CLIENT_ID = "test-client.apps.googleusercontent.com"
GOOGLE_PROVIDER_SETTINGS = {
    "google": {
        "APP": {
            "client_id": GOOGLE_CLIENT_ID,
            "secret": "test-client-secret",
            "key": "",
        },
        "SCOPE": ["profile", "email"],
        "OAUTH_PKCE_ENABLED": True,
    }
}

User = get_user_model()


def make_user(username="bolu", *, email=None, password=PASSWORD, **kwargs):
    return User.objects.create_user(
        username=username,
        email=email or f"{username}@example.com",
        password=password,
        **kwargs,
    )


def bearer(token):
    return {"HTTP_AUTHORIZATION": f"Bearer {token}"}


def post_json(client, path, payload):
    return client.post(path, data=json.dumps(payload), content_type="application/json")


def login(client, username="bolu", password=PASSWORD):
    return post_json(
        client,
        f"{HEADLESS}/auth/login",
        {"username": username, "password": password},
    )


def tokens_for(client, username="bolu", password=PASSWORD):
    response = login(client, username=username, password=password)
    assert response.status_code == 200, response.content
    return response.json()["meta"]


def api_client_for(user, password=PASSWORD):
    """Return an APIClient authenticated with a real JWT access token."""

    client = APIClient()
    tokens = tokens_for(client, username=user.username, password=password)
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access_token']}")
    return client
