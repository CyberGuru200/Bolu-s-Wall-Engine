"""Validators shared by uploaded images and external image references.

Django's ``ImageField`` delegates to Pillow in forms, but model-level
``full_clean()`` does not inspect image bytes. These validators add explicit
format, content, and size checks so model validation and the admin agree.
"""

from pathlib import PurePosixPath
from urllib.parse import urlsplit

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator
from PIL import Image, UnidentifiedImageError

ALLOWED_IMAGE_EXTENSIONS = ("jpg", "jpeg", "png", "webp", "gif")

# Pillow's format name for each extension we accept. A file whose bytes do not
# match its extension is rejected rather than silently stored.
IMAGE_FORMAT_BY_EXTENSION = {
    ".jpg": "JPEG",
    ".jpeg": "JPEG",
    ".png": "PNG",
    ".webp": "WEBP",
    ".gif": "GIF",
}

image_extension_validator = FileExtensionValidator(
    allowed_extensions=ALLOWED_IMAGE_EXTENSIONS,
    message=(
        "Unsupported image format. Allowed formats: JPEG, PNG, WebP, and GIF."
    ),
)


def validate_image_url(value):
    """Require an absolute http(s) image URL.

    This checks the shape of the URL only. It deliberately does **not** fetch
    the URL, so a saved value is not proof that the image exists, is reachable,
    or is licensed for use.
    """

    parts = urlsplit(value)
    if parts.scheme.lower() not in {"http", "https"} or not parts.netloc:
        raise ValidationError(
            "Enter an absolute http:// or https:// image URL.",
            code="invalid_image_url_scheme",
        )
    if parts.username or parts.password:
        raise ValidationError(
            "Image URLs must not contain embedded credentials.",
            code="invalid_image_url_credentials",
        )


def _file_size(value):
    size = getattr(value, "size", None)
    if size is None:
        return None
    return size


def _check_size(value, *, limit):
    size = _file_size(value)
    if size is not None and size > limit:
        if limit >= 1024 * 1024:
            maximum_label = f"{limit / (1024 * 1024):g} MB"
        else:
            maximum_label = f"{limit} bytes"
        raise ValidationError(
            f"Image files must be {maximum_label} or smaller "
            f"(this file is {size / (1024 * 1024):.1f} MB).",
            code="image_too_large",
        )


def validate_wallpaper_image_size(value):
    _check_size(
        value,
        limit=settings.WALLPAPER_IMAGE_MAX_BYTES,
    )


def validate_thumbnail_image_size(value):
    _check_size(
        value,
        limit=settings.WALLPAPER_THUMBNAIL_MAX_BYTES,
    )


def validate_category_image_size(value):
    _check_size(
        value,
        limit=settings.CATEGORY_IMAGE_MAX_BYTES,
    )


def validate_image_contents(value):
    """Verify that the uploaded bytes are a real image of an allowed format.

    The file pointer is restored afterwards so Django can save the upload.
    ``Image.verify()`` is a structural check, not a full decode; it is the
    standard Pillow check for rejecting non-images and truncated headers.
    """

    try:
        file = getattr(value, "file", value)
    except (OSError, ValueError) as exc:
        raise ValidationError(
            "The stored image could not be read.",
            code="unreadable_image",
        ) from exc
    try:
        file.seek(0)
    except (AttributeError, OSError):
        pass

    try:
        with Image.open(file) as image:
            image_format = image.format
            image.verify()
    except (UnidentifiedImageError, OSError, ValueError, SyntaxError) as exc:
        raise ValidationError(
            "Upload a valid image file (JPEG, PNG, WebP, or GIF).",
            code="invalid_image",
        ) from exc
    finally:
        try:
            file.seek(0)
        except (AttributeError, OSError):
            pass

    if image_format not in set(IMAGE_FORMAT_BY_EXTENSION.values()):
        raise ValidationError(
            "Unsupported image format. Allowed formats: JPEG, PNG, WebP, and GIF.",
            code="unsupported_image_format",
        )

    name = getattr(value, "name", "") or ""
    suffix = PurePosixPath(name).suffix.lower()
    expected_format = IMAGE_FORMAT_BY_EXTENSION.get(suffix)
    if expected_format is None:
        raise ValidationError(
            "Unsupported image format. Allowed formats: JPEG, PNG, WebP, and GIF.",
            code="unsupported_image_format",
        )
    if image_format != expected_format:
        raise ValidationError(
            "The file contents do not match the file extension.",
            code="image_extension_mismatch",
        )
