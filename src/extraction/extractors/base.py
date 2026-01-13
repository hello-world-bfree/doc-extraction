#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Base extractor interface for all document format extractors.

All format-specific extractors (EPUB, PDF, HTML, etc.) must inherit from
BaseExtractor and implement its abstract methods.
"""

import logging
from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional
from datetime import datetime

from ..core.models import Chunk, Document, Metadata, Provenance, Quality
from ..core.identifiers import sha1, stable_id
from ..core.quality import quality_signals_from_text, score_quality, route_doc
from ..core.strategies import get_strategy, ChunkConfig
from ..state import ExtractorState
from ..exceptions import MethodOrderError, ConfigError
from ..analyzers.base import BaseAnalyzer
from ..analyzers.generic import GenericAnalyzer
from .configs import BaseExtractorConfig

LOGGER = logging.getLogger(__name__)


class BaseExtractor(ABC):
    """
    Abstract base class for document extractors.

    All format-specific extractors must implement:
    - _do_load(): Load the source document
    - _do_parse(): Extract chunks and metadata
    - _do_extract_metadata(): Extract document-level metadata

    Properties available after parsing:
    - chunks: List of extracted Chunk objects
    - metadata: Document metadata
    - provenance: Provenance information
    - quality_score: Quality score (0-1)
    - route: Quality route (A/B/C)

    State machine ensures methods are called in correct order:
    CREATED → load() → LOADED → parse() → PARSED → extract_metadata() → METADATA_READY
    """

    def __init__(
        self,
        source_path: str,
        config: Optional[BaseExtractorConfig] = None,
        analyzer: Optional[BaseAnalyzer] = None
    ):
        """
        Initialize the extractor.

        Args:
            source_path: Path to the source document
            config: Configuration dataclass (defaults to BaseExtractorConfig())
            analyzer: Domain analyzer (defaults to GenericAnalyzer())

        Raises:
            ConfigError: If config is not a BaseExtractorConfig instance
        """
        if config is not None and not isinstance(config, BaseExtractorConfig):
            raise ConfigError(
                f"config must be a BaseExtractorConfig instance, got {type(config)}"
            )

        self.source_path = source_path
        self.config = config or BaseExtractorConfig()
        self.analyzer = analyzer or GenericAnalyzer()

        self.__state = ExtractorState.CREATED

        self.__chunks: List[Chunk] = []
        self.__metadata: Optional[Metadata] = None
        self.__provenance: Optional[Provenance] = None
        self.__quality: Optional[Quality] = None

        self.__doc_quality_signals: Dict[str, float] = {}
        self.__doc_quality_score: float = 0.0
        self.__doc_route: str = "A"

        self.__raw_chunks: List[Dict[str, Any]] = []

    @property
    def chunks(self) -> List[Chunk]:
        """Get extracted chunks (available after parse())."""
        self._require_state("chunks", [ExtractorState.PARSED, ExtractorState.METADATA_READY, ExtractorState.OUTPUT_READY])
        return self.__chunks

    @property
    def metadata(self) -> Optional[Metadata]:
        """Get metadata (available after extract_metadata())."""
        return self.__metadata

    @property
    def provenance(self) -> Provenance:
        """Get provenance information (available after load())."""
        if self.__provenance is None:
            raise MethodOrderError("provenance", "LOADED", self.__state.name)
        return self.__provenance

    @property
    def quality(self) -> Quality:
        """Get quality metrics (available after parse())."""
        if self.__quality is None:
            raise MethodOrderError("quality", "PARSED", self.__state.name)
        return self.__quality

    @property
    def quality_score(self) -> float:
        """Get quality score 0-1 (available after parse())."""
        self._require_state("quality_score", [ExtractorState.PARSED, ExtractorState.METADATA_READY, ExtractorState.OUTPUT_READY])
        return self.__doc_quality_score

    @property
    def route(self) -> str:
        """Get quality route A/B/C (available after parse())."""
        self._require_state("route", [ExtractorState.PARSED, ExtractorState.METADATA_READY, ExtractorState.OUTPUT_READY])
        return self.__doc_route

    @property
    def state(self) -> ExtractorState:
        """Get current extractor state."""
        return self.__state

    def _require_state(self, method_name: str, required_states: List[ExtractorState]) -> None:
        """
        Validate current state before operation.

        Args:
            method_name: Name of the method being called
            required_states: List of valid states for this operation

        Raises:
            MethodOrderError: If current state is not in required_states
        """
        if self.__state not in required_states:
            state_names = [s.name for s in required_states]
            raise MethodOrderError(method_name, state_names, self.__state.name)

    def load(self) -> None:
        """
        Load the source document.

        Must be called first. Calls _do_load() implementation and transitions
        to LOADED state.

        Raises:
            MethodOrderError: If not in CREATED state
            FileError: If document cannot be loaded
        """
        self._require_state("load", [ExtractorState.CREATED])
        self._do_load()
        self.__state = ExtractorState.LOADED
        LOGGER.debug("Extractor transitioned to LOADED state")

    def parse(self) -> None:
        """
        Parse the document and extract chunks.

        Must be called after load(). Calls _do_parse() implementation and
        transitions to PARSED state.

        Raises:
            MethodOrderError: If not in LOADED state
            ParseError: If parsing fails
        """
        self._require_state("parse", [ExtractorState.LOADED])
        self._do_parse()
        self.__state = ExtractorState.PARSED
        LOGGER.debug("Extractor transitioned to PARSED state")

    def extract_metadata(self) -> Metadata:
        """
        Extract document-level metadata.

        Must be called after parse(). Calls _do_extract_metadata() implementation,
        enriches with analyzer, and transitions to METADATA_READY state.

        Returns:
            Metadata object with all fields populated

        Raises:
            MethodOrderError: If not in PARSED state
        """
        self._require_state("extract_metadata", [ExtractorState.PARSED])

        base_metadata = self._do_extract_metadata()

        full_text = " ".join(chunk.text for chunk in self.__chunks)
        chunks_dict = [chunk.to_dict() for chunk in self.__chunks]

        enriched_metadata_dict = self.analyzer.enrich_metadata(
            base_metadata.to_dict(),
            full_text,
            chunks_dict
        )

        self.__metadata = Metadata(**enriched_metadata_dict)
        self.__state = ExtractorState.METADATA_READY
        LOGGER.debug("Extractor transitioned to METADATA_READY state")

        return self.__metadata

    @abstractmethod
    def _do_load(self) -> None:
        """
        Implementation: Load the source document.

        Should populate internal state and create provenance using
        _set_provenance().

        Raises:
            FileError: If document cannot be loaded
        """
        pass

    @abstractmethod
    def _do_parse(self) -> None:
        """
        Implementation: Parse document and extract chunks.

        Should:
        1. Extract raw paragraph chunks into self.__raw_chunks
        2. Call _compute_quality() with full text
        3. Call _apply_chunking_strategy() to finalize chunks

        Raises:
            ParseError: If parsing fails
        """
        pass

    @abstractmethod
    def _do_extract_metadata(self) -> Metadata:
        """
        Implementation: Extract base document metadata.

        Should return Metadata with format-specific fields populated.
        Analyzer enrichment happens automatically after this.

        Returns:
            Metadata object with base fields
        """
        pass

    def _compute_quality(self, full_text: str) -> None:
        """
        Compute quality metrics from full document text.

        Should be called during _do_parse() after extracting all text.

        Args:
            full_text: Complete normalized text of document
        """
        self.__doc_quality_signals = quality_signals_from_text(full_text)
        self.__doc_quality_score = score_quality(self.__doc_quality_signals)
        self.__doc_route = route_doc(self.__doc_quality_score)

        self.__quality = Quality(
            signals=self.__doc_quality_signals,
            score=round(self.__doc_quality_score, 4),
            route=self.__doc_route
        )

    def _apply_chunking_strategy(self) -> None:
        """
        Apply configured chunking strategy to raw paragraph chunks.

        Transforms self.__raw_chunks (paragraph-level) into self.__chunks
        based on config.chunking_strategy ('rag' or 'nlp').

        Should be called at the end of _do_parse() implementation.
        """
        raw_chunks_dicts = [
            chunk.to_dict() if hasattr(chunk, 'to_dict') else chunk
            for chunk in self.__raw_chunks
        ]

        strategy = get_strategy(self.config.chunking_strategy)

        chunk_config = ChunkConfig(
            min_words=self.config.min_chunk_words,
            max_words=self.config.max_chunk_words,
            preserve_hierarchy_levels=self.config.preserve_hierarchy_levels
        )

        processed_chunks = strategy.apply(raw_chunks_dicts, chunk_config)

        if self.config.filter_noise:
            from ..core.noise_filter import NoiseFilter
            processed_chunks, filtered_count = NoiseFilter.filter_chunks(processed_chunks)
            if filtered_count > 0:
                LOGGER.debug("Filtered %d noise chunks", filtered_count)

        self.__chunks = [
            Chunk(**chunk_dict) if isinstance(chunk_dict, dict) else chunk_dict
            for chunk_dict in processed_chunks
        ]

    def _set_provenance(
        self,
        parser_version: str,
        md_schema_version: str,
        source_bytes: bytes
    ) -> None:
        """
        Create and store provenance information.

        Args:
            parser_version: Version of the parser
            md_schema_version: Version of the metadata schema
            source_bytes: Raw bytes of source document for hashing
        """
        import os

        self.__provenance = Provenance(
            doc_id=stable_id(
                os.path.abspath(self.source_path),
                str(os.path.getmtime(self.source_path))
            ),
            source_file=os.path.basename(self.source_path),
            parser_version=parser_version,
            md_schema_version=md_schema_version,
            ingestion_ts=datetime.now().isoformat(),
            content_hash=sha1(source_bytes)
        )

    def _add_raw_chunk(self, chunk: Dict[str, Any]) -> None:
        """
        Add a raw paragraph chunk for strategy processing.

        Args:
            chunk: Chunk dictionary or Chunk object
        """
        self.__raw_chunks.append(chunk)

    def _get_raw_chunks(self) -> List[Dict[str, Any]]:
        """Get raw chunks (for subclass access)."""
        return self.__raw_chunks

    def _set_chunks(self, chunks: List[Chunk]) -> None:
        """Set final chunks (for subclass access)."""
        self.__chunks = chunks

    def get_output_data(self) -> Dict[str, Any]:
        """
        Get complete output data structure.

        Must be called after extract_metadata(). Returns dictionary with
        metadata, chunks, and extraction_info.

        Returns:
            Dictionary with keys: metadata, chunks, extraction_info

        Raises:
            MethodOrderError: If not in METADATA_READY or OUTPUT_READY state
        """
        self._require_state("get_output_data", [ExtractorState.METADATA_READY, ExtractorState.OUTPUT_READY])

        metadata_dict = self.__metadata.to_dict()
        metadata_dict["provenance"] = self.__provenance.to_dict()
        metadata_dict["quality"] = self.__quality.to_dict()

        doc = Document(
            metadata=self.__metadata,
            chunks=self.__chunks,
            extraction_info={
                "total_chunks": len(self.__chunks),
                "quality_route": self.__doc_route,
                "quality_score": round(self.__doc_quality_score, 4)
            }
        )

        result = doc.to_dict()
        result["metadata"] = metadata_dict

        self.__state = ExtractorState.OUTPUT_READY
        return result
