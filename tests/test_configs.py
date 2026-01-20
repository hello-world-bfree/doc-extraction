#!/usr/bin/env python3
"""Tests for config dataclasses."""

import pytest
from extraction.extractors.configs import (
    BaseExtractorConfig,
    EpubExtractorConfig,
    PdfExtractorConfig,
    HtmlExtractorConfig,
    MarkdownExtractorConfig,
    JsonExtractorConfig,
)
from extraction.exceptions import InvalidConfigValueError


class TestBaseExtractorConfig:
    """Tests for BaseExtractorConfig."""

    def test_default_values(self):
        """BaseExtractorConfig should have sensible defaults."""
        config = BaseExtractorConfig()
        assert config.chunking_strategy == "rag"
        assert config.min_chunk_words == 100
        assert config.max_chunk_words == 500
        assert config.filter_noise is True

    def test_valid_chunking_strategy_rag(self):
        """Should accept 'rag' chunking strategy."""
        config = BaseExtractorConfig(chunking_strategy="rag")
        assert config.chunking_strategy == "rag"

    def test_valid_chunking_strategy_nlp(self):
        """Should accept 'nlp' chunking strategy."""
        config = BaseExtractorConfig(chunking_strategy="nlp")
        assert config.chunking_strategy == "nlp"

    def test_valid_chunking_strategy_aliases(self):
        """Should accept strategy aliases and normalize them."""
        config1 = BaseExtractorConfig(chunking_strategy="semantic")
        assert config1.chunking_strategy == "rag"

        config2 = BaseExtractorConfig(chunking_strategy="embeddings")
        assert config2.chunking_strategy == "rag"

        config3 = BaseExtractorConfig(chunking_strategy="paragraph")
        assert config3.chunking_strategy == "nlp"

    def test_invalid_chunking_strategy(self):
        """Should reject invalid chunking strategy."""
        with pytest.raises(InvalidConfigValueError, match="chunking_strategy"):
            BaseExtractorConfig(chunking_strategy="invalid")

    def test_negative_min_chunk_words(self):
        """Should reject negative min_chunk_words."""
        with pytest.raises(InvalidConfigValueError, match="min_chunk_words"):
            BaseExtractorConfig(min_chunk_words=-1)

    def test_negative_max_chunk_words(self):
        """Should reject negative max_chunk_words."""
        with pytest.raises(InvalidConfigValueError, match="max_chunk_words"):
            BaseExtractorConfig(max_chunk_words=-1)

    def test_min_greater_than_max_chunk_words(self):
        """Should reject min_chunk_words > max_chunk_words."""
        with pytest.raises(InvalidConfigValueError, match="max_chunk_words"):
            BaseExtractorConfig(min_chunk_words=600, max_chunk_words=500)

    def test_custom_chunk_sizes(self):
        """Should accept custom chunk sizes."""
        config = BaseExtractorConfig(min_chunk_words=200, max_chunk_words=800)
        assert config.min_chunk_words == 200
        assert config.max_chunk_words == 800


class TestEpubExtractorConfig:
    """Tests for EpubExtractorConfig."""

    def test_default_values(self):
        """EpubExtractorConfig should have EPUB-specific defaults."""
        config = EpubExtractorConfig()
        assert config.toc_hierarchy_level == 1
        assert config.min_paragraph_words == 6
        assert config.min_block_words == 30
        assert config.preserve_hierarchy_across_docs is False
        assert config.reset_depth == 2
        assert config.class_denylist == r"^(?:calibre\d+|note|footnote)$"
        assert config.filter_tiny_chunks == "conservative"

    def test_inherits_base_config(self):
        """EpubExtractorConfig should inherit from BaseExtractorConfig."""
        config = EpubExtractorConfig()
        assert config.chunking_strategy == "rag"
        assert config.min_chunk_words == 100
        assert config.max_chunk_words == 500

    def test_custom_toc_hierarchy_level(self):
        """Should accept custom TOC hierarchy level."""
        config = EpubExtractorConfig(toc_hierarchy_level=5)
        assert config.toc_hierarchy_level == 5

    def test_invalid_toc_hierarchy_level(self):
        """Should reject invalid TOC hierarchy level."""
        with pytest.raises(InvalidConfigValueError, match="toc_hierarchy_level"):
            EpubExtractorConfig(toc_hierarchy_level=7)

        with pytest.raises(InvalidConfigValueError, match="toc_hierarchy_level"):
            EpubExtractorConfig(toc_hierarchy_level=0)

    def test_invalid_reset_depth(self):
        """Should reject invalid reset_depth."""
        with pytest.raises(InvalidConfigValueError, match="reset_depth"):
            EpubExtractorConfig(reset_depth=7)

        with pytest.raises(InvalidConfigValueError, match="reset_depth"):
            EpubExtractorConfig(reset_depth=0)

    def test_invalid_filter_tiny_chunks(self):
        """Should reject invalid filter_tiny_chunks value."""
        with pytest.raises(InvalidConfigValueError, match="filter_tiny_chunks"):
            EpubExtractorConfig(filter_tiny_chunks="invalid")

    def test_valid_filter_tiny_chunks_values(self):
        """Should accept all valid filter_tiny_chunks values."""
        for value in ["off", "conservative", "standard", "aggressive"]:
            config = EpubExtractorConfig(filter_tiny_chunks=value)
            assert config.filter_tiny_chunks == value


