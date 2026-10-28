"""Serializers for the authenticated user's own profile."""

from django.contrib.auth import get_user_model
from rest_framework import serializers


class UserProfileSerializer(serializers.ModelSerializer):
    """Safe, self-only fields.

    Deliberately excludes ``is_staff``, ``is_superuser``, permissions, password
    hashes, session identifiers, and token data.
    """

    display_name = serializers.SerializerMethodField()
    has_usable_password = serializers.SerializerMethodField()
    likes_count = serializers.IntegerField(read_only=True)
    saved_count = serializers.IntegerField(read_only=True)
    providers = serializers.SerializerMethodField()

    class Meta:
        model = get_user_model()
        fields = (
            "id",
            "username",
            "email",
            "display_name",
            "date_joined",
            "has_usable_password",
            "likes_count",
            "saved_count",
            "providers",
        )
        read_only_fields = fields

    def get_display_name(self, obj):
        return obj.get_full_name() or obj.get_username()

    def get_has_usable_password(self, obj):
        return obj.has_usable_password()

    def get_providers(self, obj):
        return sorted({account.provider for account in obj.socialaccount_set.all()})
