#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Sentence splitting and hierarchy management utilities.

Provides functions for breaking text into sentences and managing
hierarchical document structures (headings, table of contents).
"""

import re
from typing import Dict, List

_SENTENCE_SPLIT_RE = re.compile(r'(?<=[.!?])\s+(?=[A-Z""\'(])')

ABBREVIATIONS = frozenset({
    'St', 'Dr', 'Rev', 'Fr', 'Sr', 'Br', 'Ven', 'Bl', 'Abp', 'Bp', 'Msgr',
    'Prof', 'Mr', 'Mrs', 'Ms', 'Jr', 'Sgt', 'Lt', 'Col', 'Gen', 'Capt',
    'cf', 'ibid', 'op', 'loc', 'cit', 'viz', 'approx',
    'i.e', 'e.g', 'n.b', 'vs', 'etc', 'al', 'ff',
    'vol', 'art', 'no', 'ed', 'trans', 'ch', 'pt', 'sec', 'pp', 'p',
    'infra', 'supra',
    'Jan', 'Feb', 'Mar', 'Apr', 'Jun', 'Jul', 'Aug', 'Sep', 'Sept',
    'Oct', 'Nov', 'Dec',
    'Gen', 'Ex', 'Lev', 'Num', 'Deut', 'Josh', 'Judg',
    'Sam', 'Kgs', 'Chr', 'Neh', 'Esth', 'Ps', 'Prov', 'Eccl',
    'Isa', 'Jer', 'Lam', 'Ezek', 'Dan', 'Hos', 'Mic', 'Hab',
    'Zeph', 'Hag', 'Zech', 'Mal',
    'Sir', 'Wis', 'Tob', 'Jdt', 'Bar', 'Macc',
    'Mt', 'Mk', 'Lk', 'Jn', 'Rom', 'Cor', 'Gal', 'Eph',
    'Phil', 'Col', 'Thess', 'Tim', 'Tit', 'Phlm', 'Heb',
    'Jas', 'Pet', 'Rev',
})

_ABBREV_RE = re.compile(
    r'\b(' + '|'.join(re.escape(a) for a in sorted(ABBREVIATIONS, key=len, reverse=True)) + r')\.\s+',
)
_SENTINEL = '\x00'


def split_sentences(text: str) -> List[str]:
    """Abbreviation-aware sentence splitter.

    Protects known abbreviations from triggering false splits, then
    splits on sentence-ending punctuation (.!?) followed by whitespace
    and an uppercase letter or opening quote/parenthesis.
    """
    protected = _ABBREV_RE.sub(lambda m: m.group(0).replace('. ', '.' + _SENTINEL), text)
    sents = _SENTENCE_SPLIT_RE.split(protected)
    return [s.replace(_SENTINEL, ' ').strip() for s in sents if s.strip()]


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
