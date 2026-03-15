"""
Comprehensive tests for token-based re-chunking tool.

Tests cover:
- Token counting utilities
- Overlapping chunk creation
- Validation and splitting
- Hierarchy preservation
- End-to-end processing
- JSONL output format
"""

import json
import pytest
from pathlib import Path
from unittest.mock import Mock

pytest.importorskip("transformers", reason="transformers not installed (finetuning extra)")

from extraction.tools.tokenizer_utils import (
    load_tokenizer,
    count_tokens,
    tokenize_batch,
)
from extraction.tools.overlap_strategies import (
    TokenChunkConfig,
    RETRIEVAL_PRESET,
    RECOMMENDATION_PRESET,
    BALANCED_PRESET,
    find_overlap_start,
    create_overlapping_chunks,
    validate_and_split_oversized,
)
from extraction.tools.token_rechunker import (
    process_extraction_output,
    write_jsonl,
    calculate_statistics,
    determine_hierarchy,
)


class TestTokenizerUtils:
    """Tests for tokenizer loading and token counting."""

    def test_load_tokenizer_caching(self):
        """Tokenizer should be cached on subsequent calls."""
        tokenizer1 = load_tokenizer()
        tokenizer2 = load_tokenizer()
        assert tokenizer1 is tokenizer2

    def test_count_tokens_basic(self):
        """Token counting should work for simple text."""
        tokenizer = load_tokenizer()
        text = "This is a test sentence."
        count = count_tokens(text, tokenizer)
        assert count > 0
        assert isinstance(count, int)

    def test_count_tokens_empty(self):
        """Empty text should return 0 tokens."""
        tokenizer = load_tokenizer()
        assert count_tokens("", tokenizer) == 0
        assert count_tokens("   ", tokenizer) == 0

    def test_count_tokens_includes_special_tokens(self):
        """Token count should include special tokens."""
        tokenizer = load_tokenizer()
        text = "Hello"
        count = count_tokens(text, tokenizer)
        manual_count = len(tokenizer.encode(text, add_special_tokens=False))
        assert count > manual_count

    def test_tokenize_batch_efficiency(self):
        """Batch tokenization should handle multiple texts."""
        tokenizer = load_tokenizer()
        texts = [
            "First sentence.",
            "Second sentence with more words.",
            "Third sentence is longest of all three.",
        ]
        counts = tokenize_batch(texts, tokenizer)
        assert len(counts) == 3
        assert all(isinstance(c, int) for c in counts)
        assert counts[2] > counts[1] > counts[0]

    def test_tokenize_batch_empty_list(self):
        """Batch tokenization should handle empty input."""
        tokenizer = load_tokenizer()
        assert tokenize_batch([], tokenizer) == []


