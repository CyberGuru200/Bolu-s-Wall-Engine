"""Upload paths for user-provided images.

Stored names are generated (UUID + validated suffix) instead of trusting the
original filename, which avoids collisions and path traversal.
"""

from pathlib import PurePosixPath
from uuid import uuid4

from django.utils import timezone


def _upload_path(prefix, filename):
    suffix = PurePosixPath(filename or "").suffix.lower()[:10]
    return f"{prefix}/{timezone.now():%Y/%m}/{uuid4().hex}{suffix}"


def category_image_upload_to(instance, filename):
    return _upload_path("categories", filename)


def wallpaper_image_upload_to(instance, filename):
    return _upload_path("wallpapers", filename)


def wallpaper_thumbnail_upload_to(instance, filename):
    return _upload_path("wallpapers/thumbnails", filename)
