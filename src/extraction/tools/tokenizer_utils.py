"""
Tokenizer utilities for embeddinggemma-300m.

Provides tokenizer loading, caching, and token counting functions.
"""

from functools import lru_cache
from typing import List
from transformers import AutoTokenizer


@lru_cache(maxsize=1)
def load_tokenizer(model_name: str = "google/embeddinggemma-300m"):
    """Load and cache embeddinggemma-300m tokenizer.

    Uses AutoTokenizer to load the exact SentencePiece tokenizer
    from HuggingFace. Cached for performance across multiple calls.

    Args:
        model_name: HuggingFace model ID (default: google/embeddinggemma-300m)

    Returns:
        Cached tokenizer instance

    Example:
        >>> tokenizer = load_tokenizer()
        >>> tokens = tokenizer.encode("Hello world")
    """
    return AutoTokenizer.from_pretrained(model_name)


def count_tokens(text: str, tokenizer) -> int:
    """Count tokens in text including special tokens.

    Args:
        text: Text to tokenize
        tokenizer: Tokenizer instance from load_tokenizer()

    Returns:
        Number of tokens (including special tokens like BOS/EOS)

    Example:
        >>> tokenizer = load_tokenizer()
        >>> count = count_tokens("This is a test.", tokenizer)
        >>> print(count)  # 6 (approximate)
    """
    if not text or not text.strip():
        return 0
    return len(tokenizer.encode(text, add_special_tokens=True))


def tokenize_batch(texts: List[str], tokenizer) -> List[int]:
    """Batch tokenize texts for efficiency.

    Args:
        texts: List of texts to tokenize
        tokenizer: Tokenizer instance from load_tokenizer()

    Returns:
        List of token counts for each text

    Example:
        >>> tokenizer = load_tokenizer()
        >>> counts = tokenize_batch(["First text.", "Second text."], tokenizer)
        >>> print(counts)  # [4, 4] (approximate)
    """
    if not texts:
        return []

    encodings = tokenizer(texts, add_special_tokens=True)
    return [len(ids) for ids in encodings['input_ids']]
