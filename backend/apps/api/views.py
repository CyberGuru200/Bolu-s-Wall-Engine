"""REST API views.

Public catalogue endpoints are read-only and anonymous. Library endpoints are
session-authenticated and always scoped to ``request.user``; a client cannot
choose whose likes or saves it reads or changes.
"""

from django.db.models import F
from django.shortcuts import get_object_or_404
from rest_framework import generics, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from apps.library.models import Like, SavedWallpaper
from apps.wallpapers.models import Wallpaper

from .filters import apply_wallpaper_filters
from .pagination import StandardPagination
from .querysets import active_categories, public_tags, published_wallpapers
from .serializers import (
    CategorySerializer,
    LikeSerializer,
    SavedWallpaperSerializer,
    TagSerializer,
    WallpaperDetailSerializer,
    WallpaperSerializer,
    WallpaperSlugSerializer,
)


class CategoryViewSet(viewsets.ReadOnlyModelViewSet):
    """Read-only list/detail of active categories."""

    serializer_class = CategorySerializer
    permission_classes = [AllowAny]
    lookup_field = "slug"
    pagination_class = StandardPagination

    def get_queryset(self):
        return active_categories()


class TagViewSet(viewsets.ReadOnlyModelViewSet):
    """Read-only list/detail of tags used by published wallpapers."""

    serializer_class = TagSerializer
    permission_classes = [AllowAny]
    lookup_field = "slug"
    pagination_class = StandardPagination

    def get_queryset(self):
        return public_tags()


class WallpaperViewSet(viewsets.ReadOnlyModelViewSet):
    """Read-only list/detail of published wallpapers plus download actions."""

    permission_classes = [AllowAny]
    lookup_field = "slug"
    pagination_class = StandardPagination

    # Read by ScopedRateThrottle; only the download action attaches that
    # throttle class, so other actions are unaffected.
    throttle_scope = "downloads"

    def get_queryset(self):
        return published_wallpapers()

    def get_serializer_class(self):
        if self.action == "retrieve":
            return WallpaperDetailSerializer
        return WallpaperSerializer

    def filter_queryset(self, queryset):
        if self.action in {"list", "popular"}:
            return apply_wallpaper_filters(queryset, self.request.query_params)
        return queryset

    @action(detail=False, methods=["get"], url_path="popular")
    def popular(self, request):
        """All-time download ranking.

        This is explicitly **not** trending: the schema stores no
        time-windowed activity, so recent interest cannot be measured.
        """

        queryset = self.filter_queryset(self.get_queryset()).order_by(
            "-download_count", "-pk"
        )
        page = self.paginate_queryset(queryset)
        serializer = self.get_serializer(page, many=True)
        return self.get_paginated_response(serializer.data)

    @action(
        detail=True,
        methods=["post"],
        url_path="download",
        permission_classes=[AllowAny],
        authentication_classes=[],
        throttle_classes=[ScopedRateThrottle],
    )
    def download(self, request, slug=None):
        """Count a download and return the URL to fetch.

        The file is never proxied: uploaded images return their own media URL
        and external images return the stored URL exactly as configured. The
        response is JSON, not a redirect, so there is no open-redirect path.
        """

        wallpaper = get_object_or_404(
            Wallpaper.objects.only(
                "id",
                "slug",
                "image",
                "image_url",
                "thumbnail",
                "thumbnail_url",
                "download_count",
            ),
            slug=slug,
            status=Wallpaper.Status.PUBLISHED,
            category__is_active=True,
        )

        # F() makes the increment a single atomic UPDATE, so concurrent
        # downloads cannot overwrite each other's counts.
        updated = Wallpaper.objects.filter(
            pk=wallpaper.pk,
            status=Wallpaper.Status.PUBLISHED,
        ).update(download_count=F("download_count") + 1)
        if not updated:
            return Response(
                {"detail": "Wallpaper not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        wallpaper.refresh_from_db(fields=["download_count"])

        serializer = WallpaperSerializer(wallpaper, context={"request": request})
        data = serializer.data
        download_url = data.get("url")
        if not download_url:
            # Defensive: publication already requires an image source.
            return Response(
                {
                    "detail": "This wallpaper has no downloadable image source."
                },
                status=status.HTTP_409_CONFLICT,
            )

        return Response(
            {
                "slug": wallpaper.slug,
                "download_count": wallpaper.download_count,
                "image_source": data["image_source"],
                "download_url": download_url,
                "thumbnail_url": data["thumbnail_url"],
            }
        )


class UserLibraryMixin:
    """Shared plumbing for the current user's likes/saves."""

    permission_classes = [IsAuthenticated]
    pagination_class = StandardPagination
    queryset_model = None
    serializer_class = None
    input_serializer_class = WallpaperSlugSerializer
    ordering = ("-created_at", "-pk")

    def get_queryset(self):
        # Never accept a user identifier from the request.
        return (
            self.queryset_model.objects.filter(
                user=self.request.user,
                wallpaper__status=Wallpaper.Status.PUBLISHED,
                wallpaper__category__is_active=True,
            )
            .select_related("wallpaper__category")
            .prefetch_related("wallpaper__tags")
            .order_by(*self.ordering)
        )

    def create(self, request, *args, **kwargs):
        input_serializer = self.input_serializer_class(data=request.data)
        input_serializer.is_valid(raise_exception=True)
        wallpaper = get_object_or_404(
            published_wallpapers(),
            slug=input_serializer.validated_data["wallpaper"],
        )
        item, created = self.queryset_model.objects.get_or_create(
            user=request.user,
            wallpaper=wallpaper,
        )
        output = self.serializer_class(
            item, context=self.get_serializer_context()
        )
        # Idempotent: a duplicate request returns the existing row with 200.
        return Response(
            output.data,
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )


class LikeListCreateView(UserLibraryMixin, generics.ListCreateAPIView):
    queryset_model = Like
    serializer_class = LikeSerializer


class SavedWallpaperListCreateView(UserLibraryMixin, generics.ListCreateAPIView):
    queryset_model = SavedWallpaper
    serializer_class = SavedWallpaperSerializer


class UserWallpaperDetailView(APIView):
    """Check or remove one like/save for the authenticated user."""

    permission_classes = [IsAuthenticated]
    queryset_model = None
    timestamp_field = None

    def get(self, request, slug):
        wallpaper = get_object_or_404(published_wallpapers(), slug=slug)
        item = self.queryset_model.objects.filter(
            user=request.user, wallpaper=wallpaper
        ).first()
        return Response(
            {
                "wallpaper": wallpaper.slug,
                self.timestamp_field: item.created_at if item else None,
                "exists": item is not None,
            }
        )

    def delete(self, request, slug):
        wallpaper = get_object_or_404(published_wallpapers(), slug=slug)
        # Deleting an absent row is still 204: the desired end state holds.
        self.queryset_model.objects.filter(
            user=request.user, wallpaper=wallpaper
        ).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class LikeDetailView(UserWallpaperDetailView):
    queryset_model = Like
    timestamp_field = "liked_at"


class SavedWallpaperDetailView(UserWallpaperDetailView):
    queryset_model = SavedWallpaper
    timestamp_field = "saved_at"
