#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Unit tests for extractor classes (BaseExtractor, EpubExtractor).

Tests verify extractor interface, EPUB parsing logic, and data integrity.
"""

import pytest
import os
import tempfile
from pathlib import Path
from typing import Dict, List, Any

from src.extraction.extractors.base import BaseExtractor
from src.extraction.extractors.epub import EpubExtractor
from src.extraction.core.models import Chunk, Metadata, Provenance, Quality
from tests.helpers import create_test_chunk, create_test_metadata


class MockExtractor(BaseExtractor):
    """Mock extractor for testing abstract base class."""

    def __init__(self, source_path: str, config: Dict = None):
        super().__init__(source_path, config)
        self._loaded = False
        self._parsed = False

    def load(self) -> None:
        """Mock load implementation."""
        if not os.path.exists(self.source_path):
            raise RuntimeError(f"File not found: {self.source_path}")

        with open(self.source_path, 'rb') as f:
            source_bytes = f.read()

        self.create_provenance(
            parser_version="1.0.0",
            md_schema_version="1.0",
            source_bytes=source_bytes
        )
        self._loaded = True

    def parse(self) -> None:
        """Mock parse implementation."""
        if not self._loaded:
            raise RuntimeError("Must call load() before parse()")

        # Create mock chunks using helper
        self.chunks = [
            create_test_chunk(
                stable_id="chunk1",
                paragraph_id=1,
                text="This is test chunk one.",
                hierarchy={"level_1": "Chapter 1", "level_2": "", "level_3": "", "level_4": "", "level_5": "", "level_6": ""},
                word_count=5
            ),
            create_test_chunk(
                stable_id="chunk2",
                paragraph_id=2,
                text="This is test chunk two.",
                hierarchy={"level_1": "Chapter 1", "level_2": "", "level_3": "", "level_4": "", "level_5": "", "level_6": ""},
                word_count=5
            )
        ]

        # Compute quality from combined text
        full_text = " ".join(c.text for c in self.chunks)
        self.compute_quality(full_text)
        self._parsed = True

    def extract_metadata(self) -> Metadata:
        """Mock metadata extraction."""
        if not self._parsed:
            raise RuntimeError("Must call parse() before extract_metadata()")

        self.metadata = create_test_metadata(
            title="Test Document",
            author="Test Author",
            publisher="Test Publisher",
            language="en"
        )
        return self.metadata


class TestBaseExtractor:
    """Test BaseExtractor abstract class via MockExtractor."""

    @pytest.fixture
    def temp_file(self):
        """Create a temporary test file."""
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as f:
            f.write("Test content for extraction")
            temp_path = f.name
        yield temp_path
        os.unlink(temp_path)

    def test_initialization(self, temp_file):
        """Test extractor initialization."""
        extractor = MockExtractor(temp_file)
        assert extractor.source_path == temp_file
        assert extractor.config == {}
        assert extractor.chunks == []
        assert extractor.metadata is None

    def test_initialization_with_config(self, temp_file):
        """Test extractor initialization with config."""
        config = {"min_words": 50, "toc_level": 3}
        extractor = MockExtractor(temp_file, config)
        assert extractor.config == config

    def test_load(self, temp_file):
        """Test load method."""
        extractor = MockExtractor(temp_file)
        extractor.load()

        # Provenance should be available after load
        prov = extractor.provenance
        assert prov.source_file == os.path.basename(temp_file)
        assert prov.parser_version == "1.0.0"
        assert prov.md_schema_version == "1.0"
        assert len(prov.content_hash) == 40  # SHA1 hex length

    def test_load_missing_file(self):
        """Test load with missing file."""
        extractor = MockExtractor("/nonexistent/file.txt")
        with pytest.raises(RuntimeError, match="File not found"):
            extractor.load()

    def test_provenance_before_load(self, temp_file):
        """Test accessing provenance before load raises error."""
        extractor = MockExtractor(temp_file)
        with pytest.raises(RuntimeError, match="Provenance not available"):
            _ = extractor.provenance

    def test_parse(self, temp_file):
        """Test parse method."""
        extractor = MockExtractor(temp_file)
        extractor.load()
        extractor.parse()

        assert len(extractor.chunks) == 2
        assert extractor.chunks[0].text == "This is test chunk one."
        assert extractor.quality_score > 0
        assert extractor.route in ["A", "B", "C"]

    def test_parse_before_load(self, temp_file):
        """Test parse before load raises error."""
        extractor = MockExtractor(temp_file)
        with pytest.raises(RuntimeError, match="Must call load"):
            extractor.parse()

    def test_quality_before_parse(self, temp_file):
        """Test accessing quality before parse raises error."""
        extractor = MockExtractor(temp_file)
        extractor.load()
        with pytest.raises(RuntimeError, match="Quality not available"):
            _ = extractor.quality

    def test_extract_metadata(self, temp_file):
        """Test metadata extraction."""
        extractor = MockExtractor(temp_file)
        extractor.load()
        extractor.parse()
        metadata = extractor.extract_metadata()

        assert metadata.title == "Test Document"
        assert metadata.author == "Test Author"
        assert metadata.publisher == "Test Publisher"

    def test_extract_metadata_before_parse(self, temp_file):
        """Test extract_metadata before parse raises error."""
        extractor = MockExtractor(temp_file)
        extractor.load()
        with pytest.raises(RuntimeError, match="Must call parse"):
            extractor.extract_metadata()

    def test_compute_quality(self, temp_file):
        """Test quality computation."""
        extractor = MockExtractor(temp_file)
        extractor.load()

        # Manually call compute_quality
        test_text = "The quick brown fox jumps over the lazy dog. " * 10
        extractor.compute_quality(test_text)

        assert 0 <= extractor.quality_score <= 1
        assert extractor.route in ["A", "B", "C"]
        quality = extractor.quality
        assert "signals" in quality.to_dict()
        assert "score" in quality.to_dict()
        assert "route" in quality.to_dict()

    def test_get_output_data(self, temp_file):
        """Test getting complete output data."""
        extractor = MockExtractor(temp_file)
        extractor.load()
        extractor.parse()
        extractor.extract_metadata()

        data = extractor.get_output_data()

        assert "metadata" in data
        assert "chunks" in data
        assert "extraction_info" in data

        # Verify metadata includes provenance and quality
        assert "provenance" in data["metadata"]
        assert "quality" in data["metadata"]

        # Verify extraction_info
        assert data["extraction_info"]["total_chunks"] == 2
        assert "quality_route" in data["extraction_info"]
        assert "quality_score" in data["extraction_info"]

    def test_get_output_data_before_parse(self, temp_file):
        """Test get_output_data before parse raises error."""
        extractor = MockExtractor(temp_file)
        extractor.load()
        with pytest.raises(RuntimeError, match="No chunks available"):
            extractor.get_output_data()

    def test_get_output_data_before_extract_metadata(self, temp_file):
        """Test get_output_data before extract_metadata raises error."""
        extractor = MockExtractor(temp_file)
        extractor.load()
        extractor.parse()
        with pytest.raises(RuntimeError, match="No metadata available"):
            extractor.get_output_data()


class TestEpubExtractor:
    """Test EpubExtractor implementation."""

    @pytest.fixture
    def sample_epub_path(self):
        """Path to sample EPUB if available."""
        # Try to find a sample EPUB in the project
        possible_paths = [
            "Prayer Primer.epub",
            "tests/fixtures/sample.epub",
            "../Prayer Primer.epub"
        ]
        for path in possible_paths:
            if os.path.exists(path):
                return path
        pytest.skip("No sample EPUB available for testing")

    def test_epub_initialization(self):
        """Test EPUB extractor initialization."""
        extractor = EpubExtractor("test.epub")
        assert extractor.source_path == "test.epub"
        assert extractor.config == {}

    def test_epub_initialization_with_config(self):
        """Test EPUB extractor initialization with config."""
        config = {"min_words": 100, "toc_level": 2}
        extractor = EpubExtractor("test.epub", config)
        assert extractor.config["min_words"] == 100
        assert extractor.config["toc_level"] == 2

    @pytest.mark.skipif(not os.path.exists("Prayer Primer.epub"),
                        reason="Sample EPUB not available")
    def test_epub_load(self, sample_epub_path):
        """Test EPUB loading."""
        extractor = EpubExtractor(sample_epub_path)
        extractor.load()

        # Should have provenance after load
        prov = extractor.provenance
        assert prov.source_file == os.path.basename(sample_epub_path)
        assert prov.content_hash  # Should have a hash

    @pytest.mark.skipif(not os.path.exists("Prayer Primer.epub"),
                        reason="Sample EPUB not available")
    def test_epub_parse(self, sample_epub_path):
        """Test EPUB parsing."""
        extractor = EpubExtractor(sample_epub_path)
        extractor.load()
        extractor.parse()

        # Should have chunks
        assert len(extractor.chunks) > 0

        # Verify chunk structure
        chunk = extractor.chunks[0]
        assert hasattr(chunk, 'chunk_id')
        assert hasattr(chunk, 'text')
        assert hasattr(chunk, 'hierarchy')

        # Should have quality metrics
        assert 0 <= extractor.quality_score <= 1
        assert extractor.route in ["A", "B", "C"]

    @pytest.mark.skipif(not os.path.exists("Prayer Primer.epub"),
                        reason="Sample EPUB not available")
    def test_epub_extract_metadata(self, sample_epub_path):
        """Test EPUB metadata extraction."""
        extractor = EpubExtractor(sample_epub_path)
        extractor.load()
        extractor.parse()
        metadata = extractor.extract_metadata()

        # Metadata should have basic fields
        assert metadata.title
        assert hasattr(metadata, 'language')

    @pytest.mark.skipif(not os.path.exists("Prayer Primer.epub"),
                        reason="Sample EPUB not available")
    def test_epub_full_workflow(self, sample_epub_path):
        """Test complete EPUB extraction workflow."""
        extractor = EpubExtractor(sample_epub_path)

        # Full workflow: load -> parse -> extract_metadata -> get_output_data
        extractor.load()
        extractor.parse()
        extractor.extract_metadata()
        data = extractor.get_output_data()

        # Verify complete output structure
        assert "metadata" in data
        assert "chunks" in data
        assert "extraction_info" in data

        # Verify data types
        assert isinstance(data["chunks"], list)
        assert isinstance(data["metadata"], dict)
        assert data["extraction_info"]["total_chunks"] == len(extractor.chunks)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