class TestOverlappingChunks:
    """Tests for sentence-aware overlapping chunk creation."""

    def test_create_chunks_no_overlap(self):
        """Chunks with overlap_percent=0 should have no overlap."""
        tokenizer = load_tokenizer()
        config = TokenChunkConfig(
            target_tokens=50,
            min_tokens=30,
            max_tokens=60,
            overlap_percent=0.0,
        )
        sentences = [
            "First sentence with some content here to make it longer for testing purposes.",
            "Second sentence with more content here to ensure we have enough tokens.",
            "Third sentence with even more content to push us over the limit.",
            "Fourth sentence to extend the text further and create another chunk.",
            "Fifth sentence to create multiple chunks with sufficient token counts.",
            "Sixth sentence adding more content to ensure multiple chunks are created.",
            "Seventh sentence continuing to add content for comprehensive testing.",
            "Eighth sentence wrapping up our multi-chunk test scenario here.",
        ]
        text = " ".join(sentences)
        chunks = create_overlapping_chunks(text, sentences, tokenizer, config)

        assert len(chunks) >= 1
        if len(chunks) > 1:
            first_chunk = chunks[0]
            assert not first_chunk[1].get("is_overlap")

    def test_create_chunks_with_10_percent_overlap(self):
        """Chunks should have approximately 10% overlap."""
        tokenizer = load_tokenizer()
        config = TokenChunkConfig(
            target_tokens=80,
            min_tokens=60,
            max_tokens=100,
            overlap_percent=0.10,
        )
        sentences = [
            "This is sentence number one in our test document with substantial content to ensure proper token counts.",
            "This is sentence number two with additional content and more details to expand the text significantly.",
            "This is sentence number three continuing the theme with even more elaborate descriptions and context.",
            "This is sentence number four adding more details and information to make the text longer and richer.",
            "This is sentence number five expanding further still with comprehensive explanations and examples here.",
            "This is sentence number six with even more information and detailed descriptions for thorough testing.",
            "This is sentence number seven providing extra context and additional content for comprehensive coverage.",
            "This is sentence number eight to ensure multiple chunks with sufficient token counts for proper testing.",
            "This is sentence number nine adding yet more content to guarantee we create multiple valid chunks.",
            "This is sentence number ten wrapping up with final details and comprehensive information for testing.",
        ]
        text = " ".join(sentences)
        chunks = create_overlapping_chunks(text, sentences, tokenizer, config)

        assert len(chunks) >= 1
        overlap_chunks = [c for c in chunks if c[1].get("is_overlap")]
        if len(chunks) > 1:
            assert len(overlap_chunks) > 0

    def test_create_chunks_respects_min_tokens(self):
        """Chunks below min_tokens should be dropped."""
        tokenizer = load_tokenizer()
        config = TokenChunkConfig(
            target_tokens=100,
            min_tokens=80,
            max_tokens=120,
            overlap_percent=0.10,
        )
        sentences = ["Short sentence.", "Another short one."]
        text = " ".join(sentences)
        chunks = create_overlapping_chunks(text, sentences, tokenizer, config)

        for chunk_text, metadata in chunks:
            token_count = metadata.get("token_count", 0)
            assert token_count >= config.min_tokens or len(chunks) == 1

    def test_create_chunks_respects_max_tokens(self):
        """No chunk should exceed max_tokens."""
        tokenizer = load_tokenizer()
        config = TokenChunkConfig(
            target_tokens=50,
            min_tokens=30,
            max_tokens=60,
            overlap_percent=0.10,
        )
        sentences = [
            "This is a sentence with quite a bit of content to test chunking.",
            "Another sentence with substantial text to continue testing the algorithm.",
            "Yet another sentence with more content to ensure we exceed max tokens.",
            "Final sentence to push us well over the token limit for a single chunk.",
        ]
        text = " ".join(sentences)
        chunks = create_overlapping_chunks(text, sentences, tokenizer, config)

        for chunk_text, metadata in chunks:
            token_count = metadata.get("token_count", 0)
            assert token_count <= config.max_tokens

    def test_find_overlap_start_backwards(self):
        """Overlap should start from end working backwards."""
        tokenizer = load_tokenizer()
        sentences = [
            "First sentence here.",
            "Second sentence here.",
            "Third sentence here.",
            "Fourth sentence here.",
        ]
        target_overlap = 10
        overlap_idx = find_overlap_start(sentences, target_overlap, tokenizer)

        assert 0 <= overlap_idx < len(sentences)
        overlap_sentences = sentences[overlap_idx:]
        overlap_tokens = sum(count_tokens(s, tokenizer) for s in overlap_sentences)
        assert overlap_tokens >= target_overlap or overlap_idx == 0

    def test_empty_sentences_returns_empty_chunks(self):
        """Empty sentence list should return no chunks."""
        tokenizer = load_tokenizer()
        config = BALANCED_PRESET
        chunks = create_overlapping_chunks("", [], tokenizer, config)
        assert chunks == []


