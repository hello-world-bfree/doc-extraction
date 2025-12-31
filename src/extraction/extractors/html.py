#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
HTML extractor with hierarchical chunking from HTML structure.

Processes standalone HTML files, extracting text and preserving
heading hierarchy from h1-h6 tags.
"""

import logging
import os
from typing import Any, Dict, List, Optional

from bs4 import BeautifulSoup

from .base import BaseExtractor
from ..core.chunking import (
    heading_level,
    heading_path,
    hierarchy_depth,
    is_heading_tag,
    split_sentences,
)
from ..core.extraction import (
    extract_cross_references,
    extract_dates,
    extract_scripture_references,
)
from ..core.formatting import FormattedTextBuilder
from ..core.identifiers import stable_id
from ..core.models import Chunk, Metadata
from ..core.text import clean_text, estimate_word_count

PARSER_VERSION = "2.0.0-html"
MD_SCHEMA_VERSION = "2025-09-08"

LOGGER = logging.getLogger("html_parser")


class HtmlExtractor(BaseExtractor):
    """
    HTML document extractor using BeautifulSoup.

    Extracts text from HTML, preserving heading hierarchy (h1-h6),
    and creates structured chunks.
    """

    def __init__(self, source_path: str, config: Optional[Dict] = None):
        """
        Initialize HTML extractor.

        Args:
            source_path: Path to HTML file
            config: Configuration dict with options:
                - min_paragraph_words: Minimum words for paragraph inclusion (default: 1)
                - preserve_links: Keep link text (default: False)
        """
        super().__init__(source_path, config)

        # Configuration
        self.min_paragraph_words = self.config.get("min_paragraph_words", 1)
        self.preserve_links = self.config.get("preserve_links", False)

        # Formatting preservation config (new in v2.1)
        self.preserve_formatting = bool(self.config.get("preserve_formatting", False))
        if self.preserve_formatting:
            self.formatter = FormattedTextBuilder(
                preserve_line_breaks=self.config.get("preserve_line_breaks", True),
                preserve_emphasis=self.config.get("preserve_emphasis", True),
                preserve_lists=self.config.get("preserve_lists", True),
                preserve_blockquotes=self.config.get("preserve_blockquotes", True),
                preserve_tables=self.config.get("preserve_tables", False),
            )
        else:
            self.formatter = None

        # HTML content
        self.soup = None
        self.html_title = ""

    def load(self) -> None:
        """
        Load HTML file and parse with BeautifulSoup.

        Raises:
            RuntimeError: If HTML cannot be loaded
        """
        if not os.path.exists(self.source_path):
            raise RuntimeError(f"HTML file not found: {self.source_path}")

        # Read file
        with open(self.source_path, 'rb') as f:
            source_bytes = f.read()

        # Create provenance
        self.create_provenance(
            parser_version=PARSER_VERSION,
            md_schema_version=MD_SCHEMA_VERSION,
            source_bytes=source_bytes
        )

        # Parse HTML
        try:
            self.soup = BeautifulSoup(source_bytes, 'html.parser')

            # Extract title from <title> tag
            title_tag = self.soup.find('title')
            self.html_title = title_tag.get_text(strip=True) if title_tag else ""

            LOGGER.info("Loaded HTML: %s", self.html_title or "Untitled")
        except Exception as e:
            raise RuntimeError(f"Failed to parse HTML: {e}")

    def parse(self) -> None:
        """
        Parse HTML and create chunks from paragraphs and text blocks.

        Preserves heading hierarchy from h1-h6 tags.
        """
        if self.soup is None:
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

        # Find main content area (try <main>, <article>, or fall back to <body>)
        main_content = (
            self.soup.find('main') or
            self.soup.find('article') or
            self.soup.find('body') or
            self.soup
        )

        # Process all text-containing elements
        for elem in main_content.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'p', 'div', 'li', 'blockquote']):
            tag_name = elem.name

            # Handle headings
            if is_heading_tag(tag_name):
                level = heading_level(tag_name)
                heading_text = clean_text(elem.get_text())

                if heading_text:
                    # Update hierarchy
                    if 1 <= level <= 6:
                        # Set this level
                        current_hierarchy[f"level_{level}"] = heading_text[:100]
                        # Clear deeper levels
                        for deeper in range(level + 1, 7):
                            current_hierarchy[f"level_{deeper}"] = ""

                        LOGGER.debug("Heading level %d: %s", level, heading_text)
                continue

            # Handle text blocks (p, div, li, blockquote)
            # BEFORE flattening, extract formatted representations if configured
            formatted_text = None
            structure_metadata = None
            if self.preserve_formatting and self.formatter:
                try:
                    formatted_text = self.formatter.extract_formatted_text(elem)
                    structure_metadata = self.formatter.extract_structure_metadata(elem)
                except Exception as e:
                    LOGGER.debug("Formatting extraction error for %s: %s", tag_name, e)

            text = elem.get_text(separator=' ', strip=True)
            if not text:
                continue

            # Clean text
            cleaned = clean_text(text)
            if not cleaned:
                continue

            word_count = estimate_word_count(cleaned)

            # Skip very short paragraphs
            if word_count < self.min_paragraph_words:
                continue

            # Create chunk
            paragraph_counter += 1
            sentences = split_sentences(cleaned)

            chunk = Chunk(
                stable_id=stable_id(
                    self.provenance.doc_id,
                    tag_name,
                    str(paragraph_counter)
                ),
                paragraph_id=paragraph_counter,
                text=cleaned,
                hierarchy=current_hierarchy.copy(),
                chapter_href="",
                source_order=paragraph_counter,
                source_tag=tag_name,
                text_length=len(cleaned),
                word_count=word_count,
                cross_references=extract_cross_references(cleaned),
                scripture_references=extract_scripture_references(cleaned),
                dates_mentioned=extract_dates(cleaned),
                heading_path=heading_path(current_hierarchy),
                hierarchy_depth=hierarchy_depth(current_hierarchy),
                doc_stable_id=self.provenance.doc_id,
                sentence_count=len(sentences),
                sentences=sentences,
                normalized_text=cleaned.lower(),
                formatted_text=formatted_text,
                structure_metadata=structure_metadata,
            )

            self.chunks.append(chunk)
            all_text_parts.append(cleaned)

        # Compute overall quality
        full_text = " ".join(all_text_parts)
        self.compute_quality(full_text)

        LOGGER.info("Extracted %d chunks from HTML", len(self.chunks))

    def extract_metadata(self) -> Metadata:
        """
        Extract metadata from HTML meta tags and content.

        Returns:
            Metadata object
        """
        if self.soup is None:
            raise RuntimeError("Must call parse() before extract_metadata()")

        # Extract from meta tags
        meta_author = self.soup.find('meta', attrs={'name': 'author'})
        meta_description = self.soup.find('meta', attrs={'name': 'description'})
        meta_keywords = self.soup.find('meta', attrs={'name': 'keywords'})

        author = meta_author.get('content', '') if meta_author else ""
        description = meta_description.get('content', '') if meta_description else ""

        # Use filename as fallback title
        title = self.html_title
        if not title:
            title = os.path.splitext(os.path.basename(self.source_path))[0]

        # Create base metadata
        self.metadata = Metadata(
            title=title or "Untitled HTML",
            author=author or "Unknown",
            language="en",  # TODO: Detect from <html lang="...">
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
