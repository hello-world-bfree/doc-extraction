#!/usr/bin/env python3
"""Tests for MarkdownExtractor."""

import pytest
from pathlib import Path
from extraction.extractors.markdown import MarkdownExtractor
from extraction.extractors.configs import MarkdownExtractorConfig
from extraction.analyzers.generic import GenericAnalyzer


class TestMarkdownExtractorBasics:
    """Basic functionality tests."""

    def test_init_with_config(self):
        """Should initialize with config."""
        config = MarkdownExtractorConfig(min_paragraph_words=3)
        extractor = MarkdownExtractor("test.md", config)
        assert extractor.config.min_paragraph_words == 3

    def test_init_with_analyzer(self):
        """Should initialize with analyzer."""
        analyzer = GenericAnalyzer()
        extractor = MarkdownExtractor("test.md", analyzer=analyzer)
        assert extractor.analyzer == analyzer

    def test_state_starts_created(self):
        """Should start in CREATED state."""
        from extraction.state import ExtractorState
        extractor = MarkdownExtractor("test.md")
        assert extractor.state == ExtractorState.CREATED

    def test_preserve_code_blocks_config(self):
        """Should accept preserve_code_blocks config."""
        config = MarkdownExtractorConfig(preserve_code_blocks=False)
        extractor = MarkdownExtractor("test.md", config)
        assert extractor.config.preserve_code_blocks is False

    def test_extract_frontmatter_config(self):
        """Should accept extract_frontmatter config."""
        config = MarkdownExtractorConfig(extract_frontmatter=False)
        extractor = MarkdownExtractor("test.md", config)
        assert extractor.config.extract_frontmatter is False


class TestMarkdownExtractorParsing:
    """Parsing tests."""

    def test_parse_simple_markdown(self, tmp_path):
        """Should parse simple markdown."""
        md_file = tmp_path / "test.md"
        md_file.write_text("""
# Main Heading

This is a paragraph with multiple words to meet the minimum threshold.

## Sub Heading

Another paragraph with enough words to be included in the extraction process.
        """)

        config = MarkdownExtractorConfig(chunking_strategy='nlp', filter_noise=False)
        extractor = MarkdownExtractor(str(md_file), config)
        extractor.load()
        extractor.parse()

        chunks = extractor.chunks
        assert len(chunks) > 0


class TestMarkdownExtractorMetadata:
    """Metadata extraction tests."""

    def test_extract_metadata_from_file(self, tmp_path):
        """Should extract metadata."""
        md_file = tmp_path / "test.md"
        md_file.write_text("""
# Test Document

This is test content with enough words to create valid chunks for processing.
        """)

        config = MarkdownExtractorConfig(chunking_strategy='nlp', filter_noise=False)
        extractor = MarkdownExtractor(str(md_file), config)
        extractor.load()
        extractor.parse()
        metadata = extractor.extract_metadata()

        assert metadata is not None
        assert metadata.title == "Test Document"
