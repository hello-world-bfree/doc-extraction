import pytest
from extraction.core.strategies import (
    TokenAwareChunkingStrategy,
    TokenChunkConfig,
    ChunkConfig,
    get_strategy,
    finalize_merged_chunk,
    _estimate_tokens_from_words,
)


def _make_chunk(
    paragraph_id,
    text,
    hierarchy=None,
    content_type="prose",
    scripture_references=None,
    sentences=None,
):
    words = text.split()
    if hierarchy is None:
        hierarchy = {"level_1": "Chapter 1", "level_2": "", "level_3": ""}
    if sentences is None:
        sentences = [text]
    return {
        "paragraph_id": paragraph_id,
        "text": text,
        "hierarchy": hierarchy,
        "word_count": len(words),
        "chapter_href": "",
        "source_order": paragraph_id,
        "source_tag": "p",
        "content_type": content_type,
        "cross_references": [],
        "scripture_references": scripture_references or [],
        "dates_mentioned": [],
        "sentences": sentences,
        "doc_stable_id": "test_doc",
        "footnote_citations": None,
        "resolved_footnotes": None,
    }


def _make_prose(paragraph_id, word_count, hierarchy=None, scripture_refs=None):
    words = " ".join(f"word{i}" for i in range(word_count))
    sents = []
    for i in range(0, word_count, 10):
        sents.append(" ".join(f"word{j}" for j in range(i, min(i + 10, word_count))) + ".")
    return _make_chunk(
        paragraph_id, words, hierarchy=hierarchy,
        content_type="prose", scripture_references=scripture_refs,
        sentences=sents,
    )


def _make_code(paragraph_id, text, hierarchy=None):
    return _make_chunk(
        paragraph_id, text, hierarchy=hierarchy,
        content_type="code", sentences=[text],
    )


class TestStrategyRegistry:

    def test_token_aware_registered(self):
        s = get_strategy("token_aware")
        assert isinstance(s, TokenAwareChunkingStrategy)

    def test_technical_registered(self):
        s = get_strategy("technical")
        assert isinstance(s, TokenAwareChunkingStrategy)

    def test_name(self):
        s = TokenAwareChunkingStrategy()
        assert s.name() == "token_aware"


class TestTokenAwareRequiresTokenConfig:

    def test_raises_on_wrong_config(self):
        strategy = TokenAwareChunkingStrategy()
        config = ChunkConfig()
        with pytest.raises(TypeError, match="TokenChunkConfig"):
            strategy.apply([], config)

    def test_accepts_token_config(self):
        strategy = TokenAwareChunkingStrategy()
        config = TokenChunkConfig()
        result = strategy.apply([], config)
        assert result == []


class TestTokenChunkConfigInheritance:

    def test_inherits_chunk_config_fields(self):
        config = TokenChunkConfig(min_words=50, max_words=200, target_tokens=300)
        assert config.min_words == 50
        assert config.max_words == 200
        assert config.target_tokens == 300

    def test_defaults(self):
        config = TokenChunkConfig()
        assert config.target_tokens == 400
        assert config.min_tokens == 256
        assert config.max_tokens == 512
        assert config.overlap_percent == 0.10
        assert config.code_max_tokens == 256
        assert config.max_absolute_tokens == 2048
        assert config.tokenizer_name == "google/embeddinggemma-300m"

    def test_isinstance_check(self):
        config = TokenChunkConfig()
        assert isinstance(config, ChunkConfig)


class TestWordFallback:

    def test_estimate_tokens_from_words(self):
        assert _estimate_tokens_from_words(10) == 15
        assert _estimate_tokens_from_words(100) == 150
        assert _estimate_tokens_from_words(0) == 0


class TestCodeAsMergeBoundary:

    def test_code_not_merged_with_prose(self):
        strategy = TokenAwareChunkingStrategy()
        config = TokenChunkConfig(
            max_tokens=10000,
            min_tokens=1,
            overlap_percent=0.0,
        )
        chunks = [
            _make_prose(1, 20),
            _make_code(2, "def foo():\n    return 42"),
            _make_prose(3, 20),
        ]
        result = strategy.apply(chunks, config)
        assert len(result) == 3
        types = [c.get("content_type") for c in result]
        assert types[0] == "prose"
        assert types[1] == "code"
        assert types[2] == "prose"

    def test_code_emitted_standalone_regardless_of_size(self):
        strategy = TokenAwareChunkingStrategy()
        config = TokenChunkConfig(
            max_tokens=10000,
            min_tokens=1000,
            overlap_percent=0.0,
        )
        chunks = [
            _make_code(1, "x = 1"),
        ]
        result = strategy.apply(chunks, config)
        assert len(result) == 1
        assert "x = 1" in result[0]["text"]

    def test_code_flushes_prose_accumulator(self):
        strategy = TokenAwareChunkingStrategy()
        config = TokenChunkConfig(
            max_tokens=10000,
            min_tokens=1,
            overlap_percent=0.0,
        )
        chunks = [
            _make_prose(1, 30),
            _make_prose(2, 30),
            _make_code(3, "import os"),
            _make_prose(4, 30),
        ]
        result = strategy.apply(chunks, config)
        assert len(result) == 3
        assert result[0]["content_type"] == "prose"
        assert result[1]["content_type"] == "code"
        assert result[2]["content_type"] == "prose"
        assert result[0]["source_paragraph_count"] == 2


