#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Basic smoke tests for new extractors (PDF, HTML, Markdown).

These tests verify that extractors can be instantiated and have
the correct interface. Integration tests with real documents
are separate.
"""

import pytest
import tempfile
import os

from src.extraction.extractors.pdf import PdfExtractor
from src.extraction.extractors.html import HtmlExtractor
from src.extraction.extractors.markdown import MarkdownExtractor


class TestPdfExtractor:
    """Basic tests for PDF extractor."""

    def test_pdf_extractor_initialization(self):
        """Test PDF extractor can be instantiated."""
        extractor = PdfExtractor("test.pdf")
        assert extractor.source_path == "test.pdf"
        assert extractor.min_paragraph_words == 5
        assert extractor.heading_font_threshold == 1.2

    def test_pdf_extractor_with_config(self):
        """Test PDF extractor with custom config."""
        config = {
            "min_paragraph_words": 10,
            "heading_font_threshold": 1.5,
            "use_ocr": True,
        }
        extractor = PdfExtractor("test.pdf", config)
        assert extractor.min_paragraph_words == 10
        assert extractor.heading_font_threshold == 1.5
        assert extractor.use_ocr is True

    def test_pdf_extractor_requires_pdfplumber(self):
        """Test that PDF extractor imports are available."""
        # Just verify the module loaded successfully
        assert PdfExtractor is not None


class TestHtmlExtractor:
    """Basic tests for HTML extractor."""

    def test_html_extractor_initialization(self):
        """Test HTML extractor can be instantiated."""
        extractor = HtmlExtractor("test.html")
        assert extractor.source_path == "test.html"
        assert extractor.min_paragraph_words == 1

    def test_html_extractor_with_config(self):
        """Test HTML extractor with custom config."""
        config = {"min_paragraph_words": 5, "preserve_links": True}
        extractor = HtmlExtractor("test.html", config)
        assert extractor.min_paragraph_words == 5
        assert extractor.preserve_links is True

    def test_html_extractor_basic_parse(self):
        """Test HTML extractor can parse simple HTML."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False) as f:
            f.write("""
            <html>
            <head><title>Test Document</title></head>
            <body>
                <h1>Main Heading</h1>
                <p>This is a test paragraph with enough words to be included.</p>
                <h2>Subheading</h2>
                <p>Another paragraph here with some text content.</p>
            </body>
            </html>
            """)
            temp_path = f.name

        try:
            extractor = HtmlExtractor(temp_path)
            extractor.load()
            extractor.parse()
            extractor.extract_metadata()

            assert len(extractor.chunks) >= 2
            assert extractor.metadata.title == "Test Document"
            assert len(extractor.chunks[0].hierarchy["level_1"]) > 0  # Has hierarchy
        finally:
            os.unlink(temp_path)


class TestMarkdownExtractor:
    """Basic tests for Markdown extractor."""

    def test_markdown_extractor_initialization(self):
        """Test Markdown extractor can be instantiated."""
        extractor = MarkdownExtractor("test.md")
        assert extractor.source_path == "test.md"
        assert extractor.min_paragraph_words == 1
        assert extractor.preserve_code_blocks is True

    def test_markdown_extractor_with_config(self):
        """Test Markdown extractor with custom config."""
        config = {
            "min_paragraph_words": 3,
            "preserve_code_blocks": False,
            "extract_frontmatter": False,
        }
        extractor = MarkdownExtractor("test.md", config)
        assert extractor.min_paragraph_words == 3
        assert extractor.preserve_code_blocks is False
        assert extractor.extract_frontmatter is False

    def test_markdown_extractor_basic_parse(self):
        """Test Markdown extractor can parse simple markdown."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False, encoding='utf-8') as f:
            f.write("""
# Main Heading

This is a test paragraph with several words.

## Subheading

Another paragraph here with some content.

### Level 3 Heading

More content in the third level.
            """)
            temp_path = f.name

        try:
            extractor = MarkdownExtractor(temp_path)
            extractor.load()
            extractor.parse()
            extractor.extract_metadata()

            assert len(extractor.chunks) >= 3
            assert extractor.metadata.title == "Main Heading"
            # Check hierarchy is captured
            assert any("Main Heading" in str(c.hierarchy.get("level_1", "")) for c in extractor.chunks)
        finally:
            os.unlink(temp_path)

    def test_markdown_frontmatter_extraction(self):
        """Test Markdown frontmatter extraction."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False, encoding='utf-8') as f:
            f.write("""---
title: Test Document
author: Test Author
---

# Content Heading

This is the actual content.
            """)
            temp_path = f.name

        try:
            extractor = MarkdownExtractor(temp_path)
            extractor.load()

            assert extractor.frontmatter.get('title') == "Test Document"
            assert extractor.frontmatter.get('author') == "Test Author"

            extractor.parse()
            extractor.extract_metadata()

            assert extractor.metadata.title == "Test Document"
            assert extractor.metadata.author == "Test Author"
        finally:
            os.unlink(temp_path)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
