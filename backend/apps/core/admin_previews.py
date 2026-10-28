"""Small, escaped preview helpers for Django admin.

Uploaded files are served from our own media storage. External URLs are shown
as links rather than embedded images so opening an admin page does not make
the administrator's browser request a third-party resource.
"""

from urllib.parse import urlsplit

from django.utils.html import format_html


def uploaded_image_preview(field_file, *, max_height=64, max_width=120):
    if not field_file:
        return "—"
    try:
        url = field_file.url
    except (ValueError, AttributeError):
        return "—"
    return format_html(
        '<img src="{}" alt="" loading="lazy" '
        'style="max-height:{}px;max-width:{}px;object-fit:cover;'
        'border-radius:4px;">',
        url,
        max_height,
        max_width,
    )


def external_image_link(url):
    """Return a safe link, or an em dash for empty/unsupported values."""

    if not url:
        return "—"
    parts = urlsplit(url)
    if parts.scheme.lower() not in {"http", "https"}:
        return "—"
    return format_html(
        '<a href="{}" target="_blank" rel="noopener noreferrer">'
        "Open external image</a>",
        url,
    )
