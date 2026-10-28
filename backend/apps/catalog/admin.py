from django.contrib import admin, messages
from django.db.models import Count

from apps.core.admin_previews import external_image_link, uploaded_image_preview

from .models import Category, Tag


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "slug",
        "image_preview",
        "is_active",
        "wallpaper_count",
        "updated_at",
    )
    list_filter = ("is_active", "created_at")
    search_fields = ("name", "slug", "description")
    prepopulated_fields = {"slug": ("name",)}
    readonly_fields = ("image_preview", "created_at", "updated_at")
    list_editable = ("is_active",)
    list_per_page = 50
    save_on_top = True
    actions = ("activate_selected", "deactivate_selected")
    fieldsets = (
        (
            "Category",
            {"fields": ("name", "slug", "description", "is_active")},
        ),
        (
            "Presentation image",
            {
                "fields": ("image", "image_url", "image_preview"),
                "description": (
                    "Upload a local image or reference an external URL. "
                    "External URLs are format-checked only and are not fetched."
                ),
            },
        ),
        ("Timestamps", {"fields": ("created_at", "updated_at")}),
    )

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .annotate(wallpaper_total=Count("wallpapers"))
        )

    @admin.display(description="Wallpapers", ordering="wallpaper_total")
    def wallpaper_count(self, obj):
        return obj.wallpaper_total

    @admin.display(description="Image")
    def image_preview(self, obj):
        if obj.image:
            return uploaded_image_preview(obj.image, max_height=48, max_width=80)
        return external_image_link(obj.image_url)

    @admin.action(description="Activate selected categories")
    def activate_selected(self, request, queryset):
        updated = queryset.update(is_active=True)
        self.message_user(
            request,
            f"Activated {updated} categor{'y' if updated == 1 else 'ies'}.",
            messages.SUCCESS,
        )

    @admin.action(description="Deactivate selected categories")
    def deactivate_selected(self, request, queryset):
        updated = queryset.update(is_active=False)
        self.message_user(
            request,
            f"Deactivated {updated} categor{'y' if updated == 1 else 'ies'}.",
            messages.SUCCESS,
        )


@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "wallpaper_count", "created_at")
    search_fields = ("name", "slug")
    prepopulated_fields = {"slug": ("name",)}
    readonly_fields = ("created_at",)
    list_per_page = 50
    fieldsets = (
        ("Tag", {"fields": ("name", "slug")}),
        ("Timestamps", {"fields": ("created_at",)}),
    )

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .annotate(wallpaper_total=Count("wallpapers"))
        )

    @admin.display(description="Wallpapers", ordering="wallpaper_total")
    def wallpaper_count(self, obj):
        return obj.wallpaper_total
