from django.contrib import admin, messages
from django.core.exceptions import ValidationError
from django.utils import timezone

from apps.core.admin_previews import external_image_link, uploaded_image_preview

from .models import Wallpaper


@admin.register(Wallpaper)
class WallpaperAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "category",
        "status",
        "tag_list",
        "image_preview",
        "download_count",
        "published_at",
        "updated_at",
    )
    list_filter = ("status", "category", "tags", "license_status")
    search_fields = (
        "title",
        "slug",
        "description",
        "source_url",
        "license_name",
    )
    prepopulated_fields = {"slug": ("title",)}
    autocomplete_fields = ("category",)
    filter_horizontal = ("tags",)
    readonly_fields = (
        "image_preview",
        "thumbnail_preview",
        "download_count",
        "created_at",
        "updated_at",
    )
    date_hierarchy = "created_at"
    list_per_page = 50
    save_on_top = True
    actions = ("publish_selected", "unpublish_selected", "archive_selected")
    fieldsets = (
        (
            "Content",
            {"fields": ("title", "slug", "description", "category", "tags")},
        ),
        (
            "Image sources",
            {
                "fields": (
                    "image",
                    "image_url",
                    "image_preview",
                    "thumbnail",
                    "thumbnail_url",
                    "thumbnail_preview",
                ),
                "description": (
                    "Upload a local file or provide an external URL. At least "
                    "one image source is required. External URLs are "
                    "format-checked only; Django never downloads or verifies "
                    "them."
                ),
            },
        ),
        (
            "Source and licence",
            {
                "fields": (
                    "source_url",
                    "author",
                    "collection",
                    "license_name",
                    "license_url",
                    "license_status",
                ),
                "description": (
                    "Record only credits the source actually states. Leave "
                    "author or collection blank when they are unknown."
                ),
            },
        ),
        (
            "Media metadata",
            {"fields": ("width", "height", "file_size", "download_count")},
        ),
        (
            "Publication",
            {
                "fields": ("status", "published_at", "created_at", "updated_at"),
                "description": (
                    "A wallpaper cannot be published without an uploaded "
                    "image or an external image URL. Use the admin actions to "
                    "publish or unpublish in bulk."
                ),
            },
        ),
    )

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .select_related("category")
            .prefetch_related("tags")
        )

    @admin.display(description="Tags")
    def tag_list(self, obj):
        return ", ".join(tag.name for tag in obj.tags.all()) or "—"

    @admin.display(description="Image")
    def image_preview(self, obj):
        if obj.image:
            return uploaded_image_preview(obj.image, max_height=56, max_width=100)
        if obj.image_url:
            return external_image_link(obj.image_url)
        if obj.thumbnail:
            return uploaded_image_preview(
                obj.thumbnail, max_height=56, max_width=100
            )
        return external_image_link(obj.thumbnail_url)

    @admin.display(description="Thumbnail")
    def thumbnail_preview(self, obj):
        if obj.thumbnail:
            return uploaded_image_preview(
                obj.thumbnail, max_height=48, max_width=80
            )
        return external_image_link(obj.thumbnail_url)

    @admin.action(description="Publish selected wallpapers")
    def publish_selected(self, request, queryset):
        published = 0
        skipped = []
        for wallpaper in queryset:
            if not wallpaper.has_usable_image:
                skipped.append(f"{wallpaper.title} (no image source)")
                continue
            wallpaper.status = Wallpaper.Status.PUBLISHED
            if wallpaper.published_at is None:
                wallpaper.published_at = timezone.now()
            try:
                wallpaper.full_clean()
            except ValidationError as exc:
                skipped.append(f"{wallpaper.title} ({'; '.join(exc.messages)})")
                continue
            wallpaper.save()
            published += 1

        if published:
            self.message_user(
                request,
                f"Published {published} wallpaper"
                f"{'' if published == 1 else 's'}.",
                messages.SUCCESS,
            )
        if skipped:
            preview = "; ".join(skipped[:10])
            remainder = len(skipped) - 10
            if remainder > 0:
                preview += f"; and {remainder} more"
            self.message_user(
                request,
                f"Skipped {len(skipped)} wallpaper"
                f"{'' if len(skipped) == 1 else 's'}: {preview}",
                messages.ERROR,
            )

    @admin.action(description="Unpublish selected wallpapers (move to draft)")
    def unpublish_selected(self, request, queryset):
        updated = queryset.update(
            status=Wallpaper.Status.DRAFT, updated_at=timezone.now()
        )
        self.message_user(
            request,
            f"Moved {updated} wallpaper{'' if updated == 1 else 's'} to draft.",
            messages.SUCCESS,
        )

    @admin.action(description="Archive selected wallpapers")
    def archive_selected(self, request, queryset):
        updated = queryset.update(
            status=Wallpaper.Status.ARCHIVED, updated_at=timezone.now()
        )
        self.message_user(
            request,
            f"Archived {updated} wallpaper{'' if updated == 1 else 's'}.",
            messages.SUCCESS,
        )
