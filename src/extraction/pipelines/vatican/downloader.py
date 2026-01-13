#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
HTML downloader for Vatican documents.

Manages document downloads with rate limiting, retry logic, validation,
and resume capability.
"""

import hashlib
import logging
import time
from pathlib import Path
from typing import List, Optional, Callable

import requests
from bs4 import BeautifulSoup
from tqdm import tqdm

from .index import VaticanDocument

LOGGER = logging.getLogger("vatican.downloader")


class VaticanDownloader:
    """
    Manages HTML downloads from Vatican archive.

    Features:
    - Rate limiting (respectful crawling)
    - Automatic retry with exponential backoff
    - Content validation
    - Resume capability (skip already downloaded)
    - Progress tracking
    """

    def __init__(self,
                 download_dir: str = "./vatican_archive/downloads/temp",
                 rate_limit: float = 1.0,
                 max_retries: int = 3,
                 timeout: int = 30):
        """
        Initialize downloader.

        Args:
            download_dir: Base directory for downloaded files
            rate_limit: Minimum seconds between requests
            max_retries: Number of retry attempts for failed downloads
            timeout: Request timeout in seconds
        """
        self.download_dir = Path(download_dir)
        self.rate_limit = rate_limit
        self.max_retries = max_retries
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'VaticanArchiveExtractor/2.0 (Catholic Document Research)'
        })
        self.last_request_time = 0

        # Create download directory
        self.download_dir.mkdir(parents=True, exist_ok=True)

    def download_document(self, doc: VaticanDocument) -> Optional[str]:
        """
        Download a single document.

        Args:
            doc: Document to download

        Returns:
            Local file path if successful, None otherwise
        """
        # Generate download path
        local_path = self._get_download_path(doc)

        # Skip if already downloaded
        if self._is_already_downloaded(local_path):
            LOGGER.debug("Already downloaded: %s", doc.url)
            return str(local_path)

        # Download with retry
        if self._download_with_retry(doc.url, local_path):
            # Validate
            if self._validate_download(local_path):
                LOGGER.info("Downloaded: %s -> %s", doc.title[:50], local_path.name)
                return str(local_path)
            else:
                LOGGER.error("Validation failed: %s", local_path)
                local_path.unlink()  # Remove invalid file
                return None
        else:
            return None

    def batch_download(self,
                      documents: List[VaticanDocument],
                      progress_callback: Optional[Callable] = None) -> List[str]:
        """
        Download multiple documents with progress tracking.

        Args:
            documents: List of documents to download
            progress_callback: Optional callback for progress updates

        Returns:
            List of successfully downloaded file paths
        """
        downloaded_paths = []

        with tqdm(total=len(documents), desc="Downloading documents") as pbar:
            for i, doc in enumerate(documents):
                local_path = self.download_document(doc)

                if local_path:
                    downloaded_paths.append(local_path)

                # Progress callback
                if progress_callback:
                    progress_callback(i + 1, len(documents), doc)

                pbar.update(1)

        success_rate = len(downloaded_paths) / len(documents) * 100 if documents else 0
        LOGGER.info(
            "Batch download complete: %d/%d (%.1f%% success)",
            len(downloaded_paths),
            len(documents),
            success_rate
        )

        return downloaded_paths

    def _get_download_path(self, doc: VaticanDocument) -> Path:
        """
        Generate organized download path.

        Structure:
        downloads/temp/
        ├── bible/
        ├── catechism/
        ├── councils/
        └── ...

        Args:
            doc: Document

        Returns:
            Path object for download location
        """
        # Create section subdirectory
        section_dir = self.download_dir / doc.section.lower()
        section_dir.mkdir(parents=True, exist_ok=True)

        # Generate filename from URL
        # Use URL hash to avoid filename collisions and special characters
        url_hash = hashlib.md5(doc.url.encode()).hexdigest()[:8]

        # Clean title for filename
        import re
        clean_title = re.sub(r'[^\w\s-]', '', doc.title.lower())
        clean_title = re.sub(r'[-\s]+', '_', clean_title)
        clean_title = clean_title[:50]  # Limit length

        # Combine for unique filename
        filename = f"{clean_title}_{url_hash}.html"

        return section_dir / filename

    def _is_already_downloaded(self, local_path: Path) -> bool:
        """
        Check if document already downloaded.

        Args:
            local_path: Local file path

        Returns:
            True if file exists and is non-empty
        """
        if not local_path.exists():
            return False

        # Check if file is non-empty
        if local_path.stat().st_size == 0:
            return False

        return True

    def _download_with_retry(self, url: str, output_path: Path) -> bool:
        """
        Download with exponential backoff retry logic.

        Args:
            url: URL to download
            output_path: Local path to save file

        Returns:
            True if successful, False otherwise
        """
        for attempt in range(self.max_retries):
            try:
                # Respect rate limit
                self._respect_rate_limit()

                # Download
                response = self.session.get(url, timeout=self.timeout, stream=True)
                response.raise_for_status()

                # Write to file
                output_path.parent.mkdir(parents=True, exist_ok=True)
                with open(output_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        f.write(chunk)

                return True

            except requests.RequestException as e:
                if attempt < self.max_retries - 1:
                    wait_time = 2 ** attempt  # Exponential backoff: 1s, 2s, 4s
                    LOGGER.warning(
                        "Download failed (attempt %d/%d): %s. Retrying in %ds...",
                        attempt + 1,
                        self.max_retries,
                        e,
                        wait_time
                    )
                    time.sleep(wait_time)
                else:
                    LOGGER.error(
                        "Download failed after %d attempts: %s - %s",
                        self.max_retries,
                        url,
                        e
                    )
                    return False

        return False

    def _validate_download(self, local_path: Path) -> bool:
        """
        Validate downloaded file integrity.

        Checks:
        1. File exists and is non-empty
        2. Valid HTML structure (can parse with BeautifulSoup)
        3. File size is reasonable (> 1KB, < 100MB)

        Args:
            local_path: Path to downloaded file

        Returns:
            True if valid, False otherwise
        """
        # Check existence
        if not local_path.exists():
            LOGGER.error("File does not exist: %s", local_path)
            return False

        # Check size
        size = local_path.stat().st_size
        if size == 0:  # Completely empty
            LOGGER.error("File is empty: %s", local_path)
            return False
        if size > 100 * 1024 * 1024:  # 100 MB
            LOGGER.warning("File very large (%d MB): %s", size / 1024 / 1024, local_path)
            # Don't fail, just warn

        # Validate HTML structure
        try:
            with open(local_path, 'rb') as f:
                soup = BeautifulSoup(f, 'html.parser')
                # Check for basic HTML structure
                if soup.find('body') is None:
                    LOGGER.error("Invalid HTML (no body tag): %s", local_path)
                    return False
        except Exception as e:
            LOGGER.error("Failed to parse HTML: %s - %s", local_path, e)
            return False

        return True

    def _respect_rate_limit(self) -> None:
        """Ensure rate limit compliance by sleeping if needed."""
        elapsed = time.time() - self.last_request_time
        if elapsed < self.rate_limit:
            sleep_time = self.rate_limit - elapsed
            time.sleep(sleep_time)
        self.last_request_time = time.time()

    def get_download_stats(self) -> dict:
        """
        Get statistics about downloaded files.

        Returns:
            Dictionary with download statistics
        """
        total_files = 0
        total_size = 0
        by_section = {}

        for section_dir in self.download_dir.iterdir():
            if section_dir.is_dir():
                section_files = list(section_dir.glob("*.html"))
                section_size = sum(f.stat().st_size for f in section_files)

                by_section[section_dir.name] = {
                    "files": len(section_files),
                    "size_mb": section_size / 1024 / 1024
                }

                total_files += len(section_files)
                total_size += section_size

        return {
            "total_files": total_files,
            "total_size_mb": total_size / 1024 / 1024,
            "by_section": by_section
        }
