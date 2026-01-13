#!/usr/bin/env python3
"""Tests for chunking strategies (RAG vs NLP)."""

import pytest
from extraction.core.strategies import (
    ParagraphChunkingStrategy,
    SemanticChunkingStrategy,
    ChunkConfig,
    get_strategy,
)


@pytest.fixture
def sample_paragraph_chunks():
    """Create sample paragraph-level chunks for testing."""
    return [
        {
            'paragraph_id': 1,
            'text': 'This is the first paragraph with about ten words here.',
            'word_count': 10,
            'hierarchy': {'level_1': 'Chapter 1', 'level_2': 'Section A'},
            'chapter_href': 'ch1.html',
            'source_order': 1,
            'source_tag': 'p',
            'text_length': 55,
            'cross_references': [],
            'scripture_references': [],
            'dates_mentioned': [],
            'heading_path': 'Chapter 1 / Section A',
            'hierarchy_depth': 2,
            'doc_stable_id': 'doc123',
            'sentence_count': 1,
            'sentences': ['This is the first paragraph with about ten words here.'],
            'normalized_text': 'this is the first paragraph with about ten words here.',
        },
        {
            'paragraph_id': 2,
            'text': 'Second paragraph in same section. Has more content here. About fifteen words total in this.',
            'word_count': 15,
            'hierarchy': {'level_1': 'Chapter 1', 'level_2': 'Section A'},
            'chapter_href': 'ch1.html',
            'source_order': 2,
            'source_tag': 'p',
            'text_length': 93,
            'cross_references': [],
            'scripture_references': [],
            'dates_mentioned': [],
            'heading_path': 'Chapter 1 / Section A',
            'hierarchy_depth': 2,
            'doc_stable_id': 'doc123',
            'sentence_count': 3,
            'sentences': ['Second paragraph in same section.', 'Has more content here.', 'About fifteen words total in this.'],
            'normalized_text': 'second paragraph in same section. has more content here. about fifteen words total in this.',
        },
        {
            'paragraph_id': 3,
            'text': 'Third paragraph still in Section A. More content continues. We need enough words.',
            'word_count': 14,
            'hierarchy': {'level_1': 'Chapter 1', 'level_2': 'Section A'},
            'chapter_href': 'ch1.html',
            'source_order': 3,
            'source_tag': 'p',
            'text_length': 81,
            'cross_references': [],
            'scripture_references': [],
            'dates_mentioned': [],
            'heading_path': 'Chapter 1 / Section A',
            'hierarchy_depth': 2,
            'doc_stable_id': 'doc123',
            'sentence_count': 3,
            'sentences': ['Third paragraph still in Section A.', 'More content continues.', 'We need enough words.'],
            'normalized_text': 'third paragraph still in section a. more content continues. we need enough words.',
        },
        {
            'paragraph_id': 4,
            'text': 'Now in Section B. This is a different section with its own content.',
            'word_count': 13,
            'hierarchy': {'level_1': 'Chapter 1', 'level_2': 'Section B'},
            'chapter_href': 'ch1.html',
            'source_order': 4,
            'source_tag': 'p',
            'text_length': 68,
            'cross_references': [],
            'scripture_references': [],
            'dates_mentioned': [],
            'heading_path': 'Chapter 1 / Section B',
            'hierarchy_depth': 2,
            'doc_stable_id': 'doc123',
            'sentence_count': 2,
            'sentences': ['Now in Section B.', 'This is a different section with its own content.'],
            'normalized_text': 'now in section b. this is a different section with its own content.',
        },
        {
            'paragraph_id': 5,
            'text': 'Index entry, 42',
            'word_count': 3,
            'hierarchy': {'level_1': 'Index'},
            'chapter_href': 'index.html',
            'source_order': 5,
            'source_tag': 'p',
            'text_length': 15,
            'cross_references': [],
            'scripture_references': [],
            'dates_mentioned': [],
            'heading_path': 'Index',
            'hierarchy_depth': 1,
            'doc_stable_id': 'doc123',
            'sentence_count': 1,
            'sentences': ['Index entry, 42'],
            'normalized_text': 'index entry, 42',
        },
    ]