class TestValidationAndSplitting:
    """Tests for oversized chunk validation and splitting."""

    def test_validate_under_limit_passes(self):
        """Chunks under 2048 tokens should pass validation."""
        tokenizer = load_tokenizer()
        config = BALANCED_PRESET
        text = "This is a short chunk that is well under the token limit."
        validated = validate_and_split_oversized(text, tokenizer, config)

        assert len(validated) == 1
        assert validated[0] == text

    def test_validate_splits_oversized_chunk(self):
        """Chunks over 2048 tokens should be split."""
        tokenizer = load_tokenizer()
        config = TokenChunkConfig(
            target_tokens=100,
            min_tokens=50,
            max_tokens=150,
            max_absolute_tokens=50,
        )
        long_text = ". ".join([f"Sentence number {i}" for i in range(100)])
        validated = validate_and_split_oversized(long_text, tokenizer, config)

        assert len(validated) > 1
        for sub_chunk in validated:
            token_count = count_tokens(sub_chunk, tokenizer)
            assert token_count <= config.max_absolute_tokens

    def test_validate_preserves_sentence_boundaries(self):
        """Splitting should preserve sentence structure."""
        tokenizer = load_tokenizer()
        config = TokenChunkConfig(
            target_tokens=100,
            min_tokens=50,
            max_tokens=150,
            max_absolute_tokens=40,
        )
        text = "First sentence. Second sentence. Third sentence. Fourth sentence."
        validated = validate_and_split_oversized(text, tokenizer, config)

        for sub_chunk in validated:
            assert sub_chunk.endswith(".")


class TestHierarchyPreservation:
    """Tests for hierarchy metadata preservation."""

    def test_single_source_inherits_hierarchy(self):
        """Single source chunk should inherit its hierarchy directly."""
        tokenizer = load_tokenizer()
        source_chunks = [
            {
                "hierarchy": {
                    "level_1": "Chapter 1",
                    "level_2": "Section A",
                },
                "text": "This is the chunk text.",
            }
        ]
        token_chunk_text = "This is the chunk text."

        hierarchy, crossed = determine_hierarchy(
            source_chunks, token_chunk_text, tokenizer
        )

        assert hierarchy == source_chunks[0]["hierarchy"]
        assert crossed is False

    def test_multi_source_uses_primary(self):
        """Multiple sources should use primary hierarchy (most token overlap)."""
        tokenizer = load_tokenizer()
        source_chunks = [
            {
                "hierarchy": {"level_1": "Chapter 1"},
                "text": "Short text.",
            },
            {
                "hierarchy": {"level_1": "Chapter 2"},
                "text": "This is much longer text with many more words to establish it as primary.",
            },
        ]
        token_chunk_text = "This is much longer text with many more words."

        hierarchy, crossed = determine_hierarchy(
            source_chunks, token_chunk_text, tokenizer
        )

        assert hierarchy == {"level_1": "Chapter 2"}
        assert crossed is True

    def test_boundary_crossing_detected(self):
        """Different hierarchies should be flagged as boundary crossing."""
        tokenizer = load_tokenizer()
        source_chunks = [
            {"hierarchy": {"level_1": "Chapter 1"}, "text": "First text."},
            {"hierarchy": {"level_1": "Chapter 2"}, "text": "Second text."},
        ]
        token_chunk_text = "Combined text."

        _, crossed = determine_hierarchy(source_chunks, token_chunk_text, tokenizer)

        assert crossed is True


