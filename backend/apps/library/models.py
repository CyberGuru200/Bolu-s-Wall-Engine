"""Per-user wallpaper interactions.

Both models point at Django's built-in user model through
``settings.AUTH_USER_MODEL`` so a later custom user model (or allauth) does
not require rewriting these relations.
"""

from django.conf import settings
from django.db import models
from django.db.models import Index


class Like(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="wallpaper_likes",
    )
    wallpaper = models.ForeignKey(
        "wallpapers.Wallpaper",
        on_delete=models.CASCADE,
        related_name="likes",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at", "-pk")
        verbose_name = "like"
        verbose_name_plural = "likes"
        constraints = [
            models.UniqueConstraint(
                fields=["user", "wallpaper"],
                name="uniq_like_user_wallpaper",
            )
        ]
        indexes = [
            Index(
                fields=["wallpaper", "-created_at"],
                name="like_wallpaper_created_idx",
            )
        ]

    def __str__(self):
        return f"{self.user} likes {self.wallpaper}"


class SavedWallpaper(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="saved_wallpapers",
    )
    wallpaper = models.ForeignKey(
        "wallpapers.Wallpaper",
        on_delete=models.CASCADE,
        related_name="saves",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at", "-pk")
        verbose_name = "saved wallpaper"
        verbose_name_plural = "saved wallpapers"
        constraints = [
            models.UniqueConstraint(
                fields=["user", "wallpaper"],
                name="uniq_saved_user_wallpaper",
            )
        ]
        indexes = [
            Index(
                fields=["user", "-created_at"],
                name="saved_user_created_idx",
            )
        ]

    def __str__(self):
        return f"{self.user} saved {self.wallpaper}"
