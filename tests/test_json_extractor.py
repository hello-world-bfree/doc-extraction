#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Tests for JSON extractor (import mode).
"""

import pytest
import json
import tempfile
import os

from src.extraction.extractors.json import JsonExtractor


class TestJsonExtractor:
    """Tests for JSON extractor in import mode."""

    def test_json_extractor_initialization(self):
        """Test JSON extractor can be instantiated."""
        extractor = JsonExtractor("test.json")
        assert extractor.source_path == "test.json"
        assert extractor.mode == "import"
        assert extractor.import_chunks is True
        assert extractor.import_metadata is True

    def test_json_extractor_with_config(self):
        """Test JSON extractor with custom config."""
        config = {
            "mode": "extract",
            "import_chunks": False,
            "import_metadata": False,
        }
        extractor = JsonExtractor("test.json", config)
        assert extractor.mode == "extract"
        assert extractor.import_chunks is False
        assert extractor.import_metadata is False

    def test_json_import_simple_extraction(self):
        """Test importing a simple extraction JSON."""
        # Create sample extraction output
        sample_data = {
            "metadata": {
                "title": "Test Document",
                "author": "Test Author",
                "language": "en",
                "word_count": "approximately 50"
            },
            "chunks": [
                {
                    "stable_id": "test_chunk_1",
                    "paragraph_id": 1,
                    "text": "This is the first test paragraph with some content.",
                    "hierarchy": {
                        "level_1": "Chapter 1",
                        "level_2": "",
                        "level_3": "",
                        "level_4": "",
                        "level_5": "",
                        "level_6": ""
                    },
                    "chapter_href": "",
                    "source_order": 1,
                    "source_tag": "p",
                    "text_length": 51,
                    "word_count": 9,
                    "cross_references": [],
                    "scripture_references": [],
                    "dates_mentioned": [],
                    "heading_path": "Chapter 1",
                    "hierarchy_depth": 1,
                    "doc_stable_id": "test_doc",
                    "sentence_count": 1,
                    "sentences": ["This is the first test paragraph with some content."],
                    "normalized_text": "this is the first test paragraph with some content."
                },
                {
                    "stable_id": "test_chunk_2",
                    "paragraph_id": 2,
                    "text": "This is the second paragraph with different text.",
                    "hierarchy": {
                        "level_1": "Chapter 1",
                        "level_2": "Section A",
                        "level_3": "",
                        "level_4": "",
                        "level_5": "",
                        "level_6": ""
                    },
                    "chapter_href": "",
                    "source_order": 2,
                    "source_tag": "p",
                    "text_length": 49,
                    "word_count": 8,
                    "cross_references": [],
                    "scripture_references": [],
                    "dates_mentioned": [],
                    "heading_path": "Chapter 1 / Section A",
                    "hierarchy_depth": 2,
                    "doc_stable_id": "test_doc",
                    "sentence_count": 1,
                    "sentences": ["This is the second paragraph with different text."],
                    "normalized_text": "this is the second paragraph with different text."
                }
            ],
            "extraction_info": {
                "total_chunks": 2,
                "quality_route": "A",
                "quality_score": 0.95
            }
        }

        # Write to temporary file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False, encoding='utf-8') as f:
            json.dump(sample_data, f)
            temp_path = f.name

        try:
            # Import the JSON
            extractor = JsonExtractor(temp_path)
            extractor.load()
            extractor.parse()
            metadata = extractor.extract_metadata()

            # Verify chunks imported
            assert len(extractor.chunks) == 2
            assert extractor.chunks[0].text == "This is the first test paragraph with some content."
            assert extractor.chunks[1].text == "This is the second paragraph with different text."

            # Verify hierarchy preserved
            assert extractor.chunks[0].hierarchy["level_1"] == "Chapter 1"
            assert extractor.chunks[1].hierarchy["level_2"] == "Section A"

            # Verify metadata
            assert metadata.title == "Test Document"
            assert metadata.author == "Test Author"
            assert metadata.language == "en"

        finally:
            os.unlink(temp_path)

    def test_json_import_with_references(self):
        """Test importing JSON with scripture and cross-references."""
        sample_data = {
            "metadata": {
                "title": "Reference Test",
                "author": "Test Author",
                "language": "en"
            },
            "chunks": [
                {
                    "stable_id": "ref_chunk",
                    "paragraph_id": 1,
                    "text": "See John 3:16 and compare with Chapter 5.",
                    "hierarchy": {"level_1": "", "level_2": "", "level_3": "", "level_4": "", "level_5": "", "level_6": ""},
                    "chapter_href": "",
                    "source_order": 1,
                    "source_tag": "p",
                    "text_length": 42,
                    "word_count": 8,
                    "cross_references": ["Chapter 5"],
                    "scripture_references": ["John 3:16"],
                    "dates_mentioned": [],
                    "heading_path": "",
                    "hierarchy_depth": 0,
                    "doc_stable_id": "test",
                    "sentence_count": 1,
                    "sentences": ["See John 3:16 and compare with Chapter 5."],
                    "normalized_text": "see john 3:16 and compare with chapter 5."
                }
            ]
        }

        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False, encoding='utf-8') as f:
            json.dump(sample_data, f)
            temp_path = f.name

        try:
            extractor = JsonExtractor(temp_path)
            extractor.load()
            extractor.parse()

            # Verify references preserved
            assert len(extractor.chunks) == 1
            assert extractor.chunks[0].scripture_references == ["John 3:16"]
            assert extractor.chunks[0].cross_references == ["Chapter 5"]

        finally:
            os.unlink(temp_path)

    def test_json_invalid_file(self):
        """Test error handling for invalid JSON."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False, encoding='utf-8') as f:
            f.write("{ invalid json }")
            temp_path = f.name

        try:
            extractor = JsonExtractor(temp_path)
            with pytest.raises(RuntimeError, match="Invalid JSON file"):
                extractor.load()
        finally:
            os.unlink(temp_path)

    def test_json_extract_mode_not_implemented(self):
        """Test that extract mode raises NotImplementedError."""
        sample_data = {"some": "arbitrary", "data": "here"}

        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False, encoding='utf-8') as f:
            json.dump(sample_data, f)
            temp_path = f.name

        try:
            extractor = JsonExtractor(temp_path, config={"mode": "extract"})
            extractor.load()

            with pytest.raises(NotImplementedError, match="Extract mode"):
                extractor.parse()
        finally:
            os.unlink(temp_path)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
