"""Google sign-in through allauth Headless, with Google mocked out.

No real Google credentials or network calls are used: ``verify_token`` (the
provider method that validates the Google credential and builds the
``SocialLogin``) is patched for the success paths, and the real
``_verify_and_decode`` is patched to fail for the invalid-credential path.
"""

from unittest import mock

from allauth.account.models import EmailAddress
from allauth.socialaccount.adapter import get_adapter
from allauth.socialaccount.models import SocialAccount
from allauth.socialaccount.providers.google.provider import GoogleProvider
from allauth.socialaccount.providers.oauth2.client import OAuth2Error
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from .utils import (
    GOOGLE_CLIENT_ID,
    GOOGLE_PROVIDER_SETTINGS,
    HEADLESS,
    ME_URL,
    bearer,
    make_user,
    post_json,
)

User = get_user_model()


def provider_token(client, *, client_id=GOOGLE_CLIENT_ID, id_token="fake-id-token"):
    return post_json(
        client,
        f"{HEADLESS}/auth/provider/token",
        {
            "provider": "google",
            "process": "login",
            "token": {"id_token": id_token, "client_id": client_id},
        },
    )


def profile(**overrides):
    data = {
        "sub": "google-sub-1",
        "email": "new.user@example.com",
        "email_verified": True,
        "given_name": "New",
        "family_name": "User",
        "name": "New User",
    }
    data.update(overrides)
    return data


