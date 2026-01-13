#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Chunking strategies for different use cases.

Provides pluggable chunking strategies optimized for:
- RAG/embeddings: Semantic chunks (100-500 words) under same headings
- NLP: Paragraph-level chunks for fine-grained analysis
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any
from collections import defaultdict
from dataclasses import dataclass


@dataclass
class ChunkConfig:
    """Configuration for chunking strategies."""
    min_words: int = 100
    max_words: int = 500
    preserve_hierarchy_levels: int = 3  # How many hierarchy levels to use for grouping


class ChunkingStrategy(ABC):
    """Base interface for chunking strategies."""

    @abstractmethod
    def apply(self, chunks: List[Dict[str, Any]], config: ChunkConfig) -> List[Dict[str, Any]]:
        """
        Apply chunking strategy to raw paragraph chunks.

        Args:
            chunks: List of paragraph-level chunks from extractor
            config: Chunking configuration

        Returns:
            List of processed chunks according to strategy
        """
        pass

    @abstractmethod
    def name(self) -> str:
        """Return strategy name for logging/debugging."""
        pass


class ParagraphChunkingStrategy(ChunkingStrategy):
    """
    Paragraph-level chunking (NLP mode).

    Preserves original paragraph boundaries - each paragraph is one chunk.
    Optimal for NLP tasks requiring fine-grained text units:
    - Sentence classification
    - Named entity recognition
    - Fine-grained sentiment analysis
    """

    def apply(self, chunks: List[Dict[str, Any]], config: ChunkConfig) -> List[Dict[str, Any]]:
        """Return chunks unchanged (already paragraph-level)."""
        return chunks

    def name(self) -> str:
        return "paragraph"


