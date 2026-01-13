#!/usr/bin/env python3
"""Tests for JsonExtractor."""

import pytest
import json
from pathlib import Path
from extraction.extractors.json import JsonExtractor
from extraction.extractors.configs import JsonExtractorConfig
from extraction.analyzers.generic import GenericAnalyzer


class TestJsonExtractorBasics:
    """Basic functionality tests."""

    def test_init_with_config(self):
        """Should initialize with config."""
        config = JsonExtractorConfig(mode="import")
        extractor = JsonExtractor("test.json", config)
        assert extractor.config.mode == "import"

    def test_init_with_analyzer(self):
        """Should initialize with analyzer."""
        analyzer = GenericAnalyzer()
        extractor = JsonExtractor("test.json", analyzer=analyzer)
        assert extractor.analyzer == analyzer

    def test_state_starts_created(self):
        """Should start in CREATED state."""
        from extraction.state import ExtractorState
        extractor = JsonExtractor("test.json")
        assert extractor.state == ExtractorState.CREATED

    def test_import_mode_config(self):
        """Should accept import mode."""
        config = JsonExtractorConfig(mode="import", import_chunks=True)
        extractor = JsonExtractor("test.json", config)
        assert extractor.config.mode == "import"
        assert extractor.config.import_chunks is True

    def test_rechunk_mode_config(self):
        """Should accept rechunk mode."""
        config = JsonExtractorConfig(mode="rechunk")
        extractor = JsonExtractor("test.json", config)
        assert extractor.config.mode == "rechunk"


class TestJsonExtractorParsing:
    """Parsing tests."""

    def test_parse_simple_json(self, tmp_path):
        """Should parse simple JSON document."""
        json_file = tmp_path / "test.json"
        data = {
            "metadata": {
                "title": "Test Document",
                "author": "Test Author"
            },
            "chunks": [
                {
                    "stable_id": "chunk1",
                    "paragraph_id": 1,
                    "text": "This is test content with enough words to create valid chunks.",
                    "word_count": 11,
                    "hierarchy": {},
                    "chapter_href": "",
                    "source_order": 1,
                    "source_tag": "p",
                    "text_length": 60,
                    "cross_references": [],
                    "scripture_references": [],
                    "dates_mentioned": [],
                    "heading_path": "",
                    "hierarchy_depth": 0,
                    "doc_stable_id": "doc1",
                    "sentence_count": 1,
                    "sentences": ["This is test content with enough words to create valid chunks."],
                    "normalized_text": "this is test content with enough words to create valid chunks."
                }
            ]
        }
        json_file.write_text(json.dumps(data))

        config = JsonExtractorConfig(mode="import", chunking_strategy='nlp', filter_noise=False)
        extractor = JsonExtractor(str(json_file), config)
        extractor.load()
        extractor.parse()

        chunks = extractor.chunks
        assert len(chunks) > 0
