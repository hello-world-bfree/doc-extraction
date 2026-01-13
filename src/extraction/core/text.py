#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Text cleaning and normalization utilities.

All functions preserve exact behavior from legacy parsers for backward compatibility.
"""

import re
import unicodedata


# Unicode characters to normalize away
SOFT_HYPHEN = "\u00ad"
ZW_SPACES = r"[\u200B-\u200D\u2060\uFEFF]"

# Predefined month patterns for date extraction
MONTHS = (
    r'Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)|Apr(?:il)|May|Jun(?:e)|'
    r'Jul(?:y)|Aug(?:ust)|Sep(?:t\.|tember)|Oct(?:ober)|Nov(?:ember)|Dec(?:ember)'
)


def normalize_spaced_caps(s: str) -> str:
    """Fix spaced small-caps artifacts (e.g. 'S E C O N D' → 'SECOND')."""
    if not s:
        return s
    # A) "S E C O N D" → "SECOND"
    s = re.sub(r'\b(?:[A-Z]\s){2,}[A-Z]\b', lambda m: m.group(0).replace(' ', ''), s)
    # B) "S ON" → "SON" (also handles "P RODIGAL" → "PRODIGAL")
    s = re.sub(r'\b([A-Z])\s(?=[A-Z]{2,}\b)', r'\1', s)
    return s


def clean_text(s: str) -> str:
    """Normalize text: remove soft hyphens, zero-width spaces, collapse spaces,
    tighten punctuation spacing, and fix spaced-caps artifacts."""
    if not s:
        return ""
    s = unicodedata.normalize("NFC", s)
    # Remove soft hyphen and zero-width spaces
    s = s.replace(SOFT_HYPHEN, "")
    s = re.sub(ZW_SPACES, "", s)
    # Collapse whitespace
    s = re.sub(r"\s+", " ", s)
    s = s.replace("\u00a0", " ").strip()
    # Tighten punctuation spacing
    s = re.sub(r'(\b\d+)\s+\.', r'\1.', s)
    s = re.sub(r'\s+([,;:!?])', r'\1', s)
    s = re.sub(r'\s+([."\')\]\}])', r'\1', s)
    s = re.sub(r'([(["\'])\s+', r'\1', s)
    # Fix small-caps artifacts
    s = normalize_spaced_caps(s)
    return s


def estimate_word_count(text: str) -> int:
    """Estimate number of words in text by splitting on whitespace."""
    return len(text.split()) if text else 0


def clean_toc_title(s: str) -> str:
    """Strip leading numbers/ordinals from TOC titles."""
    if not s:
        return s
    s = clean_text(s)
    # Remove "Chapter 5:" etc.
    s = re.sub(r'^\s*(?:chapter|chap\.?)\s*\d+\s*[:.\-–—]\s*', '', s, flags=re.I)
    # Remove "1.", "1)", "IV.", etc. - Roman numerals MUST be followed by punctuation
    # This prevents matching bare letters like "C" in "Copyright" or "I" in "Index"
    s = re.sub(r'^\s*\d+\s*[.)]', '', s, flags=re.I)  # Arabic numerals with punctuation
    s = re.sub(r'^\s*[IVXLC]{2,}\s*[.)]', '', s, flags=re.I)  # Roman numerals (2+ chars) with punctuation
    # Remove bare leading numbers followed by spaces (e.g., "1 Introduction")
    s = re.sub(r'^\s*\d+\s+', '', s)
    # Clean up any leading punctuation/spaces left over
    s = re.sub(r'^[\s.)\-–—]+', '', s)
    return s


def normalize_ascii(t: str) -> str:
    """Return ASCII-normalized version of string."""
    return unicodedata.normalize("NFKD", t).encode("ascii", "ignore").decode("ascii")
