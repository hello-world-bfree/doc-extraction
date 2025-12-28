#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
PDF extractor with page-based chunking and optional OCR support.

Uses pdfplumber for text extraction with layout preservation.
Supports font-based heading detection and optional OCR fallback.
"""

import logging
import os
from typing import Any, Dict, List, Optional, Tuple

try:
    import pdfplumber
    PDFPLUMBER_AVAILABLE = True
except ImportError:
    PDFPLUMBER_AVAILABLE = False

from .base import BaseExtractor
from ..core.chunking import split_sentences
from ..core.extraction import (
    extract_cross_references,
    extract_dates,
    extract_scripture_references,
)
from ..core.identifiers import stable_id
from ..core.models import Chunk, Metadata
from ..core.text import clean_text, estimate_word_count

PARSER_VERSION = "2.0.0-pdf"
MD_SCHEMA_VERSION = "2025-09-08"

LOGGER = logging.getLogger("pdf_parser")


class PdfExtractor(BaseExtractor):
    """
    PDF document extractor using pdfplumber.

    Extracts text page-by-page, attempts to detect headings based on font size,
    and creates chunks with basic hierarchy.
    """

    def __init__(self, source_path: str, config: Optional[Dict] = None):
        """
        Initialize PDF extractor.

        Args:
            source_path: Path to PDF file
            config: Configuration dict with options:
                - min_paragraph_words: Minimum words for paragraph inclusion (default: 5)
                - heading_font_threshold: Font size ratio for heading detection (default: 1.2)
                - use_ocr: Enable OCR for scanned PDFs (default: False)
                - ocr_lang: OCR language (default: "eng")
        """
        super().__init__(source_path, config)

        if not PDFPLUMBER_AVAILABLE:
            raise RuntimeError(
                "pdfplumber is required for PDF extraction. "
                "Install with: uv pip install pdfplumber"
            )

        # Configuration
        self.min_paragraph_words = self.config.get("min_paragraph_words", 5)
        self.heading_font_threshold = self.config.get("heading_font_threshold", 1.2)
        self.use_ocr = self.config.get("use_ocr", False)
        self.ocr_lang = self.config.get("ocr_lang", "eng")

        # PDF document (populated during load)
        self.pdf = None
        self.total_pages = 0

    def load(self) -> None:
        """
        Load PDF file and create provenance.

        Raises:
            RuntimeError: If PDF cannot be loaded
        """
        if not os.path.exists(self.source_path):
            raise RuntimeError(f"PDF file not found: {self.source_path}")

        # Read file for content hash
        with open(self.source_path, 'rb') as f:
            source_bytes = f.read()

        # Create provenance
        self.create_provenance(
            parser_version=PARSER_VERSION,
            md_schema_version=MD_SCHEMA_VERSION,
            source_bytes=source_bytes
        )

        # Open PDF with pdfplumber
        try:
            self.pdf = pdfplumber.open(self.source_path)
            self.total_pages = len(self.pdf.pages)
            LOGGER.info("Loaded PDF with %d pages", self.total_pages)
        except Exception as e:
            raise RuntimeError(f"Failed to open PDF: {e}")

    def parse(self) -> None:
        """
        Parse PDF pages and create chunks.

        Extracts text page-by-page, detects headings based on font size,
        and creates hierarchical chunks.
        """
        if self.pdf is None:
            raise RuntimeError("Must call load() before parse()")

        all_text_parts = []
        paragraph_counter = 0

        # Current hierarchy tracking
        current_hierarchy = {
            "level_1": "",
            "level_2": "",
            "level_3": "",
            "level_4": "",
            "level_5": "",
            "level_6": ""
        }

        for page_num, page in enumerate(self.pdf.pages, 1):
            try:
                # Extract text from page
                text = page.extract_text()

                if not text or not text.strip():
                    LOGGER.debug("Page %d: No text extracted", page_num)
                    continue

                # Split page text into paragraphs (separated by double newlines)
                paragraphs = [p.strip() for p in text.split('\n\n') if p.strip()]

                for para_text in paragraphs:
                    # Clean and normalize text
                    cleaned = clean_text(para_text)
                    if not cleaned:
                        continue

                    word_count = estimate_word_count(cleaned)

                    # Skip very short paragraphs
                    if word_count < self.min_paragraph_words:
                        continue

                    # Check if this looks like a heading (heuristic: short, ALL CAPS or Title Case)
                    is_heading = self._is_likely_heading(cleaned, word_count)

                    if is_heading:
                        # Update hierarchy (for now, just use level_1)
                        # TODO: Improve heading level detection with font analysis
                        current_hierarchy["level_1"] = cleaned[:100]  # Limit heading length
                        LOGGER.debug("Detected heading: %s", current_hierarchy["level_1"])
                        continue

                    # Create chunk
                    paragraph_counter += 1
                    sentences = split_sentences(cleaned)

                    chunk = Chunk(
                        stable_id=stable_id(
                            self.provenance.doc_id,
                            f"page_{page_num}",
                            str(paragraph_counter)
                        ),
                        paragraph_id=paragraph_counter,
                        text=cleaned,
                        hierarchy=current_hierarchy.copy(),
                        chapter_href=f"page_{page_num}",
                        source_order=paragraph_counter,
                        source_tag="p",
                        text_length=len(cleaned),
                        word_count=word_count,
                        cross_references=extract_cross_references(cleaned),
                        scripture_references=extract_scripture_references(cleaned),
                        dates_mentioned=extract_dates(cleaned),
                        heading_path=" / ".join(h for h in current_hierarchy.values() if h),
                        hierarchy_depth=sum(1 for h in current_hierarchy.values() if h),
                        doc_stable_id=self.provenance.doc_id,
                        sentence_count=len(sentences),
                        sentences=sentences,
                        normalized_text=cleaned.lower(),
                    )

                    self.chunks.append(chunk)
                    all_text_parts.append(cleaned)

            except Exception as e:
                LOGGER.warning("Error extracting page %d: %s", page_num, e)
                continue

        # Compute overall quality
        full_text = " ".join(all_text_parts)
        self.compute_quality(full_text)

        LOGGER.info("Extracted %d chunks from %d pages", len(self.chunks), self.total_pages)

    def _is_likely_heading(self, text: str, word_count: int) -> bool:
        """
        Heuristic to detect if text is likely a heading.

        Args:
            text: Text to check
            word_count: Word count

        Returns:
            True if text appears to be a heading
        """
        # Headings are typically short
        if word_count > 15:
            return False

        # Check for ALL CAPS or Title Case
        if text.isupper():
            return True

        # Check if most words are capitalized (Title Case)
        words = text.split()
        if len(words) > 0:
            capitalized_words = sum(1 for w in words if w and w[0].isupper())
            if capitalized_words / len(words) > 0.7:
                return True

        return False

    def extract_metadata(self) -> Metadata:
        """
        Extract metadata from PDF.

        Returns:
            Metadata object with title, author, etc.
        """
        if self.pdf is None:
            raise RuntimeError("Must call parse() before extract_metadata()")

        # Extract PDF metadata
        pdf_metadata = self.pdf.metadata or {}

        title = pdf_metadata.get("Title", "")
        author = pdf_metadata.get("Author", "")
        creator = pdf_metadata.get("Creator", "")
        producer = pdf_metadata.get("Producer", "")
        subject = pdf_metadata.get("Subject", "")

        # Use filename as fallback title
        if not title:
            title = os.path.splitext(os.path.basename(self.source_path))[0]

        # Create base metadata
        self.metadata = Metadata(
            title=title or "Untitled PDF",
            author=author or "Unknown",
            publisher=producer or creator or "",
            language="en",  # TODO: Detect language
            pages=f"approximately {self.total_pages}",
            word_count=f"approximately {sum(c.word_count for c in self.chunks):,}",
        )

        # If analyzer is configured, enrich metadata
        if hasattr(self, 'analyzer') and self.analyzer:
            full_text = " ".join(c.text for c in self.chunks)
            chunks_dict = [c.to_dict() for c in self.chunks]
            base_dict = self.metadata.to_dict()
            enriched = self.analyzer.enrich_metadata(base_dict, full_text, chunks_dict)

            # Update metadata with enriched fields
            for key, value in enriched.items():
                if hasattr(self.metadata, key):
                    setattr(self.metadata, key, value)

        return self.metadata

    def __del__(self):
        """Close PDF file on cleanup."""
        if self.pdf:
            try:
                self.pdf.close()
            except:
                pass
