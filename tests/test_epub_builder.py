import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

pytest.importorskip("PIL", reason="Pillow not installed (images extra)")

from PIL import Image
from extraction.builders.epub_builder import EpubBuilder
from extraction.scrapers.image_scraper import ImageData


@pytest.fixture
def temp_dir():
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def sample_image_path(temp_dir):
    image_path = temp_dir / "test_image.jpg"

    img = Image.new('RGB', (800, 600), color='red')
    img.save(image_path)

    return image_path


@pytest.fixture
def sample_image_data(sample_image_path):
    return ImageData(
        url="https://example.com/test.jpg",
        local_path=sample_image_path,
        alt_text="Test image",
        width=800,
        height=600,
        format="JPEG",
        size_bytes=12345
    )


class TestEpubBuilder:
    def test_epub_builder_initialization(self):
        builder = EpubBuilder(title="Test Gallery", author="Test Author")

        assert builder.book.title == "Test Gallery"

    def test_add_single_image(self, sample_image_data):
        builder = EpubBuilder(title="Test Gallery")

        builder.add_image(sample_image_data)

        assert len(builder.chapters) == 1
        assert len(builder.images) == 1
        assert "Test image" in builder.chapters[0].title

    def test_add_multiple_images(self, temp_dir):
        builder = EpubBuilder(title="Multi-Image Gallery")

        image_paths = []
        for i in range(3):
            img_path = temp_dir / f"image_{i}.png"
            img = Image.new('RGB', (100, 100), color='blue')
            img.save(img_path)
            image_paths.append(img_path)

        builder.add_images(image_paths)

        assert len(builder.chapters) == 3
        assert len(builder.images) == 3

    def test_add_image_with_caption(self, sample_image_path):
        builder = EpubBuilder(title="Test Gallery")

        builder.add_image(sample_image_path, caption="Custom caption", chapter_title="Chapter One")

        assert len(builder.chapters) == 1
        assert builder.chapters[0].title == "Chapter One"
        assert "Custom caption" in str(builder.chapters[0].content)

    def test_add_cover_image(self, sample_image_path):
        builder = EpubBuilder(title="Test Gallery")

        builder.add_cover_image(sample_image_path)

    def test_save_epub(self, temp_dir, sample_image_data):
        builder = EpubBuilder(title="Test EPUB", author="Test Author")

        builder.add_image(sample_image_data)

        output_path = temp_dir / "output.epub"
        builder.save(output_path)

        assert output_path.exists()
        assert output_path.stat().st_size > 0

    def test_add_images_with_captions(self, temp_dir):
        builder = EpubBuilder(title="Test Gallery")

        image_paths = []
        for i in range(2):
            img_path = temp_dir / f"image_{i}.png"
            img = Image.new('RGB', (100, 100), color='green')
            img.save(img_path)
            image_paths.append(img_path)

        captions = ["Caption 1", "Caption 2"]
        builder.add_images(image_paths, captions=captions)

        assert len(builder.chapters) == 2
        assert "Caption 1" in str(builder.chapters[0].content)
        assert "Caption 2" in str(builder.chapters[1].content)

    def test_missing_image_warning(self, capsys):
        builder = EpubBuilder(title="Test Gallery")

        non_existent = Path("/non/existent/image.jpg")
        builder.add_image(non_existent)

        captured = capsys.readouterr()
        assert "Warning: Image not found" in captured.out
        assert len(builder.chapters) == 0

    def test_epub_with_cover(self, temp_dir):
        builder = EpubBuilder(title="Gallery with Cover")

        cover_path = temp_dir / "cover.jpg"
        img = Image.new('RGB', (800, 1200), color='purple')
        img.save(cover_path)

        builder.add_cover_image(cover_path)

        image_path = temp_dir / "content.jpg"
        img2 = Image.new('RGB', (600, 400), color='orange')
        img2.save(image_path)

        builder.add_image(image_path, caption="Content image")

        output_path = temp_dir / "output_with_cover.epub"
        builder.save(output_path)

        assert output_path.exists()
        assert len(builder.chapters) == 1
