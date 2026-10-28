"""Slug helpers shared by catalog and wallpaper models."""

from django.utils.text import slugify


def normalize_slug(value, *, max_length):
    """Return a lowercase, URL-safe slug capped at ``max_length``.

    ``slugify`` also strips characters that are unsafe in URLs. If the value
    cannot produce a slug (for example, a name written entirely in a script
    without ASCII transliteration), an empty string is returned and callers
    fall back to a stable model-specific prefix.
    """

    return slugify(value or "")[:max_length].strip("-")


def build_unique_slug(
    instance,
    source,
    *,
    slug_field="slug",
    max_length,
    fallback,
):
    """Build a slug that is unique for ``instance``'s model.

    An existing value on the instance wins over ``source``; otherwise the
    source text (usually a name or title) is slugified. Duplicates receive a
    numeric suffix (``-2``, ``-3``, ...). The database's unique constraint
    remains the final guard against concurrent writes.
    """

    base = normalize_slug(
        getattr(instance, slug_field, "") or source,
        max_length=max_length,
    )
    if not base:
        base = fallback

    manager = instance.__class__._default_manager
    candidate = base
    index = 2
    while (
        manager.filter(**{slug_field: candidate})
        .exclude(pk=instance.pk)
        .exists()
    ):
        suffix = f"-{index}"
        candidate = f"{base[: max_length - len(suffix)]}{suffix}"
        index += 1
    return candidate
