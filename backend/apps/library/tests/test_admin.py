from django.contrib import admin
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from apps.catalog.models import Category
from apps.library.admin import LikeAdmin, SavedWallpaperAdmin
from apps.library.models import Like, SavedWallpaper
from apps.wallpapers.models import Wallpaper

User = get_user_model()


class LibraryAdminTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.superuser = User.objects.create_superuser(
            username="admin", email="admin@example.com", password="admin-pass"
        )
        cls.user = User.objects.create_user(username="bolu", password="test-pass")
        category = Category.objects.create(name="Abstract")
        cls.wallpaper = Wallpaper.objects.create(
            title="Autumn",
            category=category,
            image_url="https://images.example.com/autumn.jpg",
            status=Wallpaper.Status.PUBLISHED,
        )
        cls.like = Like.objects.create(user=cls.user, wallpaper=cls.wallpaper)
        cls.saved = SavedWallpaper.objects.create(
            user=cls.user, wallpaper=cls.wallpaper
        )

    def setUp(self):
        self.client.force_login(self.superuser)

    def test_models_are_registered(self):
        self.assertIsInstance(admin.site._registry[Like], LikeAdmin)
        self.assertIsInstance(
            admin.site._registry[SavedWallpaper], SavedWallpaperAdmin
        )

    def test_like_admin_is_read_only(self):
        url = reverse("admin:library_like_changelist")

        changelist = self.client.get(url)
        self.assertEqual(changelist.status_code, 200)
        self.assertContains(changelist, "bolu")

        add_page = self.client.get(reverse("admin:library_like_add"))
        self.assertEqual(add_page.status_code, 403)

        model_admin = admin.site._registry[Like]
        self.assertFalse(model_admin.has_add_permission(request=None))
        self.assertFalse(model_admin.has_change_permission(request=None))

    def test_like_search_matches_username_and_wallpaper(self):
        url = reverse("admin:library_like_changelist")

        self.assertContains(self.client.get(url, {"q": "bolu"}), "Autumn")
        self.assertContains(self.client.get(url, {"q": "Autumn"}), "bolu")

    def test_saved_wallpaper_admin_is_read_only(self):
        url = reverse("admin:library_savedwallpaper_changelist")

        changelist = self.client.get(url)
        self.assertEqual(changelist.status_code, 200)
        self.assertContains(changelist, "bolu")

        add_page = self.client.get(reverse("admin:library_savedwallpaper_add"))
        self.assertEqual(add_page.status_code, 403)

        model_admin = admin.site._registry[SavedWallpaper]
        self.assertFalse(model_admin.has_add_permission(request=None))
        self.assertFalse(model_admin.has_change_permission(request=None))

    def test_existing_record_is_visible_but_not_editable(self):
        response = self.client.get(
            reverse("admin:library_like_change", args=[self.like.pk])
        )

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'name="_save"')
