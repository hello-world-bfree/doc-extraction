#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import logging
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from collections import defaultdict
from dataclasses import dataclass

LOGGER = logging.getLogger(__name__)


@dataclass
class ChunkConfig:
    min_words: int = 100
    max_words: int = 500
    preserve_hierarchy_levels: int = 5
    preserve_small_chunks: bool = True


@dataclass
class TokenChunkConfig(ChunkConfig):
    target_tokens: int = 400
    min_tokens: int = 256
    max_tokens: int = 512
    overlap_percent: float = 0.10
    code_max_tokens: int = 256
    max_absolute_tokens: int = 2048
    tokenizer_name: str = "google/embeddinggemma-300m"


# --- Shared helpers ---

_SKIPPABLE_SECTIONS = {'index', 'table of contents', 'contents', 'toc'}


def is_skippable_section(level_1: str) -> bool:
    return level_1.lower() in _SKIPPABLE_SECTIONS


def make_hierarchy_key(hierarchy: Dict[str, str], num_levels: int) -> tuple:
    return tuple(
        hierarchy.get(f'level_{i}', '')
        for i in range(1, num_levels + 1)
    )


def new_merged_chunk(hierarchy_key: tuple, num_levels: int) -> Dict[str, Any]:
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
        '_num_levels': num_levels,
    }


def finalize_merged_chunk(merged: Dict[str, Any]) -> Dict[str, Any]:
    source_chunks = merged['source_chunks']
    first_chunk = source_chunks[0]

    combined_text = '\n\n'.join(merged['texts'])

    all_scripture_refs = []
    all_cross_refs = []
    all_dates = []
    all_sentences = []

    for chunk in source_chunks:
        all_scripture_refs.extend(chunk.get('scripture_references', []))
        all_cross_refs.extend(chunk.get('cross_references', []))
        all_dates.extend(chunk.get('dates_mentioned', []))
        all_sentences.extend(chunk.get('sentences', []))

    from .chunking import heading_path, hierarchy_depth
    from .identifiers import stable_id
    from .text import estimate_word_count

    num_levels = merged.get('_num_levels', 3)
    first_hierarchy = first_chunk.get('hierarchy', {})
    full_hierarchy = {}
    for i in range(1, 7):
        key = f'level_{i}'
        if i <= num_levels:
            full_hierarchy[key] = first_hierarchy.get(key, '')
        else:
            full_hierarchy[key] = ''

    content_types = {
        c.get('content_type') for c in source_chunks if c.get('content_type')
    }
    if len(content_types) == 1:
        merged_content_type = content_types.pop()
    elif len(content_types) > 1:
        merged_content_type = 'mixed'
    else:
        merged_content_type = None

    merged_chunk = {
        'stable_id': stable_id(combined_text),
        'paragraph_id': merged['paragraph_ids'][0],
        'text': combined_text,
        'hierarchy': full_hierarchy,
        'chapter_href': first_chunk.get('chapter_href', ''),
        'source_order': first_chunk.get('source_order', 0),
        'source_tag': f"merged_{len(source_chunks)}_paragraphs",
        'text_length': len(combined_text),
        'word_count': estimate_word_count(combined_text),
        'cross_references': list(dict.fromkeys(all_cross_refs)),
        'scripture_references': list(dict.fromkeys(all_scripture_refs)),
        'dates_mentioned': list(dict.fromkeys(all_dates)),
        'heading_path': heading_path(full_hierarchy),
        'hierarchy_depth': hierarchy_depth(full_hierarchy),
        'doc_stable_id': first_chunk.get('doc_stable_id', ''),
        'sentence_count': len(all_sentences),
        'sentences': all_sentences,
        'normalized_text': combined_text.lower(),
        'content_type': merged_content_type,
        'source_paragraph_count': len(source_chunks),
        'merged_paragraph_ids': merged['paragraph_ids'],
    }

    all_footnote_citations_all = []
    all_footnote_citations_by_sentence = []
    all_resolved_footnotes = {}
    has_ocr = False
    ocr_confs = []
    sentence_offset = 0

    for chunk in source_chunks:
        fc = chunk.get('footnote_citations')
        if fc:
            if isinstance(fc, dict):
                all_footnote_citations_all.extend(fc.get('all', []))
                for entry in fc.get('by_sentence', []):
                    if isinstance(entry, dict) and 'index' in entry:
                        offset_entry = dict(entry)
                        offset_entry['index'] = entry['index'] + sentence_offset
                        all_footnote_citations_by_sentence.append(offset_entry)
                    else:
                        all_footnote_citations_by_sentence.append(entry)
            elif isinstance(fc, list):
                all_footnote_citations_all.extend(fc)

        sentence_offset += len(chunk.get('sentences', []))

        rf = chunk.get('resolved_footnotes')
        if rf and isinstance(rf, dict):
            all_resolved_footnotes.update(rf)

        if chunk.get('ocr') is not None:
            has_ocr = True
        oc = chunk.get('ocr_conf')
        if oc is not None:
            ocr_confs.append(oc)

    if all_footnote_citations_all:
        merged_chunk['footnote_citations'] = {
            'all': all_footnote_citations_all,
            'by_sentence': all_footnote_citations_by_sentence,
        }
    if all_resolved_footnotes:
        merged_chunk['resolved_footnotes'] = all_resolved_footnotes
    if has_ocr:
        merged_chunk['ocr'] = True
    if ocr_confs:
        merged_chunk['ocr_conf'] = sum(ocr_confs) / len(ocr_confs)

    return merged_chunk


