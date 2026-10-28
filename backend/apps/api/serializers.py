"""Read serializers for the public catalogue and write serializers for the
per-user library.

Only public, published data is serialized. Storage paths and media are turned
into absolute URLs when a request is available; no external resource is ever
fetched while serializing.
"""

from rest_framework import serializers

from apps.catalog.models import Category, Tag
from apps.library.models import Like, SavedWallpaper
from apps.wallpapers.models import Wallpaper


def absolute_file_url(serializer, field_file):
    """Return an absolute URL for an uploaded file, or ``None``.

    Falls back to the storage-relative URL when no request context exists
    (for example, serializers used directly in tests or scripts).
    """

    if not field_file:
        return None
    try:
        url = field_file.url
    except (ValueError, AttributeError):
        return None
    request = serializer.context.get("request")
    if request is not None:
        return request.build_absolute_uri(url)
    return url


def or_none(value):
    return value or None


class CategoryRefSerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ("name", "slug")


class TagRefSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tag
        fields = ("name", "slug")


class CategorySerializer(serializers.ModelSerializer):
    wallpaper_count = serializers.IntegerField(read_only=True)
    image_url = serializers.SerializerMethodField()
    image_source = serializers.SerializerMethodField()

    class Meta:
        model = Category
        fields = (
            "name",
            "slug",
            "description",
            "image_url",
            "image_source",
            "wallpaper_count",
        )

    def get_image_url(self, obj):
        if obj.image:
            return absolute_file_url(self, obj.image)
        return or_none(obj.image_url)

    def get_image_source(self, obj):
        if obj.image:
            return "uploaded"
        if obj.image_url:
            return "external"
        return None


class TagSerializer(serializers.ModelSerializer):
    wallpaper_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Tag
        fields = ("name", "slug", "wallpaper_count")


class WallpaperSerializer(serializers.ModelSerializer):
    """Fields shared by list, detail, and library responses.

    ``url`` is the resolved primary image: the uploaded file when present,
    otherwise the configured external URL. The original external URL is still
    exposed explicitly in the detail serializer.
    """

    category = CategoryRefSerializer(read_only=True)
    tags = TagRefSerializer(many=True, read_only=True)
    url = serializers.SerializerMethodField()
    thumbnail_url = serializers.SerializerMethodField()
    image_source = serializers.SerializerMethodField()
    orientation = serializers.SerializerMethodField()

    class Meta:
        model = Wallpaper
        fields = (
            "slug",
            "title",
            "description",
            "category",
            "tags",
            "author",
            "collection",
            "url",
            "thumbnail_url",
            "image_source",
            "orientation",
            "width",
            "height",
            "published_at",
            "download_count",
        )
        read_only_fields = fields

    def get_url(self, obj):
        uploaded = absolute_file_url(self, obj.image)
        if uploaded:
            return uploaded
        return or_none(obj.image_url)

    def get_thumbnail_url(self, obj):
        uploaded = absolute_file_url(self, obj.thumbnail)
        if uploaded:
            return uploaded
        if obj.thumbnail_url:
            return obj.thumbnail_url
        return self.get_url(obj)

    def get_image_source(self, obj):
        if obj.image:
            return "uploaded"
        if obj.image_url:
            return "external"
        return None

    def get_orientation(self, obj):
        if not obj.width or not obj.height:
            return None
        if obj.width > obj.height:
            return "landscape"
        if obj.height > obj.width:
            return "portrait"
        return "square"


class WallpaperDetailSerializer(WallpaperSerializer):
    """Adds provenance, licence, and explicit image-source URLs."""

    external_image_url = serializers.SerializerMethodField()
    uploaded_image_url = serializers.SerializerMethodField()
    external_thumbnail_url = serializers.SerializerMethodField()
    uploaded_thumbnail_url = serializers.SerializerMethodField()
    source_url = serializers.SerializerMethodField()
    license = serializers.SerializerMethodField()

    class Meta(WallpaperSerializer.Meta):
        fields = WallpaperSerializer.Meta.fields + (
            "external_image_url",
            "uploaded_image_url",
            "external_thumbnail_url",
            "uploaded_thumbnail_url",
            "source_url",
            "license",
        )
        read_only_fields = fields

    def get_external_image_url(self, obj):
        return or_none(obj.image_url)

    def get_uploaded_image_url(self, obj):
        return absolute_file_url(self, obj.image)

    def get_external_thumbnail_url(self, obj):
        return or_none(obj.thumbnail_url)

    def get_uploaded_thumbnail_url(self, obj):
        return absolute_file_url(self, obj.thumbnail)

    def get_source_url(self, obj):
        return or_none(obj.source_url)

    def get_license(self, obj):
        return {
            "name": or_none(obj.license_name),
            "url": or_none(obj.license_url),
            "status": obj.license_status,
        }


class LibraryItemSerializer(serializers.ModelSerializer):
    """Base representation for a like or a saved wallpaper."""

    wallpaper = WallpaperSerializer(read_only=True)

    class Meta:
        fields = ("wallpaper",)


class LikeSerializer(LibraryItemSerializer):
    liked_at = serializers.DateTimeField(source="created_at", read_only=True)

    class Meta(LibraryItemSerializer.Meta):
        model = Like
        fields = ("wallpaper", "liked_at")


class SavedWallpaperSerializer(LibraryItemSerializer):
    saved_at = serializers.DateTimeField(source="created_at", read_only=True)

    class Meta(LibraryItemSerializer.Meta):
        model = SavedWallpaper
        fields = ("wallpaper", "saved_at")


class WallpaperSlugSerializer(serializers.Serializer):
    """Validates the body of a like/save request.

    The slug is resolved against published wallpapers in the view so an
    unknown or unpublished target is a 404 rather than a leaky 400.
    """

    wallpaper = serializers.SlugField(
        max_length=220,
        allow_blank=False,
        trim_whitespace=True,
        help_text="Slug of a published wallpaper.",
    )
