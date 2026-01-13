#!/usr/bin/env python3
"""Base test framework for extraction library.

Provides reusable assertion methods for validating extraction outputs.
"""
import math
from typing import Dict, List, Any


class ExtractionTestCase:
    """Base class for extraction tests with common validation methods."""

    @staticmethod
    def assert_no_data_loss(extractor, expected_min_chunks: int):
        """Verify no silent chunk loss during extraction.

        Args:
            extractor: Extractor instance after parse()
            expected_min_chunks: Minimum number of chunks expected
        """
        actual = len(extractor.chunks_dict)
        assert actual >= expected_min_chunks, \
            f"Expected >= {expected_min_chunks} chunks, got {actual}"

    @staticmethod
    def assert_valid_quality(quality_dict: Dict[str, Any]):
        """Verify quality metrics are in valid range.

        Args:
            quality_dict: metadata.quality dictionary from output

        Checks:
            - Score in [0.0, 1.0]
            - Score is not NaN or Inf
            - Route is "A", "B", or "C"
            - All signals in [0.0, 1.0]
        """
        score = quality_dict["score"]

        # Check score validity
        assert not math.isnan(score), f"Quality score is NaN"
        assert not math.isinf(score), f"Quality score is Inf"
        assert 0.0 <= score <= 1.0, f"Score {score} out of bounds [0, 1]"

        # Check route
        route = quality_dict["route"]
        assert route in ["A", "B", "C"], f"Invalid route '{route}', expected A/B/C"

        # Check all signals
        signals = quality_dict.get("signals", {})
        for signal_name, signal_value in signals.items():
            assert not math.isnan(signal_value), \
                f"Signal '{signal_name}' is NaN"
            assert not math.isinf(signal_value), \
                f"Signal '{signal_name}' is Inf"
            assert 0.0 <= signal_value <= 1.0, \
                f"Signal '{signal_name}' = {signal_value} out of bounds [0, 1]"

    @staticmethod
    def assert_valid_hierarchy(chunks: List[Dict[str, Any]]):
        """Verify hierarchy structure is valid.

        Args:
            chunks: List of chunk dictionaries

        Checks:
            - Hierarchy keys are level_1 through level_6 only
            - No invalid level numbers
        """
        for idx, chunk in enumerate(chunks):
            hierarchy = chunk.get("hierarchy", {})

            # Check all hierarchy keys are valid
            for key in hierarchy.keys():
                assert key.startswith("level_"), \
                    f"Chunk {idx}: Invalid hierarchy key '{key}'"

                # Extract level number
                try:
                    level_num = int(key.split("_")[1])
                except (IndexError, ValueError):
                    raise AssertionError(
                        f"Chunk {idx}: Malformed hierarchy key '{key}'"
                    )

                assert 1 <= level_num <= 6, \
                    f"Chunk {idx}: Level {level_num} out of bounds [1, 6]"

    @staticmethod
    def assert_provenance_complete(provenance_dict: Dict[str, Any]):
        """Verify provenance has required hashes.

        Args:
            provenance_dict: metadata.provenance dictionary

        Checks:
            - content_hash exists and is SHA1 (40 chars)
            - normalized_hash exists and is SHA1 (40 chars)
        """
        assert "content_hash" in provenance_dict, \
            "Missing content_hash in provenance"
        assert "normalized_hash" in provenance_dict, \
            "Missing normalized_hash in provenance"

        content_hash = provenance_dict["content_hash"]
        normalized_hash = provenance_dict["normalized_hash"]

        assert len(content_hash) == 40, \
            f"content_hash length {len(content_hash)}, expected 40 (SHA1)"
        assert len(normalized_hash) == 40, \
            f"normalized_hash length {len(normalized_hash)}, expected 40 (SHA1)"

    @staticmethod
    def assert_schema_compliance(output: Dict[str, Any]):
        """Basic schema checks for extraction output.

        Args:
            output: Full output dictionary from get_output_data()

        Checks:
            - Top-level keys: metadata, chunks, extraction_info
            - chunks is a list
            - Each chunk has required fields
        """
        # Check top-level structure
        assert "metadata" in output, "Missing 'metadata' in output"
        assert "chunks" in output, "Missing 'chunks' in output"
        assert "extraction_info" in output, "Missing 'extraction_info' in output"

        # Check chunks is a list
        assert isinstance(output["chunks"], list), \
            f"chunks should be list, got {type(output['chunks'])}"

        # Check first chunk has required fields (if any chunks exist)
        if output["chunks"]:
            chunk = output["chunks"][0]
            required_fields = [
                "stable_id", "paragraph_id", "text", "hierarchy",
                "word_count", "chapter_href"
            ]
            for field in required_fields:
                assert field in chunk, \
                    f"Missing required field '{field}' in chunk"

    @staticmethod
    def assert_no_empty_chunks(chunks: List[Dict[str, Any]]):
        """Verify no chunks have empty text.

        Args:
            chunks: List of chunk dictionaries
        """
        for idx, chunk in enumerate(chunks):
            text = chunk.get("text", "")
            assert text.strip(), f"Chunk {idx} has empty text"

    @staticmethod
    def assert_word_counts_valid(chunks: List[Dict[str, Any]]):
        """Verify word counts are positive integers.

        Args:
            chunks: List of chunk dictionaries
        """
        for idx, chunk in enumerate(chunks):
            word_count = chunk.get("word_count", 0)
            assert isinstance(word_count, int), \
                f"Chunk {idx}: word_count should be int, got {type(word_count)}"
            assert word_count >= 0, \
                f"Chunk {idx}: word_count {word_count} is negative"

    @staticmethod
    def assert_paragraph_ids_sequential(chunks: List[Dict[str, Any]]):
        """Verify paragraph IDs are sequential starting from 1.

        Args:
            chunks: List of chunk dictionaries

        Note: This only checks that IDs are positive and increasing,
        not that they're strictly contiguous (some may be skipped).
        """
        prev_id = 0
        for idx, chunk in enumerate(chunks):
            para_id = chunk.get("paragraph_id", 0)
            assert para_id > 0, \
                f"Chunk {idx}: paragraph_id {para_id} must be > 0"
            assert para_id >= prev_id, \
                f"Chunk {idx}: paragraph_id {para_id} not increasing (prev={prev_id})"
            prev_id = para_id
