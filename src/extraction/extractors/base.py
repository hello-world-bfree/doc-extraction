#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Base extractor interface for all document format extractors.

All format-specific extractors (EPUB, PDF, HTML, etc.) must inherit from
BaseExtractor and implement its abstract methods.
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional
from datetime import datetime

from ..core.models import Chunk, Document, Metadata, Provenance, Quality
from ..core.identifiers import sha1, stable_id
from ..core.quality import quality_signals_from_text, score_quality, route_doc


class BaseExtractor(ABC):
    """
    Abstract base class for document extractors.

    All format-specific extractors must implement:
    - load(): Load the source document
    - parse(): Extract chunks and metadata
    - extract_metadata(): Extract document-level metadata

    Properties available after parsing:
    - chunks: List of extracted Chunk objects
    - metadata: Document metadata
    - provenance: Provenance information
    - quality_score: Quality score (0-1)
    - route: Quality route (A/B/C)
    """

    def __init__(self, source_path: str, config: Optional[Dict] = None):
        """
        Initialize the extractor.

        Args:
            source_path: Path to the source document
            config: Optional configuration dictionary
        """
        self.source_path = source_path
        self.config = config or {}

        # Output data (populated during parsing)
        self.chunks: List[Chunk] = []
        self.metadata: Optional[Metadata] = None
        self._provenance: Optional[Provenance] = None
        self._quality: Optional[Quality] = None

        # Quality metrics (populated during parsing)
        self._doc_quality_signals: Dict[str, float] = {}
        self._doc_quality_score: float = 0.0
        self._doc_route: str = "A"

    @abstractmethod
    def load(self) -> None:
        """
        Load the source document.

        Should populate any internal state needed for parsing and create
        base provenance information.

        Raises:
            RuntimeError: If document cannot be loaded
        """
        pass

    @abstractmethod
    def parse(self) -> None:
        """
        Parse the document and extract chunks.

        Should populate:
        - self.chunks: List of Chunk objects
        - self._doc_quality_signals: Quality signals
        - self._doc_quality_score: Overall quality score
        - self._doc_route: Quality route (A/B/C)

        Must be called after load().

        Raises:
            RuntimeError: If called before load() or parsing fails
        """
        pass

    @abstractmethod
    def extract_metadata(self) -> Metadata:
        """
        Extract document-level metadata.

        Should return Metadata object with all available fields populated.
        Must be called after parse().

        Returns:
            Metadata object
        """
        pass

    @property
    def provenance(self) -> Provenance:
        """Get provenance information."""
        if self._provenance is None:
            raise RuntimeError("Provenance not available. Call load() first.")
        return self._provenance

    @property
    def quality(self) -> Quality:
        """Get quality metrics."""
        if self._quality is None:
            raise RuntimeError("Quality not available. Call parse() first.")
        return self._quality

    @property
    def quality_score(self) -> float:
        """Get quality score (0-1)."""
        return self._doc_quality_score

    @property
    def route(self) -> str:
        """Get quality route (A/B/C)."""
        return self._doc_route

    def compute_quality(self, full_text: str) -> None:
        """
        Compute quality metrics from full document text.

        Should be called during parse() after extracting all text.

        Args:
            full_text: Complete normalized text of document
        """
        self._doc_quality_signals = quality_signals_from_text(full_text)
        self._doc_quality_score = score_quality(self._doc_quality_signals)
        self._doc_route = route_doc(self._doc_quality_score)

        self._quality = Quality(
            signals=self._doc_quality_signals,
            score=round(self._doc_quality_score, 4),
            route=self._doc_route
        )

    def create_provenance(
        self,
        parser_version: str,
        md_schema_version: str,
        source_bytes: bytes
    ) -> Provenance:
        """
        Create provenance information for the document.

        Args:
            parser_version: Version of the parser
            md_schema_version: Version of the metadata schema
            source_bytes: Raw bytes of source document for hashing

        Returns:
            Provenance object
        """
        import os

        self._provenance = Provenance(
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
        return self._provenance

    def get_output_data(self) -> Dict[str, Any]:
        """
        Get complete output data structure.

        Returns dictionary with metadata, chunks, and extraction_info
        matching the current output format exactly.

        Returns:
            Dictionary with keys: metadata, chunks, extraction_info

        Raises:
            RuntimeError: If called before parse() and extract_metadata()
        """
        if not self.chunks:
            raise RuntimeError("No chunks available. Call parse() first.")
        if self.metadata is None:
            raise RuntimeError("No metadata available. Call extract_metadata() first.")

        # Add provenance and quality to metadata
        metadata_dict = self.metadata.to_dict()
        metadata_dict["provenance"] = self.provenance.to_dict()
        metadata_dict["quality"] = self.quality.to_dict()

        # Create document
        doc = Document(
            metadata=self.metadata,
            chunks=self.chunks,
            extraction_info={
                "total_chunks": len(self.chunks),
                "quality_route": self.route,
                "quality_score": round(self.quality_score, 4)
            }
        )

        # Return dict format for backward compatibility
        result = doc.to_dict()
        # Override metadata to include provenance and quality
        result["metadata"] = metadata_dict

        return result
