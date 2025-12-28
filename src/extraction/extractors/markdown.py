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
from typing import Any, Dict, List, Optional, Tuple

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

PARSER_VERSION = "2.0.0-markdown"
MD_SCHEMA_VERSION = "2025-09-08"

LOGGER = logging.getLogger("markdown_parser")


class MarkdownExtractor(BaseExtractor):
    """
    Markdown document extractor.

    Parses Markdown syntax, extracting text and creating hierarchical
    chunks based on heading structure (# ## ###).
    """

    def __init__(self, source_path: str, config: Optional[Dict] = None):
        """
        Initialize Markdown extractor.

        Args:
            source_path: Path to Markdown file
            config: Configuration dict with options:
                - min_paragraph_words: Minimum words for paragraph inclusion (default: 1)
                - preserve_code_blocks: Keep code blocks as chunks (default: True)
                - extract_frontmatter: Extract YAML/TOML frontmatter (default: True)
        """
        super().__init__(source_path, config)

        # Configuration
        self.min_paragraph_words = self.config.get("min_paragraph_words", 1)
        self.preserve_code_blocks = self.config.get("preserve_code_blocks", True)
        self.extract_frontmatter = self.config.get("extract_frontmatter", True)

        # Markdown content
        self.raw_content = ""
        self.frontmatter = {}
        self.md_title = ""

    def load(self) -> None:
        """
        Load Markdown file.

        Raises:
            RuntimeError: If Markdown file cannot be loaded
        """
        if not os.path.exists(self.source_path):
            raise RuntimeError(f"Markdown file not found: {self.source_path}")

        # Read file
        with open(self.source_path, 'r', encoding='utf-8') as f:
            self.raw_content = f.read()

        # Read as bytes for content hash
        with open(self.source_path, 'rb') as f:
            source_bytes = f.read()

        # Create provenance
        self.create_provenance(
            parser_version=PARSER_VERSION,
            md_schema_version=MD_SCHEMA_VERSION,
            source_bytes=source_bytes
        )

        # Extract frontmatter if present
        if self.extract_frontmatter:
            self.raw_content, self.frontmatter = self._extract_frontmatter(self.raw_content)

        LOGGER.info("Loaded Markdown file: %s", os.path.basename(self.source_path))

    def _extract_frontmatter(self, content: str) -> Tuple[str, Dict]:
        """
        Extract YAML frontmatter from Markdown.

        Args:
            content: Raw Markdown content

        Returns:
            Tuple of (content without frontmatter, frontmatter dict)
        """
        # Match YAML frontmatter: --- ... ---
        match = re.match(r'^---\s*\n(.*?)\n---\s*\n', content, re.DOTALL)

        if match:
            frontmatter_text = match.group(1)
            content_without = content[match.end():]

            # Simple key: value parsing (doesn't handle complex YAML)
            frontmatter = {}
            for line in frontmatter_text.split('\n'):
                if ':' in line:
                    key, value = line.split(':', 1)
                    frontmatter[key.strip()] = value.strip()

            return content_without, frontmatter

        return content, {}

    def parse(self) -> None:
        """
        Parse Markdown content and create chunks.

        Processes headings, paragraphs, lists, and optionally code blocks.
        """
        if not self.raw_content:
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

        # Split into lines for processing
        lines = self.raw_content.split('\n')
        i = 0

        while i < len(lines):
            line = lines[i]

            # Check for heading (# ## ### etc.)
            heading_match = re.match(r'^(#{1,6})\s+(.+)$', line)
            if heading_match:
                level = len(heading_match.group(1))
                heading_text = heading_match.group(2).strip()

                # Update hierarchy
                if 1 <= level <= 6:
                    current_hierarchy[f"level_{level}"] = heading_text[:100]
                    # Clear deeper levels
                    for deeper in range(level + 1, 7):
                        current_hierarchy[f"level_{deeper}"] = ""

                    # Save first heading as title
                    if not self.md_title and level == 1:
                        self.md_title = heading_text

                    LOGGER.debug("Heading level %d: %s", level, heading_text)

                i += 1
                continue

            # Check for code block (```)
            if self.preserve_code_blocks and line.strip().startswith('```'):
                # Collect code block
                code_lines = [line]
                i += 1
                while i < len(lines) and not lines[i].strip().startswith('```'):
                    code_lines.append(lines[i])
                    i += 1
                if i < len(lines):
                    code_lines.append(lines[i])  # Closing ```
                    i += 1

                code_text = '\n'.join(code_lines)
                # Skip processing code blocks as regular text for now
                continue

            # Collect paragraph (consecutive non-empty lines)
            if line.strip():
                para_lines = [line]
                i += 1

                # Collect until empty line or special syntax
                while i < len(lines):
                    next_line = lines[i]

                    # Stop at heading, code block, or empty line
                    if (not next_line.strip() or
                        re.match(r'^#{1,6}\s+', next_line) or
                        next_line.strip().startswith('```')):
                        break

                    para_lines.append(next_line)
                    i += 1

                # Join and clean paragraph
                para_text = ' '.join(para_lines)
                cleaned = clean_text(para_text)

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

                self.chunks.append(chunk)
                all_text_parts.append(cleaned)
            else:
                i += 1

        # Compute overall quality
        full_text = " ".join(all_text_parts)
        self.compute_quality(full_text)

        LOGGER.info("Extracted %d chunks from Markdown", len(self.chunks))

    def extract_metadata(self) -> Metadata:
        """
        Extract metadata from frontmatter and content.

        Returns:
            Metadata object
        """
        if not self.chunks:
            raise RuntimeError("Must call parse() before extract_metadata()")

        # Use frontmatter or filename for title
        title = (
            self.frontmatter.get('title') or
            self.md_title or
            os.path.splitext(os.path.basename(self.source_path))[0]
        )

        author = self.frontmatter.get('author', '')

        # Create base metadata
        self.metadata = Metadata(
            title=title or "Untitled Markdown",
            author=author or "Unknown",
            language="en",  # Could be in frontmatter
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
