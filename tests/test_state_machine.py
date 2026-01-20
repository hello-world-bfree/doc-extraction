#!/usr/bin/env python3
"""Tests for state machine in BaseExtractor."""

import pytest
from extraction.extractors.base import BaseExtractor
from extraction.extractors.configs import BaseExtractorConfig
from extraction.state import ExtractorState
from extraction.exceptions import MethodOrderError
from extraction.core.models import Metadata


class MockExtractor(BaseExtractor):
    """Mock extractor for testing state machine."""

    def __init__(self, path: str, config=None, analyzer=None):
        from extraction.extractors.configs import BaseExtractorConfig
        super().__init__(path, config or BaseExtractorConfig(chunking_strategy='nlp', filter_noise=False), analyzer)
        self.load_called = False
        self.parse_called = False
        self.extract_metadata_called = False

    def _do_load(self):
        from extraction.core.models import Provenance
        from extraction.core.identifiers import stable_id
        from datetime import datetime
        self.load_called = True
        self._BaseExtractor__provenance = Provenance(
            doc_id=stable_id("test.txt", "12345"),
            source_file="test.txt",
            parser_version="1.0",
            md_schema_version="1.0",
            ingestion_ts=datetime.now().isoformat(),
            content_hash="abc123"
        )

    def _do_parse(self):
        self.parse_called = True
        self._add_raw_chunk({
            'stable_id': 'test1',
            'paragraph_id': 1,
            'text': 'This is a test paragraph with substantive content.',
            'word_count': 8,
            'hierarchy': {},
            'chapter_href': '',
            'source_order': 1,
            'source_tag': 'p',
            'text_length': 48,
            'cross_references': [],
            'scripture_references': [],
            'dates_mentioned': [],
            'heading_path': '',
            'hierarchy_depth': 0,
            'doc_stable_id': 'doc1',
            'sentence_count': 1,
            'sentences': ['This is a test paragraph with substantive content.'],
            'normalized_text': 'this is a test paragraph with substantive content.',
        })
        self._compute_quality("This is a test paragraph with substantive content.")
        self._apply_chunking_strategy()

    def _do_extract_metadata(self):
        self.extract_metadata_called = True
        return Metadata(title="Test", author="Author")


class TestStateTransitions:
    """Tests for state machine transitions."""

    def test_initial_state_is_created(self):
        """Extractor should start in CREATED state."""
        extractor = MockExtractor("test.txt")
        assert extractor._BaseExtractor__state == ExtractorState.CREATED

    def test_load_transitions_to_loaded(self):
        """load() should transition CREATED -> LOADED."""
        extractor = MockExtractor("test.txt")
        extractor.load()
        assert extractor._BaseExtractor__state == ExtractorState.LOADED
        assert extractor.load_called is True

    def test_parse_transitions_to_parsed(self):
        """parse() should transition LOADED -> PARSED."""
        extractor = MockExtractor("test.txt")
        extractor.load()
        extractor.parse()
        assert extractor._BaseExtractor__state == ExtractorState.PARSED
        assert extractor.parse_called is True

    def test_extract_metadata_transitions_to_metadata_ready(self):
        """extract_metadata() should transition PARSED -> METADATA_READY."""
        extractor = MockExtractor("test.txt")
        extractor.load()
        extractor.parse()
        extractor.extract_metadata()
        assert extractor._BaseExtractor__state == ExtractorState.METADATA_READY
        assert extractor.extract_metadata_called is True

    def test_get_output_data_transitions_to_output_ready(self):
        """get_output_data() should transition METADATA_READY -> OUTPUT_READY."""
        extractor = MockExtractor("test.txt")
        extractor.load()
        extractor.parse()
        extractor.extract_metadata()
        extractor.get_output_data()
        assert extractor._BaseExtractor__state == ExtractorState.OUTPUT_READY


class TestMethodOrderEnforcement:
    """Tests for method call order enforcement."""

    def test_parse_before_load_raises_error(self):
        """parse() before load() should raise MethodOrderError."""
        extractor = MockExtractor("test.txt")
        with pytest.raises(MethodOrderError, match="Cannot call parse"):
            extractor.parse()

    def test_extract_metadata_before_parse_raises_error(self):
        """extract_metadata() before parse() should raise MethodOrderError."""
        extractor = MockExtractor("test.txt")
        extractor.load()
        with pytest.raises(MethodOrderError, match="Cannot call extract_metadata"):
            extractor.extract_metadata()

    def test_get_output_data_before_extract_metadata_raises_error(self):
        """get_output_data() before extract_metadata() should raise MethodOrderError."""
        extractor = MockExtractor("test.txt")
        extractor.load()
        extractor.parse()
        with pytest.raises(MethodOrderError, match="Cannot call get_output_data"):
            extractor.get_output_data()

    def test_load_cannot_be_called_twice(self):
        """load() should raise MethodOrderError if called twice."""
        extractor = MockExtractor("test.txt")
        extractor.load()
        with pytest.raises(MethodOrderError, match="Cannot call load"):
            extractor.load()

    def test_parse_cannot_be_called_twice(self):
        """parse() should raise MethodOrderError if called twice."""
        extractor = MockExtractor("test.txt")
        extractor.load()
        extractor.parse()
        with pytest.raises(MethodOrderError, match="Cannot call parse"):
            extractor.parse()


