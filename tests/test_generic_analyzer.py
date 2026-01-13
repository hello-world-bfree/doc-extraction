#!/usr/bin/env python3
"""Tests for GenericAnalyzer."""

import pytest
from extraction.analyzers.generic import GenericAnalyzer


class TestInferDocumentType:
    """Tests for document type inference."""

    def test_empty_text_returns_unknown(self):
        """Empty text should return 'Document'."""
        analyzer = GenericAnalyzer()
        assert analyzer.infer_document_type("") == "Document"

    def test_short_text_returns_unknown(self):
        """Very short text should return 'Document' (default)."""
        analyzer = GenericAnalyzer()
        assert analyzer.infer_document_type("Short.") == "Document"

    def test_technical_document_detection(self):
        """Should detect technical documentation (>5 code blocks)."""
        analyzer = GenericAnalyzer()
        text = "```python\ncode\n```\n" * 6
        doc_type = analyzer.infer_document_type(text)
        assert doc_type == "Technical Document"

    def test_narrative_text_detection(self):
        """Should detect article (short with paragraphs)."""
        analyzer = GenericAnalyzer()
        text = "Paragraph one.\n\nParagraph two.\n\nParagraph three."
        doc_type = analyzer.infer_document_type(text)
        assert doc_type == "Article"

    def test_reference_material_detection(self):
        """Should detect manual (many numbered sections)."""
        analyzer = GenericAnalyzer()
        text = "\n".join([f"{i}. Section {i}" for i in range(1, 12)])
        doc_type = analyzer.infer_document_type(text)
        assert doc_type == "Manual"

    def test_structured_document_detection(self):
        """Should detect manual (many numbered sections)."""
        analyzer = GenericAnalyzer()
        text = "\n".join([f"{i}.{j} Item" for i in range(1, 6) for j in range(1, 5)])
        doc_type = analyzer.infer_document_type(text)
        assert doc_type == "Manual"


class TestExtractSubjects:
    """Tests for subject extraction."""

    def test_empty_chunks_returns_empty_list(self):
        """Empty chunks should return empty list."""
        analyzer = GenericAnalyzer()
        subjects = analyzer.extract_subjects("", [])
        assert subjects == []

    def test_extracts_top_level_headings(self):
        """Should extract level_1 and level_2 headings as subjects (up to 5 total)."""
        analyzer = GenericAnalyzer()
        chunks = [
            {'hierarchy': {'level_1': 'Introduction'}},
            {'hierarchy': {'level_1': 'Methods'}},
            {'hierarchy': {'level_1': 'Results'}},
        ]
        subjects = analyzer.extract_subjects("", chunks)
        assert 'Introduction' in subjects
        assert 'Methods' in subjects
        assert 'Results' in subjects

    def test_limits_to_five_subjects(self):
        """Should limit subjects to 5."""
        analyzer = GenericAnalyzer()
        chunks = [
            {'hierarchy': {'level_1': f'Chapter {i}'}} for i in range(1, 11)
        ]
        subjects = analyzer.extract_subjects("", chunks)
        assert len(subjects) <= 5

    def test_handles_missing_hierarchy(self):
        """Should handle chunks without hierarchy."""
        analyzer = GenericAnalyzer()
        chunks = [
            {'hierarchy': {}},
            {'text': 'No hierarchy here'},
        ]
        subjects = analyzer.extract_subjects("", chunks)
        assert subjects == []

    def test_deduplicates_subjects(self):
        """Should deduplicate repeated headings."""
        analyzer = GenericAnalyzer()
        chunks = [
            {'hierarchy': {'level_1': 'Introduction'}},
            {'hierarchy': {'level_1': 'Introduction'}},
            {'hierarchy': {'level_1': 'Introduction'}},
        ]
        subjects = analyzer.extract_subjects("", chunks)
        assert subjects == ['Introduction']


