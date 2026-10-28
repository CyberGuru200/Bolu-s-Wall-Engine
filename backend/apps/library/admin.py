from django.contrib import admin

from .models import Like, SavedWallpaper


class ReadOnlyUserWallpaperAdmin(admin.ModelAdmin):
    """List and delete interaction records without offering manual edits.

    Likes and saves are created by users through the future API. Changing the
    user or wallpaper of an existing row would falsify activity, so only
    deletion (for moderation) is exposed.
    """

    list_select_related = ("user", "wallpaper")
    list_filter = ("created_at",)
    date_hierarchy = "created_at"
    readonly_fields = ("user", "wallpaper", "created_at")
    list_per_page = 100

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(Like)
class LikeAdmin(ReadOnlyUserWallpaperAdmin):
    list_display = ("user", "wallpaper", "created_at")
    search_fields = (
        "user__username",
        "user__email",
        "wallpaper__title",
    )
    ordering = ("-created_at", "-pk")


@admin.register(SavedWallpaper)
class SavedWallpaperAdmin(ReadOnlyUserWallpaperAdmin):
    list_display = ("user", "wallpaper", "created_at")
    search_fields = (
        "user__username",
        "user__email",
        "wallpaper__title",
    )
    ordering = ("-created_at", "-pk")
