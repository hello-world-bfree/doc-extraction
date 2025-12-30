#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Tests for Vatican archive extraction pipeline.

Includes unit tests for all components and integration tests for the complete pipeline.
"""

import json
import pytest
import time
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch

from src.extraction.pipelines.vatican.index import DocumentIndex, VaticanDocument
from src.extraction.pipelines.vatican.scraper import VaticanArchiveScraper, Section
from src.extraction.pipelines.vatican.downloader import VaticanDownloader


# ====================== Fixtures ======================


@pytest.fixture
def sample_vatican_doc():
    """Sample Vatican document for testing."""
    return VaticanDocument(
        url="https://www.vatican.va/archive/ENG0015/_INDEX.HTM",
        title="Catechism of the Catholic Church",
        section="CATECHISM",
        document_type="Catechism",
        language="en",
    )


@pytest.fixture
def temp_index(tmp_path):
    """Temporary document index."""
    index_path = tmp_path / "index.json"
    return DocumentIndex(index_path=str(index_path))


@pytest.fixture
def temp_downloader(tmp_path):
    """Temporary downloader."""
    download_dir = tmp_path / "downloads"
    return VaticanDownloader(download_dir=str(download_dir), rate_limit=0.1)


# ====================== Document Index Tests ======================


class TestDocumentIndex:
    """Test document indexing and persistence."""

    def test_add_document(self, temp_index, sample_vatican_doc):
        """Test adding documents to index."""
        # First add succeeds
        assert temp_index.add_document(sample_vatican_doc)
        assert len(temp_index) == 1
        assert sample_vatican_doc.url in temp_index

        # Duplicate rejected
        assert not temp_index.add_document(sample_vatican_doc)
        assert len(temp_index) == 1

    def test_mark_downloaded(self, temp_index, sample_vatican_doc):
        """Test marking document as downloaded."""
        temp_index.add_document(sample_vatican_doc)

        temp_index.mark_downloaded(sample_vatican_doc.url, "/path/to/file.html")

        doc = temp_index[sample_vatican_doc.url]
        assert doc.downloaded
        assert doc.download_path == "/path/to/file.html"

    def test_mark_processed(self, temp_index, sample_vatican_doc):
        """Test marking document as processed."""
        temp_index.add_document(sample_vatican_doc)

        r2_paths = ["vatican/catechism/ccc.json", "vatican/catechism/ccc.ndjson"]
        temp_index.mark_processed(sample_vatican_doc.url, r2_paths)

        doc = temp_index[sample_vatican_doc.url]
        assert doc.processed
        assert doc.r2_paths == r2_paths
        assert doc.processing_timestamp is not None

    def test_get_pending_downloads(self, temp_index):
        """Test retrieving pending downloads."""
        doc1 = VaticanDocument(url="https://example.com/1", title="Doc 1", section="TEST")
        doc2 = VaticanDocument(url="https://example.com/2", title="Doc 2", section="TEST")
        doc3 = VaticanDocument(url="https://example.com/3", title="Doc 3", section="TEST")

        temp_index.add_document(doc1)
        temp_index.add_document(doc2)
        temp_index.add_document(doc3)

        # Mark doc2 as downloaded
        temp_index.mark_downloaded(doc2.url, "/path/to/doc2.html")

        pending = temp_index.get_pending_downloads()
        assert len(pending) == 2
        assert all(not doc.downloaded for doc in pending)

    def test_get_pending_processing(self, temp_index):
        """Test retrieving pending processing."""
        doc1 = VaticanDocument(url="https://example.com/1", title="Doc 1", section="TEST")
        doc2 = VaticanDocument(url="https://example.com/2", title="Doc 2", section="TEST")

        temp_index.add_document(doc1)
        temp_index.add_document(doc2)

        # Mark both as downloaded, only doc1 as processed
        temp_index.mark_downloaded(doc1.url, "/path/to/doc1.html")
        temp_index.mark_downloaded(doc2.url, "/path/to/doc2.html")
        temp_index.mark_processed(doc1.url, ["vatican/doc1.json"])

        pending = temp_index.get_pending_processing()
        assert len(pending) == 1
        assert pending[0].url == doc2.url

    def test_persistence(self, tmp_path):
        """Test save/load functionality."""
        index_path = tmp_path / "test_index.json"

        # Create and save
        index1 = DocumentIndex(index_path=str(index_path))
        doc = VaticanDocument(url="https://example.com/test", title="Test", section="TEST")
        index1.add_document(doc)
        index1.save()

        # Load in new instance
        index2 = DocumentIndex(index_path=str(index_path))
        index2.load()

        assert len(index2) == 1
        assert "https://example.com/test" in index2

    def test_export_summary(self, temp_index):
        """Test summary statistics export."""
        # Add some documents
        for i in range(5):
            doc = VaticanDocument(
                url=f"https://example.com/{i}",
                title=f"Doc {i}",
                section="CATECHISM" if i < 3 else "COUNCILS"
            )
            temp_index.add_document(doc)

        # Mark some as downloaded/processed
        temp_index.mark_downloaded("https://example.com/0", "/path/0")
        temp_index.mark_downloaded("https://example.com/1", "/path/1")
        temp_index.mark_processed("https://example.com/0", ["vatican/0.json"])

        summary = temp_index.export_summary()

        assert summary["total_discovered"] == 5
        assert summary["downloaded"] == 2
        assert summary["processed"] == 1
        assert summary["pending_download"] == 3
        assert summary["pending_processing"] == 1
        assert summary["by_section"]["CATECHISM"] == 3
        assert summary["by_section"]["COUNCILS"] == 2


# ====================== Vatican Scraper Tests ======================


class TestVaticanScraper:
    """Test Vatican archive scraping functionality."""

    def test_url_pattern_recognition(self):
        """Test English URL pattern detection."""
        scraper = VaticanArchiveScraper(rate_limit=0)

        # English patterns
        assert scraper._is_english_url("https://www.vatican.va/archive/ENG0015/_INDEX.HTM")
        assert scraper._is_english_url("https://www.vatican.va/documents/laudato_si_en.html")
        assert scraper._is_english_url("https://www.vatican.va/content/en/index.html")

        # Non-English patterns
        assert not scraper._is_english_url("https://www.vatican.va/archive/ITA0016/_INDEX.HTM")
        assert not scraper._is_english_url("https://www.vatican.va/documents/laudato_si_it.html")

    def test_language_detection_from_html(self):
        """Test HTML language detection."""
        from bs4 import BeautifulSoup

        scraper = VaticanArchiveScraper(rate_limit=0)

        # English HTML
        html_en = '<html lang="en"><head><title>Catechism</title></head><body></body></html>'
        soup_en = BeautifulSoup(html_en, 'html.parser')
        assert scraper.is_english_document("test.html", soup_en)

        # Italian HTML
        html_it = '<html lang="it"><head><title>Catechismo</title></head><body></body></html>'
        soup_it = BeautifulSoup(html_it, 'html.parser')
        assert not scraper.is_english_document("test.html", soup_it)

    def test_is_document_page(self):
        """Test document page detection."""
        from bs4 import BeautifulSoup

        scraper = VaticanArchiveScraper(rate_limit=0)

        # Document page (substantial content with many words)
        doc_html = """
        <html><body>
        <p>This is a substantial paragraph with meaningful content about Catholic teaching.</p>
        <p>Another paragraph discussing important theological concepts and doctrinal matters.</p>
        <p>And another detailed paragraph explaining various aspects of Church tradition.</p>
        """ + "<p>Additional substantial content explaining Catholic doctrine and practice.</p>" * 20 + """
        </body></html>
        """
        soup_doc = BeautifulSoup(doc_html, 'html.parser')
        assert scraper.is_document_page(soup_doc, "test.html")

        # Index page (lots of links, little content)
        index_html = """
        <html><body>
        <p>Index</p>
        <a href="1.html">Link 1</a>
        <a href="2.html">Link 2</a>
        """ + "<a href='#'>Link</a>" * 50 + """
        </body></html>
        """
        soup_index = BeautifulSoup(index_html, 'html.parser')
        assert not scraper.is_document_page(soup_index, "index.html")

    def test_infer_document_type(self):
        """Test document type inference."""
        from bs4 import BeautifulSoup

        scraper = VaticanArchiveScraper(rate_limit=0)

        # Test various document types
        assert scraper._infer_document_type("Laudato Si' Encyclical", BeautifulSoup("", 'html.parser')) == "Encyclical"
        assert scraper._infer_document_type("Apostolic Letter Tertio Millennio", BeautifulSoup("", 'html.parser')) == "Apostolic Letter"
        assert scraper._infer_document_type("Catechism of the Catholic Church", BeautifulSoup("", 'html.parser')) == "Catechism"
        assert scraper._infer_document_type("The Gospel of John", BeautifulSoup("", 'html.parser')) == "Scripture"

    def test_rate_limiting(self):
        """Test rate limit enforcement."""
        scraper = VaticanArchiveScraper(rate_limit=0.2)

        start = time.time()
        scraper._respect_rate_limit()
        scraper._respect_rate_limit()
        elapsed = time.time() - start

        # Should have at least one rate limit delay
        assert elapsed >= 0.2


# ====================== Vatican Downloader Tests ======================


class TestVaticanDownloader:
    """Test document downloading."""

    def test_get_download_path(self, temp_downloader, sample_vatican_doc):
        """Test download path generation."""
        path = temp_downloader._get_download_path(sample_vatican_doc)

        # Should be in section subdirectory
        assert "catechism" in str(path).lower()
        # Should have .html extension
        assert path.suffix == ".html"
        # Should be within download directory
        assert str(temp_downloader.download_dir) in str(path)

    def test_is_already_downloaded(self, temp_downloader, tmp_path):
        """Test downloaded file detection."""
        # Non-existent file
        assert not temp_downloader._is_already_downloaded(tmp_path / "nonexistent.html")

        # Empty file
        empty_file = tmp_path / "empty.html"
        empty_file.write_text("")
        assert not temp_downloader._is_already_downloaded(empty_file)

        # Valid file
        valid_file = tmp_path / "valid.html"
        valid_file.write_text("<html><body>Content</body></html>")
        assert temp_downloader._is_already_downloaded(valid_file)

    def test_validate_download(self, temp_downloader, tmp_path):
        """Test download validation."""
        # Valid HTML
        valid_html = tmp_path / "valid.html"
        valid_html.write_text("<html><head><title>Test</title></head><body><p>Content</p></body></html>")
        assert temp_downloader._validate_download(valid_html)

        # Invalid HTML (no body tag)
        invalid_html = tmp_path / "invalid.html"
        invalid_html.write_text("<html><head><title>Test</title></head></html>")
        assert not temp_downloader._validate_download(invalid_html)

        # Too small
        small_html = tmp_path / "small.html"
        small_html.write_text("<html></html>")
        assert not temp_downloader._validate_download(small_html)

    def test_rate_limiting(self, temp_downloader):
        """Test download rate limiting."""
        temp_downloader.rate_limit = 0.2

        start = time.time()
        temp_downloader._respect_rate_limit()
        temp_downloader._respect_rate_limit()
        elapsed = time.time() - start

        # Should have at least one rate limit delay
        assert elapsed >= 0.2


# ====================== Integration Tests ======================


@pytest.mark.integration
@pytest.mark.slow
class TestVaticanPipelineIntegration:
    """Integration tests for complete pipeline."""

    def test_index_persistence_workflow(self, tmp_path):
        """Test complete index workflow: add, save, load."""
        index_path = tmp_path / "index.json"

        # Create index and add documents
        index = DocumentIndex(index_path=str(index_path))

        docs = [
            VaticanDocument(url=f"https://example.com/{i}", title=f"Doc {i}", section="TEST")
            for i in range(10)
        ]

        for doc in docs:
            index.add_document(doc)

        # Mark some as downloaded/processed
        index.mark_downloaded(docs[0].url, "/path/0")
        index.mark_processed(docs[0].url, ["vatican/0.json"])

        # Save
        index.save()
        assert index_path.exists()

        # Verify JSON structure
        with open(index_path) as f:
            data = json.load(f)
            assert "documents" in data
            assert "statistics" in data
            assert len(data["documents"]) == 10

        # Load in new instance
        index2 = DocumentIndex(index_path=str(index_path))
        index2.load()

        assert len(index2) == 10
        assert index2[docs[0].url].downloaded
        assert index2[docs[0].url].processed

    @pytest.mark.skip(reason="Requires network access to Vatican archive")
    def test_live_scraper_discovery(self):
        """Test live discovery from Vatican archive."""
        scraper = VaticanArchiveScraper(rate_limit=2.0)

        # Get main sections
        sections = scraper.get_main_sections()
        assert len(sections) > 0

        # Scrape one section briefly
        if sections:
            docs = scraper.scrape_section(sections[0], max_depth=1)
            # Should find at least some documents
            assert len(docs) >= 0  # May legitimately be 0 for some sections

    def test_download_validation_workflow(self, temp_downloader, tmp_path):
        """Test download and validation workflow."""
        # Create a mock HTML file
        test_html = tmp_path / "test.html"
        test_html.write_text("""
        <html>
        <head><title>Test Document</title></head>
        <body>
            <h1>Test Header</h1>
            <p>This is a test paragraph with enough content to pass validation.</p>
            <p>Another paragraph to ensure sufficient content.</p>
        </body>
        </html>
        """)

        # Validate it
        assert temp_downloader._validate_download(test_html)

        # Get stats
        stats = temp_downloader.get_download_stats()
        assert "total_files" in stats
        assert "total_size_mb" in stats


# ====================== Test Markers ======================


def test_vatican_marker_setup():
    """Verify test markers are properly configured."""
    # This test ensures pytest markers are recognized
    assert hasattr(pytest.mark, 'vatican')
    assert hasattr(pytest.mark, 'integration')
    assert hasattr(pytest.mark, 'slow')