# --- Strategy base ---

class ChunkingStrategy(ABC):

    @abstractmethod
    def apply(self, chunks: List[Dict[str, Any]], config: ChunkConfig) -> List[Dict[str, Any]]:
        pass

    @abstractmethod
    def name(self) -> str:
        pass


class ParagraphChunkingStrategy(ChunkingStrategy):

    def apply(self, chunks: List[Dict[str, Any]], config: ChunkConfig) -> List[Dict[str, Any]]:
        return chunks

    def name(self) -> str:
        return "paragraph"


class SemanticChunkingStrategy(ChunkingStrategy):

    def apply(self, chunks: List[Dict[str, Any]], config: ChunkConfig) -> List[Dict[str, Any]]:
        hierarchy_groups = defaultdict(list)

        for chunk in chunks:
            h = chunk.get('hierarchy', {})
            level_1 = h.get('level_1', '')
            if is_skippable_section(level_1):
                continue
            key = make_hierarchy_key(h, config.preserve_hierarchy_levels)
            hierarchy_groups[key].append(chunk)

        merged_chunks = []
        for hierarchy_key, group_chunks in hierarchy_groups.items():
            group_chunks.sort(key=lambda c: c.get('paragraph_id', 0))
            merged_chunks.extend(
                self._merge_group(group_chunks, hierarchy_key, config)
            )

        if merged_chunks:
            merged_chunks.sort(key=lambda c: c['merged_paragraph_ids'][0])

        return merged_chunks

    def _merge_group(
        self,
        group_chunks: List[Dict[str, Any]],
        hierarchy_key: tuple,
        config: ChunkConfig
    ) -> List[Dict[str, Any]]:
        merged_chunks = []
        current = new_merged_chunk(hierarchy_key, config.preserve_hierarchy_levels)

        for chunk in group_chunks:
            chunk_words = chunk.get('word_count', 0)

            if (current['word_count'] + chunk_words > config.max_words
                    and current['texts']):
                merged_chunks.append(finalize_merged_chunk(current))
                current = new_merged_chunk(hierarchy_key, config.preserve_hierarchy_levels)

            current['texts'].append(chunk['text'])
            current['word_count'] += chunk_words
            current['paragraph_ids'].append(chunk.get('paragraph_id'))
            current['source_chunks'].append(chunk)

        if current['word_count'] >= config.min_words:
            merged_chunks.append(finalize_merged_chunk(current))
        elif current['texts'] and config.preserve_small_chunks:
            finalized = finalize_merged_chunk(current)
            finalized['quality_flags'] = ['below_rag_minimum']
            merged_chunks.append(finalized)

        return merged_chunks

    def name(self) -> str:
        return "semantic"


def _estimate_tokens_from_words(word_count: int) -> int:
    return int(word_count * 1.5)


def _load_tokenizer_safe(tokenizer_name: str):
    try:
        from extraction.tools.tokenizer_utils import load_tokenizer
        return load_tokenizer(tokenizer_name)
    except (ImportError, OSError) as e:
        LOGGER.warning(
            f"Could not load tokenizer '{tokenizer_name}': {e}. "
            "Falling back to word-count approximation (1 word ≈ 1.3 tokens)."
        )
        return None


