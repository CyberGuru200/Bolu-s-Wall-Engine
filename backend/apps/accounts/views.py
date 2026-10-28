"""Endpoints for the authenticated user's own account.

Sign-in, token refresh, logout, and provider management are provided by
django-allauth Headless under ``/_allauth/app/v1/``. This module adds the
application-facing profile endpoint used by the React client.
"""

from django.contrib.auth import get_user_model
from django.db.models import Count
from rest_framework import generics
from rest_framework.permissions import IsAuthenticated

from .serializers import UserProfileSerializer


class MeView(generics.RetrieveAPIView):
    """Return the authenticated user's own profile.

    The user is always taken from the authenticated request; no user
    identifier is accepted from the client.
    """

    serializer_class = UserProfileSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        return (
            get_user_model()
            .objects.filter(pk=self.request.user.pk)
            .annotate(
                likes_count=Count("wallpaper_likes", distinct=True),
                saved_count=Count("saved_wallpapers", distinct=True),
            )
            .prefetch_related("socialaccount_set")
            .get()
        )
