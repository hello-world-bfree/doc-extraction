#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Base analyzer interface for domain-specific metadata extraction.

All domain-specific analyzers (Catholic, Biblical, Academic, etc.) must inherit
from BaseAnalyzer and implement its abstract methods.
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Any


class BaseAnalyzer(ABC):
    """
    Abstract base class for domain-specific metadata analyzers.

    Analyzers extract domain-specific metadata from text and chunks,
    such as document types, subjects, themes, related documents, and
    geographic focus.

    All format-specific analyzers must implement:
    - infer_document_type(): Classify the document type
    - extract_subjects(): Extract subject areas/topics
    - extract_themes(): Extract key themes from content
    - extract_related_documents(): Find references to other documents
    - infer_geographic_focus(): Determine geographic scope
    - enrich_metadata(): Main orchestration method
    """

    def __init__(self, config: Dict[str, Any] = None):
        """
        Initialize the analyzer.

        Args:
            config: Optional configuration dictionary with patterns and settings
        """
        self.config = config or {}

    @abstractmethod
    def infer_document_type(self, text: str) -> str:
        """
        Infer the document type from text content.

        Uses pattern matching to classify documents into domain-specific types.
        Examples for Catholic domain: Encyclical, Apostolic Letter, Constitution, etc.

        Args:
            text: Complete text of the document

        Returns:
            Document type string (empty if no match)
        """
        pass

    @abstractmethod
    def extract_subjects(self, text: str, chunks: List[Dict]) -> List[str]:
        """
        Extract subject areas from document text.

        Uses pattern matching to identify domain-specific topics.
        Examples for Catholic domain: Liturgy, Sacraments, Prayer, etc.

        Args:
            text: Complete text of the document
            chunks: List of chunk dictionaries (may be used for context)

        Returns:
            List of subject strings
        """
        pass

    @abstractmethod
    def extract_themes(self, chunks: List[Dict]) -> List[str]:
        """
        Extract key themes from document hierarchy.

        Typically extracts meaningful headings from chunk hierarchy.

        Args:
            chunks: List of chunk dictionaries with hierarchy information

        Returns:
            List of theme strings (typically limited to top 10)
        """
        pass

    @abstractmethod
    def extract_related_documents(self, text: str) -> List[str]:
        """
        Find references to related documents.

        Uses pattern matching to identify mentions of other documents
        in the same domain.
        Examples for Catholic domain: CCC, Lumen Gentium, Vatican II docs, etc.

        Args:
            text: Complete text of the document

        Returns:
            Sorted list of unique related document names
        """
        pass

    @abstractmethod
    def infer_geographic_focus(self, text: str) -> str:
        """
        Infer the geographic focus or scope of the document.

        Uses pattern matching to determine geographic coverage.
        Examples for Catholic domain: Vatican, Diocese, Parish, Universal Church, etc.

        Args:
            text: Complete text of the document

        Returns:
            Geographic focus string (empty if no match)
        """
        pass

    def extract_promulgation_date(self, text: str, dates: List[str]) -> str:
        """
        Extract promulgation or publication date from text.

        This is an optional method that can be overridden by domain-specific
        analyzers. Default implementation returns the first date.

        Args:
            text: Complete text of the document
            dates: List of dates found in text

        Returns:
            Promulgation date string (empty if no dates)
        """
        return dates[0] if dates else ""

    @abstractmethod
    def enrich_metadata(
        self,
        base_metadata: Dict[str, Any],
        full_text: str,
        chunks: List[Dict]
    ) -> Dict[str, Any]:
        """
        Enrich base metadata with domain-specific fields.

        This is the main orchestration method that calls all other extraction
        methods and combines results into the metadata dictionary.

        Args:
            base_metadata: Basic metadata (title, author, publisher, etc.)
            full_text: Complete text of the document
            chunks: List of chunk dictionaries

        Returns:
            Enriched metadata dictionary with all domain-specific fields
        """
        pass

    def calculate_stats(self, chunks: List[Dict]) -> Dict[str, str]:
        """
        Calculate document statistics from chunks.

        This is a helper method that can be used by all analyzers.

        Args:
            chunks: List of chunk dictionaries

        Returns:
            Dictionary with word_count and pages estimates
        """
        total_words = sum(ch.get("word_count", 0) for ch in chunks)
        pages = max(1, total_words // 250)
        return {
            "word_count": f"approximately {total_words:,}",
            "pages": f"approximately {pages}"
        }