def _count_tokens(text: str, tokenizer) -> int:
    if tokenizer is None:
        return _estimate_tokens_from_words(len(text.split()))
    from extraction.tools.tokenizer_utils import count_tokens
    return count_tokens(text, tokenizer)


class TokenAwareChunkingStrategy(ChunkingStrategy):

    def apply(self, chunks: List[Dict[str, Any]], config: ChunkConfig) -> List[Dict[str, Any]]:
        if not isinstance(config, TokenChunkConfig):
            raise TypeError(
                f"TokenAwareChunkingStrategy requires TokenChunkConfig, got {type(config).__name__}"
            )

        tokenizer = _load_tokenizer_safe(config.tokenizer_name)

        hierarchy_groups = defaultdict(list)
        for chunk in chunks:
            h = chunk.get('hierarchy', {})
            level_1 = h.get('level_1', '')
            if is_skippable_section(level_1):
                continue
            key = make_hierarchy_key(h, config.preserve_hierarchy_levels)
            hierarchy_groups[key].append(chunk)

        merged_chunks = []
        for hierarchy_key, group_chunks in hierarchy_groups.items():
            group_chunks.sort(key=lambda c: c.get('paragraph_id', 0))
            merged_chunks.extend(
                self._merge_group_tokens(group_chunks, hierarchy_key, config, tokenizer)
            )

        if merged_chunks:
            merged_chunks.sort(key=lambda c: c['merged_paragraph_ids'][0])

        return merged_chunks

    def _merge_group_tokens(
        self,
        group_chunks: List[Dict[str, Any]],
        hierarchy_key: tuple,
        config: TokenChunkConfig,
        tokenizer,
    ) -> List[Dict[str, Any]]:
        merged_chunks = []
        current = new_merged_chunk(hierarchy_key, config.preserve_hierarchy_levels)
        current['_token_count'] = 0
        current['_sentences'] = []
        current['_overlap_word_count'] = 0
        pending_overlap_text: Optional[str] = None
        pending_overlap_tokens = 0
        pending_overlap_sentences: List[str] = []
        incoming_overlap_tokens = 0

        for chunk in group_chunks:
            is_code = chunk.get('content_type') == 'code'

            if is_code:
                if current['source_chunks']:
                    finalized = finalize_merged_chunk(current)
                    if incoming_overlap_tokens > 0:
                        finalized['overlap_token_count'] = incoming_overlap_tokens
                    merged_chunks.append(finalized)
                    pending_overlap_text = None
                    pending_overlap_tokens = 0
                    pending_overlap_sentences = []
                    incoming_overlap_tokens = 0
                    current = new_merged_chunk(hierarchy_key, config.preserve_hierarchy_levels)
                    current['_token_count'] = 0
                    current['_sentences'] = []
                    current['_overlap_word_count'] = 0

                code_tokens = _count_tokens(chunk['text'], tokenizer)
                if code_tokens > config.code_max_tokens:
                    merged_chunks.extend(
                        self._split_code_block(chunk, hierarchy_key, config, tokenizer)
                    )
                else:
                    code_merged = new_merged_chunk(hierarchy_key, config.preserve_hierarchy_levels)
                    code_merged['texts'].append(chunk['text'])
                    code_merged['paragraph_ids'].append(chunk.get('paragraph_id'))
                    code_merged['source_chunks'].append(chunk)
                    merged_chunks.append(finalize_merged_chunk(code_merged))
                continue

            chunk_tokens = _count_tokens(chunk['text'], tokenizer)

            if pending_overlap_text is not None and not current['texts']:
                current['texts'].append(pending_overlap_text)
                current['_token_count'] = pending_overlap_tokens
                current['_sentences'].extend(pending_overlap_sentences)
                current['_overlap_word_count'] = len(pending_overlap_text.split())
                incoming_overlap_tokens = pending_overlap_tokens
                pending_overlap_text = None
                pending_overlap_tokens = 0
                pending_overlap_sentences = []

            overflow_threshold = min(config.target_tokens, config.max_tokens)
            if (current['_token_count'] + chunk_tokens > overflow_threshold
                    and current['source_chunks']):
                outgoing_text, outgoing_tokens, outgoing_sentences = self._compute_overlap(
                    current['_sentences'], config, tokenizer
                )

                finalized = finalize_merged_chunk(current)
                if incoming_overlap_tokens > 0:
                    finalized['overlap_token_count'] = incoming_overlap_tokens
                merged_chunks.append(finalized)

                pending_overlap_text = outgoing_text
                pending_overlap_tokens = outgoing_tokens
                pending_overlap_sentences = outgoing_sentences
                incoming_overlap_tokens = 0

                current = new_merged_chunk(hierarchy_key, config.preserve_hierarchy_levels)
                current['_token_count'] = 0
                current['_sentences'] = []
                current['_overlap_word_count'] = 0

                if pending_overlap_text:
                    current['texts'].append(pending_overlap_text)
                    current['_token_count'] = pending_overlap_tokens
                    current['_sentences'].extend(pending_overlap_sentences)
                    current['_overlap_word_count'] = len(pending_overlap_text.split())
                    incoming_overlap_tokens = pending_overlap_tokens
                    pending_overlap_text = None
                    pending_overlap_tokens = 0
                    pending_overlap_sentences = []

            current['texts'].append(chunk['text'])
            current['_token_count'] += chunk_tokens
            current['paragraph_ids'].append(chunk.get('paragraph_id'))
            current['source_chunks'].append(chunk)
            current['_sentences'].extend(chunk.get('sentences', []))

        if current['source_chunks'] and current['_token_count'] >= config.min_tokens:
            finalized = finalize_merged_chunk(current)
            if incoming_overlap_tokens > 0:
                finalized['overlap_token_count'] = incoming_overlap_tokens
            merged_chunks.append(finalized)
        elif current['source_chunks'] and config.preserve_small_chunks:
            finalized = finalize_merged_chunk(current)
            finalized['quality_flags'] = ['below_rag_minimum']
            if incoming_overlap_tokens > 0:
                finalized['overlap_token_count'] = incoming_overlap_tokens
            merged_chunks.append(finalized)

        return merged_chunks

    def _compute_overlap(
        self,
        sentences: List[str],
        config: TokenChunkConfig,
        tokenizer,
    ) -> tuple:
        if config.overlap_percent <= 0 or not sentences:
            return None, 0, []

        total_tokens = sum(_count_tokens(s, tokenizer) for s in sentences)
        target_overlap_tokens = int(total_tokens * config.overlap_percent)

        if target_overlap_tokens <= 0:
            return None, 0, []

        accumulated = 0
        start_idx = len(sentences)
        for i in range(len(sentences) - 1, -1, -1):
            accumulated += _count_tokens(sentences[i], tokenizer)
            start_idx = i
            if accumulated >= target_overlap_tokens:
                break

        if start_idx >= len(sentences):
            return None, 0, []

        overlap_sentences = sentences[start_idx:]
        overlap_text = ' '.join(overlap_sentences)
        return overlap_text, accumulated, list(overlap_sentences)

    def _split_code_block(
        self,
        chunk: Dict[str, Any],
        hierarchy_key: tuple,
        config: TokenChunkConfig,
        tokenizer,
    ) -> List[Dict[str, Any]]:
        from .code_chunking import split_code_at_boundaries

        text = chunk['text']
        language = chunk.get('_language_hint', '')

        counter = lambda t: _count_tokens(t, tokenizer)
        parts = split_code_at_boundaries(text, language, config.code_max_tokens, counter)

        if not parts:
            parts = [text]

        result_chunks = []
        for sub_text in parts:
            sub = new_merged_chunk(hierarchy_key, config.preserve_hierarchy_levels)
            sub_chunk = dict(chunk)
            sub_chunk['text'] = sub_text
            sub_chunk['word_count'] = len(sub_text.split())
            sub['texts'].append(sub_text)
            sub['paragraph_ids'].append(chunk.get('paragraph_id'))
            sub['source_chunks'].append(sub_chunk)
            result_chunks.append(finalize_merged_chunk(sub))

        return result_chunks

    def name(self) -> str:
        return "token_aware"


