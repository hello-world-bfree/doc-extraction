#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Catholic-specific metadata analyzer.

Extracts domain-specific metadata for Catholic literature including:
- Document types (Encyclical, Apostolic Letter, Constitution, etc.)
- Subject areas (Liturgy, Sacraments, Prayer, etc.)
- Related documents (CCC, Vatican II docs, etc.)
- Geographic focus (Vatican, Diocese, Parish, etc.)
- Promulgation dates
"""

import re
from collections import Counter, OrderedDict
from typing import Dict, List, Any

from .base import BaseAnalyzer
from ..core.extraction import extract_dates
from ..core.text import MONTHS


class CatholicAnalyzer(BaseAnalyzer):
    """
    Analyzer for Catholic literature and magisterial documents.

    Recognizes Catholic-specific document types, subjects, and references.
    All patterns can be configured via config dictionary.
    """

    # Default patterns (can be overridden via config)
    DEFAULT_DOC_TYPES = {
        "Dogmatic Constitution": [
            r"\bdogmatic constitution\b",
            r"constitutio dogmatica",
        ],
        "Pastoral Constitution": [
            r"\bpastoral constitution\b",
            r"constitutio pastoralis",
        ],
        "Apostolic Constitution": [
            r"apostolic constitution",
            r"constitutio apostolica",
        ],
        "Encyclical": [r"\bencyclical\b", r"litterae encyclicae"],
        "Apostolic Exhortation": [r"apostolic exhortation", r"adhortatio"],
        "Apostolic Letter": [r"apostolic letter", r"\bepistula\b"],
        "Motu Proprio": [r"\bmotu proprio\b"],
        "Decree": [r"\bdecree\b", r"\bdecretum\b"],
        "Instruction": [r"\binstruction\b", r"\binstructio\b"],
        "Declaration": [r"\bdeclaration\b", r"\bdeclaratio\b"],
        "Constitution": [r"\bconstitution\b", r"\bconstitutio\b"],
    }

    DEFAULT_SUBJECTS = {
        "Liturgy": [
            r"\blitur(?:gy|gica|gical)\b",
            r"liturgy of the hours",
            r"officium divinum",
        ],
        "Mass": [r"\bmass\b", r"eucharist", r"holy sacrifice"],
        "Divine Office": [r"divine office", r"breviary", r"breviarium"],
        "Sacraments": [
            r"\bsacrament",
            r"\bbaptism\b",
            r"\bconfirmation\b",
            r"\borders\b",
            r"\bmarriage\b",
            r"\breconciliation\b",
            r"\banointing\b",
        ],
        "Magisterium": [r"\bmagisterium\b", r"\bapostolic see\b", r"\bholy see\b"],
        "Ecclesiology": [
            r"\bchurch\b",
            r"\becclesia\b",
            r"\bepiscopal\b",
            r"\bbishop\b",
            r"\bdiocese\b",
            r"\bparish\b",
        ],
        "Mariology": [
            r"\bmary\b",
            r"\bimmaculate conception\b",
            r"\bassumption\b",
            r"\btheotokos\b",
        ],
        "Moral Theology": [
            r"\bmoral\b",
            r"\bethics\b",
            r"\bconscience\b",
            r"\bvirtue\b",
        ],
        "Scripture": [r"\bscripture\b", r"\bverbum\b", r"\bdivine revelation\b"],
        "Canon Law": [r"canon law", r"code of canon law", r"\bcic\b", r"\bcceo\b"],
        "Prayer": [r"\bprayer\b", r"\boratio\b", r"\bdevotion\b", r"\bro\sary\b"],
        "Council Documents": [
            r"vatican\s*(?:i|ii)",
            r"council of trent",
            r"lumen gentium",
            r"dei verbum",
        ],
    }

    DEFAULT_RELATED_DOCS = [
        "Sacrosanctum Concilium",
        "Lumen Gentium",
        "Dei Verbum",
        "Gaudium et Spes",
        "Dei Filius",
        "Pastor Aeternus",
        "Syllabus of Errors",
        "Council of Trent",
        "Trent",
        "Quo Primum",
        "Humanae Vitae",
        "Laudato Si'",
        "Fidei Depositum",
        "Evangelii Nuntiandi",
        "Missale Romanum",
        "Liturgiam Authenticam",
        "Mysterii Paschalis",
        "Mediator Dei",
        "Catechism of the Catholic Church",
        "Roman Catechism",
        "General Instruction of the Roman Missal",
    ]

    DEFAULT_GEO_PATTERNS = {
        "Vatican City (Rome)": [
            r"vatican",
            r"\brome\b",
            r"apostolic see",
            r"holy see",
        ],
        "Universal Church": [
            r"universal church",
            r"catholic church",
            r"whole church",
        ],
        "Diocese": [r"\bdiocese\b", r"\bepiscopal\b", r"\bbishop\b"],
        "Parish": [r"\bparish\b", r"\bpastor\b", r"\bfaithful\b"],
    }

    def __init__(self, config: Dict[str, Any] = None):
        """
        Initialize Catholic analyzer with optional config.

        Args:
            config: Optional configuration with custom patterns:
                - document_types: Dict of type name -> patterns
                - subjects: Dict of subject name -> patterns
                - related_documents: List of document names
                - geographic_patterns: Dict of location -> patterns
        """
        super().__init__(config)

        # Load patterns from config or use defaults
        self.doc_type_patterns = self.config.get("document_types", self.DEFAULT_DOC_TYPES)
        self.subject_patterns = self.config.get("subjects", self.DEFAULT_SUBJECTS)
        self.related_doc_patterns = self.config.get("related_documents", self.DEFAULT_RELATED_DOCS)
        self.geo_patterns = self.config.get("geographic_patterns", self.DEFAULT_GEO_PATTERNS)

    def infer_document_type(self, text: str) -> str:
        """
        Infer Catholic document type from text patterns.

        Matches against: Encyclical, Apostolic Letter, Constitution, etc.

        Args:
            text: Complete text of the document

        Returns:
            Document type string (empty if no match)
        """
        tl = text.lower()
        for name, pats in self.doc_type_patterns.items():
            if any(re.search(p, tl) for p in pats):
                return name
        return ""

    def extract_subjects(self, text: str, chunks: List[Dict]) -> List[str]:
        """
        Extract Catholic subject areas from text.

        Matches against: Liturgy, Sacraments, Prayer, Canon Law, etc.

        Args:
            text: Complete text of the document
            chunks: List of chunk dictionaries (unused for Catholic analyzer)

        Returns:
            List of subject strings
        """
        tl = text.lower()
        subjects = [
            name
            for name, pats in self.subject_patterns.items()
            if any(re.search(p, tl) for p in pats)
        ]
        return subjects

    def extract_themes(self, chunks: List[Dict]) -> List[str]:
        """
        Extract key themes from document hierarchy.

        Extracts meaningful headings (>10 chars) from levels 1-4 of hierarchy.

        Args:
            chunks: List of chunk dictionaries with hierarchy information

        Returns:
            List of up to 10 unique theme strings
        """
        themes: List[str] = []
        for ch in chunks:
            h = ch.get("hierarchy", {})
            for level in ["level_1", "level_2", "level_3", "level_4"]:
                head = h.get(level, "")
                if head and len(head) > 10:
                    themes.append(head)
        # Deduplicate while preserving order, limit to 10
        return list(OrderedDict.fromkeys(themes))[:10]

    def extract_related_documents(self, text: str) -> List[str]:
        """
        Find references to Catholic documents.

        Matches against: CCC, Vatican II docs, Papal documents, etc.

        Args:
            text: Complete text of the document

        Returns:
            Sorted list of unique related document names
        """
        related = [
            doc for doc in self.related_doc_patterns
            if re.search(re.escape(doc), text, re.IGNORECASE)
        ]
        return sorted(set(related))

    def infer_geographic_focus(self, text: str) -> str:
        """
        Infer geographic focus of Catholic document.

        Matches against: Vatican, Universal Church, Diocese, Parish.

        Args:
            text: Complete text of the document

        Returns:
            Geographic focus string (empty if no match)
        """
        tl = text.lower()
        for loc, pats in self.geo_patterns.items():
            if any(re.search(p, tl) for p in pats):
                return loc
        return ""

    def extract_promulgation_date(self, text: str, dates: List[str]) -> str:
        """
        Extract promulgation date for Catholic documents.

        Looks for dates near keywords: promulgated, given, issued, published.
        Falls back to first date if no context found.

        Args:
            text: Complete text of the document
            dates: List of dates found in text

        Returns:
            Promulgation date string (empty if no dates)
        """
        if not dates:
            return ""

        # Try to find date near promulgation keywords
        ctx = re.search(
            rf"(?:promulgated?|given|issued|published).*?((?:{MONTHS})\s+\d{{1,2}}(?:st|nd|rd|th)?\,?\s+\d{{4}})",
            text,
            re.IGNORECASE,
        )
        return ctx.group(1) if ctx else dates[0]

    def rollup_footnotes(self, chunks: List[Dict]) -> Dict[str, Any]:
        """
        Aggregate footnote citations across all chunks.

        This is a Catholic-specific helper for documents with scholarly apparatus.

        Args:
            chunks: List of chunk dictionaries with footnote_citations

        Returns:
            Dictionary with unique_citations and counts, or None if no footnotes
        """
        all_nums: List[int] = []
        for ch in chunks:
            f = ch.get("footnote_citations", {})
            all_nums.extend(f.get("all", []))

        if not all_nums:
            return None

        counts = Counter(all_nums)
        return {
            "unique_citations": sorted(int(n) for n in set(all_nums)),
            "counts": {str(k): int(v) for k, v in sorted(counts.items())},
        }

    def enrich_metadata(
        self,
        base_metadata: Dict[str, Any],
        full_text: str,
        chunks: List[Dict]
    ) -> Dict[str, Any]:
        """
        Enrich metadata with Catholic-specific fields.

        Adds: document_type, date_promulgated, subject, key_themes,
        related_documents, geographic_focus, word_count, pages,
        and footnote_citation_stats (if applicable).

        Args:
            base_metadata: Basic metadata (title, author, publisher, etc.)
            full_text: Complete text of the document
            chunks: List of chunk dictionaries

        Returns:
            Enriched metadata dictionary
        """
        # Extract Catholic-specific fields
        base_metadata["document_type"] = self.infer_document_type(full_text)
        base_metadata["subject"] = self.extract_subjects(full_text, chunks)
        base_metadata["key_themes"] = self.extract_themes(chunks)
        base_metadata["related_documents"] = self.extract_related_documents(full_text)
        base_metadata["geographic_focus"] = self.infer_geographic_focus(full_text)

        # Extract dates
        dates = extract_dates(full_text)
        base_metadata["date_promulgated"] = self.extract_promulgation_date(full_text, dates)

        # Calculate stats
        stats = self.calculate_stats(chunks)
        base_metadata["word_count"] = stats["word_count"]
        base_metadata["pages"] = stats["pages"]

        # Rollup footnotes (if present)
        footnotes = self.rollup_footnotes(chunks)
        if footnotes:
            base_metadata["footnote_citation_stats"] = footnotes

        return base_metadata