class TestParagraphChunkingStrategy:
    """Tests for paragraph-level chunking (NLP mode)."""

    def test_returns_chunks_unchanged(self, sample_paragraph_chunks):
        """Paragraph strategy should return chunks as-is."""
        strategy = ParagraphChunkingStrategy()
        config = ChunkConfig(min_words=100, max_words=500)

        result = strategy.apply(sample_paragraph_chunks, config)

        assert len(result) == len(sample_paragraph_chunks)
        assert result == sample_paragraph_chunks

    def test_name(self):
        """Strategy name should be 'paragraph'."""
        strategy = ParagraphChunkingStrategy()
        assert strategy.name() == "paragraph"


class TestSemanticChunkingStrategy:
    """Tests for semantic chunking (RAG/embeddings mode)."""

    def test_merges_paragraphs_by_hierarchy(self, sample_paragraph_chunks):
        """Should merge paragraphs under same hierarchy."""
        strategy = SemanticChunkingStrategy()
        config = ChunkConfig(min_words=30, max_words=500)

        # Remove index chunk for this test
        chunks = [c for c in sample_paragraph_chunks if c['paragraph_id'] <= 4]

        result = strategy.apply(chunks, config)

        # Should merge Section A (paras 1-3) and keep Section B separate
        assert len(result) < len(chunks)

        # First merged chunk should be Section A (paras 1-3)
        section_a_chunk = next(c for c in result if c['hierarchy'].get('level_2') == 'Section A')
        assert section_a_chunk['word_count'] == 10 + 15 + 14  # Sum of word counts
        assert len(section_a_chunk['merged_paragraph_ids']) == 3
        assert '\n\n' in section_a_chunk['text']  # Paragraphs joined with double newline

    def test_respects_max_words(self, sample_paragraph_chunks):
        """Should split when max_words exceeded."""
        strategy = SemanticChunkingStrategy()
        config = ChunkConfig(min_words=5, max_words=20)  # Force split

        # Use only Section A chunks (paras 1-3)
        chunks = [c for c in sample_paragraph_chunks if c['hierarchy'].get('level_2') == 'Section A']

        result = strategy.apply(chunks, config)

        # Should split into multiple chunks due to max_words=20
        assert len(result) >= 2
        for chunk in result:
            assert chunk['word_count'] <= 20

    def test_respects_min_words(self, sample_paragraph_chunks):
        """Should filter out chunks below min_words."""
        strategy = SemanticChunkingStrategy()
        config = ChunkConfig(min_words=30, max_words=500)

        # Use only Section B (13 words - below minimum)
        chunks = [c for c in sample_paragraph_chunks if c['paragraph_id'] == 4]

        result = strategy.apply(chunks, config)

        # Should be filtered out (below 30 words)
        assert len(result) == 0

    def test_skips_index_sections(self, sample_paragraph_chunks):
        """Should skip index/TOC sections."""
        strategy = SemanticChunkingStrategy()
        config = ChunkConfig(min_words=1, max_words=500)

        result = strategy.apply(sample_paragraph_chunks, config)

        # Index chunk should be skipped
        for chunk in result:
            assert chunk['hierarchy'].get('level_1', '').lower() not in {'index', 'table of contents'}

    def test_aggregates_metadata(self, sample_paragraph_chunks):
        """Should aggregate scripture refs, cross refs, etc."""
        # Add some references to test chunks
        chunks = sample_paragraph_chunks[:3]  # Section A only
        chunks[0]['scripture_references'] = ['John 3:16']
        chunks[1]['cross_references'] = ['See Chapter 5']
        chunks[2]['scripture_references'] = ['Matthew 5:1', 'John 3:16']  # Duplicate

        strategy = SemanticChunkingStrategy()
        config = ChunkConfig(min_words=30, max_words=500)

        result = strategy.apply(chunks, config)

        # Should have merged into one chunk
        assert len(result) == 1
        merged = result[0]

        # Scripture refs should be deduplicated
        assert set(merged['scripture_references']) == {'John 3:16', 'Matthew 5:1'}
        assert 'See Chapter 5' in merged['cross_references']

    def test_preserves_document_order(self, sample_paragraph_chunks):
        """Should maintain document order via paragraph IDs."""
        strategy = SemanticChunkingStrategy()
        config = ChunkConfig(min_words=10, max_words=500)

        result = strategy.apply(sample_paragraph_chunks, config)

        # Chunks should be in order by first paragraph_id
        prev_id = 0
        for chunk in result:
            first_id = chunk['merged_paragraph_ids'][0]
            assert first_id > prev_id
            prev_id = first_id

    def test_hierarchy_grouping_depth(self):
        """Should group by configurable hierarchy depth."""
        chunks = [
            {
                'paragraph_id': 1,
                'text': 'Para 1 with enough words to meet minimum threshold here.',
                'word_count': 10,
                'hierarchy': {'level_1': 'Book', 'level_2': 'Ch 1', 'level_3': 'Sec A'},
                'chapter_href': 'ch1.html',
                'source_order': 1,
                'source_tag': 'p',
                'text_length': 50,
                'cross_references': [],
                'scripture_references': [],
                'dates_mentioned': [],
                'heading_path': 'Book / Ch 1 / Sec A',
                'hierarchy_depth': 3,
                'doc_stable_id': 'doc123',
                'sentence_count': 1,
                'sentences': ['Para 1 with enough words to meet minimum threshold here.'],
                'normalized_text': 'para 1 with enough words to meet minimum threshold here.',
            },
            {
                'paragraph_id': 2,
                'text': 'Para 2 in different subsection with enough words here too.',
                'word_count': 10,
                'hierarchy': {'level_1': 'Book', 'level_2': 'Ch 1', 'level_3': 'Sec B'},
                'chapter_href': 'ch1.html',
                'source_order': 2,
                'source_tag': 'p',
                'text_length': 50,
                'cross_references': [],
                'scripture_references': [],
                'dates_mentioned': [],
                'heading_path': 'Book / Ch 1 / Sec B',
                'hierarchy_depth': 3,
                'doc_stable_id': 'doc123',
                'sentence_count': 1,
                'sentences': ['Para 2 in different subsection with enough words here too.'],
                'normalized_text': 'para 2 in different subsection with enough words here too.',
            },
        ]

        strategy = SemanticChunkingStrategy()

        # Group by 3 levels (default) - should keep separate
        config3 = ChunkConfig(min_words=5, max_words=500, preserve_hierarchy_levels=3)
        result3 = strategy.apply(chunks, config3)
        assert len(result3) == 2  # Different level_3, so separate chunks

        # Group by 2 levels - should merge
        config2 = ChunkConfig(min_words=5, max_words=500, preserve_hierarchy_levels=2)
        result2 = strategy.apply(chunks, config2)
        assert len(result2) == 1  # Same level_1 and level_2, so merged

    def test_name(self):
        """Strategy name should be 'semantic'."""
        strategy = SemanticChunkingStrategy()
        assert strategy.name() == "semantic"

    def test_includes_merge_metadata(self, sample_paragraph_chunks):
        """Should include metadata about the merge."""
        strategy = SemanticChunkingStrategy()
        config = ChunkConfig(min_words=30, max_words=500)

        chunks = [c for c in sample_paragraph_chunks if c['hierarchy'].get('level_2') == 'Section A']

        result = strategy.apply(chunks, config)

        assert len(result) == 1
        merged = result[0]

        assert 'source_paragraph_count' in merged
        assert merged['source_paragraph_count'] == 3
        assert 'merged_paragraph_ids' in merged
        assert merged['merged_paragraph_ids'] == [1, 2, 3]


