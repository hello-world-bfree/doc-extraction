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
from typing import Any, Dict, List, Optional

from .base import BaseExtractor
from ..core.models import Chunk, Metadata, Provenance, Quality

PARSER_VERSION = "2.0.0-json-import"
MD_SCHEMA_VERSION = "2025-09-08"

LOGGER = logging.getLogger("json_parser")


class JsonExtractor(BaseExtractor):
    """
    JSON document extractor for importing existing extraction outputs.

    Supports two modes:
    1. Import Mode (default): Load JSON files in extraction output format
    2. Extract Mode (future): Extract text from arbitrary JSON documents
    """

    def __init__(self, source_path: str, config: Optional[Dict] = None):
        """
        Initialize JSON extractor.

        Args:
            source_path: Path to JSON file
            config: Configuration dict with options:
                - mode: 'import' (default) or 'extract'
                - import_chunks: Whether to import chunks (default: True)
                - import_metadata: Whether to import metadata (default: True)
        """
        super().__init__(source_path, config)

        # Configuration
        self.mode = self.config.get("mode", "import")
        self.import_chunks = self.config.get("import_chunks", True)
        self.import_metadata = self.config.get("import_metadata", True)

        # JSON content
        self.json_data = None

    def load(self) -> None:
        """
        Load JSON file.

        Raises:
            RuntimeError: If JSON file cannot be loaded or parsed
        """
        if not os.path.exists(self.source_path):
            raise RuntimeError(f"JSON file not found: {self.source_path}")

        # Read file
        try:
            with open(self.source_path, 'r', encoding='utf-8') as f:
                self.json_data = json.load(f)
        except json.JSONDecodeError as e:
            raise RuntimeError(f"Invalid JSON file: {e}")

        # Read as bytes for content hash
        with open(self.source_path, 'rb') as f:
            source_bytes = f.read()

        # Create provenance
        self.create_provenance(
            parser_version=PARSER_VERSION,
            md_schema_version=MD_SCHEMA_VERSION,
            source_bytes=source_bytes
        )

        LOGGER.info("Loaded JSON file: %s", os.path.basename(self.source_path))

    def parse(self) -> None:
        """
        Parse JSON content and import chunks.

        For import mode: Reconstruct Chunk objects from JSON data
        For extract mode: Extract text content from arbitrary JSON
        """
        if not self.json_data:
            raise RuntimeError("Must call load() before parse()")

        if self.mode == "import":
            self._parse_import_mode()
        else:
            self._parse_extract_mode()

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
        # Validate format
        if not isinstance(self.json_data, dict):
            raise RuntimeError("Import mode requires JSON object with 'chunks' array")

        chunks_data = self.json_data.get("chunks", [])
        if not isinstance(chunks_data, list):
            raise RuntimeError("'chunks' must be an array")

        # Import chunks
        if self.import_chunks:
            for chunk_dict in chunks_data:
                try:
                    # Create Chunk from dict
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
                    self.chunks.append(chunk)
                except Exception as e:
                    LOGGER.warning("Failed to import chunk %s: %s",
                                 chunk_dict.get("paragraph_id", "?"), e)

        # Compute quality from imported text
        all_text = " ".join(c.text for c in self.chunks)
        self.compute_quality(all_text)

        LOGGER.info("Imported %d chunks from JSON", len(self.chunks))

    def _parse_extract_mode(self) -> None:
        """
        Extract mode: Extract text from arbitrary JSON documents.

        This is a placeholder for future implementation that would:
        - Traverse JSON structure
        - Extract text values
        - Build chunks from structured data
        """
        raise NotImplementedError(
            "Extract mode for arbitrary JSON is not yet implemented. "
            "Use mode='import' to load existing extraction outputs."
        )

    def extract_metadata(self) -> Metadata:
        """
        Extract metadata from JSON.

        For import mode: Load metadata from JSON if available
        For extract mode: Generate metadata from JSON structure

        Returns:
            Metadata object
        """
        if not self.chunks and self.mode == "import":
            raise RuntimeError("Must call parse() before extract_metadata()")

        # Import mode: Load existing metadata if available
        if self.mode == "import" and self.import_metadata:
            metadata_dict = self.json_data.get("metadata", {})

            if metadata_dict:
                # Import existing metadata
                self.metadata = Metadata(
                    title=metadata_dict.get("title", "Untitled JSON Import"),
                    author=metadata_dict.get("author", "Unknown"),
                    language=metadata_dict.get("language", "en"),
                    word_count=metadata_dict.get("word_count",
                                                 f"approximately {sum(c.word_count for c in self.chunks):,}"),
                )

                # Copy additional fields if present
                for key in ["document_type", "date_promulgated", "subject",
                           "key_themes", "related_documents", "time_period",
                           "geographic_focus", "publisher", "pages", "source_identifiers"]:
                    if key in metadata_dict:
                        setattr(self.metadata, key, metadata_dict[key])

                LOGGER.info("Imported metadata: %s", self.metadata.title)
                return self.metadata

        # Fallback: Generate basic metadata
        title = self.json_data.get("title",
                                   os.path.splitext(os.path.basename(self.source_path))[0])

        self.metadata = Metadata(
            title=title or "Untitled JSON",
            author="Unknown",
            language="en",
            word_count=f"approximately {sum(c.word_count for c in self.chunks):,}",
        )

        return self.metadata
