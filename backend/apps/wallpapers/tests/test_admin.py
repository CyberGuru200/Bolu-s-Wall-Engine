from io import BytesIO

from django.contrib import admin
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from PIL import Image

from apps.catalog.models import Category, Tag
from apps.wallpapers.admin import WallpaperAdmin
from apps.wallpapers.models import Wallpaper

User = get_user_model()


def png_upload(name="admin-upload.png"):
    buffer = BytesIO()
    Image.new("RGB", (8, 8), (200, 80, 40)).save(buffer, format="PNG")
    return SimpleUploadedFile(
        name, buffer.getvalue(), content_type="image/png"
    )


class WallpaperAdminTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.superuser = User.objects.create_superuser(
            username="admin", email="admin@example.com", password="admin-pass"
        )
        cls.category = Category.objects.create(name="Nature")
        cls.tag = Tag.objects.create(name="mountains")
        cls.draft = Wallpaper.objects.create(
            title="Altai",
            category=cls.category,
            image_url="https://images.example.com/altai.jpg",
        )
        cls.published = Wallpaper.objects.create(
            title="Autumn",
            category=cls.category,
            image_url="https://images.example.com/autumn.jpg",
            status=Wallpaper.Status.PUBLISHED,
        )

    def setUp(self):
        self.client.force_login(self.superuser)

    def base_form_data(self, **overrides):
        data = {
            "title": "Admin added",
            "slug": "",
            "description": "Added through the admin",
            "category": self.category.pk,
            "tags": [self.tag.pk],
            "image_url": "",
            "source_url": "https://example.com/source",
            "license_name": "CC BY 4.0",
            "license_url": "https://creativecommons.org/licenses/by/4.0/",
            "license_status": "documented",
            "width": "2560",
            "height": "1440",
            "file_size": "123456",
            "status": "draft",
            "_save": "Save",
        }
        data.update(overrides)
        return data

    def test_model_is_registered(self):
        self.assertIsInstance(admin.site._registry[Wallpaper], WallpaperAdmin)

    def test_changelist_renders_with_filters_and_previews(self):
        url = reverse("admin:wallpapers_wallpaper_changelist")

        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Altai")
        self.assertContains(response, "Open external image")

        self.assertEqual(self.client.get(url, {"status__exact": "draft"}).status_code, 200)
        self.assertEqual(self.client.get(url, {"q": "Altai"}).status_code, 200)
        self.assertEqual(
            self.client.get(url, {"category__id__exact": self.category.pk}).status_code,
            200,
        )

    def test_admin_can_add_wallpaper_with_external_url_and_tags(self):
        response = self.client.post(
            reverse("admin:wallpapers_wallpaper_add"),
            self.base_form_data(
                title="External wallpaper",
                image_url="https://images.example.com/external.jpg",
            ),
        )

        self.assertEqual(response.status_code, 302)
        wallpaper = Wallpaper.objects.get(title="External wallpaper")
        self.assertEqual(wallpaper.slug, "external-wallpaper")
        self.assertEqual(wallpaper.category, self.category)
        self.assertEqual(list(wallpaper.tags.all()), [self.tag])
        self.assertEqual(wallpaper.status, Wallpaper.Status.DRAFT)

    def test_admin_can_add_wallpaper_with_uploaded_image(self):
        response = self.client.post(
            reverse("admin:wallpapers_wallpaper_add"),
            self.base_form_data(
                title="Uploaded wallpaper",
                image=png_upload(),
            ),
        )

        self.assertEqual(response.status_code, 302)
        wallpaper = Wallpaper.objects.get(title="Uploaded wallpaper")
        self.assertTrue(wallpaper.image.name.startswith("wallpapers/"))
        self.assertTrue(wallpaper.has_usable_image)

    def test_admin_can_publish_by_editing_the_status(self):
        response = self.client.post(
            reverse("admin:wallpapers_wallpaper_change", args=[self.draft.pk]),
            self.base_form_data(
                title=self.draft.title,
                slug=self.draft.slug,
                image_url=self.draft.image_url,
                status="published",
            ),
        )

        self.assertEqual(response.status_code, 302)
        self.draft.refresh_from_db()
        self.assertEqual(self.draft.status, Wallpaper.Status.PUBLISHED)
        self.assertIsNotNone(self.draft.published_at)

    def test_admin_publish_action_validates_the_image_source(self):
        response = self.client.post(
            reverse("admin:wallpapers_wallpaper_changelist"),
            {
                "action": "publish_selected",
                "_selected_action": [self.draft.pk],
                "index": "0",
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.draft.refresh_from_db()
        self.assertEqual(self.draft.status, Wallpaper.Status.PUBLISHED)
        self.assertIsNotNone(self.draft.published_at)

    def test_publish_action_skips_records_without_an_image(self):
        invalid = Wallpaper.objects.create(
            title="No image", category=self.category
        )

        response = self.client.post(
            reverse("admin:wallpapers_wallpaper_changelist"),
            {
                "action": "publish_selected",
                "_selected_action": [invalid.pk],
                "index": "0",
            },
            follow=True,
        )

        invalid.refresh_from_db()
        self.assertEqual(invalid.status, Wallpaper.Status.DRAFT)
        self.assertContains(response, "Skipped 1 wallpaper")

    def test_unpublish_action_moves_records_to_draft(self):
        response = self.client.post(
            reverse("admin:wallpapers_wallpaper_changelist"),
            {
                "action": "unpublish_selected",
                "_selected_action": [self.published.pk],
                "index": "0",
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.published.refresh_from_db()
        self.assertEqual(self.published.status, Wallpaper.Status.DRAFT)
        self.assertIsNotNone(self.published.published_at)

    def test_external_urls_are_linked_not_embedded(self):
        model_admin = admin.site._registry[Wallpaper]

        html = str(model_admin.image_preview(self.draft))

        self.assertIn("Open external image", html)
        self.assertIn('rel="noopener noreferrer"', html)
        self.assertNotIn("<img", html)

    def test_uploaded_images_get_an_embedded_preview(self):
        wallpaper = Wallpaper.objects.create(
            title="Local",
            category=self.category,
            image=png_upload("local.png"),
        )
        model_admin = admin.site._registry[Wallpaper]

        html = str(model_admin.image_preview(wallpaper))

        self.assertIn("<img", html)
        self.assertIn('loading="lazy"', html)

    def test_admin_configuration(self):
        model_admin = admin.site._registry[Wallpaper]
        self.assertEqual(model_admin.prepopulated_fields, {"slug": ("title",)})
        self.assertEqual(model_admin.filter_horizontal, ("tags",))
        self.assertEqual(model_admin.autocomplete_fields, ("category",))
        for field in ("created_at", "updated_at", "download_count"):
            self.assertIn(field, model_admin.readonly_fields)
        for field in ("status", "category"):
            self.assertIn(field, model_admin.list_filter)
        for field in ("title", "slug", "description"):
            self.assertIn(field, model_admin.search_fields)