class TestStrategyRegistry:
    """Tests for strategy lookup and aliases."""

    def test_get_strategy_rag(self):
        """Should return SemanticChunkingStrategy for 'rag'."""
        strategy = get_strategy('rag')
        assert isinstance(strategy, SemanticChunkingStrategy)

    def test_get_strategy_semantic(self):
        """'semantic' should be alias for RAG."""
        strategy = get_strategy('semantic')
        assert isinstance(strategy, SemanticChunkingStrategy)

    def test_get_strategy_embeddings(self):
        """'embeddings' should be alias for RAG."""
        strategy = get_strategy('embeddings')
        assert isinstance(strategy, SemanticChunkingStrategy)

    def test_get_strategy_nlp(self):
        """Should return ParagraphChunkingStrategy for 'nlp'."""
        strategy = get_strategy('nlp')
        assert isinstance(strategy, ParagraphChunkingStrategy)

    def test_get_strategy_paragraph(self):
        """'paragraph' should be alias for NLP."""
        strategy = get_strategy('paragraph')
        assert isinstance(strategy, ParagraphChunkingStrategy)

    def test_get_strategy_invalid(self):
        """Should raise ValueError for unknown strategy."""
        with pytest.raises(ValueError, match="Unknown chunking strategy"):
            get_strategy('invalid_strategy')