class TestExtractThemes:
    """Tests for theme extraction."""

    def test_empty_chunks_returns_empty_list(self):
        """Empty chunks should return empty list."""
        analyzer = GenericAnalyzer()
        themes = analyzer.extract_themes([])
        assert themes == []

    def test_extracts_all_hierarchy_levels(self):
        """Should extract headings from all levels."""
        analyzer = GenericAnalyzer()
        chunks = [
            {'hierarchy': {'level_1': 'Chapter 1', 'level_2': 'Section A', 'level_3': 'Subsection 1'}},
            {'hierarchy': {'level_1': 'Chapter 2', 'level_2': 'Section B'}},
        ]
        themes = analyzer.extract_themes(chunks)
        assert 'Chapter 1' in themes
        assert 'Section A' in themes
        assert 'Subsection 1' in themes
        assert 'Chapter 2' in themes
        assert 'Section B' in themes

    def test_returns_most_common_themes(self):
        """Should return most common themes first."""
        analyzer = GenericAnalyzer()
        chunks = [
            {'hierarchy': {'level_1': 'Common Topic'}},
            {'hierarchy': {'level_1': 'Common Topic'}},
            {'hierarchy': {'level_1': 'Common Topic'}},
            {'hierarchy': {'level_1': 'Rare Topic'}},
        ]
        themes = analyzer.extract_themes(chunks)
        assert themes[0] == 'Common Topic'

    def test_limits_to_ten_themes(self):
        """Should limit themes to 10."""
        analyzer = GenericAnalyzer()
        chunks = [
            {'hierarchy': {'level_1': f'Topic {i}'}} for i in range(1, 21)
        ]
        themes = analyzer.extract_themes(chunks)
        assert len(themes) <= 10


class TestExtractRelatedDocuments:
    """Tests for related document extraction."""

    def test_returns_empty_list(self):
        """GenericAnalyzer has no domain patterns, should return empty."""
        analyzer = GenericAnalyzer()
        related = analyzer.extract_related_documents("See Document A for more info.")
        assert related == []


class TestInferGeographicFocus:
    """Tests for geographic focus inference."""

    def test_returns_empty_string(self):
        """GenericAnalyzer has no geographic patterns, should return empty."""
        analyzer = GenericAnalyzer()
        focus = analyzer.infer_geographic_focus("This happened in Rome, Italy.")
        assert focus == ""


class TestEnrichMetadata:
    """Tests for metadata enrichment."""

    def test_enriches_with_all_fields(self):
        """enrich_metadata() should add all generic fields."""
        analyzer = GenericAnalyzer()
        base_metadata = {'title': 'Test Document', 'author': 'Test Author'}
        chunks = [
            {'hierarchy': {'level_1': 'Introduction', 'level_2': 'Overview'}},
            {'hierarchy': {'level_1': 'Methods', 'level_2': 'Approach'}},
        ]

        enriched = analyzer.enrich_metadata(base_metadata, "Some technical text with API endpoints.", chunks)

        assert 'document_type' in enriched
        assert 'subject' in enriched
        assert 'key_themes' in enriched
        assert 'related_documents' in enriched
        assert 'geographic_focus' in enriched

        # Original fields preserved
        assert enriched['title'] == 'Test Document'
        assert enriched['author'] == 'Test Author'

    def test_subject_is_list(self):
        """subject field should be a list."""
        analyzer = GenericAnalyzer()
        chunks = [{'hierarchy': {'level_1': 'Chapter 1'}}]
        enriched = analyzer.enrich_metadata({}, "", chunks)
        assert isinstance(enriched['subject'], list)

    def test_key_themes_is_list(self):
        """key_themes field should be a list."""
        analyzer = GenericAnalyzer()
        chunks = [{'hierarchy': {'level_1': 'Chapter 1'}}]
        enriched = analyzer.enrich_metadata({}, "", chunks)
        assert isinstance(enriched['key_themes'], list)

    def test_related_documents_is_empty_list(self):
        """related_documents should be empty list for GenericAnalyzer."""
        analyzer = GenericAnalyzer()
        enriched = analyzer.enrich_metadata({}, "", [])
        assert enriched['related_documents'] == []

    def test_geographic_focus_is_empty_string(self):
        """geographic_focus should be empty string for GenericAnalyzer."""
        analyzer = GenericAnalyzer()
        enriched = analyzer.enrich_metadata({}, "", [])
        assert enriched['geographic_focus'] == ""
