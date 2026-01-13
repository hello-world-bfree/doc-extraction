"""
Sentence-aware overlapping chunk strategies for embeddings.

Implements overlapping chunking that respects sentence boundaries
while targeting specific token counts for embedding models.
"""

import logging
from dataclasses import dataclass
from typing import List, Tuple, Dict, Any

from .tokenizer_utils import count_tokens


LOGGER = logging.getLogger(__name__)


@dataclass
class TokenChunkConfig:
    """Configuration for token-based chunking."""
    target_tokens: int
    min_tokens: int
    max_tokens: int
    overlap_percent: float = 0.10
    max_absolute_tokens: int = 2048
    tokenizer_name: str = "google/embeddinggemma-300m"
    sentence_boundary_aware: bool = True


# Task-specific presets
RETRIEVAL_PRESET = TokenChunkConfig(
    target_tokens=320,
    min_tokens=256,
    max_tokens=400,
    overlap_percent=0.15,
)

RECOMMENDATION_PRESET = TokenChunkConfig(
    target_tokens=600,
    min_tokens=512,
    max_tokens=700,
    overlap_percent=0.10,
)

BALANCED_PRESET = TokenChunkConfig(
    target_tokens=450,
    min_tokens=400,
    max_tokens=512,
    overlap_percent=0.10,
)


def find_overlap_start(
    sentences: List[str],
    target_overlap_tokens: int,
    tokenizer
) -> int:
    """Find sentence index to start overlap (working backwards from end).

    Args:
        sentences: List of sentences in current chunk
        target_overlap_tokens: Target number of tokens for overlap
        tokenizer: Tokenizer instance

    Returns:
        Index of first sentence to include in overlap
    """
    if not sentences or target_overlap_tokens <= 0:
        return 0

    accumulated_tokens = 0
    for i in range(len(sentences) - 1, -1, -1):
        sent_tokens = count_tokens(sentences[i], tokenizer)
        accumulated_tokens += sent_tokens

        if accumulated_tokens >= target_overlap_tokens:
            return i

    return 0


def create_overlapping_chunks(
    text: str,
    sentences: List[str],
    tokenizer,
    config: TokenChunkConfig
) -> List[Tuple[str, Dict[str, Any]]]:
    """Create overlapping chunks respecting sentence boundaries.

    Args:
        text: Full text (not used, sentences are primary input)
        sentences: Pre-split sentences from extraction library
        tokenizer: Tokenizer instance
        config: Chunking configuration

    Returns:
        List of (chunk_text, metadata) tuples

    Example:
        >>> tokenizer = load_tokenizer()
        >>> config = RETRIEVAL_PRESET
        >>> chunks = create_overlapping_chunks(
        ...     "full text",
        ...     ["Sentence 1.", "Sentence 2.", "Sentence 3."],
        ...     tokenizer,
        ...     config
        ... )
    """
    if not sentences:
        return []

    chunks = []
    current_sentences = []
    current_tokens = 0
    overlap_start_idx = None
    sentence_start_idx = 0

    for i, sentence in enumerate(sentences):
        # Skip empty sentences
        if not sentence.strip():
            continue

        sent_tokens = count_tokens(sentence, tokenizer)

        # Check if adding this sentence would exceed max_tokens
        if current_tokens + sent_tokens > config.max_tokens and current_sentences:
            # Finalize current chunk
            chunk_text = ' '.join(current_sentences)
            chunk_metadata = {
                'token_count': current_tokens,
                'sentence_indices': (sentence_start_idx, i - 1),
                'sentence_count': len(current_sentences),
                'is_overlap': overlap_start_idx is not None,
            }

            chunks.append((chunk_text, chunk_metadata))

            # Calculate overlap for next chunk
            overlap_tokens = int(current_tokens * config.overlap_percent)
            overlap_start_idx = find_overlap_start(
                current_sentences, overlap_tokens, tokenizer
            )

            # Start next chunk with overlap
            if overlap_start_idx < len(current_sentences):
                current_sentences = current_sentences[overlap_start_idx:]
                current_tokens = sum(
                    count_tokens(s, tokenizer) for s in current_sentences
                )
                sentence_start_idx = sentence_start_idx + overlap_start_idx
            else:
                current_sentences = []
                current_tokens = 0
                sentence_start_idx = i

        current_sentences.append(sentence)
        current_tokens += sent_tokens

    # Finalize last chunk if it meets minimum
    if current_sentences and current_tokens >= config.min_tokens:
        chunk_text = ' '.join(current_sentences)
        chunk_metadata = {
            'token_count': current_tokens,
            'sentence_indices': (sentence_start_idx, len(sentences) - 1),
            'sentence_count': len(current_sentences),
            'is_overlap': overlap_start_idx is not None,
        }
        chunks.append((chunk_text, chunk_metadata))
    elif current_sentences:
        # Log if we're dropping a chunk below minimum
        LOGGER.debug(
            f"Dropping chunk with {current_tokens} tokens (below minimum {config.min_tokens})"
        )

    return chunks


def validate_and_split_oversized(
    chunk_text: str,
    tokenizer,
    config: TokenChunkConfig
) -> List[str]:
    """Validate chunk doesn't exceed 2048 token limit and split if needed.

    Args:
        chunk_text: Text to validate
        tokenizer: Tokenizer instance
        config: Configuration with max_absolute_tokens limit

    Returns:
        List of chunks (split if oversized, otherwise single chunk)
    """
    token_count = count_tokens(chunk_text, tokenizer)

    if token_count <= config.max_absolute_tokens:
        return [chunk_text]

    LOGGER.warning(
        f"Chunk exceeds {config.max_absolute_tokens} tokens ({token_count}). "
        f"Splitting at sentence boundaries."
    )

    # Split into sentences and re-chunk
    sentences = chunk_text.split('. ')
    sub_chunks = []
    current = []
    current_tokens = 0

    for sentence in sentences:
        # Re-add period (was split off)
        if not sentence.endswith('.'):
            sentence = sentence + '.'

        sent_tokens = count_tokens(sentence, tokenizer)

        if current_tokens + sent_tokens > config.max_absolute_tokens:
            if current:
                sub_chunks.append(' '.join(current))
            current = [sentence]
            current_tokens = sent_tokens
        else:
            current.append(sentence)
            current_tokens += sent_tokens

    if current:
        sub_chunks.append(' '.join(current))

    return sub_chunks
