#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Unit tests for output management module.

Tests verify output file generation, hierarchy reports, and NDJSON format.
"""

import pytest
import os
import json
import tempfile
import shutil
from pathlib import Path

from src.extraction.core.output import (
    write_outputs,
    write_chunks_ndjson,
    write_hierarchy_report
)
from src.extraction.extractors.base import BaseExtractor
from src.extraction.core.models import Chunk, Metadata, Provenance, Quality
from tests.helpers import create_test_chunk, create_test_metadata, create_test_provenance, create_test_quality


class SimpleExtractor(BaseExtractor):
    """Simple extractor for testing output functions."""

    def __init__(self, source_path: str):
        super().__init__(source_path, {})
        self._setup_test_data()

    def _setup_test_data(self):
        """Set up minimal test data."""
        # Create provenance using helper
        self._provenance = create_test_provenance(
            doc_id="test123",
            source_file="test.epub"
        )

        # Create quality using helper
        self._quality = create_test_quality(score=0.95, route="A")
        self._doc_quality_score = 0.95
        self._doc_route = "A"

    def load(self):
        """Mock load."""
        pass

    def parse(self):
        """Mock parse with test chunks."""
        self.chunks = [
            create_test_chunk(
                stable_id="chunk1",
                paragraph_id=1,
                text="First test paragraph.",
                hierarchy={"level_1": "Chapter 1", "level_2": "", "level_3": "", "level_4": "", "level_5": "", "level_6": ""},
                word_count=3
            ),
            create_test_chunk(
                stable_id="chunk2",
                paragraph_id=2,
                text="Second test paragraph.",
                hierarchy={"level_1": "Chapter 1", "level_2": "Section A", "level_3": "", "level_4": "", "level_5": "", "level_6": ""},
                word_count=3
            ),
            create_test_chunk(
                stable_id="chunk3",
                paragraph_id=3,
                text="Third test paragraph.",
                hierarchy={"level_1": "Chapter 2", "level_2": "", "level_3": "", "level_4": "", "level_5": "", "level_6": ""},
                word_count=3
            ),
        ]

    def extract_metadata(self):
        """Mock metadata extraction."""
        self.metadata = create_test_metadata(
            title="Test Document",
            author="Test Author",
            publisher="Test Publisher",
            language="en"
        )
        return self.metadata


class TestWriteOutputs:
    """Test write_outputs function."""

    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory for output tests."""
        temp_path = tempfile.mkdtemp()
        yield temp_path
        shutil.rmtree(temp_path)

    @pytest.fixture
    def test_extractor(self):
        """Create test extractor with data."""
        extractor = SimpleExtractor("test.epub")
        extractor.parse()
        extractor.extract_metadata()
        return extractor

    def test_write_outputs_basic(self, test_extractor, temp_dir):
        """Test basic output writing."""
        write_outputs(test_extractor, base_filename="test", output_dir=temp_dir)

        # Check all output files exist
        assert os.path.exists(os.path.join(temp_dir, "test.json"))
        assert os.path.exists(os.path.join(temp_dir, "test_metadata.json"))
        assert os.path.exists(os.path.join(temp_dir, "test_hierarchy_report.txt"))

    def test_write_outputs_main_json(self, test_extractor, temp_dir):
        """Test main JSON output content."""
        write_outputs(test_extractor, base_filename="test", output_dir=temp_dir)

        with open(os.path.join(temp_dir, "test.json"), 'r') as f:
            data = json.load(f)

        assert "metadata" in data
        assert "chunks" in data
        assert "extraction_info" in data

        # Verify metadata includes provenance and quality
        assert "provenance" in data["metadata"]
        assert "quality" in data["metadata"]

        # Verify chunks
        assert len(data["chunks"]) == 3
        assert data["chunks"][0]["text"] == "First test paragraph."

        # Verify extraction_info
        assert data["extraction_info"]["total_chunks"] == 3
        assert data["extraction_info"]["quality_route"] == "A"

    def test_write_outputs_metadata_json(self, test_extractor, temp_dir):
        """Test metadata JSON output content."""
        write_outputs(test_extractor, base_filename="test", output_dir=temp_dir)

        with open(os.path.join(temp_dir, "test_metadata.json"), 'r') as f:
            metadata = json.load(f)

        assert metadata["title"] == "Test Document"
        assert metadata["author"] == "Test Author"
        assert "provenance" in metadata
        assert "quality" in metadata
        assert metadata["provenance"]["doc_id"] == "test123"
        assert metadata["quality"]["route"] == "A"

    def test_write_outputs_hierarchy_report(self, test_extractor, temp_dir):
        """Test hierarchy report generation."""
        write_outputs(test_extractor, base_filename="test", output_dir=temp_dir)

        report_path = os.path.join(temp_dir, "test_hierarchy_report.txt")
        assert os.path.exists(report_path)

        with open(report_path, 'r') as f:
            content = f.read()

        # Check report sections
        assert "DOCUMENT HIERARCHICAL STRUCTURE REPORT" in content
        assert "DOCUMENT METADATA:" in content
        assert "STRUCTURE TREE:" in content
        assert "SUMMARY:" in content

        # Check hierarchy appears
        assert "Chapter 1" in content
        assert "Chapter 2" in content

    def test_write_outputs_ndjson(self, test_extractor, temp_dir):
        """Test NDJSON output when requested."""
        write_outputs(test_extractor, base_filename="test", output_dir=temp_dir, ndjson=True)

        ndjson_path = os.path.join(temp_dir, "test.ndjson")
        assert os.path.exists(ndjson_path)

        # Read and verify NDJSON
        with open(ndjson_path, 'r') as f:
            lines = f.readlines()

        assert len(lines) == 3  # 3 chunks
        for line in lines:
            chunk = json.loads(line)
            assert "stable_id" in chunk
            assert "text" in chunk

    def test_write_outputs_no_ndjson_by_default(self, test_extractor, temp_dir):
        """Test NDJSON is not created by default."""
        write_outputs(test_extractor, base_filename="test", output_dir=temp_dir)

        ndjson_path = os.path.join(temp_dir, "test.ndjson")
        assert not os.path.exists(ndjson_path)

    def test_write_outputs_creates_directory(self, test_extractor):
        """Test output directory creation."""
        with tempfile.TemporaryDirectory() as temp_dir:
            new_dir = os.path.join(temp_dir, "new_output_dir")
            assert not os.path.exists(new_dir)

            write_outputs(test_extractor, base_filename="test", output_dir=new_dir)

            assert os.path.exists(new_dir)
            assert os.path.exists(os.path.join(new_dir, "test.json"))

    def test_write_outputs_default_filename(self, test_extractor, temp_dir):
        """Test using source filename when base_filename not provided."""
        write_outputs(test_extractor, output_dir=temp_dir)

        # Should use source_path basename without extension
        assert os.path.exists(os.path.join(temp_dir, "test.json"))


