#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Integration tests for CLI (extract command).

Tests verify command-line interface, argument parsing, and end-to-end processing.
"""

import pytest
import os
import sys
import json
import tempfile
import shutil
from pathlib import Path
from unittest.mock import patch

from src.extraction.cli.extract import (
    detect_format,
    process_document,
    process_batch,
    setup_logging,
    main
)


class TestDetectFormat:
    """Test format detection function."""

    def test_detect_epub(self):
        """Test EPUB detection."""
        assert detect_format("document.epub") == "epub"
        assert detect_format("DOCUMENT.EPUB") == "epub"

    def test_detect_pdf(self):
        """Test PDF detection."""
        assert detect_format("document.pdf") == "pdf"
        assert detect_format("DOCUMENT.PDF") == "pdf"

    def test_detect_html(self):
        """Test HTML detection."""
        assert detect_format("document.html") == "html"
        assert detect_format("document.htm") == "html"
        assert detect_format("DOCUMENT.HTML") == "html"

    def test_detect_markdown(self):
        """Test Markdown detection."""
        assert detect_format("document.md") == "md"
        assert detect_format("document.markdown") == "md"

    def test_detect_json(self):
        """Test JSON detection."""
        assert detect_format("document.json") == "json"

    def test_detect_unknown(self):
        """Test unknown format."""
        assert detect_format("document.txt") == "unknown"
        assert detect_format("document.docx") == "unknown"
        assert detect_format("no_extension") == "unknown"


class TestSetupLogging:
    """Test logging configuration."""

    def test_setup_logging_default(self):
        """Test default logging setup."""
        import logging
        setup_logging()
        # Should be INFO by default
        logger = logging.getLogger("extraction.cli")
        # Just verify it doesn't crash

    def test_setup_logging_verbose(self):
        """Test verbose logging."""
        import logging
        setup_logging(verbose=True)
        # Should be DEBUG
        # Just verify it doesn't crash

    def test_setup_logging_quiet(self):
        """Test quiet logging."""
        import logging
        setup_logging(quiet=True)
        # Should be WARNING
        # Just verify it doesn't crash


class TestProcessDocument:
    """Test single document processing."""

    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory."""
        temp_path = tempfile.mkdtemp()
        yield temp_path
        shutil.rmtree(temp_path)

    @pytest.mark.skipif(not os.path.exists("Prayer Primer.epub"),
                        reason="Sample EPUB not available")
    def test_process_document_epub_success(self, temp_dir):
        """Test successful EPUB processing."""
        config = {
            "toc_hierarchy_level": 3,
            "min_paragraph_words": 1,
            "min_block_words": 2,
            "preserve_hierarchy_across_docs": False,
            "reset_depth": 2,
            "class_denylist": r"^(?:calibre\d+|note|footnote)$",
        }

        result = process_document(
            "Prayer Primer.epub",
            config,
            output_dir=temp_dir,
            base_filename="test_output",
            ndjson=False,
            analyzer="catholic",
            debug_dump=False
        )

        assert result is True

        # Verify output files exist
        assert os.path.exists(os.path.join(temp_dir, "test_output.json"))
        assert os.path.exists(os.path.join(temp_dir, "test_output_metadata.json"))
        assert os.path.exists(os.path.join(temp_dir, "test_output_hierarchy_report.txt"))

    def test_process_document_pdf_unsupported(self, temp_dir):
        """Test PDF processing returns False (not yet implemented)."""
        config = {}
        result = process_document(
            "document.pdf",
            config,
            output_dir=temp_dir
        )

        assert result is False

    def test_process_document_unknown_format(self, temp_dir):
        """Test unknown format returns False."""
        config = {}
        result = process_document(
            "document.unknown",
            config,
            output_dir=temp_dir
        )

        assert result is False

    @pytest.mark.skipif(not os.path.exists("Prayer Primer.epub"),
                        reason="Sample EPUB not available")
    def test_process_document_with_ndjson(self, temp_dir):
        """Test EPUB processing with NDJSON output."""
        config = {
            "toc_hierarchy_level": 3,
            "min_paragraph_words": 1,
            "min_block_words": 2,
            "preserve_hierarchy_across_docs": False,
            "reset_depth": 2,
            "class_denylist": r"^(?:calibre\d+|note|footnote)$",
        }

        result = process_document(
            "Prayer Primer.epub",
            config,
            output_dir=temp_dir,
            base_filename="test_ndjson",
            ndjson=True,
            analyzer="catholic"
        )

        assert result is True
        assert os.path.exists(os.path.join(temp_dir, "test_ndjson.ndjson"))


