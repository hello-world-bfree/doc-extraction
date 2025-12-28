#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Pytest configuration and shared fixtures.

Provides common fixtures and test configuration for all test modules.
"""

import pytest
import os
import tempfile
import shutil
from pathlib import Path


@pytest.fixture
def temp_dir():
    """Create a temporary directory for test outputs."""
    temp_path = tempfile.mkdtemp()
    yield temp_path
    shutil.rmtree(temp_path, ignore_errors=True)


@pytest.fixture
def fixtures_dir():
    """Get path to test fixtures directory."""
    return Path(__file__).parent / "fixtures"


@pytest.fixture
def sample_epub_path(fixtures_dir):
    """
    Get path to sample EPUB file.

    Checks multiple locations:
    1. tests/fixtures/sample_data/
    2. Project root
    3. Parent directory

    Skips test if no sample EPUB found.
    """
    possible_locations = [
        fixtures_dir / "sample_data" / "Prayer Primer.epub",
        Path("Prayer Primer.epub"),
        Path("../Prayer Primer.epub"),
    ]

    for path in possible_locations:
        if path.exists():
            return str(path)

    pytest.skip("No sample EPUB available for testing")


@pytest.fixture
def sample_text():
    """Sample text for testing text utilities."""
    return """
    The Sacred Liturgy is the source and summit of Christian life.
    The Mass is the center of our faith. Through the sacraments,
    we receive grace. Prayer is essential for spiritual growth.

    The Church teaches that the Eucharist is the real presence
    of Christ. The Catechism of the Catholic Church explains
    this mystery in detail.
    """.strip()


@pytest.fixture
def sample_chunks():
    """Sample chunk data for testing analyzers and output."""
    return [
        {
            "chunk_id": "chunk_1",
            "paragraph_id": 1,
            "text": "Introduction to the sacred liturgy.",
            "hierarchy": {
                "level_1": "Part I: The Liturgy",
                "level_2": "Chapter 1: Introduction",
                "level_3": "",
                "level_4": "",
                "level_5": "",
                "level_6": ""
            },
            "word_count": 5,
            "footnote_citations": {"all": [1, 2]}
        },
        {
            "chunk_id": "chunk_2",
            "paragraph_id": 2,
            "text": "The Mass is the central act of worship.",
            "hierarchy": {
                "level_1": "Part I: The Liturgy",
                "level_2": "Chapter 2: The Mass",
                "level_3": "",
                "level_4": "",
                "level_5": "",
                "level_6": ""
            },
            "word_count": 7,
            "footnote_citations": {"all": [1, 3, 4]}
        },
        {
            "chunk_id": "chunk_3",
            "paragraph_id": 3,
            "text": "The sacraments convey God's grace to the faithful.",
            "hierarchy": {
                "level_1": "Part II: The Sacraments",
                "level_2": "",
                "level_3": "",
                "level_4": "",
                "level_5": "",
                "level_6": ""
            },
            "word_count": 8,
            "footnote_citations": {"all": [5]}
        },
    ]


@pytest.fixture
def sample_metadata():
    """Sample metadata for testing."""
    return {
        "title": "Test Document on Catholic Liturgy",
        "author": "Test Author",
        "publisher": "Catholic Press",
        "language": "en",
        "publication_date": "2023",
    }


def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line(
        "markers",
        "slow: marks tests as slow (deselect with '-m \"not slow\"')"
    )
    config.addinivalue_line(
        "markers",
        "integration: marks tests as integration tests requiring sample files"
    )


def pytest_collection_modifyitems(config, items):
    """Automatically mark tests based on their characteristics."""
    for item in items:
        # Mark tests that use sample_epub_path as integration tests
        if "sample_epub_path" in item.fixturenames:
            item.add_marker(pytest.mark.integration)

        # Mark batch processing tests as slow
        if "batch" in item.name.lower():
            item.add_marker(pytest.mark.slow)
