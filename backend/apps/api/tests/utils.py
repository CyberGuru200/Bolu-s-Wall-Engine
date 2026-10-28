from io import BytesIO

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image

from apps.catalog.models import Category, Tag
from apps.wallpapers.models import Wallpaper

User = get_user_model()

EXTERNAL_IMAGE = "https://images.example.com/wallpaper.jpg"


def image_upload(name="wallpaper.png", size=(8, 8), color=(20, 90, 160)):
    buffer = BytesIO()
    Image.new("RGB", size, color).save(buffer, format="PNG")
    return SimpleUploadedFile(name, buffer.getvalue(), content_type="image/png")


def make_category(name="Anime", *, is_active=True, **kwargs):
    return Category.objects.create(name=name, is_active=is_active, **kwargs)


def make_tag(name="neon"):
    return Tag.objects.create(name=name)


def make_wallpaper(
    title="Neon Tokyo",
    *,
    category=None,
    status=Wallpaper.Status.PUBLISHED,
    tags=(),
    **kwargs,
):
    category = category or make_category(name=f"Category {Category.objects.count()}")
    kwargs.setdefault("image_url", EXTERNAL_IMAGE)
    wallpaper = Wallpaper.objects.create(
        title=title,
        category=category,
        status=status,
        **kwargs,
    )
    if tags:
        wallpaper.tags.set(tags)
    return wallpaper


def make_user(username="bolu", password="test-pass-1234"):
    return User.objects.create_user(username=username, password=password)