class SemanticChunkingStrategy(ChunkingStrategy):
    """
    Semantic chunking for RAG/embeddings.

    Merges paragraphs under the same heading hierarchy into larger semantic chunks.
    Target: 100-500 words per chunk (configurable).

    Design:
    1. Group paragraphs by heading hierarchy (first N levels)
    2. Merge paragraphs within each group up to max_words
    3. Skip index/TOC sections
    4. Maintain document order

    Optimal for:
    - Vector embeddings
    - Semantic search
    - RAG systems
    """

    def apply(self, chunks: List[Dict[str, Any]], config: ChunkConfig) -> List[Dict[str, Any]]:
        """Merge paragraphs into semantic chunks."""
        # Group chunks by hierarchy
        hierarchy_groups = defaultdict(list)

        for chunk in chunks:
            h = chunk.get('hierarchy', {})

            # Skip index and TOC sections
            level_1 = h.get('level_1', '')
            if self._is_skippable_section(level_1):
                continue

            # Create hierarchy key using configured number of levels
            key = self._make_hierarchy_key(h, config.preserve_hierarchy_levels)
            hierarchy_groups[key].append(chunk)

        # Merge chunks within each group
        merged_chunks = []

        for hierarchy_key, group_chunks in hierarchy_groups.items():
            # Sort by paragraph_id to maintain document order
            group_chunks.sort(key=lambda c: c.get('paragraph_id', 0))

            merged_chunks.extend(
                self._merge_group(group_chunks, hierarchy_key, config)
            )

        # Sort final chunks by first paragraph_id to maintain overall order
        if merged_chunks:
            merged_chunks.sort(key=lambda c: c['merged_paragraph_ids'][0])

        return merged_chunks

    def _is_skippable_section(self, level_1: str) -> bool:
        """Check if section should be skipped (index, TOC, etc.)."""
        skippable = {'index', 'table of contents', 'contents', 'toc'}
        return level_1.lower() in skippable

    def _make_hierarchy_key(self, hierarchy: Dict[str, str], num_levels: int) -> tuple:
        """Create hierarchy grouping key from first N levels."""
        return tuple(
            hierarchy.get(f'level_{i}', '')
            for i in range(1, num_levels + 1)
        )

    def _merge_group(
        self,
        group_chunks: List[Dict[str, Any]],
        hierarchy_key: tuple,
        config: ChunkConfig
    ) -> List[Dict[str, Any]]:
        """Merge chunks within a hierarchy group."""
        merged_chunks = []
        current_merged = self._new_merged_chunk(hierarchy_key, config.preserve_hierarchy_levels)

        for chunk in group_chunks:
            chunk_words = chunk.get('word_count', 0)

            # If adding this chunk would exceed max_words, save current and start new
            if (current_merged['word_count'] + chunk_words > config.max_words
                    and current_merged['texts']):
                merged_chunks.append(self._finalize_merged_chunk(current_merged))
                current_merged = self._new_merged_chunk(hierarchy_key, config.preserve_hierarchy_levels)

            # Add chunk to current merged
            current_merged['texts'].append(chunk['text'])
            current_merged['word_count'] += chunk_words
            current_merged['paragraph_ids'].append(chunk.get('paragraph_id'))
            current_merged['source_chunks'].append(chunk)

        # Save final merged chunk if it meets minimum
        if current_merged['word_count'] >= config.min_words:
            merged_chunks.append(self._finalize_merged_chunk(current_merged))

        return merged_chunks

    def _new_merged_chunk(self, hierarchy_key: tuple, num_levels: int) -> Dict[str, Any]:
        """Create new empty merged chunk."""
        return {
            'hierarchy': {
                f'level_{i}': hierarchy_key[i-1]
                for i in range(1, num_levels + 1)
                if hierarchy_key[i-1]
            },
            'texts': [],
            'word_count': 0,
            'paragraph_ids': [],
            'source_chunks': [],
        }

    def _finalize_merged_chunk(self, merged: Dict[str, Any]) -> Dict[str, Any]:
        """
        Convert merged chunk to final format.

        Combines text from multiple paragraphs and aggregates metadata.
        Uses first source chunk as template for fields like stable_id, hierarchy, etc.
        """
        source_chunks = merged['source_chunks']
        first_chunk = source_chunks[0]

        # Combine texts with double newline
        combined_text = '\n\n'.join(merged['texts'])

        # Aggregate lists from all source chunks
        all_scripture_refs = []
        all_cross_refs = []
        all_dates = []
        all_sentences = []

        for chunk in source_chunks:
            all_scripture_refs.extend(chunk.get('scripture_references', []))
            all_cross_refs.extend(chunk.get('cross_references', []))
            all_dates.extend(chunk.get('dates_mentioned', []))
            all_sentences.extend(chunk.get('sentences', []))

        # Create merged chunk with combined metadata
        from .chunking import heading_path, hierarchy_depth
        from .identifiers import stable_id

        merged_chunk = {
            'stable_id': stable_id(combined_text),
            'paragraph_id': merged['paragraph_ids'][0],  # Use first para ID
            'text': combined_text,
            'hierarchy': merged['hierarchy'],
            'chapter_href': first_chunk.get('chapter_href', ''),
            'source_order': first_chunk.get('source_order', 0),
            'source_tag': f"merged_{len(source_chunks)}_paragraphs",
            'text_length': len(combined_text),
            'word_count': merged['word_count'],
            'cross_references': list(set(all_cross_refs)),  # Deduplicate
            'scripture_references': list(set(all_scripture_refs)),
            'dates_mentioned': list(set(all_dates)),
            'heading_path': heading_path(merged['hierarchy']),
            'hierarchy_depth': hierarchy_depth(merged['hierarchy']),
            'doc_stable_id': first_chunk.get('doc_stable_id', ''),
            'sentence_count': len(all_sentences),
            'sentences': all_sentences,
            'normalized_text': combined_text.lower(),

            # Metadata about merging
            'source_paragraph_count': len(source_chunks),
            'merged_paragraph_ids': merged['paragraph_ids'],
        }

        # Preserve optional fields if present in first chunk
        optional_fields = ['footnote_citations', 'resolved_footnotes', 'ocr', 'ocr_conf']
        for field in optional_fields:
            if field in first_chunk:
                merged_chunk[field] = first_chunk[field]

        return merged_chunk

    def name(self) -> str:
        return "semantic"


# Strategy registry
STRATEGIES = {
    'nlp': ParagraphChunkingStrategy(),
    'paragraph': ParagraphChunkingStrategy(),
    'rag': SemanticChunkingStrategy(),
    'semantic': SemanticChunkingStrategy(),
    'embeddings': SemanticChunkingStrategy(),
}


def get_strategy(name: str) -> ChunkingStrategy:
    """
    Get chunking strategy by name.

    Args:
        name: Strategy name ('nlp', 'rag', 'semantic', etc.)

    Returns:
        ChunkingStrategy instance

    Raises:
        ValueError: If strategy name not found
    """
    if name not in STRATEGIES:
        available = ', '.join(STRATEGIES.keys())
        raise ValueError(
            f"Unknown chunking strategy: {name}. "
            f"Available: {available}"
        )
    return STRATEGIES[name]
