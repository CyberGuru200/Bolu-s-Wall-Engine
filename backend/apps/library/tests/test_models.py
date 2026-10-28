from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.test import TestCase

from apps.catalog.models import Category
from apps.library.models import Like, SavedWallpaper
from apps.wallpapers.models import Wallpaper

User = get_user_model()


class InteractionTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(username="bolu", password="test-pass")
        cls.other_user = User.objects.create_user(
            username="visitor", password="test-pass"
        )
        cls.category = Category.objects.create(name="Abstract")
        cls.wallpaper = Wallpaper.objects.create(
            title="Altai",
            category=cls.category,
            image_url="https://images.example.com/altai.jpg",
            status=Wallpaper.Status.PUBLISHED,
        )
        cls.other_wallpaper = Wallpaper.objects.create(
            title="Autumn",
            category=cls.category,
            image_url="https://images.example.com/autumn.jpg",
            status=Wallpaper.Status.PUBLISHED,
        )


class LikeModelTests(InteractionTestCase):
    def test_user_can_like_a_wallpaper(self):
        like = Like.objects.create(user=self.user, wallpaper=self.wallpaper)

        self.assertEqual(like.user, self.user)
        self.assertEqual(like.wallpaper, self.wallpaper)
        self.assertIsNotNone(like.created_at)
        self.assertEqual(self.user.wallpaper_likes.count(), 1)
        self.assertEqual(self.wallpaper.likes.count(), 1)

    def test_duplicate_like_is_rejected_by_the_database(self):
        Like.objects.create(user=self.user, wallpaper=self.wallpaper)

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Like.objects.create(user=self.user, wallpaper=self.wallpaper)

    def test_different_users_or_wallpapers_can_like(self):
        Like.objects.create(user=self.user, wallpaper=self.wallpaper)
        Like.objects.create(user=self.user, wallpaper=self.other_wallpaper)
        Like.objects.create(user=self.other_user, wallpaper=self.wallpaper)

        self.assertEqual(Like.objects.count(), 3)

    def test_deleting_a_user_cascades_to_likes(self):
        Like.objects.create(user=self.user, wallpaper=self.wallpaper)

        self.user.delete()

        self.assertEqual(Like.objects.count(), 0)
        self.assertTrue(Wallpaper.objects.filter(pk=self.wallpaper.pk).exists())

    def test_deleting_a_wallpaper_cascades_to_likes(self):
        Like.objects.create(user=self.user, wallpaper=self.wallpaper)

        self.wallpaper.delete()

        self.assertEqual(Like.objects.count(), 0)
        self.assertTrue(User.objects.filter(pk=self.user.pk).exists())

    def test_unique_constraint_and_index_are_declared(self):
        constraints = {item.name for item in Like._meta.constraints}
        indexes = {item.name for item in Like._meta.indexes}

        self.assertEqual(constraints, {"uniq_like_user_wallpaper"})
        self.assertEqual(indexes, {"like_wallpaper_created_idx"})


class SavedWallpaperModelTests(InteractionTestCase):
    def test_user_can_save_a_wallpaper(self):
        saved = SavedWallpaper.objects.create(
            user=self.user, wallpaper=self.wallpaper
        )

        self.assertEqual(saved.user, self.user)
        self.assertEqual(saved.wallpaper, self.wallpaper)
        self.assertIsNotNone(saved.created_at)
        self.assertEqual(self.user.saved_wallpapers.count(), 1)
        self.assertEqual(self.wallpaper.saves.count(), 1)

    def test_duplicate_save_is_rejected_by_the_database(self):
        SavedWallpaper.objects.create(user=self.user, wallpaper=self.wallpaper)

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                SavedWallpaper.objects.create(
                    user=self.user, wallpaper=self.wallpaper
                )

    def test_saved_collection_is_ordered_newest_first(self):
        first = SavedWallpaper.objects.create(
            user=self.user, wallpaper=self.wallpaper
        )
        second = SavedWallpaper.objects.create(
            user=self.user, wallpaper=self.other_wallpaper
        )

        self.assertEqual(
            list(SavedWallpaper.objects.filter(user=self.user)),
            [second, first],
        )

    def test_deleting_a_user_cascades_to_saves(self):
        SavedWallpaper.objects.create(user=self.user, wallpaper=self.wallpaper)

        self.user.delete()

        self.assertEqual(SavedWallpaper.objects.count(), 0)

    def test_deleting_a_wallpaper_cascades_to_saves(self):
        SavedWallpaper.objects.create(user=self.user, wallpaper=self.wallpaper)

        self.wallpaper.delete()

        self.assertEqual(SavedWallpaper.objects.count(), 0)

    def test_unique_constraint_and_index_are_declared(self):
        constraints = {item.name for item in SavedWallpaper._meta.constraints}
        indexes = {item.name for item in SavedWallpaper._meta.indexes}

        self.assertEqual(constraints, {"uniq_saved_user_wallpaper"})
        self.assertEqual(indexes, {"saved_user_created_idx"})
