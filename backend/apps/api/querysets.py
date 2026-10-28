"""Reusable querysets for the public API.

Every public endpoint starts from these querysets so "published" and "active"
mean the same thing everywhere:

- a wallpaper is public only when it is ``published`` **and** its category is
  active;
- a category is public only when it is active;
- a tag is public only when at least one published wallpaper uses it.
"""

from django.db.models import Count, Q

from apps.catalog.models import Category, Tag
from apps.wallpapers.models import Wallpaper

PUBLISHED_FILTER = Q(
    wallpapers__status=Wallpaper.Status.PUBLISHED,
    wallpapers__category__is_active=True,
)


def published_wallpapers():
    return (
        Wallpaper.objects.filter(
            status=Wallpaper.Status.PUBLISHED,
            category__is_active=True,
        )
        .select_related("category")
        .prefetch_related("tags")
    )


def active_categories():
    return (
        Category.objects.filter(is_active=True)
        .annotate(
            wallpaper_count=Count(
                "wallpapers",
                filter=Q(
                    wallpapers__status=Wallpaper.Status.PUBLISHED,
                    wallpapers__category__is_active=True,
                ),
            )
        )
        .order_by("name")
    )


def public_tags():
    return (
        Tag.objects.filter(PUBLISHED_FILTER)
        .annotate(
            wallpaper_count=Count(
                "wallpapers",
                filter=PUBLISHED_FILTER,
                distinct=True,
            )
        )
        .distinct()
        .order_by("name")
    )
