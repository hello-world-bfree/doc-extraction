"""
Noise filtering for extraction pipeline.

Detects and filters chunks with low semantic value for embeddings:
- Index pages
- Reference lists
- Number-heavy content
- Navigation/TOC fragments
- Copyright/legal boilerplate
"""
import re
from typing import Dict, Any


class NoiseFilter:
    """
    Multi-tier noise detection for chunks.

    Designed to catch content that has zero semantic value for embeddings
    while preserving all legitimate content chunks.
    """

    @staticmethod
    def is_index_page(chunk: Dict[str, Any]) -> bool:
        """
        Detect index/reference list pages.

        Characteristics:
        - High number density (>50% of tokens are numbers/punctuation)
        - Repetitive patterns (number sequences, reference formats)
        - High token/word ratio (lots of symbols)

        Examples:
        - "1, Part 1 109 24 8* 27 133* 356 109*, 133* 357 108..."
        - "Genesis 1:1-31 ... 2:1-25 ... 3:1-24 ..."
        """
        text = chunk.get('text', '').strip()
        if not text:
            return False

        tokens = text.split()
        if not tokens:
            return False

        # Check 1: High number density
        number_tokens = sum(1 for t in tokens if re.match(r'^[\d\*,\.\-:;]+$', t))
        number_ratio = number_tokens / len(tokens)

        if number_ratio > 0.5:
            return True

        # Check 2: Repetitive reference patterns
        # Matches: "123 45* 678" or "1:1-31 2:1-25" patterns
        reference_pattern = r'(?:\d+[\*,\.\-:;\s]+){5,}'
        if re.search(reference_pattern, text):
            # Verify it's mostly numbers
            nums_in_text = len(re.findall(r'\d+', text))
            if nums_in_text > len(tokens) * 0.3:  # 30%+ of tokens contain numbers
                return True

        # Check 3: High token/word ratio (indicates special chars/symbols)
        word_count = len(tokens)
        token_count = chunk.get('token_count', 0)
        if word_count > 0 and token_count > 0:
            ratio = token_count / word_count
            # Normal text: ~1.3 tokens/word
            # Index pages: ~3+ tokens/word due to symbols
            if ratio > 2.5 and number_ratio > 0.3:
                return True

        return False

    @staticmethod
    def is_navigation_fragment(chunk: Dict[str, Any]) -> bool:
        """
        Detect navigation/TOC fragments.

        Examples:
        - "Chapter 1 ... 5"
        - "Next | Previous | Home"
        - "Table of Contents"
        """
        text = chunk.get('text', '').strip().lower()
        hierarchy = chunk.get('hierarchy', {})
        level_1 = hierarchy.get('level_1', '').lower()

        # TOC/Index in hierarchy
        if any(kw in level_1 for kw in ['table of contents', 'index', 'contents']):
            word_count = chunk.get('word_count', 0)
            if word_count < 20:  # Short chunks in TOC/index sections
                return True

        # Navigation keywords
        nav_patterns = [
            r'^\s*(next|previous|home|back|forward|up)\s*$',
            r'^\s*(chapter|section|part)\s+\d+\s*$',
            r'^\s*page\s+\d+\s*$',
        ]
        for pattern in nav_patterns:
            if re.match(pattern, text):
                return True

        return False

    @staticmethod
    def is_copyright_boilerplate(chunk: Dict[str, Any]) -> bool:
        """
        Detect copyright/legal boilerplate.

        Examples:
        - Copyright notices
        - ISBN numbers
        - Publisher info (when standalone)
        """
        text = chunk.get('text', '').strip().lower()

        # Copyright patterns
        if re.search(r'©|\bcopyright\b|\ball rights reserved\b', text):
            word_count = chunk.get('word_count', 0)
            if word_count < 50:  # Short copyright notices
                return True

        # ISBN/Publisher codes
        if re.search(r'\bisbn\b|publisher code|catalog number', text):
            return True

        return False

    @staticmethod
    def has_low_semantic_value(chunk: Dict[str, Any]) -> bool:
        """
        Detect chunks with low semantic value for embeddings.

        Combines all noise detection heuristics.
        """
        if NoiseFilter.is_index_page(chunk):
            return True

        if NoiseFilter.is_navigation_fragment(chunk):
            return True

        if NoiseFilter.is_copyright_boilerplate(chunk):
            return True

        return False

    @staticmethod
    def filter_chunks(chunks: list[Dict[str, Any]], verbose: bool = False) -> tuple[list[Dict[str, Any]], int]:
        """
        Filter noise chunks from a list.

        Args:
            chunks: List of chunk dictionaries
            verbose: Print filtered chunk IDs

        Returns:
            (filtered_chunks, num_filtered)
        """
        filtered = []
        num_filtered = 0

        for chunk in chunks:
            if NoiseFilter.has_low_semantic_value(chunk):
                if verbose:
                    chunk_id = chunk.get('chunk_id', chunk.get('stable_id', 'unknown'))
                    reason = 'index' if NoiseFilter.is_index_page(chunk) else 'nav/boilerplate'
                    print(f"  Filtered ({reason}): {chunk_id}")
                num_filtered += 1
            else:
                filtered.append(chunk)

        return filtered, num_filtered


def scan_corpus_for_noise(corpus_file: str, sample_size: int = 0) -> Dict[str, Any]:
    """
    Scan JSONL corpus file for noise chunks.

    Args:
        corpus_file: Path to JSONL file
        sample_size: If >0, only scan first N chunks

    Returns:
        Statistics dict with noise detection results
    """
    import json

    total = 0
    noise_count = 0
    noise_chunks = []

    with open(corpus_file) as f:
        for i, line in enumerate(f):
            if sample_size > 0 and i >= sample_size:
                break

            chunk = json.loads(line)
            total += 1

            if NoiseFilter.has_low_semantic_value(chunk):
                noise_count += 1
                chunk_id = chunk.get('chunk_id', chunk.get('stable_id', 'unknown'))
                reason = []
                if NoiseFilter.is_index_page(chunk):
                    reason.append('index')
                if NoiseFilter.is_navigation_fragment(chunk):
                    reason.append('navigation')
                if NoiseFilter.is_copyright_boilerplate(chunk):
                    reason.append('copyright')

                noise_chunks.append({
                    'chunk_id': chunk_id,
                    'reason': '+'.join(reason),
                    'text_preview': chunk.get('text', '')[:100],
                    'word_count': chunk.get('word_count', 0),
                    'token_count': chunk.get('token_count', 0),
                })

    return {
        'total_scanned': total,
        'noise_detected': noise_count,
        'noise_rate': noise_count / total if total > 0 else 0,
        'noise_chunks': noise_chunks,
    }
