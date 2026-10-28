from django.contrib import admin
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from apps.catalog.admin import CategoryAdmin, TagAdmin
from apps.catalog.models import Category, Tag

User = get_user_model()


class CatalogAdminTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.superuser = User.objects.create_superuser(
            username="admin", email="admin@example.com", password="admin-pass"
        )
        cls.category = Category.objects.create(
            name="Anime", description="Animated artwork"
        )
        cls.tag = Tag.objects.create(name="neon")

    def setUp(self):
        self.client.force_login(self.superuser)

    def test_models_are_registered(self):
        self.assertIsInstance(admin.site._registry[Category], CategoryAdmin)
        self.assertIsInstance(admin.site._registry[Tag], TagAdmin)

    def test_category_changelist_and_filters_render(self):
        url = reverse("admin:catalog_category_changelist")

        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Anime")

        self.assertEqual(self.client.get(url, {"q": "Ani"}).status_code, 200)
        self.assertEqual(
            self.client.get(url, {"is_active__exact": "1"}).status_code, 200
        )

    def test_category_add_page_renders(self):
        response = self.client.get(reverse("admin:catalog_category_add"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'name="slug"')

    def test_tag_changelist_and_search_render(self):
        url = reverse("admin:catalog_tag_changelist")

        self.assertEqual(self.client.get(url).status_code, 200)
        self.assertContains(self.client.get(url, {"q": "neon"}), "neon")

    def test_category_admin_configuration(self):
        model_admin = admin.site._registry[Category]
        self.assertEqual(model_admin.prepopulated_fields, {"slug": ("name",)})
        self.assertIn("created_at", model_admin.readonly_fields)
        self.assertIn("updated_at", model_admin.readonly_fields)
        self.assertIn("is_active", model_admin.list_display)
        self.assertIn("image_preview", model_admin.list_display)
        self.assertIn("name", model_admin.search_fields)
        self.assertEqual(model_admin.list_editable, ("is_active",))

    def test_tag_admin_configuration(self):
        model_admin = admin.site._registry[Tag]
        self.assertEqual(model_admin.prepopulated_fields, {"slug": ("name",)})
        self.assertIn("created_at", model_admin.readonly_fields)
        self.assertIn("wallpaper_count", model_admin.list_display)

    def test_category_deactivate_action(self):
        response = self.client.post(
            reverse("admin:catalog_category_changelist"),
            {
                "action": "deactivate_selected",
                "_selected_action": [self.category.pk],
                "index": "0",
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.category.refresh_from_db()
        self.assertFalse(self.category.is_active)
