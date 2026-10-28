from io import BytesIO

from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError, models, transaction
from django.db.models.deletion import ProtectedError
from django.test import TestCase, override_settings
from PIL import Image

from apps.catalog.models import Category, Tag
from apps.wallpapers.models import Wallpaper


def image_bytes(image_format="PNG", size=(8, 8)):
    buffer = BytesIO()
    Image.new("RGB", size, (30, 120, 200)).save(buffer, format=image_format)
    return buffer.getvalue()


def upload(name="wallpaper.png", content=None, content_type="image/png"):
    return SimpleUploadedFile(
        name,
        content if content is not None else image_bytes(),
        content_type=content_type,
    )


class WallpaperModelTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.category = Category.objects.create(name="Nature")
        cls.tag = Tag.objects.create(name="mountains")

    def test_external_url_is_a_valid_image_source(self):
        wallpaper = Wallpaper(
            title="Altai",
            category=self.category,
            image_url="https://images.example.com/altai.jpg?w=2560",
        )

        wallpaper.full_clean()
        wallpaper.save()

        self.assertEqual(wallpaper.slug, "altai")
        self.assertTrue(wallpaper.has_usable_image)
        self.assertEqual(wallpaper.status, Wallpaper.Status.DRAFT)
        self.assertEqual(wallpaper.download_count, 0)
        self.assertIsNone(wallpaper.published_at)
        self.assertEqual(wallpaper.license_status, Wallpaper.LicenseStatus.UNKNOWN)

    def test_uploaded_image_is_a_valid_image_source(self):
        wallpaper = Wallpaper(
            title="Uploaded",
            category=self.category,
            image=upload(),
        )

        wallpaper.full_clean()
        wallpaper.save()

        self.assertTrue(wallpaper.image.name.startswith("wallpapers/"))
        self.assertNotIn("wallpaper.png", wallpaper.image.name)
        self.assertTrue(wallpaper.has_usable_image)

    def test_wallpaper_requires_at_least_one_image_source(self):
        wallpaper = Wallpaper(title="No image", category=self.category)

        with self.assertRaises(ValidationError) as raised:
            wallpaper.full_clean()

        self.assertIn("image_url", raised.exception.message_dict)

    def test_published_wallpaper_without_image_is_rejected_by_validation(self):
        wallpaper = Wallpaper(
            title="Invalid published",
            category=self.category,
            status=Wallpaper.Status.PUBLISHED,
        )

        with self.assertRaises(ValidationError) as raised:
            wallpaper.full_clean()

        self.assertIn("image_url", raised.exception.message_dict)
        self.assertFalse(wallpaper.has_usable_image)

    def test_database_rejects_publishing_without_an_image_source(self):
        wallpaper = Wallpaper(
            title="Invalid published",
            category=self.category,
            status=Wallpaper.Status.PUBLISHED,
        )

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                wallpaper.save()

    def test_publishing_sets_published_at_once(self):
        wallpaper = Wallpaper.objects.create(
            title="Published",
            category=self.category,
            image_url="https://images.example.com/a.jpg",
            status=Wallpaper.Status.PUBLISHED,
        )

        first_published_at = wallpaper.published_at
        self.assertIsNotNone(first_published_at)

        wallpaper.title = "Published again"
        wallpaper.save()
        wallpaper.refresh_from_db()

        self.assertEqual(wallpaper.published_at, first_published_at)

    def test_invalid_external_urls_are_rejected(self):
        for value in (
            "not-a-url",
            "ftp://images.example.com/a.jpg",
            "https://user:password@images.example.com/a.jpg",
            "javascript:alert(1)",
        ):
            with self.subTest(value=value):
                wallpaper = Wallpaper(
                    title="Bad URL",
                    category=self.category,
                    image_url=value,
                )
                with self.assertRaises(ValidationError):
                    wallpaper.full_clean()

    def test_extension_is_validated(self):
        wallpaper = Wallpaper(
            title="Text file",
            category=self.category,
            image=upload(name="notes.txt", content=b"not an image"),
        )

        with self.assertRaises(ValidationError) as raised:
            wallpaper.full_clean()

        self.assertIn("image", raised.exception.message_dict)

    def test_non_image_bytes_are_rejected(self):
        wallpaper = Wallpaper(
            title="Fake image",
            category=self.category,
            image=upload(name="fake.png", content=b"<script>alert(1)</script>"),
        )

        with self.assertRaises(ValidationError) as raised:
            wallpaper.full_clean()

        self.assertIn("image", raised.exception.message_dict)
        self.assertIn(
            "valid image",
            " ".join(raised.exception.message_dict["image"]).lower(),
        )

    def test_extension_must_match_image_contents(self):
        wallpaper = Wallpaper(
            title="Mismatch",
            category=self.category,
            image=upload(
                name="looks-like.png",
                content=image_bytes("JPEG"),
                content_type="image/png",
            ),
        )

        with self.assertRaises(ValidationError) as raised:
            wallpaper.full_clean()

        self.assertIn("extension", " ".join(raised.exception.message_dict["image"]))

    @override_settings(WALLPAPER_IMAGE_MAX_BYTES=10)
    def test_upload_size_limit_is_enforced(self):
        wallpaper = Wallpaper(
            title="Too large",
            category=self.category,
            image=upload(),
        )

        with self.assertRaises(ValidationError) as raised:
            wallpaper.full_clean()

        self.assertIn("or smaller", str(raised.exception).lower())

    @override_settings(WALLPAPER_THUMBNAIL_MAX_BYTES=10)
    def test_thumbnail_size_limit_is_enforced(self):
        wallpaper = Wallpaper(
            title="Thumbnail too large",
            category=self.category,
            image_url="https://images.example.com/a.jpg",
            thumbnail=upload(name="thumb.png"),
        )

        with self.assertRaises(ValidationError) as raised:
            wallpaper.full_clean()

        self.assertIn("thumbnail", raised.exception.message_dict)

    def test_category_and_tag_relationships(self):
        wallpaper = Wallpaper.objects.create(
            title="Altai",
            category=self.category,
            image_url="https://images.example.com/a.jpg",
        )
        other = Wallpaper.objects.create(
            title="Autumn",
            category=self.category,
            image_url="https://images.example.com/b.jpg",
        )
        wallpaper.tags.add(self.tag)
        other.tags.add(self.tag)

        self.assertEqual(self.category.wallpapers.count(), 2)
        self.assertEqual(self.tag.wallpapers.count(), 2)
        self.assertIn(wallpaper, self.tag.wallpapers.all())
        self.assertIn(self.tag, wallpaper.tags.all())

    def test_category_with_wallpapers_is_protected(self):
        Wallpaper.objects.create(
            title="Protected",
            category=self.category,
            image_url="https://images.example.com/a.jpg",
        )

        with self.assertRaises(ProtectedError):
            self.category.delete()

    def test_deleting_a_tag_does_not_delete_wallpapers(self):
        wallpaper = Wallpaper.objects.create(
            title="Altai",
            category=self.category,
            image_url="https://images.example.com/a.jpg",
        )
        wallpaper.tags.add(self.tag)

        self.tag.delete()

        self.assertTrue(Wallpaper.objects.filter(pk=wallpaper.pk).exists())
        self.assertEqual(wallpaper.tags.count(), 0)

    def test_title_collisions_receive_unique_slugs(self):
        first = Wallpaper.objects.create(
            title="Altai",
            category=self.category,
            image_url="https://images.example.com/a.jpg",
        )
        second = Wallpaper.objects.create(
            title="Altai",
            category=self.category,
            image_url="https://images.example.com/b.jpg",
        )

        self.assertEqual(first.slug, "altai")
        self.assertEqual(second.slug, "altai-2")

    def test_documented_licence_requires_details(self):
        wallpaper = Wallpaper(
            title="Licence",
            category=self.category,
            image_url="https://images.example.com/a.jpg",
            license_status=Wallpaper.LicenseStatus.DOCUMENTED,
        )

        with self.assertRaises(ValidationError) as raised:
            wallpaper.full_clean()
        self.assertIn("license_name", raised.exception.message_dict)

        wallpaper.license_name = "CC BY-SA 4.0"
        wallpaper.license_url = "https://creativecommons.org/licenses/by-sa/4.0/"
        wallpaper.full_clean()

    def test_download_counter_is_an_integer_and_defaults_to_zero(self):
        field = Wallpaper._meta.get_field("download_count")

        self.assertEqual(field.get_internal_type(), "PositiveBigIntegerField")
        self.assertEqual(field.default, 0)

    def test_images_are_file_paths_not_database_blobs(self):
        for name in ("image", "thumbnail"):
            field = Wallpaper._meta.get_field(name)
            self.assertIsInstance(field, models.FileField)
            self.assertNotIsInstance(field, models.TextField)

    def test_filtering_indexes_and_constraints_are_declared(self):
        index_names = {index.name for index in Wallpaper._meta.indexes}
        constraint_names = {item.name for item in Wallpaper._meta.constraints}

        self.assertEqual(
            index_names,
            {
                "wp_status_published_idx",
                "wp_cat_status_pub_idx",
                "wp_downloads_idx",
            },
        )
        self.assertEqual(
            constraint_names,
            {"wp_status_valid", "wp_published_has_image"},
        )
