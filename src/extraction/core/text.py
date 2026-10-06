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
_SPACE_BEFORE_CLOSE_RE = re.compile(r'\s+([.)\]\}])')
_SPACE_AFTER_OPEN_RE = re.compile(r'([(\[])\s+')
# A straight quote may open or close, so a space is removed only where the quote's role is clear:
# stripping both sides unconditionally glued 'Flesh: "Who His own self," writes' into 'Flesh:"Who...,"writes'.
_SPACE_BEFORE_CLOSE_QUOTE_RE = re.compile(r'(?<=\S)\s+(["\'])(?=[.,;:!?)\]]|$)')
_SPACE_AFTER_OPEN_QUOTE_RE = re.compile(r'(?:^|(?<=[(\[]))(["\'])\s+')
_SPACED_DOUBLE_QUOTE_RE = re.compile(r'(?<=\S)\s+"\s+(?=\S)')
_SPACED_CAPS_RE = re.compile(r'\b(?:[A-Z]\s){2,}[A-Z]\b')
# A, I and O are words: joining them turned "O LORD" into "OLORD" and "I AM" into "IAM".
_SPACED_CAP_PAIR_RE = re.compile(r'\b([B-HJ-NP-Z])\s(?=[A-Z]{2,}\b)')
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
    s = _SPACE_BEFORE_CLOSE_QUOTE_RE.sub(r'\1', s)
    s = _SPACE_AFTER_OPEN_QUOTE_RE.sub(r'\1', s)
    s = _SPACED_DOUBLE_QUOTE_RE.sub(lambda m: ' "' if m.string.count('"', 0, m.start()) % 2 == 0 else '" ', s)
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
