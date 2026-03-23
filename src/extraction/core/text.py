#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Text cleaning and normalization utilities.

All functions preserve exact behavior from legacy parsers for backward compatibility.
"""

import re
import unicodedata


SOFT_HYPHEN = "\u00ad"

MONTHS = (
    r'Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)|Apr(?:il)|May|Jun(?:e)|'
    r'Jul(?:y)|Aug(?:ust)|Sep(?:t\.|tember)|Oct(?:ober)|Nov(?:ember)|Dec(?:ember)'
)

_ZW_SPACES_RE = re.compile(r'[\u200B-\u200D\u2060\uFEFF]')
_HTML_TAG_RE = re.compile(r'<[^>]+>')
_WHITESPACE_RE = re.compile(r'\s+')
_VERSE_NUM_RE = re.compile(r'(\b\d+)([A-Z][a-z])')
_NUM_DOT_RE = re.compile(r'(\b\d+)\s+\.')
_SPACE_BEFORE_PUNCT_RE = re.compile(r'\s+([,;:!?])')
_SPACE_BEFORE_CLOSE_RE = re.compile(r'\s+([."\')\]\}])')
_SPACE_AFTER_OPEN_RE = re.compile(r'([(["\'])\s+')
_SPACED_CAPS_RE = re.compile(r'\b(?:[A-Z]\s){2,}[A-Z]\b')
_SPACED_CAP_PAIR_RE = re.compile(r'\b([A-Z])\s(?=[A-Z]{2,}\b)')
_CHAPTER_RE = re.compile(r'^\s*(?:chapter|chap\.?)\s*\d+\s*[:.\-–—]\s*', re.IGNORECASE)
_ARABIC_NUM_RE = re.compile(r'^\s*\d+\s*[.)]')
_ROMAN_NUM_RE = re.compile(r'^\s*[IVXLC]{2,}\s*[.)]', re.IGNORECASE)
_BARE_NUM_RE = re.compile(r'^\s*\d+\s+')
_LEADING_PUNCT_RE = re.compile(r'^[\s.)\-–—]+')


def normalize_spaced_caps(s: str) -> str:
    """Fix spaced small-caps artifacts (e.g. 'S E C O N D' → 'SECOND')."""
    if not s:
        return s
    s = _SPACED_CAPS_RE.sub(lambda m: m.group(0).replace(' ', ''), s)
    s = _SPACED_CAP_PAIR_RE.sub(r'\1', s)
    return s


def clean_text(s: str) -> str:
    """Normalize text: remove soft hyphens, zero-width spaces, collapse spaces,
    tighten punctuation spacing, and fix spaced-caps artifacts."""
    if not s:
        return ""
    s = unicodedata.normalize("NFC", s)
    s = s.replace(SOFT_HYPHEN, "")
    s = _ZW_SPACES_RE.sub("", s)
    s = _HTML_TAG_RE.sub('', s)
    s = _WHITESPACE_RE.sub(" ", s)
    s = s.replace("\u00a0", " ").strip()
    s = _VERSE_NUM_RE.sub(r'\1 \2', s)
    s = _NUM_DOT_RE.sub(r'\1.', s)
    s = _SPACE_BEFORE_PUNCT_RE.sub(r'\1', s)
    s = _SPACE_BEFORE_CLOSE_RE.sub(r'\1', s)
    s = _SPACE_AFTER_OPEN_RE.sub(r'\1', s)
    s = normalize_spaced_caps(s)
    return s


def clean_code_text(s: str) -> str:
    if not s:
        return ""
    s = unicodedata.normalize("NFC", s)
    s = s.replace(SOFT_HYPHEN, "")
    s = _ZW_SPACES_RE.sub("", s)
    s = s.replace("\u00a0", " ")
    return s


def estimate_word_count(text: str) -> int:
    """Estimate number of words in text by splitting on whitespace."""
    return len(text.split()) if text else 0


def clean_toc_title(s: str) -> str:
    """Strip leading numbers/ordinals from TOC titles."""
    if not s:
        return s
    s = clean_text(s)
    s = _CHAPTER_RE.sub('', s)
    s = _ARABIC_NUM_RE.sub('', s)
    s = _ROMAN_NUM_RE.sub('', s)
    s = _BARE_NUM_RE.sub('', s)
    s = _LEADING_PUNCT_RE.sub('', s)
    return s


def normalize_ascii(t: str) -> str:
    """Return ASCII-normalized version of string."""
    return unicodedata.normalize("NFKD", t).encode("ascii", "ignore").decode("ascii")
