#!/usr/bin/env python3
"""Regression tests for previously fixed bugs.

These tests ensure that fixed bugs don't resurface.
"""
import math
import pytest
from pathlib import Path

from extraction.extractors.epub import EpubExtractor
from extraction.core.quality import score_quality, quality_signals_from_text
from extraction.core.text import clean_toc_title
from test_framework import ExtractionTestCase


class TestQualityScoreFixes(ExtractionTestCase):
    """Regression tests for quality scoring fixes."""

    def test_quality_no_nan_on_empty_text(self):
        """Bug fix: Empty text should not produce NaN quality score.

        Previously, division by zero could cause NaN in quality signals.
        Now handled explicitly with default values.
        """
        signals = quality_signals_from_text("")
        score = score_quality(signals)

        assert not math.isnan(score), "Score is NaN for empty text"
        assert not math.isinf(score), "Score is Inf for empty text"
        assert 0.0 <= score <= 1.0, f"Score {score} out of bounds"

    def test_quality_no_nan_on_malformed_signals(self):
        """Bug fix: Malformed signals should not crash score_quality().

        Defensive validation added to handle NaN/Inf in signals.
        """
        # Artificially create malformed signals
        malformed_signals = {
            "garble_rate": float('inf'),
            "mean_conf": float('nan'),
            "line_len_std_norm": 2.0,  # Out of bounds
            "lang_prob": -1.0  # Out of bounds
        }

        score = score_quality(malformed_signals)

        # Should not crash, should return valid score
        assert not math.isnan(score), "Score is NaN with malformed signals"
        assert not math.isinf(score), "Score is Inf with malformed signals"
        assert 0.0 <= score <= 1.0, f"Score {score} out of bounds"

    def test_quality_bounds_clamping(self):
        """Bug fix: Quality scores are clamped to [0, 1].

        Even if formula produces out-of-range value, final score is clamped.
        """
        # Create signals that might produce >1.0 (though formula prevents this)
        max_signals = {
            "garble_rate": 0.0,  # Best
            "mean_conf": 1.0,    # Best
            "line_len_std_norm": 0.0,  # Best
            "lang_prob": 1.0     # Best
        }

        score = score_quality(max_signals)
        assert 0.0 <= score <= 1.0, f"Score {score} exceeds [0, 1]"

        # Create signals that produce lowest score
        min_signals = {
            "garble_rate": 1.0,  # Worst
            "mean_conf": 0.0,    # Worst
            "line_len_std_norm": 1.0,  # Worst
            "lang_prob": 0.0     # Worst
        }

        score = score_quality(min_signals)
        assert 0.0 <= score <= 1.0, f"Score {score} below [0, 1]"
        assert score == 0.0, f"Minimum score should be 0.0, got {score}"


class TestTOCCleaningFixes(ExtractionTestCase):
    """Regression tests for TOC title cleaning fixes."""

    def test_toc_preserves_words_starting_with_roman_chars(self):
        """Bug fix: Words starting with I, V, X, L, C should not be truncated.

        Previously, clean_toc_title() incorrectly matched single Roman
        numeral letters and stripped them from valid words.
        """
        # These were failing before the fix
        assert clean_toc_title("Cover Page") == "Cover Page"
        assert clean_toc_title("Copyright Page") == "Copyright Page"
        assert clean_toc_title("Contents") == "Contents"
        assert clean_toc_title("Index") == "Index"
        assert clean_toc_title("List of Tables") == "List of Tables"

        # Additional edge cases
        assert clean_toc_title("Introduction") == "Introduction"
        assert clean_toc_title("Vocabulary") == "Vocabulary"
        assert clean_toc_title("Conclusions") == "Conclusions"

    def test_toc_removes_chapter_prefixes(self):
        """Verify 'Chapter N' prefixes are removed correctly."""
        assert clean_toc_title("Chapter 1: Introduction") == "Introduction"
        assert clean_toc_title("Chapter 5 - The Problem") == "The Problem"
        assert clean_toc_title("Chap. 3: Solutions") == "Solutions"

    def test_toc_removes_numeric_prefixes(self):
        """Verify numeric prefixes like '1.', '1)' are removed."""
        assert clean_toc_title("1. Recurrent Problems") == "Recurrent Problems"
        assert clean_toc_title("2. Sums") == "Sums"
        assert clean_toc_title("10) Final Chapter") == "Final Chapter"

    def test_toc_removes_roman_numeral_prefixes(self):
        """Verify Roman numeral prefixes (2+ chars) are removed."""
        assert clean_toc_title("IV. Fourth Chapter") == "Fourth Chapter"
        assert clean_toc_title("XII. Twelfth Section") == "Twelfth Section"

        # Single Roman chars without punctuation preserved
        assert clean_toc_title("I am a title") == "I am a title"
        assert clean_toc_title("V for Vendetta") == "V for Vendetta"