class TestProcessBatch:
    """Test batch processing."""

    @pytest.fixture
    def temp_dir_with_epubs(self):
        """Create temporary directory with test EPUB files."""
        temp_path = tempfile.mkdtemp()

        # Only run if sample EPUB exists
        if os.path.exists("Prayer Primer.epub"):
            # Copy sample EPUB multiple times with different names
            for i in range(3):
                shutil.copy("Prayer Primer.epub", os.path.join(temp_path, f"test_{i}.epub"))

        yield temp_path
        shutil.rmtree(temp_path)

    @pytest.mark.skipif(not os.path.exists("Prayer Primer.epub"),
                        reason="Sample EPUB not available")
    def test_process_batch_success(self, temp_dir_with_epubs):
        """Test batch processing of multiple files."""
        config = {
            "toc_hierarchy_level": 3,
            "min_paragraph_words": 1,
            "min_block_words": 2,
            "preserve_hierarchy_across_docs": False,
            "reset_depth": 2,
            "class_denylist": r"^(?:calibre\d+|note|footnote)$",
        }

        success_count, total_count = process_batch(
            temp_dir_with_epubs,
            recursive=False,
            config=config,
            output_dir=temp_dir_with_epubs,
            ndjson=False,
            analyzer="catholic"
        )

        assert total_count == 3
        assert success_count == 3

        # Verify output files for each
        for i in range(3):
            assert os.path.exists(os.path.join(temp_dir_with_epubs, f"test_{i}.json"))

    def test_process_batch_no_files(self):
        """Test batch processing with no supported files."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config = {}
            success_count, total_count = process_batch(
                temp_dir,
                recursive=False,
                config=config
            )

            assert total_count == 0
            assert success_count == 0

    @pytest.mark.skipif(not os.path.exists("Prayer Primer.epub"),
                        reason="Sample EPUB not available")
    def test_process_batch_recursive(self):
        """Test batch processing with recursive flag."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create subdirectory
            subdir = os.path.join(temp_dir, "subdir")
            os.makedirs(subdir)

            # Copy EPUB to both directories
            shutil.copy("Prayer Primer.epub", os.path.join(temp_dir, "root.epub"))
            shutil.copy("Prayer Primer.epub", os.path.join(subdir, "sub.epub"))

            config = {
                "toc_hierarchy_level": 3,
                "min_paragraph_words": 1,
                "min_block_words": 2,
                "preserve_hierarchy_across_docs": False,
                "reset_depth": 2,
                "class_denylist": r"^(?:calibre\d+|note|footnote)$",
            }

            # Non-recursive should find 1
            success, total = process_batch(
                temp_dir,
                recursive=False,
                config=config,
                output_dir=temp_dir
            )
            assert total == 1

            # Recursive should find 2
            success, total = process_batch(
                temp_dir,
                recursive=True,
                config=config,
                output_dir=temp_dir
            )
            assert total == 2


class TestCLI:
    """Test CLI main function."""

    @pytest.mark.skipif(not os.path.exists("Prayer Primer.epub"),
                        reason="Sample EPUB not available")
    def test_main_single_file(self):
        """Test CLI with single file argument."""
        with tempfile.TemporaryDirectory() as temp_dir:
            test_args = [
                "extract",
                "Prayer Primer.epub",
                "--output-dir", temp_dir,
                "--quiet"
            ]

            with patch.object(sys, 'argv', test_args):
                exit_code = main()

            assert exit_code == 0
            # Check output files exist
            assert any(f.endswith(".json") for f in os.listdir(temp_dir))

    def test_main_no_path(self):
        """Test CLI with no path provided."""
        test_args = ["extract"]

        with patch.object(sys, 'argv', test_args):
            with patch('builtins.input', return_value=''):
                exit_code = main()

        assert exit_code == 2  # Error: no path

    def test_main_nonexistent_path(self):
        """Test CLI with nonexistent path."""
        test_args = ["extract", "/nonexistent/path.epub"]

        with patch.object(sys, 'argv', test_args):
            exit_code = main()

        assert exit_code == 2  # Error: path not found

    @pytest.mark.skipif(not os.path.exists("Prayer Primer.epub"),
                        reason="Sample EPUB not available")
    def test_main_with_all_options(self):
        """Test CLI with all configuration options."""
        with tempfile.TemporaryDirectory() as temp_dir:
            test_args = [
                "extract",
                "Prayer Primer.epub",
                "--output-dir", temp_dir,
                "--output", "custom_name",
                "--ndjson",
                "--analyzer", "catholic",
                "--toc-level", "2",
                "--min-words", "5",
                "--min-block-words", "3",
                "--preserve-hierarchy",
                "--reset-depth", "3",
                "--verbose"
            ]

            with patch.object(sys, 'argv', test_args):
                exit_code = main()

            assert exit_code == 0

            # Verify output with custom name
            assert os.path.exists(os.path.join(temp_dir, "custom_name.json"))
            assert os.path.exists(os.path.join(temp_dir, "custom_name.ndjson"))


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
