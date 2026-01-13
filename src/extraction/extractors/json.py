#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
JSON extractor for importing existing extraction outputs.

Loads JSON files in the extraction output format, allowing re-processing,
validation, or format conversion of previously extracted documents.
"""

import json
import logging
import os
from typing import Optional

from .base import BaseExtractor
from .configs import JsonExtractorConfig
from ..core.models import Chunk, Metadata
from ..exceptions import FileNotFoundError, ParseError
from ..analyzers.base import BaseAnalyzer

PARSER_VERSION = "2.0.0-json-import"
MD_SCHEMA_VERSION = "2025-09-08"

LOGGER = logging.getLogger("json_parser")


class JsonExtractor(BaseExtractor):
    """
    JSON document extractor for importing existing extraction outputs.

    Supports two modes:
    1. Import Mode (default): Load JSON files in extraction output format
    2. Rechunk Mode: Re-apply chunking strategies to existing extractions
    """

    def __init__(
        self,
        source_path: str,
        config: Optional[JsonExtractorConfig] = None,
        analyzer: Optional[BaseAnalyzer] = None
    ):
        """
        Initialize JSON extractor.

        Args:
            source_path: Path to JSON file
            config: Configuration dataclass (defaults to JsonExtractorConfig())
            analyzer: Domain analyzer (defaults to GenericAnalyzer())
        """
        super().__init__(source_path, config or JsonExtractorConfig(), analyzer)

        self.__json_data = None

    def _do_load(self) -> None:
        """
        Load JSON file.

        Raises:
            FileNotFoundError: If JSON file does not exist
            ParseError: If JSON is invalid
        """
        if not os.path.exists(self.source_path):
            raise FileNotFoundError(self.source_path)

        try:
            with open(self.source_path, 'r', encoding='utf-8') as f:
                self.__json_data = json.load(f)
        except json.JSONDecodeError as e:
            raise ParseError(self.source_path, f"Invalid JSON: {e}")

        with open(self.source_path, 'rb') as f:
            source_bytes = f.read()

        self._set_provenance(
            parser_version=PARSER_VERSION,
            md_schema_version=MD_SCHEMA_VERSION,
            source_bytes=source_bytes
        )

        LOGGER.info("Loaded JSON file: %s", os.path.basename(self.source_path))

    def _do_parse(self) -> None:
        """
        Parse JSON content and import chunks.

        For import mode: Reconstruct Chunk objects from JSON data
        For rechunk mode: Re-apply chunking strategies
        """
        if self.config.mode == "import":
            self._parse_import_mode()
        else:
            self._parse_rechunk_mode()

    def _parse_import_mode(self) -> None:
        """
        Import mode: Load chunks from extraction output format.

        Expected format:
        {
            "metadata": {...},
            "chunks": [...],
            "extraction_info": {...}
        }
        """
        if not isinstance(self.__json_data, dict):
            raise ParseError(
                self.source_path,
                "Import mode requires JSON object with 'chunks' array"
            )

        chunks_data = self.__json_data.get("chunks", [])
        if not isinstance(chunks_data, list):
            raise ParseError(self.source_path, "'chunks' must be an array")

        if self.config.import_chunks:
            for chunk_dict in chunks_data:
                try:
                    chunk = Chunk(
                        stable_id=chunk_dict.get("stable_id", ""),
                        paragraph_id=chunk_dict.get("paragraph_id", 0),
                        text=chunk_dict.get("text", ""),
                        hierarchy=chunk_dict.get("hierarchy", {}),
                        chapter_href=chunk_dict.get("chapter_href", ""),
                        source_order=chunk_dict.get("source_order", 0),
                        source_tag=chunk_dict.get("source_tag", ""),
                        text_length=chunk_dict.get("text_length", 0),
                        word_count=chunk_dict.get("word_count", 0),
                        cross_references=chunk_dict.get("cross_references", []),
                        scripture_references=chunk_dict.get("scripture_references", []),
                        dates_mentioned=chunk_dict.get("dates_mentioned", []),
                        heading_path=chunk_dict.get("heading_path", ""),
                        hierarchy_depth=chunk_dict.get("hierarchy_depth", 0),
                        doc_stable_id=chunk_dict.get("doc_stable_id", ""),
                        sentence_count=chunk_dict.get("sentence_count", 0),
                        sentences=chunk_dict.get("sentences", []),
                        normalized_text=chunk_dict.get("normalized_text", ""),
                    )
                    self._add_raw_chunk(chunk)
                except Exception as e:
                    LOGGER.warning("Failed to import chunk %s: %s",
                                 chunk_dict.get("paragraph_id", "?"), e)

        all_text = " ".join(c.text for c in self._get_raw_chunks())
        self._compute_quality(all_text)

        self._apply_chunking_strategy()

        LOGGER.info("Imported %d chunks from JSON (strategy: %s)",
                    len(self._BaseExtractor__raw_chunks),
                    self.config.chunking_strategy)

    def _parse_rechunk_mode(self) -> None:
        """
        Rechunk mode: Re-apply chunking strategies to existing data.

        Loads chunks and re-processes them with different strategy settings.
        """
        raise NotImplementedError(
            "Rechunk mode is not yet implemented. "
            "Use mode='import' to load existing extraction outputs."
        )

    def _do_extract_metadata(self) -> Metadata:
        """
        Extract metadata from JSON.

        Returns:
            Metadata object
        """
        if self.config.mode == "import" and self.config.import_metadata:
            metadata_dict = self.__json_data.get("metadata", {})

            if metadata_dict:
                metadata = Metadata(
                    title=metadata_dict.get("title", "Untitled JSON Import"),
                    author=metadata_dict.get("author", "Unknown"),
                    language=metadata_dict.get("language", "en"),
                    word_count=metadata_dict.get("word_count",
                                                 f"approximately {sum(c.word_count for c in self.chunks):,}"),
                )

                for key in ["document_type", "date_promulgated", "subject",
                           "key_themes", "related_documents", "time_period",
                           "geographic_focus", "publisher", "pages", "source_identifiers"]:
                    if key in metadata_dict:
                        setattr(metadata, key, metadata_dict[key])

                LOGGER.info("Imported metadata: %s", metadata.title)
                return metadata

        title = self.__json_data.get("title",
                                   os.path.splitext(os.path.basename(self.source_path))[0])

        return Metadata(
            title=title or "Untitled JSON",
            author="Unknown",
            language="en",
            word_count=f"approximately {sum(c.word_count for c in self.chunks):,}",
        )
