#!/usr/bin/env python3
"""Tests for NoiseFilter."""

import pytest
from extraction.core.noise_filter import NoiseFilter


class TestIndexPageDetection:
    """Tests for index page detection."""

    def test_detects_high_number_density(self):
        """Should detect chunks with >50% numbers/punctuation."""
        chunk = {"text": "1, Part 1 109 24 8* 27 133* 356 109*, 133* 357 108..."}
        assert NoiseFilter.is_index_page(chunk) is True

    def test_allows_normal_text_with_some_numbers(self):
        """Should allow normal text with reasonable number usage."""
        chunk = {"text": "In Chapter 3, we discuss the 5 main principles of design."}
        assert NoiseFilter.is_index_page(chunk) is False

    def test_detects_token_word_ratio_anomaly(self):
        """Should detect symbol-heavy content (token/word ratio > 2.5)."""
        chunk = {
            "text": "1:1-31 2:1-25 3:1-15 4:1-20 5:1-30 6:1-40",
            "token_count": 30,
            "word_count": 6
        }
        assert NoiseFilter.is_index_page(chunk) is True

    def test_detects_repetitive_reference_pattern(self):
        """Should detect repetitive reference patterns with many numbers."""
        chunk = {"text": "123 45* 678 91* 234 567* 890 12* 345"}
        assert NoiseFilter.is_index_page(chunk) is True


class TestCopyrightBoilerplate:
    """Tests for copyright boilerplate detection."""

    def test_detects_copyright_text(self):
        """Should detect copyright statements."""
        chunk = {
            "text": "Copyright © 2024 Publisher Name. All rights reserved.",
            "word_count": 7
        }
        assert NoiseFilter.is_copyright_boilerplate(chunk) is True

    def test_detects_isbn_numbers(self):
        """Should detect ISBN numbers."""
        chunk = {"text": "ISBN 978-0-123456-78-9"}
        assert NoiseFilter.is_copyright_boilerplate(chunk) is True

    def test_detects_publisher_boilerplate(self):
        """Should detect publisher codes."""
        chunk = {"text": "Publisher code: ABC-123"}
        assert NoiseFilter.is_copyright_boilerplate(chunk) is True

    def test_allows_normal_publication_discussion(self):
        """Should allow normal discussion mentioning publication."""
        chunk = {
            "text": "The book was published in 1995 and discusses the history of printing.",
            "word_count": 15
        }
        assert NoiseFilter.is_copyright_boilerplate(chunk) is False


class TestNavigationFragments:
    """Tests for navigation fragment detection."""

    def test_detects_toc_entry(self):
        """Should detect table of contents entries."""
        chunk = {
            "text": "Chapter 2, Arrays . . . . . . . . . 45",
            "hierarchy": {"level_1": "Table of Contents"},
            "word_count": 5
        }
        assert NoiseFilter.is_navigation_fragment(chunk) is True

    def test_detects_page_number_only(self):
        """Should detect standalone page numbers."""
        chunk = {"text": "page 305"}
        assert NoiseFilter.is_navigation_fragment(chunk) is True

    def test_detects_next_previous_links(self):
        """Should detect navigation links."""
        chunk = {"text": "next"}
        assert NoiseFilter.is_navigation_fragment(chunk) is True

    def test_allows_normal_short_sentences(self):
        """Should allow valid short content."""
        chunk = {"text": "Or both."}
        assert NoiseFilter.is_navigation_fragment(chunk) is False


class TestHierarchyBasedFiltering:
    """Tests for hierarchy-based filtering."""

    def test_filters_short_chunks_in_index_section(self):
        """Should filter short chunks in 'Index' sections."""
        chunk = {
            "text": "mutex, 343",
            "hierarchy": {"level_1": "Index"},
            "word_count": 2
        }
        assert NoiseFilter.is_navigation_fragment(chunk) is True

    def test_filters_short_chunks_in_toc_section(self):
        """Should filter short chunks in 'Contents' sections."""
        chunk = {
            "text": "Introduction 1",
            "hierarchy": {"level_1": "Contents"},
            "word_count": 2
        }
        assert NoiseFilter.is_navigation_fragment(chunk) is True

    def test_allows_short_chunks_in_normal_sections(self):
        """Should allow short chunks in normal sections."""
        chunk = {
            "text": "See below.",
            "hierarchy": {"level_1": "Chapter 1"},
            "word_count": 2
        }
        assert NoiseFilter.is_navigation_fragment(chunk) is False


class TestValidContentPreservation:
    """Tests ensuring valid content is not filtered."""

    def test_preserves_short_code_snippets(self):
        """Should preserve valid short code."""
        chunk = {"text": "return nil"}
        assert NoiseFilter.has_low_semantic_value(chunk) is False

    def test_preserves_short_statements(self):
        """Should preserve valid short statements."""
        chunk = {"text": "Or both."}
        assert NoiseFilter.has_low_semantic_value(chunk) is False

    def test_preserves_list_items_with_content(self):
        """Should preserve valid list items."""
        chunk = {"text": "• Compute costs money."}
        assert NoiseFilter.has_low_semantic_value(chunk) is False

    def test_preserves_normal_paragraphs(self):
        """Should preserve normal paragraphs."""
        chunk = {
            "text": "This is a normal paragraph with substantive content about a topic.",
            "word_count": 12
        }
        assert NoiseFilter.has_low_semantic_value(chunk) is False


class TestEdgeCases:
    """Tests for edge cases."""

    def test_empty_string(self):
        """Should handle empty strings."""
        chunk = {"text": ""}
        assert NoiseFilter.has_low_semantic_value(chunk) is False

    def test_whitespace_only(self):
        """Should handle whitespace-only."""
        chunk = {"text": "   \n\t  "}
        assert NoiseFilter.has_low_semantic_value(chunk) is False

    def test_very_long_valid_text(self):
        """Should allow long valid text."""
        chunk = {
            "text": "This is a very long paragraph " * 50,
            "word_count": 300
        }
        assert NoiseFilter.has_low_semantic_value(chunk) is False

    def test_mixed_content(self):
        """Should handle mixed content appropriately."""
        chunk = {
            "text": "Chapter 5 discusses algorithms with O(n) complexity.",
            "word_count": 7
        }
        assert NoiseFilter.has_low_semantic_value(chunk) is False
