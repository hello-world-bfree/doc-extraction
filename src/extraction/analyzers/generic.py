#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Generic domain-agnostic metadata analyzer.

Provides minimal domain logic by extracting subjects and themes from
document hierarchy and structure rather than domain-specific patterns.
"""

from typing import Dict, List, Any
from collections import Counter

from .base import BaseAnalyzer


class GenericAnalyzer(BaseAnalyzer):
    """
    Generic analyzer for domain-agnostic documents.

    This is the default analyzer when no specific domain is known.
    It extracts metadata from document structure (hierarchy, headings)
    rather than using domain-specific pattern matching.

    Key differences from domain-specific analyzers:
    - Document type inferred from file extension or metadata
    - Subjects extracted from top-level headings
    - Themes extracted from heading hierarchy
    - Related documents: empty (no domain patterns)
    - Geographic focus: empty (no domain patterns)
    """

    def infer_document_type(self, text: str) -> str:
        """
        Infer document type from structural cues.

        For generic documents, we classify based on simple heuristics:
        - Presence of many code blocks → Technical Document
        - Many numbered sections → Manual or Specification
        - Short with few headings → Article or Essay
        - Default → Document

        Args:
            text: Complete text of the document

        Returns:
            Document type string
        """
        if not text.strip():
            return "Document"

        lines = text.split('\n')
        code_block_count = text.count('```')
        numbered_section_count = sum(
            1 for line in lines
            if line.strip() and line.strip()[0].isdigit() and '.' in line[:5]
        )

        if code_block_count > 5:
            return "Technical Document"
        elif numbered_section_count > 10:
            return "Manual"
        elif len(text) < 5000 and '\n\n' in text:
            return "Article"
        else:
            return "Document"

    def extract_subjects(self, text: str, chunks: List[Dict]) -> List[str]:
        """
        Extract subjects from top-level headings.

        Looks at level_1 and level_2 hierarchy entries across all chunks
        to identify main subject areas.

        Args:
            text: Complete text of the document
            chunks: List of chunk dictionaries

        Returns:
            List of subject strings (up to 5 most common)
        """
        subjects = []

        for chunk in chunks:
            hierarchy = chunk.get("hierarchy", {})

            level_1 = hierarchy.get("level_1", "").strip()
            if level_1 and level_1 not in subjects:
                subjects.append(level_1)

            level_2 = hierarchy.get("level_2", "").strip()
            if level_2 and level_2 not in subjects:
                subjects.append(level_2)

        return subjects[:5]

    def extract_themes(self, chunks: List[Dict]) -> List[str]:
        """
        Extract themes from heading hierarchy.

        Collects all non-empty headings from chunk hierarchy,
        counts occurrences, and returns most common themes.

        Args:
            chunks: List of chunk dictionaries

        Returns:
            List of theme strings (up to 10 most common)
        """
        themes = []

        for chunk in chunks:
            hierarchy = chunk.get("hierarchy", {})

            for level_key in ["level_1", "level_2", "level_3", "level_4"]:
                heading = hierarchy.get(level_key, "").strip()
                if heading:
                    themes.append(heading)

        theme_counts = Counter(themes)
        common_themes = [theme for theme, _ in theme_counts.most_common(10)]

        return common_themes

    def extract_related_documents(self, text: str) -> List[str]:
        """
        Extract related documents (generic: none).

        Generic analyzer has no domain-specific patterns for detecting
        related documents.

        Args:
            text: Complete text of the document

        Returns:
            Empty list
        """
        return []

    def infer_geographic_focus(self, text: str) -> str:
        """
        Infer geographic focus (generic: none).

        Generic analyzer has no domain-specific patterns for detecting
        geographic focus.

        Args:
            text: Complete text of the document

        Returns:
            Empty string
        """
        return ""

    def enrich_metadata(
        self,
        base_metadata: Dict[str, Any],
        full_text: str,
        chunks: List[Dict]
    ) -> Dict[str, Any]:
        """
        Enrich metadata with generic domain-agnostic fields.

        Extracts:
        - document_type: Inferred from structure
        - subject: Top-level headings (up to 5)
        - key_themes: All headings (up to 10 most common)
        - related_documents: Empty (no domain patterns)
        - geographic_focus: Empty (no domain patterns)

        Args:
            base_metadata: Basic metadata dictionary
            full_text: Complete text of the document
            chunks: List of chunk dictionaries

        Returns:
            Enriched metadata dictionary
        """
        enriched = base_metadata.copy()

        enriched["document_type"] = self.infer_document_type(full_text)
        enriched["subject"] = self.extract_subjects(full_text, chunks)
        enriched["key_themes"] = self.extract_themes(chunks)
        enriched["related_documents"] = self.extract_related_documents(full_text)
        enriched["geographic_focus"] = self.infer_geographic_focus(full_text)

        return enriched
