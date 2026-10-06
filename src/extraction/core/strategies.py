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
    allow_word_estimate: bool = False


# --- Shared helpers ---

_SKIPPABLE_SECTIONS = {'index', 'table of contents', 'contents', 'toc'}

# A genuine TOC/index is navigation (a list of links and page numbers) and stays
# small even for large books. Some epubs, however, name the BODY document itself
# "Contents" in the nav, which stamps level_1='Contents' on every paragraph; that
# section then holds the entire book. Only treat a skippable-named section as real
# front matter when its total prose is below this cap, so a mislabeled body is not
# discarded wholesale (which produced 0 chunks → ParseError "No chunks available").
# Large books carry large indexes, though (5,352 words before the noise filter in a
# 152-book corpus), so the word cap alone keeps them; a section must also exceed
# this share of the document to be kept. Real navigation measured at most 3.06% of
# its book; a mislabeled body is nearly all of it.
_SKIPPABLE_MAX_WORDS = 2000
_SKIPPABLE_MAX_SHARE = 0.10


def is_skippable_heading(text: str) -> bool:
    return (text or "").strip().lower() in _SKIPPABLE_SECTIONS


def _skippable_subtree(hierarchy: Dict[str, str]) -> Optional[tuple]:
    for i in range(1, 7):
        if is_skippable_heading(hierarchy.get(f"level_{i}")):
            return tuple(hierarchy.get(f"level_{j}", "") for j in range(1, i + 1))
    return None


def _word_count(chunk: Dict[str, Any]) -> int:
    return chunk.get('word_count') or len(chunk.get('text', '').split())


