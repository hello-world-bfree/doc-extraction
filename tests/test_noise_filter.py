#!/usr/bin/env python3
"""Tests for NoiseFilter."""

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


class TestFrontMatterDetection:
    """Tests for front matter detection."""

    def test_detects_dedication_phrases(self):
        """Should detect dedication patterns."""
        test_cases = [
            {"text": "Dedicated to my loving wife Sarah"},
            {"text": "For my parents, who always believed in me"},
            {"text": "In memory of John Doe, 1950-2020"},
            {"text": "To our soldiers who gave everything"},
        ]
        for chunk in test_cases:
            is_fm, reason = NoiseFilter.is_front_matter(chunk)
            assert is_fm is True
            assert reason == 'dedication_phrase'

    def test_detects_endorsement_sections(self):
        """Should detect endorsement/testimonial patterns."""
        test_cases = [
            {"text": "Praise for The Great Book..."},
            {"text": "Advance Praise: This book is amazing..."},
            {"text": "What readers are saying about this book"},
            {"text": "What people are saying: wonderful content"},
            {"text": "Acclaim for this masterpiece"},
            {"text": "Testimonials from our readers"},
        ]
        for chunk in test_cases:
            is_fm, reason = NoiseFilter.is_front_matter(chunk)
            assert is_fm is True
            assert reason == 'endorsement_section'

    def test_detects_toc_labels(self):
        """Should detect front matter via TOC hierarchy."""
        test_cases = [
            {"hierarchy": {"level_1": "dedication"}},
            {"hierarchy": {"level_1": "praise"}},
            {"hierarchy": {"level_1": "endorsements"}},
            {"hierarchy": {"level_1": "testimonials"}},
            {"hierarchy": {"level_1": "also by"}},
            {"hierarchy": {"level_1": "title page"}},
            {"hierarchy": {"level_1": "series page"}},
            {"hierarchy": {"level_1": "illustrations"}},
            {"hierarchy": {"level_1": "list of illustrations"}},
            {"hierarchy": {"level_1": "list of figures"}},
            {"hierarchy": {"level_1": "figures"}},
            {"hierarchy": {"level_1": "abbreviations"}},
            {"hierarchy": {"level_1": "list of abbreviations"}},
            {"hierarchy": {"level_1": "editor's preface"}},
            {"hierarchy": {"level_1": "editors' preface"}},
            {"hierarchy": {"level_1": "preface"}},
        ]
        for chunk in test_cases:
            is_fm, reason = NoiseFilter.is_front_matter(chunk)
            assert is_fm is True, f"Failed to detect: {chunk['hierarchy']}"
            assert reason == 'front_matter_toc_label'

    def test_false_positives_dedication(self):
        """Should NOT flag normal content mentioning dedication."""
        chunk = {"text": "This chapter discusses the dedication of the temple."}
        is_fm, _ = NoiseFilter.is_front_matter(chunk)
        assert is_fm is False

    def test_false_positives_praise(self):
        """Should NOT flag normal content about praise."""
        chunk = {"text": "The author praised God for his mercy."}
        is_fm, _ = NoiseFilter.is_front_matter(chunk)
        assert is_fm is False

    def test_false_positives_for_preposition(self):
        """Should NOT flag normal use of 'to' preposition."""
        chunk = {"text": "To understand this concept, we must look deeper."}
        is_fm, _ = NoiseFilter.is_front_matter(chunk)
        assert is_fm is False

    def test_false_positives_normal_hierarchy(self):
        """Should NOT flag normal chapter hierarchy."""
        chunk = {"hierarchy": {"level_1": "chapter 1"}}
        is_fm, _ = NoiseFilter.is_front_matter(chunk)
        assert is_fm is False

    def test_empty_chunk(self):
        """Should handle empty chunks gracefully."""
        chunk = {"text": ""}
        is_fm, reason = NoiseFilter.is_front_matter(chunk)
        assert is_fm is False
        assert reason == 'content'

    def test_missing_hierarchy(self):
        """Should handle chunks without hierarchy."""
        chunk = {"text": "Some normal text"}
        is_fm, reason = NoiseFilter.is_front_matter(chunk)
        assert is_fm is False
        assert reason == 'content'

    def test_detects_outline_sections(self):
        """Should detect outline sections via substring match."""
        test_cases = [
            {"hierarchy": {"level_1": "outline of mark"}, "text": "Prologue: The beginning"},
            {"hierarchy": {"level_1": "book outline"}, "text": "Chapter 1..."},
            {"hierarchy": {"level_1": "outline"}, "text": "Part I: Introduction"},
        ]
        for chunk in test_cases:
            is_fm, reason = NoiseFilter.is_front_matter(chunk)
            assert is_fm is True, f"Failed to detect: {chunk['hierarchy']}"
            assert reason == 'front_matter_toc_label'