class SmallToBigChunkingStrategy(ChunkingStrategy):

    def apply(self, chunks: List[Dict[str, Any]], config: ChunkConfig) -> List[Dict[str, Any]]:
        if not isinstance(config, TokenChunkConfig):
            raise TypeError(
                f"SmallToBigChunkingStrategy requires TokenChunkConfig, got {type(config).__name__}"
            )

        tokenizer = _load_tokenizer_safe(config.tokenizer_name)

        parent_strategy = TokenAwareChunkingStrategy()
        parent_config = TokenChunkConfig(
            min_words=config.min_words,
            max_words=config.max_words,
            preserve_hierarchy_levels=config.preserve_hierarchy_levels,
            preserve_small_chunks=config.preserve_small_chunks,
            target_tokens=config.max_tokens * 2,
            min_tokens=config.max_tokens,
            max_tokens=config.max_tokens * 2,
            overlap_percent=0.0,
            code_max_tokens=config.code_max_tokens,
            max_absolute_tokens=config.max_absolute_tokens,
            tokenizer_name=config.tokenizer_name,
        )
        parents = parent_strategy.apply(chunks, parent_config)

        from .identifiers import stable_id as compute_stable_id
        from .chunking import split_sentences

        result = []
        for parent in parents:
            parent_id = parent['stable_id']

            if parent.get('content_type') == 'code':
                parent['chunk_level'] = 'standalone'
                result.append(parent)
                continue

            sentences = parent.get('sentences', [])
            if not sentences:
                sentences = split_sentences(parent['text'])

            children = []
            current_sents = []
            current_tokens = 0

            for sent in sentences:
                sent_tokens = _count_tokens(sent, tokenizer)

                if current_tokens + sent_tokens > config.max_tokens and current_sents:
                    children.append(self._build_child_chunk(
                        parent, current_sents, len(children), parent_id, compute_stable_id
                    ))
                    current_sents = []
                    current_tokens = 0

                current_sents.append(sent)
                current_tokens += sent_tokens

            if current_sents:
                children.append(self._build_child_chunk(
                    parent, current_sents, len(children), parent_id, compute_stable_id
                ))

            if len(children) <= 1:
                parent['chunk_level'] = 'standalone'
                result.append(parent)
            else:
                parent['chunk_level'] = 'parent'
                parent['child_chunk_ids'] = [c['stable_id'] for c in children]
                result.append(parent)
                result.extend(children)

        return result

    @staticmethod
    def _build_child_chunk(
        parent: Dict[str, Any],
        sents: List[str],
        child_idx: int,
        parent_id: str,
        compute_stable_id,
    ) -> Dict[str, Any]:
        child_text = ' '.join(sents)
        return {
            'stable_id': compute_stable_id(parent_id, str(child_idx)),
            'paragraph_id': parent['paragraph_id'],
            'text': child_text,
            'hierarchy': parent['hierarchy'],
            'chapter_href': parent.get('chapter_href', ''),
            'source_order': parent.get('source_order', 0),
            'source_tag': 'child_chunk',
            'text_length': len(child_text),
            'word_count': len(child_text.split()),
            'cross_references': [r for r in parent.get('cross_references', []) if r in child_text],
            'scripture_references': [r for r in parent.get('scripture_references', []) if r in child_text],
            'dates_mentioned': [r for r in parent.get('dates_mentioned', []) if r in child_text],
            'heading_path': parent.get('heading_path', ''),
            'hierarchy_depth': parent.get('hierarchy_depth', 0),
            'doc_stable_id': parent.get('doc_stable_id', ''),
            'sentence_count': len(sents),
            'sentences': list(sents),
            'normalized_text': child_text.lower(),
            'content_type': parent.get('content_type'),
            'parent_chunk_id': parent_id,
            'chunk_level': 'child',
        }

    def name(self) -> str:
        return "small_to_big"


# Strategy registry
STRATEGIES = {
    'nlp': ParagraphChunkingStrategy(),
    'paragraph': ParagraphChunkingStrategy(),
    'rag': SemanticChunkingStrategy(),
    'semantic': SemanticChunkingStrategy(),
    'embeddings': SemanticChunkingStrategy(),
    'token_aware': TokenAwareChunkingStrategy(),
    'technical': TokenAwareChunkingStrategy(),
    'small_to_big': SmallToBigChunkingStrategy(),
}


def get_strategy(name: str) -> ChunkingStrategy:
    if name not in STRATEGIES:
        available = ', '.join(STRATEGIES.keys())
        raise ValueError(
            f"Unknown chunking strategy: {name}. "
            f"Available: {available}"
        )
    return STRATEGIES[name]
