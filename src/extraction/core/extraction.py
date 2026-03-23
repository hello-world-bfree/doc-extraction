#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Content extraction utilities for dates, scripture references, and cross-references.

These functions identify and extract structured information from text,
particularly focused on Catholic literature but generally applicable.
"""

import re
from typing import List

from .text import clean_text, MONTHS

_DATE_PATTERNS = [
    re.compile(rf'\b(?:{MONTHS})\s+\d{{1,2}}(?:st|nd|rd|th)?\,?\s+\d{{4}}\b', re.IGNORECASE),
    re.compile(rf'\b\d{{1,2}}(?:st|nd|rd|th)?\s+(?:{MONTHS})\s+\d{{4}}\b', re.IGNORECASE),
    re.compile(r'\b\d{4}-\d{2}-\d{2}\b'),
    re.compile(r'\b\d{1,2}/\d{1,2}/\d{4}\b'),
]

_NON_SCRIPTURE_WORDS = r'(?:Note|Section|Part|Chapter|Table|Figure|Item|Page|Line|Rule|Step|Verse|Article|Art|Class|Grade|Level|Phase|Round|Stage|Type|Version)'

_SCRIPTURE_PATTERNS = [
    re.compile(rf'\b(?:[1-3]\s*)?(?!{_NON_SCRIPTURE_WORDS}\b)[A-Z][a-z]+\.?\s+\d+:\d+(?:-\d+(?::\d+)?)?'),
    re.compile(r'\b(?:[1-3]\s*)?(?:Kings?|Chronicles?|Corinthians?|Thessalonians?|Timothy|Peter|John)\s+\d+:\d+(?:-\d+)?', re.IGNORECASE),
    re.compile(r'\b(?:Gen|Ex|Lev|Num|Deut|Josh|Judg|Ruth|Sam|Kgs|Chr|Ezra|Neh|Esth|Job|Ps|Prov|Eccl|Song|Isa|Jer|Lam|Ezek|Dan|Hos|Joel|Amos|Obad|Jonah|Mic|Nah|Hab|Zeph|Hag|Zech|Mal|Mt|Mk|Lk|Jn|Acts|Rom|Cor|Gal|Eph|Phil|Col|Thess|Tim|Tit|Phlm|Heb|Jas|Pet|Jude|Rev)\.?\s+\d+:\d+(?:-\d+)?', re.IGNORECASE),
]

_CROSS_REF_PATTERNS = [
    re.compile(r'\b(?:cf\.|compare|see(?: also)?)\s+(?:chapter|section|part|§|art\.?|can\.?)\s+[A-Za-z0-9.:§-]{1,60}', re.IGNORECASE),
    re.compile(r'\b(?:CIC|CCEO)\s*(?:/1983|/1990)?\s*(?:can\.?|canon)\s*\d+(?:\s*§\s*\d+)?', re.IGNORECASE),
    re.compile(r'\b(?:canon|can\.)\s*\d+(?:\s*§\s*\d+)?', re.IGNORECASE),
    re.compile(r'\b(?:CCC|Catechism(?: of the Catholic Church)?)\s*\d{1,4}', re.IGNORECASE),
    re.compile(r'\b(?:Roman Catechism|Catechism of (?:Pius V|Trent))\b', re.IGNORECASE),
    re.compile(r'\b(?:DS|Denz\.?)\s*\d{3,5}\b', re.IGNORECASE),
    re.compile(r'\b(?:GIRM|GILH|IGMR|OGMR)\s*\d{1,4}\b', re.IGNORECASE),
    re.compile(r'\b(?:Council of Trent|Trent(?:,?\s*Session)?\s*[IVXLC]+)\b', re.IGNORECASE),
    re.compile(r'\b(?:Vatican\s*(?:I|II))\b', re.IGNORECASE),
    re.compile(r'\b§{1,2}\s*\d{1,4}\b'),
    re.compile(r'\bAAS\s+\d{1,3}\s*\(\d{4}\)\s*\d+', re.IGNORECASE),
]

_SEE_MAX = 140


def extract_dates(text: str) -> List[str]:
    """Extract various date formats from text.

    Recognizes:
    - "January 15, 2023"
    - "15th January 2023"
    - "2023-01-15"
    - "1/15/2023"

    Returns:
        Sorted list of unique date strings found in text.
    """
    out: List[str] = []
    for pat in _DATE_PATTERNS:
        out.extend(pat.findall(text))
    return sorted(set(clean_text(x) for x in out))


def extract_scripture_references(text: str) -> List[str]:
    """Extract scripture references (e.g., 'John 3:16-17').

    Recognizes various Bible verse formats:
    - "John 3:16-18"
    - "1 Corinthians 13:1-13"
    - "Mt 5:3-12"
    - "Gen 1:1"

    Returns:
        Sorted list of unique scripture references found in text.
    """
    refs: List[str] = []
    for pat in _SCRIPTURE_PATTERNS:
        refs.extend(pat.findall(text))
    return sorted(set(clean_text(r) for r in refs))


def extract_cross_references(text: str) -> List[str]:
    """Extract Catholic-focused cross references from text.

    Recognizes:
    - CCC (Catechism) references: "CCC 2309"
    - Canon law: "CIC can. 1234", "canon 456"
    - Denzinger: "DS 1234"
    - Liturgical documents: "GIRM 123"
    - Councils: "Vatican II", "Council of Trent"
    - Section markers: "§ 123"
    - See also/cf. references

    Returns:
        Sorted list of unique cross-references found in text.
    """
    refs: List[str] = []
    for pat in _CROSS_REF_PATTERNS:
        for m in pat.findall(text):
            m = clean_text(m)
            if 3 < len(m) <= _SEE_MAX:
                refs.append(m)
    return sorted(set(refs))
