"""django-allauth account adapters for Bolu's Wall Engine.

Google is the only self-service signup path. Public username/password signup is
closed so the backend does not run an unverified open registration endpoint;
existing staff/test accounts can still sign in with a password to obtain JWTs.
"""

from allauth.account.adapter import DefaultAccountAdapter
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from django.conf import settings
from django.contrib.auth import get_user_model
from django.utils.text import slugify

USERNAME_MAX_LENGTH = 30


class AccountAdapter(DefaultAccountAdapter):
    def is_open_for_signup(self, request):
        """Gate allauth's password signup endpoint.

        Social signup uses ``SocialAccountAdapter.is_open_for_signup`` instead,
        so Google sign-in still creates accounts when enabled.
        """

        return settings.ACCOUNT_ALLOW_PASSWORD_SIGNUP

    def populate_username(self, request, user):
        """Give social signups a readable, unique username.

        Google supplies a name and email but no username. Deriving one from the
        email local part is friendlier than allauth's ``user``/``user2``
        sequence, and it keeps the value inside Django's username rules.
        """

        if user.username:
            return

        local_part = (user.email or "").split("@")[0]
        base = slugify(local_part).replace("-", "")[:USERNAME_MAX_LENGTH]
        if not base:
            base = "user"

        User = get_user_model()
        username = base
        suffix = 2
        while User.objects.filter(username__iexact=username).exists():
            ending = f"-{suffix}"
            username = f"{base[: USERNAME_MAX_LENGTH - len(ending)]}{ending}"
            suffix += 1
        user.username = username


class SocialAccountAdapter(DefaultSocialAccountAdapter):
    """Allow first-time Google sign-ins.

    ``DefaultSocialAccountAdapter.is_open_for_signup`` delegates to the account
    adapter, which closes password signup. Social signup is the intended
    self-service path, so it is allowed explicitly here.
    """

    def is_open_for_signup(self, request, sociallogin):
        return True