class TestChunkConfig:
    """Tests for ChunkConfig dataclass."""

    def test_defaults(self):
        """Should have correct default values."""
        config = ChunkConfig()
        assert config.min_words == 100
        assert config.max_words == 500
        assert config.preserve_hierarchy_levels == 3

    def test_custom_values(self):
        """Should accept custom values."""
        config = ChunkConfig(min_words=50, max_words=1000, preserve_hierarchy_levels=2)
        assert config.min_words == 50
        assert config.max_words == 1000
        assert config.preserve_hierarchy_levels == 2


class TestExtractorIntegration:
    """Integration tests for extractors with chunking strategies."""

    def test_base_extractor_handles_dict_input(self):
        """BaseExtractor.apply_chunking_strategy() should handle dict input."""
        from extraction.extractors.base import BaseExtractor
        from extraction.core.models import Provenance, Metadata
        from extraction.core.identifiers import stable_id
        from datetime import datetime

        # Create a mock extractor with dict-based _raw_chunks
        class MockExtractor(BaseExtractor):
            def _do_load(self):
                self._BaseExtractor__provenance = Provenance(
                    doc_id=stable_id("test.txt", "12345"),
                    source_file="test.txt",
                    parser_version="1.0",
                    md_schema_version="1.0",
                    ingestion_ts=datetime.now().isoformat(),
                    content_hash="abc123"
                )

            def _do_parse(self):
                self._add_raw_chunk({
                    'stable_id': 'test1',
                    'paragraph_id': 1,
                    'text': 'Test paragraph one with some words here.',
                    'word_count': 7,
                    'hierarchy': {'level_1': 'Chapter 1'},
                    'chapter_href': '',
                    'source_order': 1,
                    'source_tag': 'p',
                    'text_length': 40,
                    'cross_references': [],
                    'scripture_references': [],
                    'dates_mentioned': [],
                    'heading_path': 'Chapter 1',
                    'hierarchy_depth': 1,
                    'doc_stable_id': 'doc1',
                    'sentence_count': 1,
                    'sentences': ['Test paragraph one with some words here.'],
                    'normalized_text': 'test paragraph one with some words here.',
                })
                self._compute_quality("Test paragraph one with some words here.")
                self._apply_chunking_strategy()

            def _do_extract_metadata(self):
                return Metadata(title="Test", author="Author")

        from extraction.extractors.configs import BaseExtractorConfig
        config = BaseExtractorConfig(chunking_strategy='nlp', filter_noise=False)
        extractor = MockExtractor("test.txt", config=config)
        extractor.load()
        extractor.parse()

        # Should not raise
        assert len(extractor.chunks) == 1

    def test_base_extractor_handles_chunk_object_input(self):
        """BaseExtractor.apply_chunking_strategy() should handle Chunk object input."""
        from extraction.extractors.base import BaseExtractor
        from extraction.core.models import Chunk, Provenance, Metadata
        from extraction.core.identifiers import stable_id
        from datetime import datetime

        class MockExtractor(BaseExtractor):
            def _do_load(self):
                self._BaseExtractor__provenance = Provenance(
                    doc_id=stable_id("test.txt", "12345"),
                    source_file="test.txt",
                    parser_version="1.0",
                    md_schema_version="1.0",
                    ingestion_ts=datetime.now().isoformat(),
                    content_hash="abc123"
                )

            def _do_parse(self):
                chunk = Chunk(
                    stable_id='test1',
                    paragraph_id=1,
                    text='Test paragraph one with some words here.',
                    word_count=7,
                    hierarchy={'level_1': 'Chapter 1'},
                    chapter_href='',
                    source_order=1,
                    source_tag='p',
                    text_length=40,
                    cross_references=[],
                    scripture_references=[],
                    dates_mentioned=[],
                    heading_path='Chapter 1',
                    hierarchy_depth=1,
                    doc_stable_id='doc1',
                    sentence_count=1,
                    sentences=['Test paragraph one with some words here.'],
                    normalized_text='test paragraph one with some words here.',
                )
                self._add_raw_chunk(chunk)
                self._compute_quality("Test paragraph one with some words here.")
                self._apply_chunking_strategy()

            def _do_extract_metadata(self):
                return Metadata(title="Test", author="Author")

        from extraction.extractors.configs import BaseExtractorConfig
        config = BaseExtractorConfig(chunking_strategy='nlp', filter_noise=False)
        extractor = MockExtractor("test.txt", config=config)
        extractor.load()
        extractor.parse()

        # Should not raise
        assert len(extractor.chunks) == 1
        assert isinstance(extractor.chunks[0], Chunk)
