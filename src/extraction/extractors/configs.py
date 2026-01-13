#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Configuration dataclasses for document extractors.

All config classes inherit from BaseExtractorConfig and add format-specific
options. Validation happens in __post_init__ to catch errors early.
"""

import re
from dataclasses import dataclass, field
from typing import Literal, Optional

from ..exceptions import ConfigError, InvalidConfigValueError


@dataclass
class BaseExtractorConfig:
    """
    Base configuration for all extractors.

    Attributes:
        chunking_strategy: Strategy for chunking text ('rag' or 'nlp')
        min_chunk_words: Minimum words per chunk (for RAG strategy)
        max_chunk_words: Maximum words per chunk (for RAG strategy)
        preserve_hierarchy_levels: Number of hierarchy levels to preserve
        filter_noise: Filter index pages, TOC, and copyright boilerplate
    """

    chunking_strategy: Literal["rag", "nlp", "semantic", "embeddings", "paragraph"] = "rag"
    min_chunk_words: int = 100
    max_chunk_words: int = 500
    preserve_hierarchy_levels: int = 3
    filter_noise: bool = True

    def __post_init__(self):
        if self.chunking_strategy not in ("rag", "nlp", "semantic", "embeddings", "paragraph"):
            raise InvalidConfigValueError(
                "chunking_strategy",
                self.chunking_strategy,
                ["rag", "nlp", "semantic", "embeddings", "paragraph"]
            )

        if self.min_chunk_words < 1:
            raise InvalidConfigValueError(
                "min_chunk_words",
                self.min_chunk_words,
                "Must be >= 1"
            )

        if self.max_chunk_words < self.min_chunk_words:
            raise InvalidConfigValueError(
                "max_chunk_words",
                self.max_chunk_words,
                f"Must be >= min_chunk_words ({self.min_chunk_words})"
            )

        if self.preserve_hierarchy_levels < 0 or self.preserve_hierarchy_levels > 6:
            raise InvalidConfigValueError(
                "preserve_hierarchy_levels",
                self.preserve_hierarchy_levels,
                "Must be between 0 and 6"
            )

        if self.chunking_strategy in ("semantic", "embeddings"):
            self.chunking_strategy = "rag"
        elif self.chunking_strategy == "paragraph":
            self.chunking_strategy = "nlp"


@dataclass
class EpubExtractorConfig(BaseExtractorConfig):
    """
    Configuration for EPUB extractor.

    Attributes:
        toc_hierarchy_level: TOC hierarchy level to use (1-6)
        min_paragraph_words: Minimum words to consider text as paragraph
        min_block_words: Minimum words to consider a block valid
        preserve_hierarchy_across_docs: Whether to preserve hierarchy across spine documents
        reset_depth: Hierarchy depth at which to reset across documents
        class_denylist: Regex pattern for CSS classes to exclude
        filter_tiny_chunks: Tiny chunk filtering level ('off', 'conservative', 'standard', 'aggressive')
    """

    toc_hierarchy_level: int = 3
    min_paragraph_words: int = 6
    min_block_words: int = 30
    preserve_hierarchy_across_docs: bool = False
    reset_depth: int = 2
    class_denylist: str = r"^(?:calibre\d+|note|footnote)$"
    filter_tiny_chunks: Literal["off", "conservative", "standard", "aggressive"] = "conservative"

    def __post_init__(self):
        super().__post_init__()

        if self.toc_hierarchy_level < 1 or self.toc_hierarchy_level > 6:
            raise InvalidConfigValueError(
                "toc_hierarchy_level",
                self.toc_hierarchy_level,
                "Must be between 1 and 6"
            )

        if self.min_paragraph_words < 1:
            raise InvalidConfigValueError(
                "min_paragraph_words",
                self.min_paragraph_words,
                "Must be >= 1"
            )

        if self.min_block_words < 1:
            raise InvalidConfigValueError(
                "min_block_words",
                self.min_block_words,
                "Must be >= 1"
            )

        if self.reset_depth < 1 or self.reset_depth > 6:
            raise InvalidConfigValueError(
                "reset_depth",
                self.reset_depth,
                "Must be between 1 and 6"
            )

        try:
            re.compile(self.class_denylist, re.I)
        except re.error as e:
            raise InvalidConfigValueError(
                "class_denylist",
                self.class_denylist,
                f"Invalid regex pattern: {e}"
            )

        if self.filter_tiny_chunks not in ("off", "conservative", "standard", "aggressive"):
            raise InvalidConfigValueError(
                "filter_tiny_chunks",
                self.filter_tiny_chunks,
                ["off", "conservative", "standard", "aggressive"]
            )


@dataclass
class PdfExtractorConfig(BaseExtractorConfig):
    """
    Configuration for PDF extractor.

    Attributes:
        min_paragraph_words: Minimum words to consider text as paragraph
        heading_font_threshold: Font size multiplier to detect headings
        use_ocr: Whether to use OCR for image-based PDFs
        ocr_lang: OCR language code (e.g., 'eng', 'fra', 'spa')
    """

    min_paragraph_words: int = 5
    heading_font_threshold: float = 1.2
    use_ocr: bool = False
    ocr_lang: str = "eng"

    def __post_init__(self):
        super().__post_init__()

        if self.min_paragraph_words < 1:
            raise InvalidConfigValueError(
                "min_paragraph_words",
                self.min_paragraph_words,
                "Must be >= 1"
            )

        if self.heading_font_threshold < 1.0 or self.heading_font_threshold > 3.0:
            raise InvalidConfigValueError(
                "heading_font_threshold",
                self.heading_font_threshold,
                "Must be between 1.0 and 3.0"
            )

        if not isinstance(self.ocr_lang, str) or len(self.ocr_lang) < 2:
            raise InvalidConfigValueError(
                "ocr_lang",
                self.ocr_lang,
                "Must be a valid language code (e.g., 'eng', 'fra')"
            )


@dataclass
class HtmlExtractorConfig(BaseExtractorConfig):
    """
    Configuration for HTML extractor.

    Attributes:
        min_paragraph_words: Minimum words to consider text as paragraph
        preserve_links: Whether to preserve hyperlinks in output
    """

    min_paragraph_words: int = 1
    preserve_links: bool = False

    def __post_init__(self):
        super().__post_init__()

        if self.min_paragraph_words < 0:
            raise InvalidConfigValueError(
                "min_paragraph_words",
                self.min_paragraph_words,
                "Must be >= 0"
            )


@dataclass
class MarkdownExtractorConfig(BaseExtractorConfig):
    """
    Configuration for Markdown extractor.

    Attributes:
        min_paragraph_words: Minimum words to consider text as paragraph
        preserve_code_blocks: Whether to preserve code blocks
        extract_frontmatter: Whether to extract YAML frontmatter
    """

    min_paragraph_words: int = 1
    preserve_code_blocks: bool = True
    extract_frontmatter: bool = True

    def __post_init__(self):
        super().__post_init__()

        if self.min_paragraph_words < 0:
            raise InvalidConfigValueError(
                "min_paragraph_words",
                self.min_paragraph_words,
                "Must be >= 0"
            )


@dataclass
class JsonExtractorConfig(BaseExtractorConfig):
    """
    Configuration for JSON extractor.

    Attributes:
        mode: Import mode ('import' or 'rechunk')
        import_chunks: Whether to import chunks from JSON
        import_metadata: Whether to import metadata from JSON
    """

    mode: Literal["import", "rechunk"] = "import"
    import_chunks: bool = True
    import_metadata: bool = True

    def __post_init__(self):
        super().__post_init__()

        if self.mode not in ("import", "rechunk"):
            raise InvalidConfigValueError(
                "mode",
                self.mode,
                ["import", "rechunk"]
            )
