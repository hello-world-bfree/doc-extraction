#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Unit tests for core utilities.

Tests verify that extracted utilities match behavior of original implementations.
"""

import pytest
from src.extraction.core.identifiers import sha1, stable_id
from src.extraction.core.text import (
    normalize_spaced_caps, clean_text, estimate_word_count,
    clean_toc_title, normalize_ascii
)
from src.extraction.core.chunking import (
    split_sentences, heading_path, hierarchy_depth,
    heading_level, is_heading_tag
)
from src.extraction.core.extraction import (
    extract_dates, extract_scripture_references, extract_cross_references
)
from src.extraction.core.quality import (
    quality_signals_from_text, score_quality, route_doc
)


class TestIdentifiers:
    """Test ID generation functions."""

    def test_sha1(self):
        assert sha1(b"hello") == "aaf4c61ddcc5e8a2dabede0f3b482cd9aea9434d"
        assert sha1(b"") == "da39a3ee5e6b4b0d3255bfef95601890afd80709"

    def test_stable_id(self):
        # Test basic ID generation
        id1 = stable_id("part1", "part2", "part3")
        assert len(id1) == 16
        assert isinstance(id1, str)

        # Test consistency
        id2 = stable_id("part1", "part2", "part3")
        assert id1 == id2

        # Test different inputs produce different IDs
        id3 = stable_id("different", "parts")
        assert id1 != id3


class TestText:
    """Test text cleaning and normalization."""

    def test_normalize_spaced_caps(self):
        assert normalize_spaced_caps("S E C O N D") == "SECOND"
        assert normalize_spaced_caps("P RODIGAL") == "PRODIGAL"
        assert normalize_spaced_caps("S ON") == "SON"
        assert normalize_spaced_caps("A Word") == "A Word"  # Should not change
        assert normalize_spaced_caps("") == ""
        # Regression tests for spacing bug fix
        assert normalize_spaced_caps("Introduction to HTML Testing") == "Introduction to HTML Testing"
        assert normalize_spaced_caps("About XML Documents") == "About XML Documents"
        assert normalize_spaced_caps("Data from PDF Parser") == "Data from PDF Parser"

    def test_clean_text(self):
        assert clean_text("hello  world") == "hello world"
        assert clean_text("3 .") == "3."
        assert clean_text("word ,") == "word,"
        assert clean_text("") == ""
        # Test soft hyphen removal
        assert clean_text("hy\u00adphen") == "hyphen"

    def test_estimate_word_count(self):
        assert estimate_word_count("one two three") == 3
        assert estimate_word_count("") == 0
        assert estimate_word_count("single") == 1

    def test_clean_toc_title(self):
        assert clean_toc_title("1. Introduction") == "Introduction"
        assert clean_toc_title("Chapter 5: The Beginning") == "The Beginning"
        assert clean_toc_title("I.) First Section") == "First Section"
        assert clean_toc_title("Just a title") == "Just a title"

    def test_normalize_ascii(self):
        assert normalize_ascii("café") == "cafe"
        assert normalize_ascii("résumé") == "resume"
        assert normalize_ascii("hello") == "hello"


class TestChunking:
    """Test sentence splitting and hierarchy management."""

    def test_split_sentences(self):
        text = "First sentence. Second sentence! Third sentence?"
        sentences = split_sentences(text)
        assert len(sentences) == 3
        assert "First sentence." in sentences[0]

    def test_heading_path(self):
        hierarchy = {
            "level_1": "Book",
            "level_2": "Chapter 1",
            "level_3": "Section A",
            "level_4": "",
            "level_5": "",
            "level_6": ""
        }
        assert heading_path(hierarchy) == "Book / Chapter 1 / Section A"

        empty_hierarchy = {f"level_{i}": "" for i in range(1, 7)}
        assert heading_path(empty_hierarchy) == ""

    def test_hierarchy_depth(self):
        hierarchy = {
            "level_1": "Book",
            "level_2": "Chapter",
            "level_3": "",
            "level_4": "",
            "level_5": "",
            "level_6": ""
        }
        assert hierarchy_depth(hierarchy) == 2

        empty_hierarchy = {f"level_{i}": "" for i in range(1, 7)}
        assert hierarchy_depth(empty_hierarchy) == 0

    def test_heading_level(self):
        assert heading_level("h1") == 1
        assert heading_level("h6") == 6
        assert heading_level("div") == 99
        assert heading_level("") == 99

    def test_is_heading_tag(self):
        assert is_heading_tag("h1") is True
        assert is_heading_tag("h6") is True
        assert is_heading_tag("div") is False
        assert is_heading_tag("p") is False


class TestExtraction:
    """Test content extraction functions."""

    def test_extract_dates(self):
        text = "Published on January 15, 2023 and updated on 2023-12-25"
        dates = extract_dates(text)
        assert len(dates) >= 1
        assert any("January" in d or "2023" in d for d in dates)

    def test_extract_scripture_references(self):
        text = "As seen in John 3:16 and Matthew 5:1-12"
        refs = extract_scripture_references(text)
        assert len(refs) >= 1
        # Should find at least one reference
        assert any("John" in r or "Matthew" in r for r in refs)

    def test_extract_cross_references(self):
        text = "See CCC 2309 and canon 1234 for more information"
        refs = extract_cross_references(text)
        assert len(refs) >= 1
        assert any("CCC" in r or "canon" in r for r in refs)


class TestQuality:
    """Test quality scoring and routing."""

    def test_quality_signals_from_text(self):
        # Test with good quality text
        text = "The quick brown fox jumps over the lazy dog. " * 20
        signals = quality_signals_from_text(text)

        assert "garble_rate" in signals
        assert "mean_conf" in signals
        assert "line_len_std_norm" in signals
        assert "lang_prob" in signals

        # All signals should be in 0-1 range
        for value in signals.values():
            assert 0 <= value <= 1

    def test_quality_signals_empty_text(self):
        signals = quality_signals_from_text("")
        assert signals["garble_rate"] == 1.0
        assert signals["mean_conf"] == 0.0

    def test_score_quality(self):
        # Test with perfect signals
        perfect_signals = {
            "garble_rate": 0.0,
            "mean_conf": 1.0,
            "line_len_std_norm": 0.0,
            "lang_prob": 1.0
        }
        score = score_quality(perfect_signals)
        assert 0 <= score <= 1
        assert score > 0.9  # Should be high

        # Test with poor signals
        poor_signals = {
            "garble_rate": 1.0,
            "mean_conf": 0.0,
            "line_len_std_norm": 1.0,
            "lang_prob": 0.0
        }
        score = score_quality(poor_signals)
        assert 0 <= score <= 1
        assert score < 0.3  # Should be low

    def test_route_doc(self):
        # Test routing thresholds
        assert route_doc(0.85) == "A"  # High quality
        assert route_doc(0.80) == "A"  # Threshold
        assert route_doc(0.65) == "B"  # Medium quality
        assert route_doc(0.55) == "B"  # Threshold
        assert route_doc(0.45) == "C"  # Low quality
        assert route_doc(0.10) == "C"  # Very low quality


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
