import hashlib
import mimetypes
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Optional
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from PIL import Image

from .configs import ScraperConfig


@dataclass
class ImageData:
    url: str
    local_path: Path
    alt_text: Optional[str] = None
    width: Optional[int] = None
    height: Optional[int] = None
    format: Optional[str] = None
    size_bytes: int = 0
    source_page: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "url": self.url,
            "local_path": str(self.local_path),
            "alt_text": self.alt_text,
            "width": self.width,
            "height": self.height,
            "format": self.format,
            "size_bytes": self.size_bytes,
            "source_page": self.source_page,
        }


class BaseImageScraper(ABC):
    def __init__(self, url: str, config: Optional[ScraperConfig] = None):
        self.url = url
        self.config = config or ScraperConfig()
        self.images: list[ImageData] = []

        self.config.output_dir.mkdir(parents=True, exist_ok=True)

    @abstractmethod
    def extract_images(self) -> list[ImageData]:
        pass

    def _is_valid_image_url(self, url: str) -> bool:
        parsed = urlparse(url)
        if not parsed.scheme or not parsed.netloc:
            return False

        path_lower = parsed.path.lower()

        valid_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp'}
        if self.config.include_svg:
            valid_extensions.add('.svg')

        # Check if path contains a valid image extension (handles Fandom-style URLs)
        has_image_extension = any(ext in path_lower for ext in valid_extensions)

        if not has_image_extension:
            # Try MIME type as fallback
            mime_type, _ = mimetypes.guess_type(url)
            if not (mime_type and mime_type.startswith('image/')):
                return False

        # Extract filename for ignore pattern checking
        # For URLs like /images/foo.png/revision/latest, extract foo.png
        for ext in valid_extensions:
            if ext in path_lower:
                # Find the part before the extension
                parts = path_lower.split(ext)
                if parts[0]:
                    # Get the last path component before the extension
                    filename = parts[0].split('/')[-1] + ext
                    break
        else:
            # Fallback to last path component
            filename = Path(parsed.path).name.lower()

        # Check ignore patterns against filename only
        if any(pattern in filename for pattern in self.config.ignore_patterns):
            return False

        return True

    def _generate_filename(self, url: str, alt_text: Optional[str] = None) -> str:
        url_hash = hashlib.md5(url.encode()).hexdigest()[:12]

        parsed = urlparse(url)
        path = parsed.path

        extension = Path(path).suffix.lower()
        if not extension or extension not in {'.jpg', '.jpeg', '.png', '.gif', '.webp', '.svg', '.bmp'}:
            extension = '.jpg'

        if alt_text:
            clean_alt = re.sub(r'[^\w\s-]', '', alt_text.lower())
            clean_alt = re.sub(r'[-\s]+', '_', clean_alt)[:30]
            return f"{clean_alt}_{url_hash}{extension}"

        return f"image_{url_hash}{extension}"

    def _download_image(self, url: str, alt_text: Optional[str] = None) -> Optional[ImageData]:
        try:
            headers = {'User-Agent': self.config.user_agent}
            response = requests.get(
                url,
                headers=headers,
                timeout=self.config.timeout,
                stream=True
            )
            response.raise_for_status()

            size_bytes = int(response.headers.get('content-length', 0))
            if size_bytes > 0 and size_bytes < self.config.min_image_size_kb * 1024:
                return None

            filename = self._generate_filename(url, alt_text)
            local_path = self.config.output_dir / filename

            with open(local_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)

            actual_size = local_path.stat().st_size
            if actual_size < self.config.min_image_size_kb * 1024:
                local_path.unlink()
                return None

            try:
                with Image.open(local_path) as img:
                    width, height = img.size
                    img_format = img.format

                    # Quality check: filter out tiny images
                    if self.config.quality_check:
                        if width < self.config.min_width or height < self.config.min_height:
                            local_path.unlink()
                            return None

                    if self.config.convert_webp and img_format == 'WEBP':
                        new_path = local_path.with_suffix('.png')
                        img.convert('RGB').save(new_path, 'PNG')
                        local_path.unlink()
                        local_path = new_path
                        img_format = 'PNG'
            except Exception:
                width, height, img_format = None, None, None

            return ImageData(
                url=url,
                local_path=local_path,
                alt_text=alt_text,
                width=width,
                height=height,
                format=img_format,
                size_bytes=actual_size,
                source_page=self.url,
            )

        except Exception as e:
            print(f"Failed to download {url}: {e}")
            return None

    def _resolve_url(self, img_url: str) -> str:
        return urljoin(self.url, img_url)


