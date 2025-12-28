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
    patterns = [
        rf'\b(?:{MONTHS})\s+\d{{1,2}}(?:st|nd|rd|th)?\,?\s+\d{{4}}\b',
        rf'\b\d{{1,2}}(?:st|nd|rd|th)?\s+(?:{MONTHS})\s+\d{{4}}\b',
        r'\b\d{4}-\d{2}-\d{2}\b',
        r'\b\d{1,2}/\d{1,2}/\d{4}\b',
    ]
    out: List[str] = []
    for pat in patterns:
        out.extend(re.findall(pat, text, flags=re.IGNORECASE))
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
    patterns = [
        r'\b(?:[1-3]\s*)?[A-Z][a-z]+\.?\s+\d+:\d+(?:-\d+(?::\d+)?)?',  # John 3:16-18
        r'\b(?:[1-3]\s*)?(?:Kings?|Chronicles?|Corinthians?|Thessalonians?|Timothy|Peter|John)\s+\d+:\d+(?:-\d+)?',
        r'\b(?:Gen|Ex|Lev|Num|Deut|Josh|Judg|Ruth|Sam|Kgs|Chr|Ezra|Neh|Esth|Job|Ps|Prov|Eccl|Song|Isa|Jer|Lam|Ezek|Dan|Hos|Joel|Amos|Obad|Jonah|Mic|Nah|Hab|Zeph|Hag|Zech|Mal|Mt|Mk|Lk|Jn|Acts|Rom|Cor|Gal|Eph|Phil|Col|Thess|Tim|Tit|Phlm|Heb|Jas|Pet|Jude|Rev)\.?\s+\d+:\d+(?:-\d+)?'
    ]
    refs: List[str] = []
    for pat in patterns:
        refs.extend(re.findall(pat, text, flags=re.IGNORECASE))
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
    SEE_MAX = 140
    patterns = [
        r'\b(?:cf\.|compare|see(?: also)?)\s+(?:chapter|section|part|§|art\.?|can\.?)\s+[A-Za-z0-9.:§-]{1,60}',
        r'\b(?:CIC|CCEO)\s*(?:/1983|/1990)?\s*(?:can\.?|canon)\s*\d+(?:\s*§\s*\d+)?',
        r'\b(?:canon|can\.)\s*\d+(?:\s*§\s*\d+)?',
        r'\b(?:CCC|Catechism(?: of the Catholic Church)?)\s*\d{1,4}',
        r'\b(?:Roman Catechism|Catechism of (?:Pius V|Trent))\b',
        r'\b(?:DS|Denz\.?)\s*\d{3,5}\b',
        r'\b(?:GIRM|GILH|IGMR|OGMR)\s*\d{1,4}\b',
        r'\b(?:Council of Trent|Trent(?:,?\s*Session)?\s*[IVXLC]+)\b',
        r'\b(?:Vatican\s*(?:I|II))\b',
        r'\b§{1,2}\s*\d{1,4}\b',
    ]
    refs: List[str] = []
    for pat in patterns:
        for m in re.findall(pat, text, flags=re.IGNORECASE):
            m = clean_text(m)
            if 3 < len(m) <= SEE_MAX:
                refs.append(m)
    return sorted(set(refs))
