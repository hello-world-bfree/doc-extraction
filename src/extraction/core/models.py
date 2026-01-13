#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Data models for extraction system.

Provides type-safe dataclasses for chunks, documents, and metadata while
maintaining backward compatibility with dict-based output through to_dict() methods.
"""

from dataclasses import dataclass, asdict, field
from typing import Dict, List, Optional, Any


@dataclass
class Hierarchy:
    """Document hierarchy (6 levels of headings)."""
    level_1: str = ""
    level_2: str = ""
    level_3: str = ""
    level_4: str = ""
    level_5: str = ""
    level_6: str = ""

    def to_dict(self) -> Dict[str, str]:
        """Convert to dictionary format matching current output."""
        return asdict(self)


@dataclass
class Chunk:
    """A single text chunk (paragraph) from a document."""
    stable_id: str
    paragraph_id: int
    text: str
    hierarchy: Dict[str, str]
    chapter_href: str
    source_order: int
    source_tag: str
    text_length: int
    word_count: int
    cross_references: List[str]
    scripture_references: List[str]
    dates_mentioned: List[str]
    heading_path: str
    hierarchy_depth: int
    doc_stable_id: str
    sentence_count: int
    sentences: List[str]
    normalized_text: str
    footnote_citations: Optional[List[int]] = None
    resolved_footnotes: Optional[Dict[str, str]] = None
    ocr: Optional[bool] = None
    ocr_conf: Optional[float] = None
    # Chunking strategy metadata (v2.3+)
    merged_paragraph_ids: Optional[List[int]] = None
    source_paragraph_count: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict format matching current output.

        Removes None values to match current behavior where optional
        fields are not included if they have no value.
        """
        d = asdict(self)
        return {k: v for k, v in d.items() if v is not None}


@dataclass
class Provenance:
    """Document provenance and processing metadata."""
    doc_id: str
    source_file: str
    parser_version: str
    md_schema_version: str
    ingestion_ts: str
    content_hash: str
    normalized_hash: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict format."""
        d = asdict(self)
        return {k: v for k, v in d.items() if v is not None}


@dataclass
class Quality:
    """Document quality metrics and routing."""
    signals: Dict[str, float]
    score: float
    route: str

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict format."""
        return asdict(self)


@dataclass
class Metadata:
    """Document-level metadata."""
    title: str = ""
    author: str = ""
    description: str = ""
    document_type: str = ""
    date_promulgated: str = ""
    subject: List[str] = field(default_factory=list)
    key_themes: List[str] = field(default_factory=list)
    related_documents: List[str] = field(default_factory=list)
    time_period: str = ""
    geographic_focus: str = ""
    language: str = ""
    publisher: str = ""
    pages: str = ""
    word_count: str = ""
    source_identifiers: Dict[str, Any] = field(default_factory=dict)
    md_schema_version: str = ""
    provenance: Optional[Dict[str, Any]] = None
    quality: Optional[Dict[str, Any]] = None
    footnotes_index: Optional[Dict[str, str]] = None
    footnote_index_count: int = 0
    footnote_citation_stats: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict format matching current output.

        Preserves empty lists for subject, key_themes, and related_documents
        to match current behavior. Removes other None values.
        """
        d = asdict(self)
        # Always include these fields even if empty
        required_lists = ["subject", "key_themes", "related_documents"]
        return {
            k: v for k, v in d.items()
            if v is not None or k in required_lists
        }


@dataclass
class Document:
    """Complete document with metadata, chunks, and extraction info."""
    metadata: Metadata
    chunks: List[Chunk]
    extraction_info: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict format matching current output."""
        return {
            "metadata": self.metadata.to_dict(),
            "chunks": [c.to_dict() for c in self.chunks],
            "extraction_info": self.extraction_info
        }
