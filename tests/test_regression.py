#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Regression tests for backward compatibility.

Ensures that refactored code produces the same outputs as legacy parsers.
Tests verify:
- ID generation (sha1, stable_id) matches exactly
- Quality scoring formula unchanged
- Output format structure matches legacy
- Metadata fields preserved
"""

import pytest
import hashlib
from src.extraction.core.identifiers import sha1, stable_id
from src.extraction.core.quality import score_quality, route_doc
from src.extraction.core.text import normalize_spaced_caps, clean_text
from src.extraction.core.chunking import heading_level, is_heading_tag


class TestIDGenerationRegression:
    """Test that ID generation exactly matches legacy implementation."""

    def test_sha1_matches_legacy_implementation(self):
        """
        Verify sha1() produces exact same output as legacy implementation.

        Legacy implementation used:
        hashlib.sha1(content).hexdigest()
        """
        # Test cases from legacy parser
        test_cases = [
            (b"hello world", "2aae6c35c94fcfb415dbe95f408b9ce91ee846ed"),
            (b"", "da39a3ee5e6b4b0d3255bfef95601890afd80709"),
            (b"The quick brown fox", "5c6ce81d2ff22a069dce6e3f1be7e08e6e273c07"),
        ]

        for content, expected_hash in test_cases:
            result = sha1(content)
            # Verify against both our implementation and hashlib
            assert result == expected_hash
            assert result == hashlib.sha1(content).hexdigest()

    def test_stable_id_deterministic(self):
        """
        Verify stable_id is deterministic and matches legacy.

        Legacy implementation:
        sha1("|".join(str(s) for s in parts).encode())[:16]
        """
        # Same inputs should always produce same ID
        id1 = stable_id("part1", "part2", "part3")
        id2 = stable_id("part1", "part2", "part3")
        assert id1 == id2
        assert len(id1) == 16

        # Verify against legacy formula
        parts = ["part1", "part2", "part3"]
        joined = "|".join(str(s) for s in parts).encode()
        legacy_id = hashlib.sha1(joined).hexdigest()[:16]
        assert id1 == legacy_id

    def test_stable_id_different_inputs(self):
        """Verify different inputs produce different IDs."""
        id1 = stable_id("doc1", "2023-01-01")
        id2 = stable_id("doc2", "2023-01-01")
        id3 = stable_id("doc1", "2023-01-02")

        assert id1 != id2
        assert id1 != id3
        assert id2 != id3


class TestQualityScoringRegression:
    """Test that quality scoring formula exactly matches legacy."""

    def test_score_quality_formula_unchanged(self):
        """
        Verify quality scoring formula matches legacy exactly.

        Legacy formula:
        1.0 - (
            0.35 * garble_rate +
            0.25 * (1 - mean_conf) +
            0.25 * line_len_std_norm +
            0.15 * (1 - lang_prob)
        )
        """
        # Test with known signal values
        signals = {
            "garble_rate": 0.1,
            "mean_conf": 0.9,
            "line_len_std_norm": 0.2,
            "lang_prob": 0.95
        }

        # Calculate manually using legacy formula
        expected = 1.0 - (
            0.35 * 0.1 +
            0.25 * (1 - 0.9) +
            0.25 * 0.2 +
            0.15 * (1 - 0.95)
        )

        result = score_quality(signals)
        assert abs(result - expected) < 0.0001  # Allow tiny floating point diff

    def test_score_quality_perfect_signals(self):
        """Test perfect quality signals produce score of 1.0."""
        signals = {
            "garble_rate": 0.0,
            "mean_conf": 1.0,
            "line_len_std_norm": 0.0,
            "lang_prob": 1.0
        }
        assert score_quality(signals) == 1.0

    def test_score_quality_worst_signals(self):
        """Test worst quality signals produce score of 0.0."""
        signals = {
            "garble_rate": 1.0,
            "mean_conf": 0.0,
            "line_len_std_norm": 1.0,
            "lang_prob": 0.0
        }
        assert score_quality(signals) == 0.0

    def test_route_doc_thresholds_unchanged(self):
        """
        Verify route_doc thresholds match legacy exactly.

        Legacy thresholds:
        - A: score >= 0.80
        - B: 0.55 <= score < 0.80
        - C: score < 0.55
        """
        # Test exact threshold boundaries
        assert route_doc(0.85) == "A"
        assert route_doc(0.80) == "A"  # Exactly at threshold
        assert route_doc(0.79) == "B"
        assert route_doc(0.65) == "B"
        assert route_doc(0.55) == "B"  # Exactly at threshold
        assert route_doc(0.54) == "C"
        assert route_doc(0.30) == "C"


class TestTextUtilsRegression:
    """Test text utilities match legacy implementations exactly."""

    def test_normalize_spaced_caps_legacy_pattern(self):
        """
        Verify normalize_spaced_caps matches legacy regex pattern.

        Legacy pattern: r"(?<![A-Z])\s+(?=[A-Z](?:\s+[A-Z])*(?!\s+[A-Z]))"
        """
        # Test cases from legacy parser
        test_cases = [
            ("S E C O N D", "SECOND"),
            ("P RODIGAL", "PRODIGAL"),
            ("S ON", "SON"),
            ("T H E  P R O D I G A L  S O N", "THE PRODIGAL SON"),
            ("Already Normal", "Already Normal"),  # No change
        ]

        for input_text, expected in test_cases:
            assert normalize_spaced_caps(input_text) == expected

    def test_clean_text_legacy_behavior(self):
        """Verify clean_text matches legacy implementation exactly."""
        # Test cases from legacy parser
        test_cases = [
            ("hello  world", "hello world"),  # Collapse spaces
            ("text\u00adwith\u00adhyphens", "textwith­hyphens"),  # Remove soft hyphens
            ("  leading and trailing  ", "leading and trailing"),  # Strip
            ("word ,", "word,"),  # Fix punctuation spacing
            ("word .", "word."),
            ("3 . 14", "3.14"),
        ]

        for input_text, expected in test_cases:
            result = clean_text(input_text)
            # Strip for comparison since legacy also strips
            assert result.strip() == expected.strip()


class TestChunkingRegression:
    """Test chunking utilities match legacy behavior."""

    def test_heading_level_legacy_behavior(self):
        """
        Verify heading_level matches legacy implementation.

        Legacy: returns int(tag[1]) for h1-h6, else 99
        """
        assert heading_level("h1") == 1
        assert heading_level("h2") == 2
        assert heading_level("h6") == 6
        assert heading_level("div") == 99
        assert heading_level("p") == 99
        assert heading_level("") == 99

    def test_is_heading_tag_legacy_behavior(self):
        """
        Verify is_heading_tag matches legacy implementation.

        Legacy: tag in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']
        """
        assert is_heading_tag("h1") is True
        assert is_heading_tag("h6") is True
        assert is_heading_tag("div") is False
        assert is_heading_tag("p") is False
        assert is_heading_tag("") is False


class TestOutputFormatRegression:
    """Test that output format structure matches legacy parsers."""

    def test_output_structure_keys(self):
        """
        Verify output JSON has exact same top-level keys as legacy.

        Legacy structure:
        {
            "metadata": {...},
            "chunks": [...],
            "extraction_info": {...}
        }
        """
        from src.extraction.extractors.base import BaseExtractor
        from src.extraction.core.models import Chunk, Metadata, Provenance, Quality

        class MinimalExtractor(BaseExtractor):
            def __init__(self):
                super().__init__("test.epub", {})
                self._provenance = Provenance(
                    doc_id="test", source_file="test.epub",
                    parser_version="1.0", md_schema_version="1.0",
                    ingestion_ts="2024-01-01T00:00:00", content_hash="abc"
                )
                self._quality = Quality(
                    signals={}, score=0.9, route="A"
                )
                self._doc_quality_score = 0.9
                self._doc_route = "A"

            def load(self): pass
            def parse(self):
                self.chunks = [Chunk(
                    chunk_id="c1", paragraph_id=1, text="Test",
                    hierarchy={"level_1": "", "level_2": "", "level_3": "", "level_4": "", "level_5": "", "level_6": ""},
                    word_count=1
                )]

            def extract_metadata(self):
                self.metadata = Metadata(title="Test", language="en")
                return self.metadata

        extractor = MinimalExtractor()
        extractor.parse()
        extractor.extract_metadata()
        output = extractor.get_output_data()

        # Verify exact key structure matches legacy
        assert set(output.keys()) == {"metadata", "chunks", "extraction_info"}

    def test_metadata_includes_provenance_and_quality(self):
        """Verify metadata dict includes provenance and quality (as in legacy)."""
        from src.extraction.extractors.base import BaseExtractor
        from src.extraction.core.models import Chunk, Metadata, Provenance, Quality

        class MinimalExtractor(BaseExtractor):
            def __init__(self):
                super().__init__("test.epub", {})
                self._provenance = Provenance(
                    doc_id="test", source_file="test.epub",
                    parser_version="1.0", md_schema_version="1.0",
                    ingestion_ts="2024-01-01T00:00:00", content_hash="abc"
                )
                self._quality = Quality(
                    signals={}, score=0.9, route="A"
                )
                self._doc_quality_score = 0.9
                self._doc_route = "A"

            def load(self): pass
            def parse(self):
                self.chunks = [Chunk(
                    chunk_id="c1", paragraph_id=1, text="Test",
                    hierarchy={"level_1": "", "level_2": "", "level_3": "", "level_4": "", "level_5": "", "level_6": ""},
                    word_count=1
                )]

            def extract_metadata(self):
                self.metadata = Metadata(title="Test", language="en")
                return self.metadata

        extractor = MinimalExtractor()
        extractor.parse()
        extractor.extract_metadata()
        output = extractor.get_output_data()

        # Legacy parsers include provenance and quality in metadata dict
        assert "provenance" in output["metadata"]
        assert "quality" in output["metadata"]

        # Verify structure
        assert "doc_id" in output["metadata"]["provenance"]
        assert "score" in output["metadata"]["quality"]
        assert "route" in output["metadata"]["quality"]

    def test_extraction_info_structure(self):
        """Verify extraction_info matches legacy structure."""
        from src.extraction.extractors.base import BaseExtractor
        from src.extraction.core.models import Chunk, Metadata, Provenance, Quality

        class MinimalExtractor(BaseExtractor):
            def __init__(self):
                super().__init__("test.epub", {})
                self._provenance = Provenance(
                    doc_id="test", source_file="test.epub",
                    parser_version="1.0", md_schema_version="1.0",
                    ingestion_ts="2024-01-01T00:00:00", content_hash="abc"
                )
                self._quality = Quality(
                    signals={}, score=0.9, route="A"
                )
                self._doc_quality_score = 0.9
                self._doc_route = "A"

            def load(self): pass
            def parse(self):
                self.chunks = [
                    Chunk(chunk_id="c1", paragraph_id=1, text="Test",
                          hierarchy={"level_1": "", "level_2": "", "level_3": "", "level_4": "", "level_5": "", "level_6": ""},
                          word_count=1),
                    Chunk(chunk_id="c2", paragraph_id=2, text="Test2",
                          hierarchy={"level_1": "", "level_2": "", "level_3": "", "level_4": "", "level_5": "", "level_6": ""},
                          word_count=1),
                ]

            def extract_metadata(self):
                self.metadata = Metadata(title="Test", language="en")
                return self.metadata

        extractor = MinimalExtractor()
        extractor.parse()
        extractor.extract_metadata()
        output = extractor.get_output_data()

        # Legacy extraction_info structure
        ext_info = output["extraction_info"]
        assert "total_chunks" in ext_info
        assert "quality_route" in ext_info
        assert "quality_score" in ext_info

        assert ext_info["total_chunks"] == 2
        assert ext_info["quality_route"] == "A"
        assert ext_info["quality_score"] == 0.9


class TestHierarchyStructureRegression:
    """Test hierarchy dictionary structure matches legacy exactly."""

    def test_hierarchy_has_six_levels(self):
        """
        Verify hierarchy dict has exactly 6 levels (level_1 through level_6).

        Legacy structure:
        {
            "level_1": "...",
            "level_2": "...",
            "level_3": "...",
            "level_4": "...",
            "level_5": "...",
            "level_6": ""
        }
        """
        from src.extraction.core.models import Chunk

        chunk = Chunk(
            chunk_id="test",
            paragraph_id=1,
            text="Test",
            hierarchy={
                "level_1": "Chapter",
                "level_2": "Section",
                "level_3": "",
                "level_4": "",
                "level_5": "",
                "level_6": ""
            },
            word_count=1
        )

        h = chunk.hierarchy
        assert set(h.keys()) == {
            "level_1", "level_2", "level_3", "level_4", "level_5", "level_6"
        }


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
