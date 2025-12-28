#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Test helper functions for creating test data.

Provides convenience functions for creating Chunk, Metadata, and other
model instances with reasonable defaults for testing.
"""

from typing import Dict, List, Optional
from src.extraction.core.models import Chunk, Metadata, Provenance, Quality


def create_test_chunk(
    stable_id: str = "test_chunk",
    paragraph_id: int = 1,
    text: str = "Test paragraph text.",
    hierarchy: Optional[Dict[str, str]] = None,
    chapter_href: str = "chapter.html",
    source_order: int = 1,
    source_tag: str = "p",
    word_count: Optional[int] = None,
    **kwargs
) -> Chunk:
    """
    Create a test Chunk with sensible defaults.

    Args:
        stable_id: Chunk stable ID
        paragraph_id: Paragraph number
        text: Chunk text content
        hierarchy: Hierarchy dict (defaults to empty hierarchy)
        chapter_href: Source chapter reference
        source_order: Order in source document
        source_tag: HTML tag name
        word_count: Word count (auto-calculated if None)
        **kwargs: Additional Chunk fields to override

    Returns:
        Chunk instance with all required fields populated
    """
    if hierarchy is None:
        hierarchy = {
            "level_1": "",
            "level_2": "",
            "level_3": "",
            "level_4": "",
            "level_5": "",
            "level_6": ""
        }

    if word_count is None:
        word_count = len(text.split())

    sentences = [s.strip() + "." for s in text.replace(".", "").split() if s][:1]
    if not sentences:
        sentences = [text]

    defaults = {
        "stable_id": stable_id,
        "paragraph_id": paragraph_id,
        "text": text,
        "hierarchy": hierarchy,
        "chapter_href": chapter_href,
        "source_order": source_order,
        "source_tag": source_tag,
        "text_length": len(text),
        "word_count": word_count,
        "cross_references": [],
        "scripture_references": [],
        "dates_mentioned": [],
        "heading_path": "",
        "hierarchy_depth": 0,
        "doc_stable_id": "doc123",
        "sentence_count": len(sentences),
        "sentences": sentences,
        "normalized_text": text.lower(),
    }

    # Override with any provided kwargs
    defaults.update(kwargs)

    return Chunk(**defaults)


def create_test_metadata(
    title: str = "Test Document",
    author: str = "Test Author",
    language: str = "en",
    **kwargs
) -> Metadata:
    """
    Create a test Metadata instance with sensible defaults.

    Args:
        title: Document title
        author: Document author
        language: Document language
        **kwargs: Additional Metadata fields to override

    Returns:
        Metadata instance
    """
    defaults = {
        "title": title,
        "author": author,
        "language": language,
    }

    defaults.update(kwargs)
    return Metadata(**defaults)


def create_test_provenance(
    doc_id: str = "test123",
    source_file: str = "test.epub",
    **kwargs
) -> Provenance:
    """
    Create a test Provenance instance with sensible defaults.

    Args:
        doc_id: Document ID
        source_file: Source file name
        **kwargs: Additional Provenance fields to override

    Returns:
        Provenance instance
    """
    defaults = {
        "doc_id": doc_id,
        "source_file": source_file,
        "parser_version": "1.0.0",
        "md_schema_version": "1.0",
        "ingestion_ts": "2024-01-01T00:00:00",
        "content_hash": "abc123def456",
    }

    defaults.update(kwargs)
    return Provenance(**defaults)


def create_test_quality(
    score: float = 0.9,
    route: str = "A",
    **kwargs
) -> Quality:
    """
    Create a test Quality instance with sensible defaults.

    Args:
        score: Quality score (0-1)
        route: Quality route (A/B/C)
        **kwargs: Additional Quality fields to override

    Returns:
        Quality instance
    """
    defaults = {
        "signals": {
            "garble_rate": 0.0,
            "mean_conf": 1.0,
            "line_len_std_norm": 0.0,
            "lang_prob": 1.0
        },
        "score": score,
        "route": route,
    }

    defaults.update(kwargs)
    return Quality(**defaults)