class StaticImageScraper(BaseImageScraper):
    def extract_images(self) -> list[ImageData]:
        try:
            headers = {'User-Agent': self.config.user_agent}
            response = requests.get(self.url, headers=headers, timeout=self.config.timeout)
            response.raise_for_status()

            soup = BeautifulSoup(response.content, 'html.parser')

            img_tags = soup.find_all('img')

            for img_tag in img_tags:
                if self.config.max_images and len(self.images) >= self.config.max_images:
                    break

                img_url = None
                for attr in ['src'] + self.config.lazy_load_attributes:
                    if img_tag.get(attr):
                        img_url = img_tag.get(attr)
                        break

                if not img_url:
                    continue

                img_url = self._resolve_url(img_url)

                if not self._is_valid_image_url(img_url):
                    continue

                alt_text = img_tag.get('alt', '').strip()

                image_data = self._download_image(img_url, alt_text)
                if image_data:
                    self.images.append(image_data)

            return self.images

        except Exception as e:
            print(f"Failed to scrape images from {self.url}: {e}")
            return []


class DynamicImageScraper(BaseImageScraper):
    def extract_images(self) -> list[ImageData]:
        try:
            from playwright.sync_api import sync_playwright

            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                context = browser.new_context(
                    user_agent=self.config.user_agent,
                    viewport={'width': 1920, 'height': 1080}
                )
                page = context.new_page()

                page.goto(self.url, timeout=self.config.timeout * 1000, wait_until='networkidle')

                page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                page.wait_for_timeout(2000)

                page.evaluate("window.scrollTo(0, 0)")

                html_content = page.content()
                browser.close()

            soup = BeautifulSoup(html_content, 'html.parser')

            img_tags = soup.find_all('img')

            for img_tag in img_tags:
                if self.config.max_images and len(self.images) >= self.config.max_images:
                    break

                img_url = None
                for attr in ['src'] + self.config.lazy_load_attributes:
                    if img_tag.get(attr):
                        img_url = img_tag.get(attr)
                        break

                if not img_url:
                    continue

                img_url = self._resolve_url(img_url)

                if not self._is_valid_image_url(img_url):
                    continue

                alt_text = img_tag.get('alt', '').strip()

                image_data = self._download_image(img_url, alt_text)
                if image_data:
                    self.images.append(image_data)

            return self.images

        except ImportError:
            raise ImportError(
                "Playwright is not installed. Install with: uv pip install -e '.[scraping]'"
            )
        except Exception as e:
            print(f"Failed to scrape images from {self.url}: {e}")
            return []


class AutoImageScraper(BaseImageScraper):
    def extract_images(self) -> list[ImageData]:
        print(f"Attempting static scraping of {self.url}")
        static_scraper = StaticImageScraper(self.url, self.config)
        images = static_scraper.extract_images()

        if images:
            print(f"Static scraping successful: found {len(images)} images")
            self.images = images
            return self.images

        print("Static scraping found no images, falling back to dynamic scraping with Playwright")
        try:
            dynamic_scraper = DynamicImageScraper(self.url, self.config)
            images = dynamic_scraper.extract_images()
            print(f"Dynamic scraping found {len(images)} images")
            self.images = images
            return self.images
        except ImportError:
            print("Playwright not available. Returning empty results.")
            return []
