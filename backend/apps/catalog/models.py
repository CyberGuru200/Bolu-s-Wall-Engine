"""Category and tag catalogue models.

These are deliberately generic: Anime, Abstract, Minimalist, Colored, and any
future category are rows, never hardcoded choices.
"""

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Index

from apps.core.slugs import build_unique_slug, normalize_slug
from apps.core.uploads import category_image_upload_to
from apps.core.validators import (
    image_extension_validator,
    validate_category_image_size,
    validate_image_contents,
    validate_image_url,
)


class Category(models.Model):
    """A user-facing wallpaper category."""

    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(
        max_length=120,
        unique=True,
        blank=True,
        help_text="Leave blank to generate a unique slug from the name.",
    )
    description = models.TextField(blank=True)
    image = models.ImageField(
        upload_to=category_image_upload_to,
        blank=True,
        validators=[
            image_extension_validator,
            validate_image_contents,
            validate_category_image_size,
        ],
        help_text="Optional local presentation image.",
    )
    image_url = models.URLField(
        max_length=500,
        blank=True,
        validators=[validate_image_url],
        help_text=(
            "Optional external presentation image. Format-checked only; "
            "Django does not fetch or verify the URL."
        ),
    )
    is_active = models.BooleanField(
        default=True,
        db_index=True,
        help_text="Inactive categories are hidden from public listings.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("name",)
        verbose_name = "category"
        verbose_name_plural = "categories"
        indexes = [
            Index(fields=["is_active", "name"], name="cat_active_name_idx"),
        ]

    def __str__(self):
        return self.name

    def clean(self):
        super().clean()
        self.name = " ".join((self.name or "").split())
        if not self.name:
            raise ValidationError({"name": "Enter a category name."})
        duplicate_name = (
            Category.objects.filter(name__iexact=self.name)
            .exclude(pk=self.pk)
            .exists()
        )
        if duplicate_name:
            raise ValidationError(
                {"name": "A category with this name already exists."}
            )
        if self.slug:
            self.slug = normalize_slug(self.slug, max_length=120)
            if not self.slug:
                raise ValidationError(
                    {"slug": "Enter a valid slug, or leave it blank."}
                )

    def save(self, *args, **kwargs):
        self.name = " ".join((self.name or "").split())
        if not self.slug:
            self.slug = build_unique_slug(
                self,
                self.name,
                max_length=120,
                fallback="category",
            )
        else:
            self.slug = normalize_slug(self.slug, max_length=120)
        super().save(*args, **kwargs)


class Tag(models.Model):
    """A reusable label that can be attached to many wallpapers."""

    name = models.CharField(max_length=80, unique=True)
    slug = models.SlugField(
        max_length=90,
        unique=True,
        blank=True,
        help_text="Leave blank to generate a unique slug from the name.",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("name",)
        verbose_name = "tag"
        verbose_name_plural = "tags"

    def __str__(self):
        return self.name

    def clean(self):
        super().clean()
        self.name = " ".join((self.name or "").split())
        if not self.name:
            raise ValidationError({"name": "Enter a tag name."})
        duplicate_name = (
            Tag.objects.filter(name__iexact=self.name)
            .exclude(pk=self.pk)
            .exists()
        )
        if duplicate_name:
            raise ValidationError({"name": "A tag with this name already exists."})
        if self.slug:
            self.slug = normalize_slug(self.slug, max_length=90)
            if not self.slug:
                raise ValidationError(
                    {"slug": "Enter a valid slug, or leave it blank."}
                )

    def save(self, *args, **kwargs):
        self.name = " ".join((self.name or "").split())
        if not self.slug:
            self.slug = build_unique_slug(
                self,
                self.name,
                max_length=90,
                fallback="tag",
            )
        else:
            self.slug = normalize_slug(self.slug, max_length=90)
        super().save(*args, **kwargs)