@override_settings(SOCIALACCOUNT_PROVIDERS=GOOGLE_PROVIDER_SETTINGS)
class GoogleConfigurationTests(TestCase):
    def test_headless_config_advertises_google(self):
        body = self.client.get(f"{HEADLESS}/config").json()

        providers = body["data"]["socialaccount"]["providers"]
        self.assertEqual([provider["id"] for provider in providers], ["google"])
        self.assertEqual(providers[0]["client_id"], GOOGLE_CLIENT_ID)
        self.assertIn("provider_redirect", providers[0]["flows"])
        self.assertIn("provider_token", providers[0]["flows"])

    def test_provider_redirect_returns_a_google_authorization_url(self):
        response = self.client.post(
            f"{HEADLESS}/auth/provider/redirect",
            {
                "provider": "google",
                "callback_url": "http://localhost:5173/auth/callback",
                "process": "login",
            },
        )

        self.assertEqual(response.status_code, 302)
        location = response["Location"]
        self.assertTrue(location.startswith("https://accounts.google.com/"))
        self.assertIn("client_id=", location)
        self.assertIn("state=", location)
        self.assertIn("code_challenge=", location)  # PKCE enabled

    def test_redirect_requires_a_process(self):
        response = self.client.post(
            f"{HEADLESS}/auth/provider/redirect",
            {
                "provider": "google",
                "callback_url": "http://localhost:5173/auth/callback",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertIn("error=", response["Location"])

    def test_unsafe_callback_url_is_rejected(self):
        response = self.client.post(
            f"{HEADLESS}/auth/provider/redirect",
            {
                "provider": "google",
                "callback_url": "https://evil.example.net/steal",
                "process": "login",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertIn("error=", response["Location"])
        self.assertEqual(len(self.client.session.get("socialaccount_states", {})), 0)

    def test_oauth_callback_with_a_bogus_state_is_rejected(self):
        response = self.client.get(
            "/accounts/google/login/callback/?state=bogus&code=bogus"
        )

        self.assertEqual(response.status_code, 302)
        self.assertIn("error=unknown", response["Location"])
        self.assertFalse(User.objects.exists())
        self.assertFalse(SocialAccount.objects.exists())

    def test_oauth_callback_without_state_is_rejected(self):
        response = self.client.get("/accounts/google/login/callback/?code=bogus")

        self.assertEqual(response.status_code, 302)
        self.assertIn("error=", response["Location"])
        self.assertFalse(User.objects.exists())
        self.assertFalse(SocialAccount.objects.exists())


@override_settings(SOCIALACCOUNT_PROVIDERS=GOOGLE_PROVIDER_SETTINGS)
class GoogleTokenLoginTests(TestCase):
    """The frontend-driven ``provider_token`` flow with mocked verification."""

    def verify_as(self, data):
        def verifier(request, token):
            provider = get_adapter().get_provider(request, "google")
            return provider.sociallogin_from_response(request, data)

        return mock.patch.object(GoogleProvider, "verify_token", side_effect=verifier)

    def test_first_google_login_creates_an_account_and_tokens(self):
        with self.verify_as(profile()):
            response = provider_token(self.client)

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertTrue(body["meta"]["is_authenticated"])
        self.assertTrue(body["meta"]["access_token"])
        self.assertTrue(body["meta"]["refresh_token"])

        user = User.objects.get(email="new.user@example.com")
        self.assertEqual(user.username, "newuser")
        self.assertFalse(user.has_usable_password())
        self.assertEqual(user.first_name, "New")
        self.assertEqual(user.last_name, "User")
        self.assertEqual(
            SocialAccount.objects.get(uid="google-sub-1").user_id, user.pk
        )

    def test_google_email_is_recorded_as_verified(self):
        with self.verify_as(profile()):
            provider_token(self.client)

        address = EmailAddress.objects.get(email="new.user@example.com")
        self.assertTrue(address.verified)

    def test_returning_google_user_reuses_the_same_account(self):
        with self.verify_as(profile()):
            first = provider_token(self.client)
        with self.verify_as(profile()):
            second = provider_token(self.client)

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(
            first.json()["data"]["user"]["id"], second.json()["data"]["user"]["id"]
        )
        self.assertEqual(User.objects.count(), 1)
        self.assertEqual(SocialAccount.objects.count(), 1)

        user = User.objects.get()
        token = second.json()["meta"]["access_token"]
        me = self.client.get(ME_URL, **bearer(token))
        self.assertEqual(me.data["username"], user.username)
        self.assertEqual(me.data["providers"], ["google"])

    def test_google_identity_is_never_matched_by_email(self):
        existing = make_user("existing", email="taken@example.com")

        with self.verify_as(profile(sub="google-sub-2", email="taken@example.com")):
            response = provider_token(self.client)

        self.assertEqual(response.status_code, 401)
        flows = {flow["id"]: flow for flow in response.json()["data"]["flows"]}
        self.assertIn("provider_signup", flows)
        self.assertTrue(flows["provider_signup"]["is_pending"])

        self.assertEqual(User.objects.count(), 1)
        self.assertFalse(existing.socialaccount_set.exists())
        self.assertFalse(SocialAccount.objects.exists())

    def test_unverified_google_email_is_never_merged_either(self):
        existing = make_user("existing", email="taken@example.com")
        existing.emailaddress_set.all().delete()

        with self.verify_as(
            profile(
                sub="google-sub-3",
                email="taken@example.com",
                email_verified=False,
            )
        ):
            response = provider_token(self.client)

        self.assertEqual(response.status_code, 401)
        self.assertEqual(User.objects.count(), 1)
        self.assertFalse(existing.socialaccount_set.exists())

    def test_invalid_google_credential_is_rejected(self):
        with mock.patch(
            "allauth.socialaccount.providers.google.views._verify_and_decode",
            side_effect=OAuth2Error("invalid"),
        ):
            response = provider_token(self.client)

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["errors"][0]["code"], "invalid_token")
        self.assertFalse(User.objects.exists())

    def test_mismatched_client_id_is_rejected_before_verification(self):
        with mock.patch.object(GoogleProvider, "verify_token") as verify:
            response = provider_token(self.client, client_id="another-client")

        self.assertEqual(response.status_code, 400)
        verify.assert_not_called()

    def test_google_is_unavailable_when_no_credentials_are_configured(self):
        # No override here: the test settings do not define a Google app.
        response = provider_token(self.client)

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["errors"][0]["param"], "token")

    def test_callbacks_with_bogus_state_do_not_create_anything(self):
        response = self.client.get(
            "/accounts/google/login/callback/?state=bogus&code=bogus"
        )

        self.assertEqual(response.status_code, 302)
        self.assertFalse(User.objects.exists())
        self.assertFalse(SocialAccount.objects.exists())
