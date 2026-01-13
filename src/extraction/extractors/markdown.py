#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Markdown extractor with heading-based chunking.

Parses Markdown files, extracting text and preserving heading hierarchy
from # ## ### style headings.
"""

import logging
import os
import re
from typing import Dict, Optional, Tuple

from .base import BaseExtractor
from .configs import MarkdownExtractorConfig
from ..core.chunking import split_sentences
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

PARSER_VERSION = "2.0.0-markdown"
MD_SCHEMA_VERSION = "2025-09-08"

LOGGER = logging.getLogger("markdown_parser")


class MarkdownExtractor(BaseExtractor):
    """
    Markdown document extractor.

    Parses Markdown syntax, extracting text and creating hierarchical
    chunks based on heading structure (# ## ###).
    """

    def __init__(
        self,
        source_path: str,
        config: Optional[MarkdownExtractorConfig] = None,
        analyzer: Optional[BaseAnalyzer] = None
    ):
        """
        Initialize Markdown extractor.

        Args:
            source_path: Path to Markdown file
            config: Configuration dataclass (defaults to MarkdownExtractorConfig())
            analyzer: Domain analyzer (defaults to GenericAnalyzer())
        """
        super().__init__(source_path, config or MarkdownExtractorConfig(), analyzer)

        self.__raw_content = ""
        self.__frontmatter = {}
        self.__md_title = ""

    def _do_load(self) -> None:
        """
        Load Markdown file.

        Raises:
            FileNotFoundError: If Markdown file does not exist
            ParseError: If file cannot be read
        """
        if not os.path.exists(self.source_path):
            raise FileNotFoundError(self.source_path)

        try:
            with open(self.source_path, 'r', encoding='utf-8') as f:
                self.__raw_content = f.read()

            with open(self.source_path, 'rb') as f:
                source_bytes = f.read()
        except Exception as e:
            raise ParseError(self.source_path, f"Failed to read file: {e}")

        self._set_provenance(
            parser_version=PARSER_VERSION,
            md_schema_version=MD_SCHEMA_VERSION,
            source_bytes=source_bytes
        )

        if self.config.extract_frontmatter:
            self.__raw_content, self.__frontmatter = self._extract_frontmatter(self.__raw_content)

        LOGGER.info("Loaded Markdown file: %s", os.path.basename(self.source_path))

    def _extract_frontmatter(self, content: str) -> Tuple[str, Dict]:
        """
        Extract YAML frontmatter from Markdown.

        Args:
            content: Raw Markdown content

        Returns:
            Tuple of (content without frontmatter, frontmatter dict)
        """
        match = re.match(r'^---\s*\n(.*?)\n---\s*\n', content, re.DOTALL)

        if match:
            frontmatter_text = match.group(1)
            content_without = content[match.end():]

            frontmatter = {}
            for line in frontmatter_text.split('\n'):
                if ':' in line:
                    key, value = line.split(':', 1)
                    frontmatter[key.strip()] = value.strip()

            return content_without, frontmatter

        return content, {}

    def _do_parse(self) -> None:
        """
        Parse Markdown content and create chunks.

        Processes headings, paragraphs, lists, and optionally code blocks.
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

        lines = self.__raw_content.split('\n')
        i = 0

        while i < len(lines):
            line = lines[i]

            heading_match = re.match(r'^(#{1,6})\s+(.+)$', line)
            if heading_match:
                level = len(heading_match.group(1))
                heading_text = heading_match.group(2).strip()

                if 1 <= level <= 6:
                    current_hierarchy[f"level_{level}"] = heading_text[:100]
                    for deeper in range(level + 1, 7):
                        current_hierarchy[f"level_{deeper}"] = ""

                    if not self.__md_title and level == 1:
                        self.__md_title = heading_text

                    LOGGER.debug("Heading level %d: %s", level, heading_text)

                i += 1
                continue

            if self.config.preserve_code_blocks and line.strip().startswith('```'):
                code_lines = [line]
                i += 1
                while i < len(lines) and not lines[i].strip().startswith('```'):
                    code_lines.append(lines[i])
                    i += 1
                if i < len(lines):
                    code_lines.append(lines[i])
                    i += 1

                continue

            if line.strip():
                para_lines = [line]
                i += 1

                while i < len(lines):
                    next_line = lines[i]

                    if (not next_line.strip() or
                        re.match(r'^#{1,6}\s+', next_line) or
                        next_line.strip().startswith('```')):
                        break

                    para_lines.append(next_line)
                    i += 1

                para_text = ' '.join(para_lines)
                cleaned = clean_text(para_text)

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
                        "paragraph",
                        str(paragraph_counter)
                    ),
                    paragraph_id=paragraph_counter,
                    text=cleaned,
                    hierarchy=current_hierarchy.copy(),
                    chapter_href="",
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
            else:
                i += 1

        full_text = " ".join(all_text_parts)
        self._compute_quality(full_text)

        self._apply_chunking_strategy()

        LOGGER.info("Extracted %d chunks from Markdown (strategy: %s)",
                    len(self._BaseExtractor__raw_chunks),
                    self.config.chunking_strategy)

    def _do_extract_metadata(self) -> Metadata:
        """
        Extract metadata from frontmatter and content.

        Returns:
            Metadata object
        """
        title = (
            self.__frontmatter.get('title') or
            self.__md_title or
            os.path.splitext(os.path.basename(self.source_path))[0]
        )

        author = self.__frontmatter.get('author', '')

        return Metadata(
            title=title or "Untitled Markdown",
            author=author or "Unknown",
            language="en",
            word_count=f"approximately {sum(c.word_count for c in self.chunks):,}",
        )
