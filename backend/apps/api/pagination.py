from django.conf import settings
from rest_framework.pagination import PageNumberPagination


class StandardPagination(PageNumberPagination):
    """Page-number pagination used by every public and library list.

    The default size and the hard cap come from settings so they can be tuned
    per environment without code changes. ``page_size`` is honoured only up to
    ``API_MAX_PAGE_SIZE``.
    """

    page_size_query_param = "page_size"

    def __init__(self):
        super().__init__()
        self.page_size = getattr(settings, "API_PAGE_SIZE", 24)
        self.max_page_size = getattr(settings, "API_MAX_PAGE_SIZE", 60)