class TestPropertyAccess:
    """Tests for property access restrictions based on state."""

    def test_provenance_before_load_raises_error(self):
        """Accessing provenance before load() should raise MethodOrderError."""
        extractor = MockExtractor("test.txt")
        with pytest.raises(MethodOrderError, match="provenance.*LOADED"):
            _ = extractor.provenance

    def test_provenance_after_load_succeeds(self):
        """Accessing provenance after load() should succeed."""
        extractor = MockExtractor("test.txt")
        extractor.load()
        provenance = extractor.provenance
        assert provenance is not None
        assert hasattr(provenance, 'doc_id')

    def test_quality_before_parse_raises_error(self):
        """Accessing quality before parse() should raise MethodOrderError."""
        extractor = MockExtractor("test.txt")
        extractor.load()
        with pytest.raises(MethodOrderError, match="quality.*PARSED"):
            _ = extractor.quality

    def test_quality_after_parse_succeeds(self):
        """Accessing quality after parse() should succeed."""
        extractor = MockExtractor("test.txt")
        extractor.load()
        extractor.parse()
        quality = extractor.quality
        assert quality is not None

    def test_chunks_before_parse_raises_error(self):
        """Accessing chunks before parse() should raise MethodOrderError."""
        extractor = MockExtractor("test.txt")
        extractor.load()
        with pytest.raises(MethodOrderError, match="chunks.*PARSED"):
            _ = extractor.chunks

    def test_chunks_after_parse_succeeds(self):
        """Accessing chunks after parse() should succeed."""
        extractor = MockExtractor("test.txt")
        extractor.load()
        extractor.parse()
        chunks = extractor.chunks
        assert isinstance(chunks, list)
        assert len(chunks) > 0

    def test_metadata_before_extract_metadata_returns_none(self):
        """Accessing metadata before extract_metadata() should return None."""
        extractor = MockExtractor("test.txt")
        extractor.load()
        extractor.parse()
        assert extractor.metadata is None

    def test_metadata_after_extract_metadata_succeeds(self):
        """Accessing metadata after extract_metadata() should succeed."""
        extractor = MockExtractor("test.txt")
        extractor.load()
        extractor.parse()
        extractor.extract_metadata()
        metadata = extractor.metadata
        assert metadata is not None
        assert metadata.title == "Test"


class TestStateProperty:
    """Tests for state property."""

    def test_state_property_returns_current_state(self):
        """state property should return current ExtractorState."""
        extractor = MockExtractor("test.txt")
        assert extractor.state == ExtractorState.CREATED

        extractor.load()
        assert extractor.state == ExtractorState.LOADED

        extractor.parse()
        assert extractor.state == ExtractorState.PARSED

        extractor.extract_metadata()
        assert extractor.state == ExtractorState.METADATA_READY


class TestDocumentContext:
    """Tests for get_document_context() method."""

    def test_get_document_context_before_metadata_raises_error(self):
        """get_document_context() before extract_metadata() should raise MethodOrderError."""
        extractor = MockExtractor("test.txt")
        extractor.load()
        extractor.parse()
        with pytest.raises(MethodOrderError, match="get_document_context"):
            extractor.get_document_context()

    def test_get_document_context_after_metadata_succeeds(self):
        """get_document_context() after extract_metadata() should return context string."""
        extractor = MockExtractor("test.txt")
        extractor.load()
        extractor.parse()
        extractor.extract_metadata()
        context = extractor.get_document_context()
        assert isinstance(context, str)
        assert "Title: Test" in context
        assert "Author: Author" in context

    def test_get_document_context_after_output_succeeds(self):
        """get_document_context() after get_output_data() should still work."""
        extractor = MockExtractor("test.txt")
        extractor.load()
        extractor.parse()
        extractor.extract_metadata()
        extractor.get_output_data()
        context = extractor.get_document_context()
        assert "Title: Test" in context
