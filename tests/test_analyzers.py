#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Unit tests for analyzer classes (BaseAnalyzer, CatholicAnalyzer).

Tests verify analyzer interface, pattern matching, and metadata enrichment.
"""

import pytest
from typing import Dict, List, Any

from src.extraction.analyzers.base import BaseAnalyzer
from src.extraction.analyzers.catholic import CatholicAnalyzer


class MockAnalyzer(BaseAnalyzer):
    """Mock analyzer for testing abstract base class."""

    def infer_document_type(self, text: str) -> str:
        """Mock document type inference."""
        if "technical manual" in text.lower():
            return "Technical Manual"
        return ""

    def extract_subjects(self, text: str, chunks: List[Dict]) -> List[str]:
        """Mock subject extraction."""
        subjects = []
        if "python" in text.lower():
            subjects.append("Python")
        if "testing" in text.lower():
            subjects.append("Testing")
        return subjects

    def extract_themes(self, chunks: List[Dict]) -> List[str]:
        """Mock theme extraction."""
        themes = []
        for chunk in chunks:
            h = chunk.get("hierarchy", {})
            if h.get("level_1"):
                themes.append(h["level_1"])
        return list(set(themes))[:10]

    def extract_related_documents(self, text: str) -> List[str]:
        """Mock related document extraction."""
        docs = []
        if "PEP 8" in text:
            docs.append("PEP 8")
        if "pytest docs" in text:
            docs.append("pytest documentation")
        return sorted(set(docs))

    def infer_geographic_focus(self, text: str) -> str:
        """Mock geographic focus inference."""
        if "worldwide" in text.lower():
            return "Global"
        return ""

    def enrich_metadata(
        self,
        base_metadata: Dict[str, Any],
        full_text: str,
        chunks: List[Dict]
    ) -> Dict[str, Any]:
        """Mock metadata enrichment."""
        base_metadata["document_type"] = self.infer_document_type(full_text)
        base_metadata["subject"] = self.extract_subjects(full_text, chunks)
        base_metadata["key_themes"] = self.extract_themes(chunks)
        base_metadata["related_documents"] = self.extract_related_documents(full_text)
        base_metadata["geographic_focus"] = self.infer_geographic_focus(full_text)

        stats = self.calculate_stats(chunks)
        base_metadata["word_count"] = stats["word_count"]
        base_metadata["pages"] = stats["pages"]

        return base_metadata


class TestBaseAnalyzer:
    """Test BaseAnalyzer abstract class via MockAnalyzer."""

    def test_initialization(self):
        """Test analyzer initialization."""
        analyzer = MockAnalyzer()
        assert analyzer.config == {}

    def test_initialization_with_config(self):
        """Test analyzer initialization with config."""
        config = {"patterns": ["test"], "threshold": 0.5}
        analyzer = MockAnalyzer(config)
        assert analyzer.config == config

    def test_calculate_stats(self):
        """Test stats calculation helper."""
        analyzer = MockAnalyzer()
        chunks = [
            {"word_count": 100},
            {"word_count": 150},
            {"word_count": 250},
        ]

        stats = analyzer.calculate_stats(chunks)
        assert "word_count" in stats
        assert "pages" in stats
        assert "500" in stats["word_count"]  # Approximately 500
        assert stats["pages"] == "approximately 2"  # 500 / 250 = 2

    def test_calculate_stats_empty_chunks(self):
        """Test stats calculation with empty chunks."""
        analyzer = MockAnalyzer()
        stats = analyzer.calculate_stats([])

        assert stats["word_count"] == "approximately 0"
        assert stats["pages"] == "approximately 1"  # Minimum 1 page

    def test_enrich_metadata(self):
        """Test metadata enrichment."""
        analyzer = MockAnalyzer()

        base = {"title": "Test Doc", "author": "Test Author"}
        text = "This is a technical manual about Python testing worldwide. See PEP 8."
        chunks = [
            {"hierarchy": {"level_1": "Chapter 1"}, "word_count": 100},
            {"hierarchy": {"level_1": "Chapter 2"}, "word_count": 150},
        ]

        enriched = analyzer.enrich_metadata(base, text, chunks)

        assert enriched["document_type"] == "Technical Manual"
        assert "Python" in enriched["subject"]
        assert "Testing" in enriched["subject"]
        assert "Chapter 1" in enriched["key_themes"] or "Chapter 2" in enriched["key_themes"]
        assert enriched["related_documents"] == ["PEP 8"]
        assert enriched["geographic_focus"] == "Global"
        assert "word_count" in enriched
        assert "pages" in enriched


class TestCatholicAnalyzer:
    """Test CatholicAnalyzer implementation."""

    def test_initialization(self):
        """Test Catholic analyzer initialization."""
        analyzer = CatholicAnalyzer()
        assert analyzer.config == {}
        assert analyzer.doc_type_patterns
        assert analyzer.subject_patterns
        assert analyzer.related_doc_patterns
        assert analyzer.geo_patterns

    def test_initialization_with_custom_config(self):
        """Test Catholic analyzer with custom patterns."""
        custom_docs = {
            "Custom Type": [r"custom pattern"]
        }
        config = {"document_types": custom_docs}
        analyzer = CatholicAnalyzer(config)
        assert analyzer.doc_type_patterns == custom_docs

    def test_infer_document_type_encyclical(self):
        """Test encyclical detection."""
        analyzer = CatholicAnalyzer()
        text = "This is a papal encyclical letter on social teaching."
        doc_type = analyzer.infer_document_type(text)
        assert doc_type == "Encyclical"

    def test_infer_document_type_apostolic_exhortation(self):
        """Test apostolic exhortation detection."""
        analyzer = CatholicAnalyzer()
        text = "This apostolic exhortation addresses the family."
        doc_type = analyzer.infer_document_type(text)
        assert doc_type == "Apostolic Exhortation"

    def test_infer_document_type_constitution(self):
        """Test constitution detection."""
        analyzer = CatholicAnalyzer()
        text = "The dogmatic constitution on Divine Revelation."
        doc_type = analyzer.infer_document_type(text)
        assert doc_type == "Dogmatic Constitution"

    def test_infer_document_type_no_match(self):
        """Test document type when no pattern matches."""
        analyzer = CatholicAnalyzer()
        text = "This is a general Catholic book about prayer."
        doc_type = analyzer.infer_document_type(text)
        assert doc_type == ""

    def test_extract_subjects_liturgy(self):
        """Test liturgy subject extraction."""
        analyzer = CatholicAnalyzer()
        text = "The sacred liturgy is the source and summit of Christian life."
        subjects = analyzer.extract_subjects(text, [])
        assert "Liturgy" in subjects

    def test_extract_subjects_sacraments(self):
        """Test sacraments subject extraction."""
        analyzer = CatholicAnalyzer()
        text = "The seven sacraments are baptism, confirmation, eucharist, reconciliation, anointing, holy orders, and marriage."
        subjects = analyzer.extract_subjects(text, [])
        assert "Sacraments" in subjects

    def test_extract_subjects_prayer(self):
        """Test prayer subject extraction."""
        analyzer = CatholicAnalyzer()
        text = "Prayer is the raising of one's mind and heart to God."
        subjects = analyzer.extract_subjects(text, [])
        assert "Prayer" in subjects

    def test_extract_subjects_multiple(self):
        """Test multiple subject extraction."""
        analyzer = CatholicAnalyzer()
        text = "The liturgy of the Mass includes sacramental prayer and devotion to Mary."
        subjects = analyzer.extract_subjects(text, [])
        assert len(subjects) >= 2
        assert any(s in subjects for s in ["Liturgy", "Mass", "Prayer", "Mariology"])

    def test_extract_themes(self):
        """Test theme extraction from chunks."""
        analyzer = CatholicAnalyzer()
        chunks = [
            {"hierarchy": {"level_1": "Introduction to Prayer", "level_2": ""}},
            {"hierarchy": {"level_1": "Introduction to Prayer", "level_2": ""}},
            {"hierarchy": {"level_1": "The Nature of Liturgy", "level_2": ""}},
            {"hierarchy": {"level_1": "Sacramental Theology", "level_2": ""}},
        ]
        themes = analyzer.extract_themes(chunks)

        assert len(themes) <= 10
        assert "Introduction to Prayer" in themes
        assert "The Nature of Liturgy" in themes
        assert "Sacramental Theology" in themes
        # Should deduplicate
        assert themes.count("Introduction to Prayer") == 1

    def test_extract_themes_filters_short_headings(self):
        """Test that short headings are filtered out."""
        analyzer = CatholicAnalyzer()
        chunks = [
            {"hierarchy": {"level_1": "Short", "level_2": ""}},  # 5 chars, should be filtered
            {"hierarchy": {"level_1": "This is a long heading", "level_2": ""}},  # Should be kept
        ]
        themes = analyzer.extract_themes(chunks)

        assert "Short" not in themes
        assert "This is a long heading" in themes

    def test_extract_themes_limit_to_ten(self):
        """Test that themes are limited to 10."""
        analyzer = CatholicAnalyzer()
        chunks = [
            {"hierarchy": {"level_1": f"Heading Number {i:02d}", "level_2": ""}}
            for i in range(15)
        ]
        themes = analyzer.extract_themes(chunks)
        assert len(themes) == 10

    def test_extract_related_documents(self):
        """Test related document extraction."""
        analyzer = CatholicAnalyzer()
        text = "As stated in Lumen Gentium and echoed in Dei Verbum, the Catechism of the Catholic Church affirms..."
        related = analyzer.extract_related_documents(text)

        assert "Lumen Gentium" in related
        assert "Dei Verbum" in related
        assert "Catechism of the Catholic Church" in related
        # Should be sorted and unique
        assert related == sorted(related)

    def test_extract_related_documents_none_found(self):
        """Test related documents when none are found."""
        analyzer = CatholicAnalyzer()
        text = "This is a general discussion with no specific document references."
        related = analyzer.extract_related_documents(text)
        assert related == []

    def test_infer_geographic_focus_vatican(self):
        """Test Vatican geographic focus detection."""
        analyzer = CatholicAnalyzer()
        text = "Given at the Vatican, from the Apostolic See in Rome."
        focus = analyzer.infer_geographic_focus(text)
        assert focus == "Vatican City (Rome)"

    def test_infer_geographic_focus_universal(self):
        """Test Universal Church focus detection."""
        analyzer = CatholicAnalyzer()
        text = "To the bishops and faithful of the universal Church."
        focus = analyzer.infer_geographic_focus(text)
        assert focus == "Universal Church"

    def test_infer_geographic_focus_no_match(self):
        """Test geographic focus when no pattern matches."""
        analyzer = CatholicAnalyzer()
        text = "This is a general theological reflection."
        focus = analyzer.infer_geographic_focus(text)
        assert focus == ""

    def test_extract_promulgation_date_with_context(self):
        """Test promulgation date extraction with keyword context."""
        analyzer = CatholicAnalyzer()
        text = "Given at Rome, from Saint Peter's, on December 25, 1963, the promulgated date."
        dates = ["December 25, 1963", "January 1, 1964"]

        date = analyzer.extract_promulgation_date(text, dates)
        assert "December 25, 1963" in date

    def test_extract_promulgation_date_fallback(self):
        """Test promulgation date fallback to first date."""
        analyzer = CatholicAnalyzer()
        text = "This document was created in 1960."
        dates = ["1960", "1961"]

        date = analyzer.extract_promulgation_date(text, dates)
        assert date == "1960"

    def test_extract_promulgation_date_no_dates(self):
        """Test promulgation date with no dates."""
        analyzer = CatholicAnalyzer()
        date = analyzer.extract_promulgation_date("Some text", [])
        assert date == ""

    def test_rollup_footnotes(self):
        """Test footnote rollup."""
        analyzer = CatholicAnalyzer()
        chunks = [
            {"footnote_citations": {"all": [1, 2, 3]}},
            {"footnote_citations": {"all": [2, 3, 4]}},
            {"footnote_citations": {"all": [1, 5]}},
        ]

        result = analyzer.rollup_footnotes(chunks)
        assert result is not None
        assert "unique_citations" in result
        assert "counts" in result
        assert sorted(result["unique_citations"]) == [1, 2, 3, 4, 5]
        assert result["counts"]["1"] == 2
        assert result["counts"]["2"] == 2
        assert result["counts"]["3"] == 2
        assert result["counts"]["4"] == 1
        assert result["counts"]["5"] == 1

    def test_rollup_footnotes_no_footnotes(self):
        """Test footnote rollup with no footnotes."""
        analyzer = CatholicAnalyzer()
        chunks = [
            {"text": "Some text without footnotes"},
            {"text": "More text"},
        ]

        result = analyzer.rollup_footnotes(chunks)
        assert result is None

    def test_enrich_metadata_complete(self):
        """Test complete metadata enrichment."""
        analyzer = CatholicAnalyzer()

        base = {
            "title": "Sacrosanctum Concilium",
            "author": "Pope Paul VI",
            "publisher": "Vatican Press"
        }

        text = """
        Constitution on the Sacred Liturgy Sacrosanctum Concilium.
        Given at Rome from Saint Peter's on December 4, 1963.
        The sacred liturgy is the source and summit. The Mass and sacraments
        are central to Catholic life. Reference to Lumen Gentium.
        """

        chunks = [
            {
                "hierarchy": {"level_1": "Introduction to Liturgy", "level_2": ""},
                "word_count": 150,
                "footnote_citations": {"all": [1, 2]}
            },
            {
                "hierarchy": {"level_1": "The Nature of the Liturgy", "level_2": ""},
                "word_count": 200,
                "footnote_citations": {"all": [1, 3]}
            },
        ]

        enriched = analyzer.enrich_metadata(base, text, chunks)

        # Basic metadata preserved
        assert enriched["title"] == "Sacrosanctum Concilium"

        # Catholic-specific fields added
        assert enriched["document_type"] == "Constitution"
        assert "Liturgy" in enriched["subject"] or "Mass" in enriched["subject"]
        assert len(enriched["key_themes"]) > 0
        assert "Lumen Gentium" in enriched["related_documents"]
        assert enriched["date_promulgated"]  # Should extract December 4, 1963
        assert "word_count" in enriched
        assert "pages" in enriched

        # Footnotes rollup
        assert "footnotes_summary" in enriched
        assert enriched["footnotes_summary"]["unique_citations"] == [1, 2, 3]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