class TestWriteChunksNdjson:
    """Test write_chunks_ndjson function."""

    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory."""
        temp_path = tempfile.mkdtemp()
        yield temp_path
        shutil.rmtree(temp_path)

    def test_write_chunks_ndjson_basic(self, temp_dir):
        """Test basic NDJSON writing."""
        chunks = [
            {"chunk_id": "c1", "text": "First", "word_count": 1},
            {"chunk_id": "c2", "text": "Second", "word_count": 1},
        ]

        output_path = os.path.join(temp_dir, "chunks.ndjson")
        write_chunks_ndjson(chunks, output_path)

        assert os.path.exists(output_path)

        with open(output_path, 'r') as f:
            lines = f.readlines()

        assert len(lines) == 2
        chunk1 = json.loads(lines[0])
        chunk2 = json.loads(lines[1])

        assert chunk1["chunk_id"] == "c1"
        assert chunk2["chunk_id"] == "c2"

    def test_write_chunks_ndjson_empty(self, temp_dir):
        """Test NDJSON with empty chunks."""
        output_path = os.path.join(temp_dir, "empty.ndjson")
        write_chunks_ndjson([], output_path)

        assert os.path.exists(output_path)
        with open(output_path, 'r') as f:
            content = f.read()
        assert content == ""


class TestWriteHierarchyReport:
    """Test write_hierarchy_report function."""

    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory."""
        temp_path = tempfile.mkdtemp()
        yield temp_path
        shutil.rmtree(temp_path)

    @pytest.fixture
    def test_extractor(self):
        """Create test extractor."""
        extractor = SimpleExtractor("test.epub")
        extractor.parse()
        extractor.extract_metadata()
        return extractor

    def test_write_hierarchy_report_structure(self, test_extractor, temp_dir):
        """Test hierarchy report structure."""
        metadata = test_extractor.metadata.to_dict()
        metadata["provenance"] = test_extractor.provenance.to_dict()
        metadata["quality"] = test_extractor.quality.to_dict()

        chunks = [c.to_dict() for c in test_extractor.chunks]

        report_path = os.path.join(temp_dir, "report.txt")
        write_hierarchy_report(test_extractor, metadata, chunks, report_path)

        with open(report_path, 'r') as f:
            content = f.read()

        # Check all sections present
        assert "DOCUMENT HIERARCHICAL STRUCTURE REPORT" in content
        assert "Source: test.epub" in content
        assert "DOCUMENT METADATA:" in content
        assert "STRUCTURE TREE:" in content
        assert "SUMMARY:" in content

        # Check metadata fields
        assert "Test Document" in content
        assert "Test Author" in content

        # Check hierarchy
        assert "Chapter 1" in content
        assert "Chapter 2" in content

        # Check summary stats
        assert "Total paragraphs: 3" in content
        assert "Total words:" in content

    def test_write_hierarchy_report_with_nested_hierarchy(self, temp_dir):
        """Test hierarchy report with nested structure."""
        extractor = SimpleExtractor("nested.epub")

        # Create chunks with nested hierarchy using helper
        extractor.chunks = [
            create_test_chunk(
                stable_id="c1",
                paragraph_id=1,
                text="Text 1",
                hierarchy={"level_1": "Part I", "level_2": "Chapter 1", "level_3": "Section A", "level_4": "", "level_5": "", "level_6": ""},
                word_count=50
            ),
            create_test_chunk(
                stable_id="c2",
                paragraph_id=2,
                text="Text 2",
                hierarchy={"level_1": "Part I", "level_2": "Chapter 1", "level_3": "Section A", "level_4": "", "level_5": "", "level_6": ""},
                word_count=50
            ),
        ]

        extractor.extract_metadata()

        metadata = extractor.metadata.to_dict()
        metadata["provenance"] = extractor.provenance.to_dict()
        metadata["quality"] = extractor.quality.to_dict()
        chunks = [c.to_dict() for c in extractor.chunks]

        report_path = os.path.join(temp_dir, "nested_report.txt")
        write_hierarchy_report(extractor, metadata, chunks, report_path)

        with open(report_path, 'r') as f:
            content = f.read()

        # Should show nested structure
        assert "Part I" in content
        assert "Chapter 1" in content
        assert "Section A" in content

        # Should show paragraph range and word count
        assert "1-2" in content  # Paragraph range
        assert "100 words" in content  # Total words for that section


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
