"""Public query-string filtering for wallpaper collections.

Kept as plain functions instead of a filter-backend dependency so every
supported parameter is explicit and validated against real model fields:

- ``search``      → ``title`` or ``description`` (case-insensitive contains)
- ``category``    → exact category slug
- ``tag``         → exact tag slug; repeat the parameter for AND semantics
- ``orientation`` → landscape / portrait / square (derived from width/height)
- ``ordering``    → whitelisted fields, comma-separated
"""

from django.db.models import F, Q
from rest_framework.exceptions import ValidationError

ORIENTATIONS = {
    "landscape": lambda: Q(width__gt=F("height")),
    "portrait": lambda: Q(height__gt=F("width")),
    "square": lambda: Q(width=F("height")),
}

ORDERING_FIELDS = {
    "published_at": "published_at",
    "-published_at": "-published_at",
    "download_count": "download_count",
    "-download_count": "-download_count",
    "title": "title",
    "-title": "-title",
}

MAX_SEARCH_LENGTH = 100
MAX_TAG_FILTERS = 10


def _search(queryset, query):
    value = (query or "").strip()
    if not value:
        return queryset
    if len(value) > MAX_SEARCH_LENGTH:
        raise ValidationError(
            {
                "search": [
                    f"Search terms must be {MAX_SEARCH_LENGTH} "
                    "characters or fewer."
                ]
            }
        )
    return queryset.filter(
        Q(title__icontains=value) | Q(description__icontains=value)
    )


def _category(queryset, value):
    value = (value or "").strip()
    if not value:
        return queryset
    return queryset.filter(category__slug=value)


def _tags(queryset, values):
    """Apply repeated ``tag`` parameters with AND semantics.

    Each additional tag adds another join, so one row per *matching* wallpaper
    can appear several times; ``distinct()`` collapses the duplicates.
    """

    slugs = []
    for raw in values:
        for part in (raw or "").split(","):
            slug = part.strip()
            if slug and slug not in slugs:
                slugs.append(slug)
            if len(slugs) > MAX_TAG_FILTERS:
                raise ValidationError(
                    {
                        "tag": [
                            f"Use at most {MAX_TAG_FILTERS} tag filters per request."
                        ]
                    }
                )
    if not slugs:
        return queryset
    for slug in slugs:
        queryset = queryset.filter(tags__slug=slug)
    return queryset.distinct()


def _orientation(queryset, value):
    value = (value or "").strip().lower()
    if not value:
        return queryset
    condition = ORIENTATIONS.get(value)
    if condition is None:
        allowed = ", ".join(sorted(ORIENTATIONS))
        raise ValidationError(
            {"orientation": [f"Unsupported orientation. Choose one of: {allowed}."]}
        )
    return queryset.filter(condition())


def _ordering(queryset, value):
    """Apply a whitelisted ordering; unknown fields are a 400, not a silent
    fallback, so clients notice typos."""

    raw = (value or "").strip()
    if not raw:
        return queryset

    fields = []
    for token in raw.split(","):
        token = token.strip()
        if not token:
            continue
        ordering = ORDERING_FIELDS.get(token)
        if ordering is None:
            allowed = ", ".join(sorted(ORDERING_FIELDS))
            raise ValidationError(
                {"ordering": [f"Unsupported ordering field. Use: {allowed}."]}
            )
        if ordering not in fields:
            fields.append(ordering)
    if not fields:
        return queryset
    # A single deterministic tie-breaker at the end; appending it per field
    # would make every ordering after the first one irrelevant.
    fields.append("-pk")
    return queryset.order_by(*fields)


def apply_wallpaper_filters(queryset, query_params):
    queryset = _search(queryset, query_params.get("search"))
    queryset = _category(queryset, query_params.get("category"))
    queryset = _tags(queryset, query_params.getlist("tag"))
    queryset = _orientation(queryset, query_params.get("orientation"))
    return _ordering(queryset, query_params.get("ordering"))
