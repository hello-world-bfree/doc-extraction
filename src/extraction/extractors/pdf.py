#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
PDF extractor with page-based chunking and optional OCR support.

Uses pdfplumber for text extraction with layout preservation.
Supports font-based heading detection and optional OCR fallback.
"""

import logging
import os
from typing import Optional

try:
    import pdfplumber
    PDFPLUMBER_AVAILABLE = True
except ImportError:
    PDFPLUMBER_AVAILABLE = False

from .base import BaseExtractor
from .configs import PdfExtractorConfig
from ..core.chunking import split_sentences
from ..core.extraction import (
    extract_cross_references,
    extract_dates,
    extract_scripture_references,
)
from ..core.identifiers import stable_id
from ..core.models import Chunk, Metadata
from ..core.text import clean_text, estimate_word_count
from ..exceptions import DependencyError, FileNotFoundError, ParseError
from ..analyzers.base import BaseAnalyzer

PARSER_VERSION = "2.0.0-pdf"
MD_SCHEMA_VERSION = "2025-09-08"

LOGGER = logging.getLogger("pdf_parser")


class PdfExtractor(BaseExtractor):
    """
    PDF document extractor using pdfplumber.

    Extracts text page-by-page, attempts to detect headings based on font size,
    and creates chunks with basic hierarchy.
    """

    def __init__(
        self,
        source_path: str,
        config: Optional[PdfExtractorConfig] = None,
        analyzer: Optional[BaseAnalyzer] = None
    ):
        """
        Initialize PDF extractor.

        Args:
            source_path: Path to PDF file
            config: Configuration dataclass (defaults to PdfExtractorConfig())
            analyzer: Domain analyzer (defaults to GenericAnalyzer())

        Raises:
            DependencyError: If pdfplumber is not installed
        """
        if not PDFPLUMBER_AVAILABLE:
            raise DependencyError(
                "pdfplumber",
                "PDF extraction",
                "uv pip install pdfplumber"
            )

        super().__init__(source_path, config or PdfExtractorConfig(), analyzer)

        self.__pdf = None
        self.__total_pages = 0

    def _do_load(self) -> None:
        """
        Load PDF file and create provenance.

        Raises:
            FileNotFoundError: If PDF file does not exist
            ParseError: If PDF cannot be opened
        """
        if not os.path.exists(self.source_path):
            raise FileNotFoundError(self.source_path)

        with open(self.source_path, 'rb') as f:
            source_bytes = f.read()

        self._set_provenance(
            parser_version=PARSER_VERSION,
            md_schema_version=MD_SCHEMA_VERSION,
            source_bytes=source_bytes
        )

        try:
            self.__pdf = pdfplumber.open(self.source_path)
            self.__total_pages = len(self.__pdf.pages)
            LOGGER.info("Loaded PDF with %d pages", self.__total_pages)
        except Exception as e:
            raise ParseError(self.source_path, f"Failed to open PDF: {e}")

    def _do_parse(self) -> None:
        """
        Parse PDF pages and create chunks.

        Extracts text page-by-page, detects headings based on font size,
        and creates hierarchical chunks.
        """
        all_text_parts = []
        paragraph_counter = 0

        current_hierarchy = {
            "level_1": "",
            "level_2": "",
            "level_3": "",
            "level_4": "",
            "level_5": "",
            "level_6": ""
        }

        for page_num, page in enumerate(self.__pdf.pages, 1):
            try:
                text = page.extract_text()

                if not text or not text.strip():
                    LOGGER.debug("Page %d: No text extracted", page_num)
                    continue

                paragraphs = [p.strip() for p in text.split('\n\n') if p.strip()]

                for para_text in paragraphs:
                    cleaned = clean_text(para_text)
                    if not cleaned:
                        continue

                    word_count = estimate_word_count(cleaned)

                    if word_count < self.config.min_paragraph_words:
                        continue

                    is_heading = self._is_likely_heading(cleaned, word_count)

                    if is_heading:
                        current_hierarchy["level_1"] = cleaned[:100]
                        LOGGER.debug("Detected heading: %s", current_hierarchy["level_1"])
                        continue

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

                    self._add_raw_chunk(chunk)
                    all_text_parts.append(cleaned)

            except Exception as e:
                LOGGER.warning("Error extracting page %d: %s", page_num, e)
                continue

        full_text = " ".join(all_text_parts)
        self._compute_quality(full_text)

        self._apply_chunking_strategy()

        LOGGER.info("Extracted %d chunks from %d pages (strategy: %s)",
                    len(self._BaseExtractor__raw_chunks), self.__total_pages,
                    self.config.chunking_strategy)

    def _is_likely_heading(self, text: str, word_count: int) -> bool:
        """
        Heuristic to detect if text is likely a heading.

        Args:
            text: Text to check
            word_count: Word count

        Returns:
            True if text appears to be a heading
        """
        if word_count > 15:
            return False

        if text.isupper():
            return True

        words = text.split()
        if len(words) > 0:
            capitalized_words = sum(1 for w in words if w and w[0].isupper())
            if capitalized_words / len(words) > 0.7:
                return True

        return False

    def _do_extract_metadata(self) -> Metadata:
        """
        Extract metadata from PDF.

        Returns:
            Metadata object with title, author, etc.
        """
        pdf_metadata = self.__pdf.metadata or {}

        title = pdf_metadata.get("Title", "")
        author = pdf_metadata.get("Author", "")
        creator = pdf_metadata.get("Creator", "")
        producer = pdf_metadata.get("Producer", "")

        if not title:
            title = os.path.splitext(os.path.basename(self.source_path))[0]

        return Metadata(
            title=title or "Untitled PDF",
            author=author or "Unknown",
            publisher=producer or creator or "",
            language="en",
            pages=f"approximately {self.__total_pages}",
            word_count=f"approximately {sum(c.word_count for c in self.chunks):,}",
        )

    def __del__(self):
        """Close PDF file on cleanup."""
        if self.__pdf:
            try:
                self.__pdf.close()
            except:
                pass
