"""Core utilities and models."""

# Models
from extraction.core.models import Chunk, Metadata, Provenance, Quality, Hierarchy, Document

# Chunking utilities
from extraction.core.chunking import (
    split_sentences,
    heading_path,
    hierarchy_depth,
    heading_level,
    is_heading_tag,
)

# Quality scoring
from extraction.core.quality import (
    quality_signals_from_text,
    score_quality,
    route_doc,
)

# Reference extraction
from extraction.core.extraction import (
    extract_dates,
    extract_scripture_references,
    extract_cross_references,
)

# Text utilities
from extraction.core.text import (
    normalize_spaced_caps,
    clean_text,
    estimate_word_count,
    clean_toc_title,
    normalize_ascii,
)

# Identifiers
from extraction.core.identifiers import sha1, stable_id

# Output utilities
from extraction.core.output import write_outputs, write_chunks_ndjson, write_hierarchy_report

__all__ = [
    # Models
    "Chunk", "Metadata", "Provenance", "Quality", "Hierarchy", "Document",
    # Chunking
    "split_sentences", "heading_path", "hierarchy_depth", "heading_level", "is_heading_tag",
    # Quality
    "quality_signals_from_text", "score_quality", "route_doc",
    # Extraction
    "extract_dates", "extract_scripture_references", "extract_cross_references",
    # Text
    "normalize_spaced_caps", "clean_text", "estimate_word_count", "clean_toc_title", "normalize_ascii",
    # Identifiers
    "sha1", "stable_id",
    # Output
    "write_outputs", "write_chunks_ndjson", "write_hierarchy_report",
]
