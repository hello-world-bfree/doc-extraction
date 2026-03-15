import tempfile
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest

pytest.importorskip("PIL", reason="Pillow not installed (images extra)")

from extraction.scrapers.configs import ScraperConfig
from extraction.scrapers.image_scraper import (
    AutoImageScraper,
    DynamicImageScraper,
    ImageData,
    StaticImageScraper,
)


@pytest.fixture
def temp_output_dir():
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def scraper_config(temp_output_dir):
    return ScraperConfig(
        min_image_size_kb=1,
        max_images=5,
        output_dir=temp_output_dir,
        timeout=10
    )


class TestImageData:
    def test_image_data_creation(self):
        image = ImageData(
            url="https://example.com/image.jpg",
            local_path=Path("/tmp/image.jpg"),
            alt_text="Test image",
            width=800,
            height=600,
            format="JPEG",
            size_bytes=12345
        )

        assert image.url == "https://example.com/image.jpg"
        assert image.alt_text == "Test image"
        assert image.width == 800
        assert image.height == 600

    def test_image_data_to_dict(self):
        image = ImageData(
            url="https://example.com/image.jpg",
            local_path=Path("/tmp/image.jpg"),
            width=800,
            height=600
        )

        result = image.to_dict()

        assert result["url"] == "https://example.com/image.jpg"
        assert result["local_path"] == "/tmp/image.jpg"
        assert result["width"] == 800
        assert result["height"] == 600


class TestScraperConfig:
    def test_default_config(self):
        config = ScraperConfig()

        assert config.min_image_size_kb == 10
        assert config.max_images is None
        assert config.include_svg is False
        assert config.convert_webp is True

    def test_custom_config(self):
        config = ScraperConfig(
            min_image_size_kb=50,
            max_images=10,
            include_svg=True
        )

        assert config.min_image_size_kb == 50
        assert config.max_images == 10
        assert config.include_svg is True


class TestStaticImageScraper:
    def test_is_valid_image_url(self, scraper_config):
        scraper = StaticImageScraper("https://example.com", scraper_config)

        assert scraper._is_valid_image_url("https://example.com/image.jpg")
        assert scraper._is_valid_image_url("https://example.com/photo.png")
        assert scraper._is_valid_image_url("https://example.com/pic.webp")

        assert not scraper._is_valid_image_url("not-a-url")
        assert not scraper._is_valid_image_url("https://example.com/icon.png")

    def test_resolve_url(self, scraper_config):
        scraper = StaticImageScraper("https://example.com/page", scraper_config)

        assert scraper._resolve_url("/image.jpg") == "https://example.com/image.jpg"
        assert scraper._resolve_url("image.jpg") == "https://example.com/image.jpg"
        assert scraper._resolve_url("https://other.com/pic.png") == "https://other.com/pic.png"

    def test_generate_filename(self, scraper_config):
        scraper = StaticImageScraper("https://example.com", scraper_config)

        filename = scraper._generate_filename("https://example.com/photo.jpg")
        assert filename.endswith(".jpg")
        assert len(filename) > 12

        filename_with_alt = scraper._generate_filename(
            "https://example.com/photo.jpg",
            "Beautiful sunset"
        )
        assert "beautiful_sunset" in filename_with_alt.lower()
        assert filename_with_alt.endswith(".jpg")

    @patch('extraction.scrapers.image_scraper.requests.get')
    @patch('extraction.scrapers.image_scraper.BeautifulSoup')
    def test_extract_images_success(self, mock_soup, mock_get, scraper_config):
        html_content = """
        <html>
            <body>
                <img src="photo1.jpg" alt="Photo 1">
                <img src="photo2.png" alt="Photo 2">
            </body>
        </html>
        """

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.content = html_content.encode()
        mock_get.return_value = mock_response

        mock_img1 = Mock()
        mock_img1.get.side_effect = lambda attr, default='': {
            'src': 'https://example.com/photo1.jpg',
            'alt': 'Photo 1'
        }.get(attr, default)

        mock_img2 = Mock()
        mock_img2.get.side_effect = lambda attr, default='': {
            'src': 'https://example.com/photo2.png',
            'alt': 'Photo 2'
        }.get(attr, default)

        mock_soup.return_value.find_all.return_value = [mock_img1, mock_img2]

        scraper = StaticImageScraper("https://example.com", scraper_config)

        with patch.object(scraper, '_download_image') as mock_download:
            mock_download.side_effect = [
                ImageData(
                    url="https://example.com/photo1.jpg",
                    local_path=Path("/tmp/photo1.jpg"),
                    alt_text="Photo 1"
                ),
                ImageData(
                    url="https://example.com/photo2.png",
                    local_path=Path("/tmp/photo2.png"),
                    alt_text="Photo 2"
                )
            ]

            images = scraper.extract_images()

            assert len(images) == 2
            assert images[0].alt_text == "Photo 1"
            assert images[1].alt_text == "Photo 2"


class TestAutoImageScraper:
    @patch.object(StaticImageScraper, 'extract_images')
    def test_auto_scraper_static_success(self, mock_static_extract, scraper_config, capsys):
        mock_images = [
            ImageData(
                url="https://example.com/image.jpg",
                local_path=Path("/tmp/image.jpg")
            )
        ]
        mock_static_extract.return_value = mock_images

        scraper = AutoImageScraper("https://example.com", scraper_config)
        images = scraper.extract_images()

        assert len(images) == 1
        assert images[0].url == "https://example.com/image.jpg"

        captured = capsys.readouterr()
        assert "Static scraping successful" in captured.out

    @patch.object(StaticImageScraper, 'extract_images')
    @patch.object(DynamicImageScraper, 'extract_images')
    def test_auto_scraper_fallback_to_dynamic(
        self,
        mock_dynamic_extract,
        mock_static_extract,
        scraper_config,
        capsys
    ):
        mock_static_extract.return_value = []

        mock_dynamic_images = [
            ImageData(
                url="https://example.com/dynamic.jpg",
                local_path=Path("/tmp/dynamic.jpg")
            )
        ]
        mock_dynamic_extract.return_value = mock_dynamic_images

        scraper = AutoImageScraper("https://example.com", scraper_config)
        images = scraper.extract_images()

        assert len(images) == 1
        assert images[0].url == "https://example.com/dynamic.jpg"

        captured = capsys.readouterr()
        assert "falling back to dynamic scraping" in captured.out


class TestDynamicImageScraper:
    def test_dynamic_scraper_requires_playwright(self, scraper_config):
        with patch('extraction.scrapers.image_scraper.DynamicImageScraper.extract_images') as mock_extract:
            mock_extract.side_effect = ImportError("Playwright is not installed")

            scraper = DynamicImageScraper("https://example.com", scraper_config)

            with pytest.raises(ImportError, match="Playwright is not installed"):
                scraper.extract_images()
