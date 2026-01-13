#!/usr/bin/env python3
"""Tests for PdfExtractor."""

import pytest

try:
    import pdfplumber
    PDFPLUMBER_AVAILABLE = True
except ImportError:
    PDFPLUMBER_AVAILABLE = False

from extraction.extractors.pdf import PdfExtractor
from extraction.extractors.configs import PdfExtractorConfig
from extraction.analyzers.generic import GenericAnalyzer


@pytest.mark.skipif(not PDFPLUMBER_AVAILABLE, reason="pdfplumber not installed")
class TestPdfExtractorBasics:
    """Basic functionality tests."""

    def test_init_with_config(self):
        """Should initialize with config."""
        config = PdfExtractorConfig(min_paragraph_words=10)
        extractor = PdfExtractor("test.pdf", config)
        assert extractor.config.min_paragraph_words == 10

    def test_init_with_analyzer(self):
        """Should initialize with analyzer."""
        analyzer = GenericAnalyzer()
        extractor = PdfExtractor("test.pdf", analyzer=analyzer)
        assert extractor.analyzer == analyzer

    def test_state_starts_created(self):
        """Should start in CREATED state."""
        from extraction.state import ExtractorState
        extractor = PdfExtractor("test.pdf")
        assert extractor.state == ExtractorState.CREATED

    def test_heading_font_threshold_config(self):
        """Should accept custom heading font threshold."""
        config = PdfExtractorConfig(heading_font_threshold=1.5)
        extractor = PdfExtractor("test.pdf", config)
        assert extractor.config.heading_font_threshold == 1.5

    def test_ocr_config(self):
        """Should accept OCR configuration."""
        config = PdfExtractorConfig(use_ocr=True, ocr_lang="fra")
        extractor = PdfExtractor("test.pdf", config)
        assert extractor.config.use_ocr is True
        assert extractor.config.ocr_lang == "fra"
