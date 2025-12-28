#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Sentence splitting and hierarchy management utilities.

Provides functions for breaking text into sentences and managing
hierarchical document structures (headings, table of contents).
"""

import re
from typing import Dict, List


def split_sentences(text: str) -> List[str]:
    """Simple sentence splitter based on punctuation boundaries.

    Splits on sentence-ending punctuation (.!?) followed by whitespace
    and an uppercase letter or opening quote/parenthesis.
    """
    sents = re.split(r'(?<=[.!?])\s+(?=[A-Z""\'(])', text)
    return [s for s in sents if s.strip()]


def heading_path(hierarchy: Dict[str, str]) -> str:
    """Join non-empty hierarchy levels into a path string.

    Example:
        {"level_1": "Book", "level_2": "Chapter 1", "level_3": "Section A"}
        -> "Book / Chapter 1 / Section A"
    """
    parts = [hierarchy.get(f"level_{i}", "") for i in range(1, 7)]
    return " / ".join([p for p in parts if p])


def hierarchy_depth(hierarchy: Dict[str, str]) -> int:
    """Return deepest non-empty level index.

    Returns the highest level number (1-6) that contains a non-empty value,
    or 0 if all levels are empty.
    """
    for i in range(6, 0, -1):
        if hierarchy.get(f"level_{i}"):
            return i
    return 0


def heading_level(tag_name: str) -> int:
    """Return integer level if tag is h1-h6; else 99.

    Converts HTML heading tag names to their numeric level.
    Returns 99 for invalid or non-heading tags.
    """
    if tag_name and tag_name.lower().startswith("h"):
        try:
            return int(tag_name[1])
        except (ValueError, IndexError):
            return 99
    return 99


def is_heading_tag(tag_name: str) -> bool:
    """Check if tag is one of h1-h6."""
    return tag_name in {f"h{i}" for i in range(1, 7)}