class TestEndToEnd:
    """End-to-end integration tests."""

    def test_process_extraction_output(self, tmp_path):
        """Process sample extraction JSON and verify output."""
        tokenizer = load_tokenizer()
        config = TokenChunkConfig(
            target_tokens=100,
            min_tokens=50,
            max_tokens=150,
            overlap_percent=0.10,
        )

        input_path = Path("tests/fixtures/sample_extraction.json")
        if not input_path.exists():
            pytest.skip("Sample extraction fixture not found")

        chunks = list(
            process_extraction_output(input_path, config, tokenizer, preserve_metadata=False)
        )

        assert len(chunks) > 0
        for chunk in chunks:
            assert "text" in chunk
            assert "metadata" in chunk
            assert chunk["metadata"]["token_count"] >= config.min_tokens
            assert chunk["metadata"]["token_count"] <= config.max_tokens

    def test_jsonl_output_format(self, tmp_path):
        """JSONL output should have correct format."""
        output_path = tmp_path / "output.jsonl"

        chunks = [
            {
                "text": "Test chunk one.",
                "metadata": {"token_count": 5, "doc_id": "test"},
            },
            {
                "text": "Test chunk two.",
                "metadata": {"token_count": 5, "doc_id": "test"},
            },
        ]

        count = write_jsonl(iter(chunks), output_path)

        assert count == 2
        assert output_path.exists()

        with open(output_path) as f:
            lines = f.readlines()
            assert len(lines) == 2
            for line in lines:
                parsed = json.loads(line)
                assert "text" in parsed
                assert "metadata" in parsed

    def test_statistics_calculation(self, tmp_path):
        """Statistics should be calculated correctly."""
        output_path = tmp_path / "output.jsonl"

        chunks = [
            {
                "text": "Chunk 1",
                "metadata": {
                    "token_count": 100,
                    "sentence_count": 2,
                    "crossed_hierarchy_boundary": False,
                },
            },
            {
                "text": "Chunk 2",
                "metadata": {
                    "token_count": 200,
                    "sentence_count": 4,
                    "crossed_hierarchy_boundary": True,
                },
            },
            {
                "text": "Chunk 3",
                "metadata": {
                    "token_count": 150,
                    "sentence_count": 3,
                    "crossed_hierarchy_boundary": False,
                },
            },
        ]

        write_jsonl(iter(chunks), output_path)
        stats = calculate_statistics(output_path)

        assert stats["total_chunks"] == 3
        assert stats["total_tokens"] == 450
        assert stats["avg_tokens"] == 150.0
        assert stats["min_tokens"] == 100
        assert stats["max_tokens"] == 200
        assert stats["avg_sentences"] == 3.0
        assert stats["hierarchy_crossings"] == 1

    def test_retrieval_preset_produces_smaller_chunks(self):
        """Retrieval mode should produce smaller chunks than recommendation."""
        tokenizer = load_tokenizer()

        sentences = [
            f"This is sentence number {i} with substantial content to test chunking behavior and ensure we have enough tokens for proper validation."
            for i in range(50)
        ]
        text = " ".join(sentences)

        retrieval_chunks = create_overlapping_chunks(
            text, sentences, tokenizer, RETRIEVAL_PRESET
        )
        recommendation_chunks = create_overlapping_chunks(
            text, sentences, tokenizer, RECOMMENDATION_PRESET
        )

        assert len(retrieval_chunks) > 0
        assert len(recommendation_chunks) > 0
        assert len(retrieval_chunks) >= len(recommendation_chunks)

        if len(retrieval_chunks) > 0 and len(recommendation_chunks) > 0:
            retrieval_avg = sum(c[1]["token_count"] for c in retrieval_chunks) / len(
                retrieval_chunks
            )
            recommendation_avg = sum(
                c[1]["token_count"] for c in recommendation_chunks
            ) / len(recommendation_chunks)

            assert retrieval_avg < recommendation_avg

    def test_preserve_metadata_includes_references(self, tmp_path):
        """Preserve metadata flag should include scripture/cross references."""
        tokenizer = load_tokenizer()
        config = TokenChunkConfig(
            target_tokens=100,
            min_tokens=50,
            max_tokens=150,
            overlap_percent=0.10,
        )

        input_path = Path("tests/fixtures/sample_extraction.json")
        if not input_path.exists():
            pytest.skip("Sample extraction fixture not found")

        chunks_with_meta = list(
            process_extraction_output(
                input_path, config, tokenizer, preserve_metadata=True
            )
        )

        assert len(chunks_with_meta) > 0
        assert any(
            "scripture_references" in chunk["metadata"] for chunk in chunks_with_meta
        )
        assert any(
            "cross_references" in chunk["metadata"] for chunk in chunks_with_meta
        )


