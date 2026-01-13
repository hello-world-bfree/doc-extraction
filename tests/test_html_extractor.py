#!/usr/bin/env python3
"""Tests for HtmlExtractor."""

import pytest
from pathlib import Path
from extraction.extractors.html import HtmlExtractor
from extraction.extractors.configs import HtmlExtractorConfig
from extraction.analyzers.generic import GenericAnalyzer


class TestHtmlExtractorBasics:
    """Basic functionality tests."""

    def test_init_with_config(self):
        """Should initialize with config."""
        config = HtmlExtractorConfig(min_paragraph_words=5)
        extractor = HtmlExtractor("test.html", config)
        assert extractor.config.min_paragraph_words == 5

    def test_init_with_analyzer(self):
        """Should initialize with analyzer."""
        analyzer = GenericAnalyzer()
        extractor = HtmlExtractor("test.html", analyzer=analyzer)
        assert extractor.analyzer == analyzer

    def test_state_starts_created(self):
        """Should start in CREATED state."""
        from extraction.state import ExtractorState
        extractor = HtmlExtractor("test.html")
        assert extractor.state == ExtractorState.CREATED


class TestHtmlExtractorParsing:
    """Parsing tests."""

    def test_parse_simple_html(self, tmp_path):
        """Should parse simple HTML."""
        html_file = tmp_path / "test.html"
        html_file.write_text("""
        <html>
        <body>
            <h1>Test Title</h1>
            <p>This is a paragraph with multiple words to meet minimum threshold.</p>
            <p>Another paragraph with enough words to be included in extraction.</p>
        </body>
        </html>
        """)

        config = HtmlExtractorConfig(chunking_strategy='nlp', filter_noise=False)
        extractor = HtmlExtractor(str(html_file), config)
        extractor.load()
        extractor.parse()

        chunks = extractor.chunks
        assert len(chunks) > 0

    def test_parse_with_headings(self, tmp_path):
        """Should parse headings into hierarchy."""
        html_file = tmp_path / "test.html"
        html_file.write_text("""
        <html>
        <body>
            <h1>Main Heading</h1>
            <p>Content under main heading with sufficient words for extraction.</p>
            <h2>Sub Heading</h2>
            <p>Content under sub heading with multiple words exceeding minimum.</p>
        </body>
        </html>
        """)

        config = HtmlExtractorConfig(chunking_strategy='nlp', filter_noise=False)
        extractor = HtmlExtractor(str(html_file), config)
        extractor.load()
        extractor.parse()

        chunks = extractor.chunks
        assert len(chunks) > 0


class TestHtmlExtractorMetadata:
    """Metadata extraction tests."""

    def test_extract_metadata(self, tmp_path):
        """Should extract metadata."""
        html_file = tmp_path / "test.html"
        html_file.write_text("""
        <html>
        <head>
            <title>Test Document</title>
        </head>
        <body>
            <h1>Content</h1>
            <p>This is test content with enough words to create valid chunks.</p>
        </body>
        </html>
        """)

        config = HtmlExtractorConfig(chunking_strategy='nlp', filter_noise=False)
        extractor = HtmlExtractor(str(html_file), config)
        extractor.load()
        extractor.parse()
        metadata = extractor.extract_metadata()

        assert metadata is not None
        assert metadata.title == "Test Document"