class TestBackMatterDetection:
    """Tests for back matter detection."""

    def test_detects_glossary(self):
        """Should detect glossary sections."""
        chunk = {"hierarchy": {"level_1": "glossary"}, "text": "amen: Hebrew term..."}
        is_bm, reason = NoiseFilter.is_front_matter(chunk)
        assert is_bm is True
        assert reason == 'back_matter_toc_label'

    def test_detects_index_sections(self):
        """Should detect various index sections."""
        test_cases = [
            {"hierarchy": {"level_1": "index"}},
            {"hierarchy": {"level_1": "general index"}},
            {"hierarchy": {"level_1": "subject index"}},
            {"hierarchy": {"level_1": "scripture index"}},
            {"hierarchy": {"level_1": "index of sidebars"}},
        ]
        for chunk in test_cases:
            is_bm, reason = NoiseFilter.is_front_matter(chunk)
            assert is_bm is True, f"Failed to detect: {chunk['hierarchy']}"
            assert reason == 'back_matter_toc_label'

    def test_detects_notes_sections(self):
        """Should detect notes/endnotes sections."""
        test_cases = [
            {"hierarchy": {"level_1": "notes"}},
            {"hierarchy": {"level_1": "endnotes"}},
            {"hierarchy": {"level_1": "footnotes"}},
        ]
        for chunk in test_cases:
            is_bm, reason = NoiseFilter.is_front_matter(chunk)
            assert is_bm is True
            assert reason == 'back_matter_toc_label'

    def test_detects_resources_sections(self):
        """Should detect suggested resources sections."""
        test_cases = [
            {"hierarchy": {"level_1": "suggested resources"}},
            {"hierarchy": {"level_1": "further reading"}},
            {"hierarchy": {"level_1": "recommended reading"}},
            {"hierarchy": {"level_1": "bibliography"}},
        ]
        for chunk in test_cases:
            is_bm, reason = NoiseFilter.is_front_matter(chunk)
            assert is_bm is True
            assert reason == 'back_matter_toc_label'

    def test_detects_back_cover(self):
        """Should detect back cover."""
        chunk = {"hierarchy": {"level_1": "back cover"}}
        is_bm, reason = NoiseFilter.is_front_matter(chunk)
        assert is_bm is True
        assert reason == 'back_matter_toc_label'

    def test_detects_about_author(self):
        """Should detect about the author sections."""
        test_cases = [
            {"hierarchy": {"level_1": "about the author"}},
            {"hierarchy": {"level_1": "about the authors"}},
        ]
        for chunk in test_cases:
            is_bm, reason = NoiseFilter.is_front_matter(chunk)
            assert is_bm is True
            assert reason == 'back_matter_toc_label'

    def test_detects_geography_sections(self):
        """Should detect geography/map sections."""
        test_cases = [
            {"hierarchy": {"level_1": "geography"}},
            {"hierarchy": {"level_1": "geography of palestine in the time of christ"}},
        ]
        for chunk in test_cases:
            is_bm, reason = NoiseFilter.is_front_matter(chunk)
            assert is_bm is True
            assert reason == 'back_matter_toc_label'


class TestReferenceBlockDetection:
    """Tests for end-of-chapter reference block detection."""

    def test_detects_numbered_citations(self):
        """Should detect sequential numbered citations."""
        text = """Some chapter content here.

1. Michael Dauphinais, Holy People, Holy Land (Grand Rapids: Brazos, 2005), 46.

2. Origen, Homilies on Genesis and Exodus (Washington, DC: Catholic University Press, 1982), 232–38.

3. Karl Barth, The Doctrine of Creation, vol. 3.3 of Church Dogmatics (Edinburgh: T&T Clark, 1960), 289.

4. R. R. Reno, Genesis (Grand Rapids: Brazos, 2010), 39–46."""

        has_refs, start, count = NoiseFilter.detect_reference_block(text)
        assert has_refs is True
        assert count >= 4
        assert start > 0

    def test_detects_ibid_references(self):
        """Should detect references with Ibid."""
        text = """Content here.

1. Author Name, Book Title (Publisher, 2005), 100.

2. Ibid., 45-46.

3. Ibid., 50."""

        has_refs, start, count = NoiseFilter.detect_reference_block(text)
        assert has_refs is True
        assert count >= 3

    def test_requires_minimum_citations(self):
        """Should require at least 3 sequential citations."""
        text = """Content here.

1. Single Author, Book (2005).

2. Another Author, Another Book (2010)."""

        has_refs, start, count = NoiseFilter.detect_reference_block(text)
        assert has_refs is False

    def test_requires_sequential_numbering(self):
        """Should require citations starting from 1."""
        text = """Content here.

5. Author Name, Book Title (Publisher, 2005), 100.

6. Another Author, Another Book (2010), 200.

7. Third Author, Third Book (2015), 300."""

        has_refs, start, count = NoiseFilter.detect_reference_block(text)
        assert has_refs is False

    def test_does_not_flag_numbered_lists(self):
        """Should not flag normal numbered lists."""
        text = """Here are the steps:

1. First do this thing
2. Then do that thing
3. Finally complete the process"""

        has_refs, start, count = NoiseFilter.detect_reference_block(text)
        assert has_refs is False

    def test_empty_text(self):
        """Should handle empty text."""
        has_refs, start, count = NoiseFilter.detect_reference_block("")
        assert has_refs is False
        assert start == -1
        assert count == 0


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