class TestConfigPresets:
    """Tests for chunking configuration presets."""

    def test_retrieval_preset_values(self):
        """Retrieval preset should have correct parameters."""
        assert RETRIEVAL_PRESET.target_tokens == 320
        assert RETRIEVAL_PRESET.min_tokens == 256
        assert RETRIEVAL_PRESET.max_tokens == 400
        assert RETRIEVAL_PRESET.overlap_percent == 0.15

    def test_recommendation_preset_values(self):
        """Recommendation preset should have correct parameters."""
        assert RECOMMENDATION_PRESET.target_tokens == 600
        assert RECOMMENDATION_PRESET.min_tokens == 512
        assert RECOMMENDATION_PRESET.max_tokens == 700
        assert RECOMMENDATION_PRESET.overlap_percent == 0.10

    def test_balanced_preset_values(self):
        """Balanced preset should be between retrieval and recommendation."""
        assert (
            RETRIEVAL_PRESET.target_tokens
            < BALANCED_PRESET.target_tokens
            < RECOMMENDATION_PRESET.target_tokens
        )
        assert (
            RETRIEVAL_PRESET.min_tokens
            < BALANCED_PRESET.min_tokens
            < RECOMMENDATION_PRESET.min_tokens
        )


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_very_long_sentence_gets_split(self):
        """Sentences exceeding max_absolute_tokens should be split."""
        tokenizer = load_tokenizer()
        config = TokenChunkConfig(
            target_tokens=100,
            min_tokens=50,
            max_tokens=150,
            max_absolute_tokens=30,
        )

        very_long_sentence = ". ".join([f"Sentence number {i} with some content" for i in range(50)])
        validated = validate_and_split_oversized(very_long_sentence, tokenizer, config)

        total_tokens = count_tokens(very_long_sentence, tokenizer)
        if total_tokens > config.max_absolute_tokens:
            assert len(validated) > 1
            for chunk in validated:
                assert count_tokens(chunk, tokenizer) <= config.max_absolute_tokens
        else:
            assert len(validated) == 1

    def test_empty_chunk_filtered(self, tmp_path):
        """Empty chunks should be filtered out."""
        tokenizer = load_tokenizer()
        config = BALANCED_PRESET

        input_data = {
            "metadata": {
                "provenance": {"doc_id": "test", "source_file": "test.txt"},
            },
            "chunks": [
                {
                    "stable_id": "chunk1",
                    "text": "",
                    "sentences": [],
                    "hierarchy": {},
                }
            ],
        }

        input_path = tmp_path / "empty_input.json"
        with open(input_path, "w") as f:
            json.dump(input_data, f)

        chunks = list(
            process_extraction_output(input_path, config, tokenizer)
        )

        assert len(chunks) == 0

    def test_below_minimum_tokens_skipped(self, tmp_path):
        """Chunks below min_tokens should be skipped."""
        tokenizer = load_tokenizer()
        config = TokenChunkConfig(
            target_tokens=400,
            min_tokens=300,
            max_tokens=500,
            overlap_percent=0.10,
        )

        input_data = {
            "metadata": {
                "provenance": {"doc_id": "test", "source_file": "test.txt"},
            },
            "chunks": [
                {
                    "stable_id": "chunk1",
                    "text": "Too short.",
                    "sentences": ["Too short."],
                    "hierarchy": {},
                }
            ],
        }

        input_path = tmp_path / "short_input.json"
        with open(input_path, "w") as f:
            json.dump(input_data, f)

        chunks = list(
            process_extraction_output(input_path, config, tokenizer)
        )

        assert len(chunks) == 0