class TestPdfExtractorConfig:
    """Tests for PdfExtractorConfig."""

    def test_default_values(self):
        """PdfExtractorConfig should have PDF-specific defaults."""
        config = PdfExtractorConfig()
        assert config.min_paragraph_words == 5
        assert config.heading_font_threshold == 1.2
        assert config.use_ocr is False
        assert config.ocr_lang == "eng"

    def test_custom_heading_font_threshold(self):
        """Should accept custom heading font threshold."""
        config = PdfExtractorConfig(heading_font_threshold=1.5)
        assert config.heading_font_threshold == 1.5

    def test_invalid_heading_font_threshold(self):
        """Should reject heading_font_threshold < 1."""
        with pytest.raises(InvalidConfigValueError, match="heading_font_threshold"):
            PdfExtractorConfig(heading_font_threshold=0.9)

    def test_use_ocr_boolean(self):
        """Should accept boolean use_ocr."""
        config = PdfExtractorConfig(use_ocr=True)
        assert config.use_ocr is True


class TestHtmlExtractorConfig:
    """Tests for HtmlExtractorConfig."""

    def test_default_values(self):
        """HtmlExtractorConfig should have HTML-specific defaults."""
        config = HtmlExtractorConfig()
        assert config.min_paragraph_words == 1
        assert config.preserve_links is False

    def test_custom_preserve_links(self):
        """Should accept custom preserve_links."""
        config = HtmlExtractorConfig(preserve_links=False)
        assert config.preserve_links is False


class TestMarkdownExtractorConfig:
    """Tests for MarkdownExtractorConfig."""

    def test_default_values(self):
        """MarkdownExtractorConfig should have Markdown-specific defaults."""
        config = MarkdownExtractorConfig()
        assert config.min_paragraph_words == 1
        assert config.preserve_code_blocks is True
        assert config.extract_frontmatter is True

    def test_custom_preserve_code_blocks(self):
        """Should accept custom preserve_code_blocks."""
        config = MarkdownExtractorConfig(preserve_code_blocks=False)
        assert config.preserve_code_blocks is False

    def test_custom_extract_frontmatter(self):
        """Should accept custom extract_frontmatter."""
        config = MarkdownExtractorConfig(extract_frontmatter=False)
        assert config.extract_frontmatter is False


class TestJsonExtractorConfig:
    """Tests for JsonExtractorConfig."""

    def test_default_values(self):
        """JsonExtractorConfig should have JSON-specific defaults."""
        config = JsonExtractorConfig()
        assert config.mode == "import"
        assert config.import_chunks is True
        assert config.import_metadata is True

    def test_custom_import_mode(self):
        """Should accept custom mode."""
        config = JsonExtractorConfig(mode="rechunk")
        assert config.mode == "rechunk"

    def test_custom_validate_schema(self):
        """Should accept custom import_chunks."""
        config = JsonExtractorConfig(import_chunks=False)
        assert config.import_chunks is False

    def test_custom_rechunk(self):
        """Should accept custom import_metadata."""
        config = JsonExtractorConfig(import_metadata=False)
        assert config.import_metadata is False