class TestContentTypePropagation:

    def test_same_type_propagated(self):
        strategy = TokenAwareChunkingStrategy()
        config = TokenChunkConfig(
            max_tokens=10000,
            min_tokens=1,
            overlap_percent=0.0,
        )
        chunks = [
            _make_prose(1, 20),
            _make_prose(2, 20),
        ]
        result = strategy.apply(chunks, config)
        assert len(result) == 1
        assert result[0]["content_type"] == "prose"

    def test_finalize_mixed_types(self):
        merged = {
            "texts": ["hello", "world"],
            "word_count": 2,
            "paragraph_ids": [1, 2],
            "source_chunks": [
                _make_chunk(1, "hello", content_type="prose"),
                _make_chunk(2, "world", content_type="code"),
            ],
            "_num_levels": 3,
        }
        result = finalize_merged_chunk(merged)
        assert result["content_type"] == "mixed"


class TestOverlapWithinSections:

    def test_overlap_text_only_not_metadata(self):
        strategy = TokenAwareChunkingStrategy()
        config = TokenChunkConfig(
            max_tokens=40,
            min_tokens=1,
            overlap_percent=0.30,
        )
        chunks = [
            _make_prose(1, 25, scripture_refs=["Gen 1:1"]),
            _make_prose(2, 25, scripture_refs=["Gen 2:1"]),
        ]
        result = strategy.apply(chunks, config)
        assert len(result) >= 2
        first_refs = result[0].get("scripture_references", [])
        second_refs = result[1].get("scripture_references", [])
        assert "Gen 1:1" in first_refs
        assert "Gen 2:1" in second_refs
        assert "Gen 1:1" not in second_refs

    def test_no_overlap_across_sections(self):
        strategy = TokenAwareChunkingStrategy()
        config = TokenChunkConfig(
            max_tokens=40,
            min_tokens=1,
            overlap_percent=0.30,
        )
        h1 = {"level_1": "Chapter 1", "level_2": "", "level_3": ""}
        h2 = {"level_1": "Chapter 2", "level_2": "", "level_3": ""}
        chunks = [
            _make_prose(1, 25, hierarchy=h1),
            _make_prose(2, 25, hierarchy=h2),
        ]
        result = strategy.apply(chunks, config)
        for chunk in result:
            assert chunk.get("overlap_token_count") is None or chunk["overlap_token_count"] == 0 or "overlap_token_count" not in chunk

    def test_zero_overlap_config(self):
        strategy = TokenAwareChunkingStrategy()
        config = TokenChunkConfig(
            max_tokens=40,
            min_tokens=1,
            overlap_percent=0.0,
        )
        chunks = [
            _make_prose(1, 25),
            _make_prose(2, 25),
        ]
        result = strategy.apply(chunks, config)
        for chunk in result:
            assert chunk.get("overlap_token_count") is None or "overlap_token_count" not in chunk


class TestSkipsIndexSections:

    def test_skips_index(self):
        strategy = TokenAwareChunkingStrategy()
        config = TokenChunkConfig(min_tokens=1, overlap_percent=0.0)
        chunks = [
            _make_prose(1, 20, hierarchy={"level_1": "Index", "level_2": "", "level_3": ""}),
            _make_prose(2, 20, hierarchy={"level_1": "Chapter 1", "level_2": "", "level_3": ""}),
        ]
        result = strategy.apply(chunks, config)
        assert len(result) == 1


class TestDocumentOrderPreserved:

    def test_maintains_order(self):
        strategy = TokenAwareChunkingStrategy()
        config = TokenChunkConfig(
            max_tokens=10000,
            min_tokens=1,
            overlap_percent=0.0,
        )
        h1 = {"level_1": "B", "level_2": "", "level_3": ""}
        h2 = {"level_1": "A", "level_2": "", "level_3": ""}
        chunks = [
            _make_prose(1, 20, hierarchy=h1),
            _make_prose(2, 20, hierarchy=h2),
        ]
        result = strategy.apply(chunks, config)
        assert result[0]["merged_paragraph_ids"][0] < result[1]["merged_paragraph_ids"][0]


class TestBackwardCompatibility:

    def test_existing_strategies_unchanged(self):
        from extraction.core.strategies import SemanticChunkingStrategy
        s = get_strategy("rag")
        assert isinstance(s, SemanticChunkingStrategy)

    def test_chunk_config_still_works(self):
        config = ChunkConfig(min_words=50, max_words=200)
        assert config.min_words == 50
        assert not hasattr(config, "target_tokens")
