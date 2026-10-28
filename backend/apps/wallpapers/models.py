"""Wallpaper records.

A wallpaper may reference an externally hosted image, an uploaded file, or
both. Uploaded binaries live in the configured file storage (``media/`` by
default); MySQL stores only the relative path.
"""

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Index, Q
from django.utils import timezone

from apps.core.slugs import build_unique_slug, normalize_slug
from apps.core.uploads import wallpaper_image_upload_to, wallpaper_thumbnail_upload_to
from apps.core.validators import (
    image_extension_validator,
    validate_image_contents,
    validate_image_url,
    validate_thumbnail_image_size,
    validate_wallpaper_image_size,
)


class Wallpaper(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        PUBLISHED = "published", "Published"
        ARCHIVED = "archived", "Archived"

    class LicenseStatus(models.TextChoices):
        DOCUMENTED = "documented", "Documented"
        UNVERIFIED = "unverified", "Unverified"
        UNKNOWN = "unknown", "Unknown"

    title = models.CharField(max_length=200)
    slug = models.SlugField(
        max_length=220,
        unique=True,
        blank=True,
        help_text="Leave blank to generate a unique slug from the title.",
    )
    description = models.TextField(blank=True)

    category = models.ForeignKey(
        "catalog.Category",
        on_delete=models.PROTECT,
        related_name="wallpapers",
    )
    tags = models.ManyToManyField(
        "catalog.Tag",
        blank=True,
        related_name="wallpapers",
    )

    image_url = models.URLField(
        max_length=500,
        blank=True,
        validators=[validate_image_url],
        help_text=(
            "External image URL. Format-checked only: Django does not fetch "
            "it, so availability and content are not verified."
        ),
    )
    image = models.ImageField(
        upload_to=wallpaper_image_upload_to,
        blank=True,
        validators=[
            image_extension_validator,
            validate_image_contents,
            validate_wallpaper_image_size,
        ],
        help_text="Optional uploaded image (JPEG, PNG, WebP, or GIF).",
    )
    thumbnail_url = models.URLField(
        max_length=500,
        blank=True,
        validators=[validate_image_url],
        help_text="Optional external thumbnail URL; never fetched by Django.",
    )
    thumbnail = models.ImageField(
        upload_to=wallpaper_thumbnail_upload_to,
        blank=True,
        validators=[
            image_extension_validator,
            validate_image_contents,
            validate_thumbnail_image_size,
        ],
        help_text="Optional uploaded thumbnail (JPEG, PNG, WebP, or GIF).",
    )

    source_url = models.URLField(
        max_length=500,
        blank=True,
        help_text="Original source or artist page. Optional when unknown.",
    )
    author = models.CharField(
        max_length=200,
        blank=True,
        help_text=(
            "Artist or photographer credited by the source. Leave blank when "
            "the credit is unknown; never guess a name."
        ),
    )
    collection = models.CharField(
        max_length=200,
        blank=True,
        help_text=(
            "Source collection or series the artwork belongs to. Optional; "
            "leave blank when unknown."
        ),
    )
    license_name = models.CharField(max_length=120, blank=True)
    license_url = models.URLField(max_length=500, blank=True)
    license_status = models.CharField(
        max_length=20,
        choices=LicenseStatus.choices,
        default=LicenseStatus.UNKNOWN,
        db_index=True,
        help_text=(
            "Use 'Documented' only when the licence is recorded. "
            "Do not mark an external image as verified without checking it."
        ),
    )

    width = models.PositiveIntegerField(null=True, blank=True, help_text="Pixels.")
    height = models.PositiveIntegerField(null=True, blank=True, help_text="Pixels.")
    file_size = models.PositiveBigIntegerField(
        null=True,
        blank=True,
        help_text="Bytes, when known.",
    )

    download_count = models.PositiveBigIntegerField(
        default=0,
        help_text="Incremented by application code; not a floating-point value.",
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.DRAFT,
        db_index=True,
    )
    published_at = models.DateTimeField(null=True, blank=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-published_at", "-created_at", "-pk")
        verbose_name = "wallpaper"
        verbose_name_plural = "wallpapers"
        indexes = [
            Index(
                fields=["status", "-published_at"],
                name="wp_status_published_idx",
            ),
            Index(
                fields=["category", "status", "-published_at"],
                name="wp_cat_status_pub_idx",
            ),
            Index(fields=["-download_count"], name="wp_downloads_idx"),
        ]
        constraints = [
            models.CheckConstraint(
                condition=Q(status__in=["draft", "published", "archived"]),
                name="wp_status_valid",
            ),
            models.CheckConstraint(
                condition=(
                    ~Q(status="published") | ~Q(image="") | ~Q(image_url="")
                ),
                name="wp_published_has_image",
            ),
        ]

    def __str__(self):
        return self.title

    @property
    def has_usable_image(self):
        """True when an uploaded file or a non-empty external URL exists.

        No network request is made. An external URL is a usable *source*, not
        a verified image.
        """

        return bool(self.image or self.image_url)

    @property
    def is_published(self):
        return self.status == self.Status.PUBLISHED

    def clean(self):
        super().clean()
        self.title = " ".join((self.title or "").split())
        if not self.title:
            raise ValidationError({"title": "Enter a wallpaper title."})

        if self.slug:
            self.slug = normalize_slug(self.slug, max_length=220)
            if not self.slug:
                raise ValidationError(
                    {"slug": "Enter a valid slug, or leave it blank."}
                )

        if not self.has_usable_image:
            raise ValidationError(
                {
                    "image_url": (
                        "Provide an external image URL or upload an image. "
                        "At least one usable image source is required."
                    )
                }
            )

        if self.license_status == self.LicenseStatus.DOCUMENTED and not (
            self.license_name or self.license_url
        ):
            raise ValidationError(
                {
                    "license_name": (
                        "Record a licence name or URL when the status is "
                        "'Documented'."
                    )
                }
            )

    def save(self, *args, **kwargs):
        self.title = " ".join((self.title or "").split())
        if not self.slug:
            self.slug = build_unique_slug(
                self,
                self.title,
                max_length=220,
                fallback="wallpaper",
            )
        else:
            self.slug = normalize_slug(self.slug, max_length=220)

        if self.status == self.Status.PUBLISHED and self.published_at is None:
            self.published_at = timezone.now()
            update_fields = kwargs.get("update_fields")
            if update_fields is not None:
                kwargs["update_fields"] = set(update_fields) | {"published_at"}

        super().save(*args, **kwargs)
