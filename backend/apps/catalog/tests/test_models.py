from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase

from apps.catalog.models import Category, Tag


class CategoryModelTests(TestCase):
    def test_create_generates_slug_and_timestamps(self):
        category = Category.objects.create(name="  Anime  ")

        self.assertEqual(category.name, "Anime")
        self.assertEqual(category.slug, "anime")
        self.assertTrue(category.is_active)
        self.assertIsNotNone(category.created_at)
        self.assertIsNotNone(category.updated_at)

    def test_name_is_required(self):
        category = Category(name="   ")

        with self.assertRaises(ValidationError) as raised:
            category.full_clean()

        self.assertIn("name", raised.exception.message_dict)

    def test_duplicate_name_is_rejected_even_with_different_case(self):
        Category.objects.create(name="Abstract")
        duplicate = Category(name="abstract")

        with self.assertRaises(ValidationError) as raised:
            duplicate.full_clean()

        self.assertIn("name", raised.exception.message_dict)

    def test_explicit_slug_is_normalized(self):
        category = Category.objects.create(
            name="Minimalist", slug="Minimalist-Walls"
        )

        self.assertEqual(category.slug, "minimalist-walls")

    def test_slug_collisions_receive_numeric_suffixes(self):
        first = Category.objects.create(name="C++")
        second = Category.objects.create(name="C#")

        self.assertEqual(first.slug, "c")
        self.assertEqual(second.slug, "c-2")

    def test_duplicate_explicit_slug_fails_at_the_database_level(self):
        Category.objects.create(name="First", slug="shared-slug")

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Category.objects.create(name="Second", slug="shared-slug")

    def test_non_latin_name_falls_back_to_a_stable_slug(self):
        first = Category.objects.create(name="アニメ")
        second = Category.objects.create(name="アニメ！")

        self.assertEqual(first.slug, "category")
        self.assertEqual(second.slug, "category-2")

    def test_slug_is_capped_to_the_field_length(self):
        category = Category.objects.create(name="Long", slug="a" * 150)

        self.assertEqual(len(category.slug), 120)

    def test_categories_are_ordered_by_name(self):
        Category.objects.create(name="Nature")
        Category.objects.create(name="Abstract")
        Category.objects.create(name="Minimalist")

        self.assertEqual(
            list(Category.objects.values_list("name", flat=True)),
            ["Abstract", "Minimalist", "Nature"],
        )

    def test_inactive_category_is_supported_without_hardcoded_names(self):
        category = Category.objects.create(name="Seasonal", is_active=False)

        self.assertFalse(category.is_active)
        self.assertEqual(Category.objects.filter(is_active=False).count(), 1)


class TagModelTests(TestCase):
    def test_create_generates_unique_slug(self):
        tag = Tag.objects.create(name="Blue Skies")

        self.assertEqual(tag.slug, "blue-skies")
        self.assertIsNotNone(tag.created_at)

    def test_duplicate_name_is_rejected(self):
        Tag.objects.create(name="mountains")
        duplicate = Tag(name="mountains")

        with self.assertRaises(ValidationError) as raised:
            duplicate.full_clean()

        self.assertIn("name", raised.exception.message_dict)

    def test_case_insensitive_duplicate_is_rejected_by_validation(self):
        Tag.objects.create(name="Warm")
        duplicate = Tag(name="warm")

        with self.assertRaises(ValidationError):
            duplicate.full_clean()

    def test_slug_collision_is_resolved_safely(self):
        Tag.objects.create(name="Neon!")
        second = Tag.objects.create(name="Neon?")

        self.assertEqual(second.slug, "neon-2")

    def test_explicit_duplicate_slug_is_rejected_by_the_database(self):
        Tag.objects.create(name="First", slug="tag-slug")

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Tag.objects.create(name="Second", slug="tag-slug")

    def test_tags_are_ordered_by_name(self):
        Tag.objects.create(name="warm")
        Tag.objects.create(name="autumn")

        self.assertEqual(
            list(Tag.objects.values_list("name", flat=True)),
            ["autumn", "warm"],
        )
