#!/usr/bin/env python3
"""Pytest configuration and shared fixtures for extraction library tests."""
import os
from pathlib import Path
import pytest


@pytest.fixture
def fixtures_dir() -> Path:
    """Return path to test fixtures directory."""
    return Path(__file__).parent / "fixtures"


@pytest.fixture
def sample_epubs_dir(fixtures_dir) -> Path:
    """Return path to sample EPUBs directory."""
    return fixtures_dir / "sample_epubs"


@pytest.fixture
def expected_outputs_dir(fixtures_dir) -> Path:
    """Return path to expected outputs directory."""
    return fixtures_dir / "expected_outputs"


@pytest.fixture
def simple_epub_path(sample_epubs_dir) -> Path:
    """Return path to simple.epub test fixture."""
    epub_path = sample_epubs_dir / "simple.epub"
    if not epub_path.exists():
        pytest.skip(f"Test fixture not found: {epub_path}")
    return epub_path


@pytest.fixture
def temp_output_dir(tmp_path) -> Path:
    """Return temporary directory for test outputs."""
    output_dir = tmp_path / "test_outputs"
    output_dir.mkdir(exist_ok=True)
    return output_dir