class TestEPUBExtractorFixes(ExtractionTestCase):
    """Regression tests for EPUB extractor fixes."""

    def test_no_xml_parser_warning(self, simple_epub_path, temp_output_dir, caplog):
        """Bug fix: No XMLParsedAsHTMLWarning with lxml-xml parser.

        Previously used "lxml" which triggered warnings.
        Now uses "lxml-xml" for proper XHTML parsing.
        """
        import warnings
        from bs4 import XMLParsedAsHTMLWarning

        # Capture warnings
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")

            extractor = EpubExtractor(str(simple_epub_path))
            extractor.load()
            extractor.parse()

            # Check no XMLParsedAsHTMLWarning was raised
            xml_warnings = [warning for warning in w
                           if issubclass(warning.category, XMLParsedAsHTMLWarning)]

            assert len(xml_warnings) == 0, \
                f"Got {len(xml_warnings)} XMLParsedAsHTMLWarning(s)"

    def test_provenance_hashes_present(self, simple_epub_path):
        """Bug fix: Provenance includes both content_hash and normalized_hash.

        Previously thought to be missing, but testing confirmed they work.
        This test ensures they remain present.
        """
        extractor = EpubExtractor(str(simple_epub_path))
        extractor.load()
        extractor.parse()

        provenance = extractor.provenance.to_dict()
        self.assert_provenance_complete(provenance)


class TestIntegrationRegression(ExtractionTestCase):
    """Full integration regression tests."""

    def test_simple_epub_extraction(self, simple_epub_path, temp_output_dir):
        """Smoke test: simple.epub should extract successfully.

        This is a regression test to ensure basic extraction works.
        """
        from extraction.extractors.configs import EpubExtractorConfig
        config = EpubExtractorConfig(chunking_strategy='nlp', filter_noise=False)
        extractor = EpubExtractor(str(simple_epub_path), config=config)
        extractor.load()
        extractor.parse()
        metadata = extractor.extract_metadata()
        output = extractor.get_output_data()

        # Basic validations
        self.assert_schema_compliance(output)
        self.assert_valid_quality(output["metadata"]["quality"])
        self.assert_valid_hierarchy(output["chunks"])

        # Should have extracted chunks
        assert len(output["chunks"]) > 0, "No chunks extracted"

        # All chunks should have text
        self.assert_no_empty_chunks(output["chunks"])

        # Word counts should be valid
        self.assert_word_counts_valid(output["chunks"])

        # Paragraph IDs should be sequential
        self.assert_paragraph_ids_sequential(output["chunks"])

    def test_quality_signals_all_valid(self, simple_epub_path):
        """Regression: All quality signals should be in [0, 1]."""
        from extraction.extractors.configs import EpubExtractorConfig
        config = EpubExtractorConfig(chunking_strategy='nlp', filter_noise=False)
        extractor = EpubExtractor(str(simple_epub_path), config=config)
        extractor.load()
        extractor.parse()
        metadata = extractor.extract_metadata()

        quality = metadata.to_dict().get("quality", {})
        signals = quality.get("signals", {})

        # Check each signal individually
        for signal_name, signal_value in signals.items():
            assert not math.isnan(signal_value), \
                f"Signal '{signal_name}' is NaN"
            assert not math.isinf(signal_value), \
                f"Signal '{signal_name}' is Inf"
            assert 0.0 <= signal_value <= 1.0, \
                f"Signal '{signal_name}' = {signal_value} out of bounds"


# Pytest markers for organization
pytest.mark.regression = pytest.mark.regression