def drop_skippable_sections(chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Drop contents/index sections at any heading level, unless one is too large to be navigation."""
    document_words = sum(_word_count(c) for c in chunks)
    section_words: Dict[tuple, int] = defaultdict(int)
    for chunk in chunks:
        subtree = _skippable_subtree(chunk.get('hierarchy', {}))
        if subtree is not None:
            section_words[subtree] += _word_count(chunk)

    def keep(chunk: Dict[str, Any]) -> bool:
        subtree = _skippable_subtree(chunk.get('hierarchy', {}))
        if subtree is None:
            return True
        words = section_words[subtree]
        return words > _SKIPPABLE_MAX_WORDS and words > _SKIPPABLE_MAX_SHARE * document_words

    return [c for c in chunks if keep(c)]


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

        for chunk in drop_skippable_sections(chunks):
            h = chunk.get('hierarchy', {})
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


def _load_tokenizer(tokenizer_name: str, allow_word_estimate: bool):
    try:
        from extraction.tools.tokenizer_utils import load_tokenizer
        return load_tokenizer(tokenizer_name)
    except (ImportError, OSError) as e:
        if not allow_word_estimate:
            from ..exceptions import DependencyError
            raise DependencyError(
                f"tokenizer '{tokenizer_name}'",
                "token-aware chunking",
                "uv pip install 'doc-extraction[embeddings]' and export HF_TOKEN "
                "(the model is gated), or set allow_word_estimate=True",
            ) from e
        LOGGER.warning(
            f"Could not load tokenizer '{tokenizer_name}': {e}. "
            "Falling back to word-count approximation (1 word ≈ 1.5 tokens)."
        )
        return None


def _count_tokens(text: str, tokenizer) -> int:
    if tokenizer is None:
        return _estimate_tokens_from_words(len(text.split()))
    from extraction.tools.tokenizer_utils import count_tokens
    return count_tokens(text, tokenizer)


def _split_by_chars(word: str, budget: int, tokenizer) -> List[str]:
    if len(word) <= 1 or _count_tokens(word, tokenizer) <= budget:
        return [word]
    mid = len(word) // 2
    return _split_by_chars(word[:mid], budget, tokenizer) + _split_by_chars(word[mid:], budget, tokenizer)


def _split_by_words(text: str, budget: int, tokenizer) -> List[str]:
    parts: List[str] = []
    current: List[str] = []
    for word in text.split():
        if _count_tokens(word, tokenizer) > budget:
            if current:
                parts.append(' '.join(current))
                current = []
            parts.extend(_split_by_chars(word, budget, tokenizer))
            continue
        if current and _count_tokens(' '.join(current + [word]), tokenizer) > budget:
            parts.append(' '.join(current))
            current = []
        current.append(word)
    if current:
        parts.append(' '.join(current))
    return parts


def _unit_pieces(chunk: Dict[str, Any], max_tokens: int, tokenizer):
    """Yield (text, sentences) pieces of a unit, each at most max_tokens: the whole unit, else its sentences."""
    text = chunk['text']
    if _count_tokens(text, tokenizer) <= max_tokens:
        yield text, list(chunk.get('sentences') or [text])
        return
    from .chunking import split_sentences
    for sentence in split_sentences(text):
        if _count_tokens(sentence, tokenizer) <= max_tokens:
            yield sentence, [sentence]
        else:
            for part in _split_by_words(sentence, max_tokens, tokenizer):
                yield part, [part]


class _TokenPacker:
    """Packs one section's pieces into chunks of at most max_tokens, overlap included.

    A chunk closes once it holds min_tokens and the next piece would pass the target, or at
    section end. Below min_tokens it keeps filling, splitting the next piece to fit max_tokens.
    """

    def __init__(self, hierarchy_key, config: TokenChunkConfig, tokenizer, compute_overlap, out):
        self._key = hierarchy_key
        self._config = config
        self._tokenizer = tokenizer
        self._compute_overlap = compute_overlap
        self._out = out
        self._pending_overlap: Optional[tuple] = None
        self._reset()

    def _reset(self) -> None:
        self._texts: List[str] = []
        self._sources: List[Dict[str, Any]] = []
        self._paragraph_ids: List[Any] = []
        self._sentences: List[str] = []
        self._unit = None
        self._incoming: Optional[tuple] = None

    def _render(self, texts: List[str]) -> str:
        return '\n\n'.join(([self._incoming[0]] if self._incoming else []) + texts)

    def _tokens(self, texts: List[str]) -> int:
        return _count_tokens(self._render(texts), self._tokenizer)

    def _with(self, text: str, unit) -> List[str]:
        if self._texts and self._unit is unit:
            return self._texts[:-1] + [self._texts[-1] + ' ' + text]
        return self._texts + [text]

    def _open(self, text: str) -> None:
        pending, self._pending_overlap = self._pending_overlap, None
        if not pending:
            return
        overlap_text, _, overlap_sentences = pending
        sentences = list(overlap_sentences)
        while sentences:
            self._incoming = (' '.join(sentences), sentences)
            if self._tokens([text]) <= self._config.max_tokens:
                return
            sentences = sentences[1:]
        self._incoming = None

    def _append(self, text: str, sentences: List[str], unit) -> None:
        if self._texts and self._unit is unit:
            self._texts[-1] = self._texts[-1] + ' ' + text
            source = self._sources[-1]
            source['text'] = self._texts[-1]
            source['sentences'] = source['sentences'] + list(sentences)
            source['word_count'] = len(source['text'].split())
            source['text_length'] = len(source['text'])
        else:
            self._texts.append(text)
            if text == unit['text']:
                source = unit
            else:
                source = dict(unit)
                source.update(text=text, sentences=list(sentences), word_count=len(text.split()),
                              text_length=len(text), footnote_citations=None)
            self._sources.append(source)
            self._paragraph_ids.append(unit.get('paragraph_id'))
        self._sentences.extend(sentences)
        self._unit = unit

    def _fill(self, text: str, sentences: List[str], unit) -> tuple:
        """Split the longest prefix of a piece that still fits max_tokens; return (head, head_sents, rest, rest_sents).

        Whole sentences first; if the chunk is still under min_tokens, words of the next sentence.
        """
        limit = self._config.max_tokens
        head: List[str] = []
        for sentence in sentences:
            if self._tokens(self._with(' '.join(head + [sentence]), unit)) > limit:
                break
            head.append(sentence)
        rest = list(sentences[len(head):])
        if rest and (not head or self._tokens(self._with(' '.join(head), unit)) < self._config.min_tokens):
            words = rest[0].split()
            taken: List[str] = []
            for word in words:
                if self._tokens(self._with(' '.join(head + taken + [word]), unit)) > limit:
                    break
                taken.append(word)
            if taken:
                head.append(' '.join(taken))
                remainder = ' '.join(words[len(taken):])
                rest = ([remainder] if remainder else []) + rest[1:]
        if not head:
            return '', [], text, sentences
        return ' '.join(head), head, ' '.join(rest), rest

    def add(self, piece: tuple, unit: Dict[str, Any]) -> None:
        text, sentences = piece
        config = self._config
        while text:
            if not self._texts:
                self._open(text)
                self._append(text, sentences, unit)
                return
            current = self._tokens(self._texts)
            candidate = self._tokens(self._with(text, unit))
            if current >= config.min_tokens:
                if candidate > min(config.target_tokens, config.max_tokens):
                    self.close(carry_overlap=True)
                    continue
                self._append(text, sentences, unit)
                return
            if candidate <= config.max_tokens:
                self._append(text, sentences, unit)
                return
            head, head_sentences, text, sentences = self._fill(text, sentences, unit)
            if head:
                self._append(head, head_sentences, unit)
            self.close(carry_overlap=True)

    def close(self, carry_overlap: bool, section_end: bool = False) -> None:
        if not self._texts:
            self._pending_overlap = None
            self._reset()
            return
        config = self._config
        merged = new_merged_chunk(self._key, config.preserve_hierarchy_levels)
        merged['texts'] = ([self._incoming[0]] if self._incoming else []) + self._texts
        merged['paragraph_ids'] = self._paragraph_ids
        merged['source_chunks'] = self._sources
        finalized = finalize_merged_chunk(merged)

        tokens = _count_tokens(finalized['text'], self._tokenizer)
        if tokens > config.max_absolute_tokens:
            raise AssertionError(
                f"packed chunk has {tokens} tokens, over max_absolute_tokens={config.max_absolute_tokens}; "
                "units should have been split to max_tokens"
            )
        if self._incoming:
            finalized['overlap_token_count'] = _count_tokens(self._incoming[0], self._tokenizer)
        keep = True
        if tokens < config.min_tokens:
            finalized['quality_flags'] = ['below_rag_minimum']
            keep = config.preserve_small_chunks or not section_end
        if keep:
            self._out.append(finalized)

        self._pending_overlap = (
            self._compute_overlap(self._sentences, config, self._tokenizer) if carry_overlap else None
        )
        if self._pending_overlap and self._pending_overlap[0] is None:
            self._pending_overlap = None
        self._reset()


class TokenAwareChunkingStrategy(ChunkingStrategy):

    def apply(self, chunks: List[Dict[str, Any]], config: ChunkConfig) -> List[Dict[str, Any]]:
        if not isinstance(config, TokenChunkConfig):
            raise TypeError(
                f"TokenAwareChunkingStrategy requires TokenChunkConfig, got {type(config).__name__}"
            )

        tokenizer = _load_tokenizer(config.tokenizer_name, config.allow_word_estimate)

        hierarchy_groups = defaultdict(list)
        for chunk in drop_skippable_sections(chunks):
            h = chunk.get('hierarchy', {})
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
        merged_chunks: List[Dict[str, Any]] = []
        packer = _TokenPacker(hierarchy_key, config, tokenizer, self._compute_overlap, merged_chunks)

        for chunk in group_chunks:
            if chunk.get('content_type') == 'code':
                packer.close(carry_overlap=False)
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

            for piece in _unit_pieces(chunk, config.max_tokens, tokenizer):
                packer.add(piece, chunk)

        packer.close(carry_overlap=False, section_end=True)
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

        tokenizer = _load_tokenizer(config.tokenizer_name, config.allow_word_estimate)

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
            allow_word_estimate=config.allow_word_estimate,
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
