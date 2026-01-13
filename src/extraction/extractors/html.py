#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
HTML extractor with hierarchical chunking from HTML structure.

Processes standalone HTML files, extracting text and preserving
heading hierarchy from h1-h6 tags.
"""

import logging
import os
from typing import Optional

from bs4 import BeautifulSoup

from .base import BaseExtractor
from .configs import HtmlExtractorConfig
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
from ..core.identifiers import stable_id
from ..core.models import Chunk, Metadata
from ..core.text import clean_text, estimate_word_count
from ..exceptions import FileNotFoundError, ParseError
from ..analyzers.base import BaseAnalyzer

PARSER_VERSION = "2.0.0-html"
MD_SCHEMA_VERSION = "2025-09-08"

LOGGER = logging.getLogger("html_parser")


class HtmlExtractor(BaseExtractor):
    """
    HTML document extractor using BeautifulSoup.

    Extracts text from HTML, preserving heading hierarchy (h1-h6),
    and creates structured chunks.
    """

    def __init__(
        self,
        source_path: str,
        config: Optional[HtmlExtractorConfig] = None,
        analyzer: Optional[BaseAnalyzer] = None
    ):
        """
        Initialize HTML extractor.

        Args:
            source_path: Path to HTML file
            config: Configuration dataclass (defaults to HtmlExtractorConfig())
            analyzer: Domain analyzer (defaults to GenericAnalyzer())
        """
        super().__init__(source_path, config or HtmlExtractorConfig(), analyzer)

        self.__soup = None
        self.__html_title = ""

    def _do_load(self) -> None:
        """
        Load HTML file and parse with BeautifulSoup.

        Raises:
            FileNotFoundError: If HTML file does not exist
            ParseError: If HTML cannot be parsed
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
            self.__soup = BeautifulSoup(source_bytes, 'html.parser')

            title_tag = self.__soup.find('title')
            self.__html_title = title_tag.get_text(strip=True) if title_tag else ""

            LOGGER.info("Loaded HTML: %s", self.__html_title or "Untitled")
        except Exception as e:
            raise ParseError(self.source_path, f"Failed to parse HTML: {e}")

    def _do_parse(self) -> None:
        """
        Parse HTML and create chunks from paragraphs and text blocks.

        Preserves heading hierarchy from h1-h6 tags.
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

        main_content = (
            self.__soup.find('main') or
            self.__soup.find('article') or
            self.__soup.find('body') or
            self.__soup
        )

        for elem in main_content.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'p', 'div', 'li', 'blockquote']):
            tag_name = elem.name

            if is_heading_tag(tag_name):
                level = heading_level(tag_name)
                heading_text = clean_text(elem.get_text())

                if heading_text:
                    if 1 <= level <= 6:
                        current_hierarchy[f"level_{level}"] = heading_text[:100]
                        for deeper in range(level + 1, 7):
                            current_hierarchy[f"level_{deeper}"] = ""

                        LOGGER.debug("Heading level %d: %s", level, heading_text)
                continue

            text = elem.get_text(separator=' ', strip=True)
            if not text:
                continue

            cleaned = clean_text(text)
            if not cleaned:
                continue

            word_count = estimate_word_count(cleaned)

            if word_count < self.config.min_paragraph_words:
                continue

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
            )

            self._add_raw_chunk(chunk)
            all_text_parts.append(cleaned)

        full_text = " ".join(all_text_parts)
        self._compute_quality(full_text)

        self._apply_chunking_strategy()

        LOGGER.info("Extracted %d chunks from HTML (strategy: %s)",
                    len(self._BaseExtractor__raw_chunks),
                    self.config.chunking_strategy)

    def _do_extract_metadata(self) -> Metadata:
        """
        Extract metadata from HTML meta tags and content.

        Returns:
            Metadata object
        """
        meta_author = self.__soup.find('meta', attrs={'name': 'author'})
        meta_description = self.__soup.find('meta', attrs={'name': 'description'})

        author = meta_author.get('content', '') if meta_author else ""
        description = meta_description.get('content', '') if meta_description else ""

        title = self.__html_title
        if not title:
            title = os.path.splitext(os.path.basename(self.source_path))[0]

        return Metadata(
            title=title or "Untitled HTML",
            author=author or "Unknown",
            language="en",
            word_count=f"approximately {sum(c.word_count for c in self.chunks):,}",
        )
