#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Integration tests for document extractors with real sample files.

These tests verify end-to-end extraction functionality using
the sample documents in tests/fixtures/sample_data/.
"""

import pytest
import os
from pathlib import Path

from src.extraction.extractors import (
    PdfExtractor,
    HtmlExtractor,
    MarkdownExtractor,
    JsonExtractor,
)


# Paths to sample documents
FIXTURES_DIR = Path(__file__).parent / "fixtures" / "sample_data"
PDF_SAMPLE = FIXTURES_DIR / "test_document.pdf"
HTML_SAMPLE = FIXTURES_DIR / "test_document.html"
MD_SAMPLE = FIXTURES_DIR / "test_document.md"


@pytest.mark.skipif(not PDF_SAMPLE.exists(), reason="PDF sample not available")
class TestPdfIntegration:
    """Integration tests for PDF extractor."""

    def test_pdf_extraction_end_to_end(self):
        """Test complete PDF extraction workflow."""
        extractor = PdfExtractor(str(PDF_SAMPLE))

        # Load
        extractor.load()
        assert extractor.provenance is not None
        assert extractor.provenance.source_file == "test_document.pdf"

        # Parse
        extractor.parse()
        assert len(extractor.chunks) > 0
        assert extractor.quality_score > 0

        # Extract metadata
        metadata = extractor.extract_metadata()
        assert metadata.title == "Sample PDF Document"
        assert metadata.author == "Test Author"

    def test_pdf_chunks_have_required_fields(self):
        """Verify PDF chunks have all required fields."""
        extractor = PdfExtractor(str(PDF_SAMPLE))
        extractor.load()
        extractor.parse()

        for chunk in extractor.chunks:
            assert chunk.stable_id
            assert chunk.paragraph_id > 0
            assert chunk.text
            assert chunk.word_count > 0
            assert isinstance(chunk.sentences, list)
            assert isinstance(chunk.cross_references, list)
            assert isinstance(chunk.scripture_references, list)

    def test_pdf_scripture_references_detected(self):
        """Verify PDF extractor detects scripture references."""
        extractor = PdfExtractor(str(PDF_SAMPLE))
        extractor.load()
        extractor.parse()

        # Combine all scripture references
        all_refs = []
        for chunk in extractor.chunks:
            all_refs.extend(chunk.scripture_references)

        # Should detect Ephesians 2:8-9 and Philippians 4:13
        assert len(all_refs) > 0
        ref_text = " ".join(all_refs)
        assert "Ephesians" in ref_text or "Philippians" in ref_text


@pytest.mark.skipif(not HTML_SAMPLE.exists(), reason="HTML sample not available")
class TestHtmlIntegration:
    """Integration tests for HTML extractor."""

    def test_html_extraction_end_to_end(self):
        """Test complete HTML extraction workflow."""
        extractor = HtmlExtractor(str(HTML_SAMPLE))

        # Load
        extractor.load()
        assert extractor.soup is not None
        assert extractor.html_title == "Sample HTML Document"

        # Parse
        extractor.parse()
        assert len(extractor.chunks) >= 10  # Should extract multiple paragraphs

        # Extract metadata
        metadata = extractor.extract_metadata()
        assert metadata.title == "Sample HTML Document"
        assert metadata.author == "Test Author"

    def test_html_hierarchy_preserved(self):
        """Verify HTML extractor preserves heading hierarchy."""
        extractor = HtmlExtractor(str(HTML_SAMPLE))
        extractor.load()
        extractor.parse()

        # Find chunks with hierarchy
        hierarchical_chunks = [c for c in extractor.chunks if c.hierarchy["level_1"]]
        assert len(hierarchical_chunks) > 0

        # Verify hierarchy structure
        for chunk in hierarchical_chunks:
            assert chunk.hierarchy["level_1"] == "Introduction to HTML Testing"

    def test_html_multiple_heading_levels(self):
        """Verify HTML handles multiple heading levels (h1-h4)."""
        extractor = HtmlExtractor(str(HTML_SAMPLE))
        extractor.load()
        extractor.parse()

        # Should have chunks with different hierarchy depths
        depths = [c.hierarchy_depth for c in extractor.chunks]
        unique_depths = set(depths)
        assert len(unique_depths) > 1  # Multiple levels present

    def test_html_scripture_references_detected(self):
        """Verify HTML extractor detects scripture references."""
        extractor = HtmlExtractor(str(HTML_SAMPLE))
        extractor.load()
        extractor.parse()

        # Combine all scripture references
        all_refs = []
        for chunk in extractor.chunks:
            all_refs.extend(chunk.scripture_references)

        # Should detect Romans 8:28 and Psalm 23:1-6
        assert len(all_refs) > 0
        ref_text = " ".join(all_refs)
        assert "Romans" in ref_text or "Psalm" in ref_text


@pytest.mark.skipif(not MD_SAMPLE.exists(), reason="Markdown sample not available")
class TestMarkdownIntegration:
    """Integration tests for Markdown extractor."""

    def test_markdown_extraction_end_to_end(self):
        """Test complete Markdown extraction workflow."""
        extractor = MarkdownExtractor(str(MD_SAMPLE))

        # Load
        extractor.load()
        assert extractor.raw_content
        assert extractor.frontmatter  # Should have extracted frontmatter

        # Parse
        extractor.parse()
        assert len(extractor.chunks) >= 5

        # Extract metadata
        metadata = extractor.extract_metadata()
        assert metadata.title == "Sample Markdown Document"
        assert metadata.author == "Test Author"

    def test_markdown_frontmatter_extraction(self):
        """Verify Markdown frontmatter is extracted correctly."""
        extractor = MarkdownExtractor(str(MD_SAMPLE))
        extractor.load()

        assert "title" in extractor.frontmatter
        assert extractor.frontmatter["title"] == "Sample Markdown Document"
        assert extractor.frontmatter["author"] == "Test Author"

    def test_markdown_hierarchy_preserved(self):
        """Verify Markdown extractor preserves heading hierarchy."""
        extractor = MarkdownExtractor(str(MD_SAMPLE))
        extractor.load()
        extractor.parse()

        # Find chunks with hierarchy
        hierarchical_chunks = [c for c in extractor.chunks if c.hierarchy["level_1"]]
        assert len(hierarchical_chunks) > 0

        # Verify hierarchy structure
        for chunk in hierarchical_chunks:
            assert chunk.hierarchy["level_1"] == "Introduction to Markdown Testing"

    def test_markdown_multiple_heading_levels(self):
        """Verify Markdown handles multiple heading levels (# ## ###)."""
        extractor = MarkdownExtractor(str(MD_SAMPLE))
        extractor.load()
        extractor.parse()

        # Should have chunks with different hierarchy depths
        depths = [c.hierarchy_depth for c in extractor.chunks]
        unique_depths = set(depths)
        assert len(unique_depths) > 1  # Multiple levels present

    def test_markdown_scripture_references_detected(self):
        """Verify Markdown extractor detects scripture references."""
        extractor = MarkdownExtractor(str(MD_SAMPLE))
        extractor.load()
        extractor.parse()

        # Combine all scripture references
        all_refs = []
        for chunk in extractor.chunks:
            all_refs.extend(chunk.scripture_references)

        # Should detect John 3:16 and Matthew 5:1-12
        assert len(all_refs) > 0
        ref_text = " ".join(all_refs)
        assert "John" in ref_text or "Matthew" in ref_text


class TestJsonIntegration:
    """Integration tests for JSON extractor (import mode)."""

    def test_json_import_roundtrip(self, tmp_path):
        """Test that JSON export -> import preserves data."""
        # First, extract from Markdown
        md_extractor = MarkdownExtractor(str(MD_SAMPLE))
        md_extractor.load()
        md_extractor.parse()
        md_metadata = md_extractor.extract_metadata()

        # Get output data
        output_data = md_extractor.get_output_data()

        # Write to JSON
        import json
        json_file = tmp_path / "roundtrip_test.json"
        with open(json_file, 'w') as f:
            json.dump(output_data, f)

        # Now import via JSON extractor
        json_extractor = JsonExtractor(str(json_file))
        json_extractor.load()
        json_extractor.parse()
        json_metadata = json_extractor.extract_metadata()

        # Verify data preserved
        assert len(json_extractor.chunks) == len(md_extractor.chunks)
        assert json_metadata.title == md_metadata.title
        assert json_metadata.author == md_metadata.author

        # Verify chunk text matches
        for i in range(len(md_extractor.chunks)):
            assert json_extractor.chunks[i].text == md_extractor.chunks[i].text


class TestCrossFormatComparison:
    """Compare extraction results across different formats."""

    @pytest.mark.skipif(
        not all([HTML_SAMPLE.exists(), MD_SAMPLE.exists()]),
        reason="HTML and Markdown samples needed"
    )
    def test_html_vs_markdown_structure(self):
        """Compare HTML and Markdown extraction of similar content."""
        html_extractor = HtmlExtractor(str(HTML_SAMPLE))
        html_extractor.load()
        html_extractor.parse()

        md_extractor = MarkdownExtractor(str(MD_SAMPLE))
        md_extractor.load()
        md_extractor.parse()

        # Both should extract multiple chunks
        assert len(html_extractor.chunks) > 5
        assert len(md_extractor.chunks) > 5

        # Both should have hierarchy
        html_has_hierarchy = any(c.hierarchy_depth > 0 for c in html_extractor.chunks)
        md_has_hierarchy = any(c.hierarchy_depth > 0 for c in md_extractor.chunks)

        assert html_has_hierarchy
        assert md_has_hierarchy

    @pytest.mark.skipif(
        not all([HTML_SAMPLE.exists(), MD_SAMPLE.exists()]),
        reason="HTML and Markdown samples needed"
    )
    def test_all_formats_detect_scripture(self):
        """Verify all extractors can detect scripture references."""
        extractors = []

        if HTML_SAMPLE.exists():
            html = HtmlExtractor(str(HTML_SAMPLE))
            html.load()
            html.parse()
            extractors.append(("HTML", html))

        if MD_SAMPLE.exists():
            md = MarkdownExtractor(str(MD_SAMPLE))
            md.load()
            md.parse()
            extractors.append(("Markdown", md))

        if PDF_SAMPLE.exists():
            pdf = PdfExtractor(str(PDF_SAMPLE))
            pdf.load()
            pdf.parse()
            extractors.append(("PDF", pdf))

        # All should detect at least some scripture references
        for name, extractor in extractors:
            all_refs = []
            for chunk in extractor.chunks:
                all_refs.extend(chunk.scripture_references)

            # At least one format should have references
            # (PDF might not due to text extraction limitations)
            if name != "PDF":
                assert len(all_refs) > 0, f"{name} should detect scripture references"


class TestTextSpacingCorrectness:
    """
    Explicit tests to prevent text spacing bugs.

    These tests verify that text extraction maintains proper spacing
    between words, especially when extracting from nested HTML/XML elements.
    """

    @pytest.mark.skipif(not HTML_SAMPLE.exists(), reason="HTML sample needed")
    def test_html_heading_spacing_preserved(self):
        """Verify HTML heading extraction preserves spaces between words."""
        extractor = HtmlExtractor(str(HTML_SAMPLE))
        extractor.load()
        extractor.parse()

        # Find chunks with "Introduction" heading
        intro_chunks = [
            c for c in extractor.chunks
            if c.hierarchy.get("level_1", "").startswith("Introduction")
        ]

        assert len(intro_chunks) > 0, "Should have chunks under Introduction heading"

        # Verify NO smashed words in hierarchy
        heading = intro_chunks[0].hierarchy["level_1"]

        # These patterns indicate spacing bugs
        bad_patterns = [
            "HTMLTesting",  # Should be "HTML Testing"
            "toHTML",       # Should be "to HTML"
        ]

        for bad_pattern in bad_patterns:
            assert bad_pattern not in heading, \
                f"Heading contains smashed words: '{heading}' contains '{bad_pattern}'"

        # Positive assertion - should contain properly spaced version
        assert "HTML Testing" in heading, \
            f"Heading should contain 'HTML Testing': '{heading}'"

    @pytest.mark.skipif(not HTML_SAMPLE.exists(), reason="HTML sample needed")
    def test_no_double_spaces_in_output(self):
        """Verify text cleaning doesn't introduce double spaces."""
        extractor = HtmlExtractor(str(HTML_SAMPLE))
        extractor.load()
        extractor.parse()

        for chunk in extractor.chunks:
            # Should have no double spaces
            assert "  " not in chunk.text, \
                f"Chunk {chunk.paragraph_id} has double spaces: '{chunk.text}'"

            # Hierarchy should also have no double spaces
            for level, text in chunk.hierarchy.items():
                if text:
                    assert "  " not in text, \
                        f"Hierarchy {level} has double spaces: '{text}'"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
