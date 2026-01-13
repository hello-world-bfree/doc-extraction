"""
Token-based re-chunking tool for embedding-based applications.

Transforms extraction library JSON output (word-based chunks) into
token-based chunks optimized for embedding models like embeddinggemma-300m.
Use this to prepare content for RAG systems, semantic search, and
recommendation engines.
"""

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Dict, Any, List, Iterator

from .tokenizer_utils import load_tokenizer, count_tokens
from .overlap_strategies import (
    create_overlapping_chunks,
    validate_and_split_oversized,
    TokenChunkConfig,
    RETRIEVAL_PRESET,
    RECOMMENDATION_PRESET,
    BALANCED_PRESET,
)


LOGGER = logging.getLogger(__name__)


def setup_logging(verbose: bool = False) -> None:
    """Configure logging level based on flags."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s: %(message)s",
        datefmt="%H:%M:%S",
    )


def determine_hierarchy(
    source_chunks: List[Dict[str, Any]],
    token_chunk_text: str,
    tokenizer
) -> tuple[Dict[str, Any], bool]:
    """Determine hierarchy for token chunk spanning multiple sources.

    Args:
        source_chunks: List of source chunks this token chunk spans
        token_chunk_text: Text of the token chunk
        tokenizer: Tokenizer instance

    Returns:
        Tuple of (hierarchy_dict, crossed_boundary_flag)
    """
    if len(source_chunks) == 1:
        return source_chunks[0].get('hierarchy', {}), False

    # Find chunk contributing most tokens via word overlap approximation
    token_chunk_words = set(token_chunk_text.lower().split())
    max_overlap = 0
    primary_hierarchy = {}

    for chunk in source_chunks:
        chunk_text = chunk.get('text', '')
        chunk_words = set(chunk_text.lower().split())
        overlap = len(token_chunk_words & chunk_words)

        if overlap > max_overlap:
            max_overlap = overlap
            primary_hierarchy = chunk.get('hierarchy', {})

    # Check if hierarchies differ
    hierarchies = [c.get('hierarchy', {}) for c in source_chunks]
    crossed_boundary = len(set(str(h) for h in hierarchies)) > 1

    if crossed_boundary:
        LOGGER.warning(
            f"Token chunk crosses hierarchy boundaries. "
            f"Using primary: {primary_hierarchy}"
        )

    return primary_hierarchy, crossed_boundary


def process_extraction_output(
    input_path: Path,
    config: TokenChunkConfig,
    tokenizer,
    preserve_metadata: bool = False
) -> Iterator[Dict[str, Any]]:
    """Process extraction JSON and yield token-based chunks.

    Args:
        input_path: Path to extraction library JSON output
        config: Token chunking configuration
        tokenizer: Tokenizer instance
        preserve_metadata: Whether to preserve scripture_references, etc.

    Yields:
        Dictionaries with 'text' and 'metadata' keys
    """
    with open(input_path) as f:
        data = json.load(f)

    doc_metadata = data.get('metadata', {})
    source_chunks = data.get('chunks', [])

    if not source_chunks:
        LOGGER.warning(f"No chunks found in {input_path}")
        return

    LOGGER.info(f"Processing {len(source_chunks)} source chunks from {input_path.name}")

    for source_chunk in source_chunks:
        # Get pre-split sentences (extraction library provides these)
        sentences = source_chunk.get('sentences', [])

        # Fallback: if no sentences, use full text as single sentence
        if not sentences or not any(s.strip() for s in sentences):
            text = source_chunk.get('text', '')
            if text.strip():
                sentences = [text]
            else:
                continue

        # Create overlapping token chunks
        token_chunks = create_overlapping_chunks(
            source_chunk.get('text', ''),
            sentences,
            tokenizer,
            config
        )

        for chunk_text, chunk_meta in token_chunks:
            # Validate and split if needed
            validated_chunks = validate_and_split_oversized(
                chunk_text, tokenizer, config
            )

            for final_text in validated_chunks:
                # Build metadata
                metadata = {
                    'doc_id': doc_metadata.get('provenance', {}).get('doc_id'),
                    'source_file': doc_metadata.get('provenance', {}).get('source_file'),
                    'hierarchy': source_chunk.get('hierarchy', {}),
                    'token_count': count_tokens(final_text, tokenizer),
                    'source_chunk_id': source_chunk.get('stable_id'),
                    'sentence_count': chunk_meta.get('sentence_count', 0),
                    'is_overlap': chunk_meta.get('is_overlap', False),
                }

                # Add optional metadata
                if preserve_metadata:
                    metadata.update({
                        'scripture_references': source_chunk.get('scripture_references', []),
                        'cross_references': source_chunk.get('cross_references', []),
                        'dates_mentioned': source_chunk.get('dates_mentioned', []),
                    })

                # Quality check: meets min/max tokens
                token_count = metadata['token_count']
                if token_count < config.min_tokens:
                    LOGGER.debug(
                        f"Skipping chunk with {token_count} tokens "
                        f"(below minimum {config.min_tokens})"
                    )
                    continue

                if token_count > config.max_tokens:
                    LOGGER.warning(
                        f"Chunk exceeds max tokens: {token_count} > {config.max_tokens}"
                    )

                # Skip empty chunks
                if not final_text.strip():
                    continue

                yield {'text': final_text, 'metadata': metadata}


def write_jsonl(chunks: Iterator[Dict[str, Any]], output_path: Path) -> int:
    """Write chunks to JSONL file.

    Args:
        chunks: Iterator of chunk dictionaries
        output_path: Output file path

    Returns:
        Number of chunks written
    """
    count = 0
    with open(output_path, 'w') as f:
        for chunk in chunks:
            f.write(json.dumps(chunk) + '\n')
            count += 1

    return count


def calculate_statistics(output_path: Path) -> Dict[str, Any]:
    """Calculate statistics from output JSONL file.

    Args:
        output_path: Path to JSONL file

    Returns:
        Dictionary of statistics
    """
    token_counts = []
    sentence_counts = []
    hierarchy_crossings = 0

    if not output_path.exists():
        return {
            'total_chunks': 0,
            'total_tokens': 0,
            'avg_tokens': 0,
            'min_tokens': 0,
            'max_tokens': 0,
            'avg_sentences': 0,
            'hierarchy_crossings': 0,
        }

    with open(output_path) as f:
        for line in f:
            chunk = json.loads(line)
            metadata = chunk.get('metadata', {})

            token_counts.append(metadata.get('token_count', 0))
            sentence_counts.append(metadata.get('sentence_count', 0))

            if metadata.get('crossed_hierarchy_boundary'):
                hierarchy_crossings += 1

    if not token_counts:
        return {
            'total_chunks': 0,
            'total_tokens': 0,
            'avg_tokens': 0,
            'min_tokens': 0,
            'max_tokens': 0,
            'avg_sentences': 0,
            'hierarchy_crossings': 0,
        }

    return {
        'total_chunks': len(token_counts),
        'total_tokens': sum(token_counts),
        'avg_tokens': sum(token_counts) / len(token_counts),
        'min_tokens': min(token_counts),
        'max_tokens': max(token_counts),
        'avg_sentences': sum(sentence_counts) / len(sentence_counts) if sentence_counts else 0,
        'hierarchy_crossings': hierarchy_crossings,
    }


def print_statistics(
    input_path: Path,
    output_path: Path,
    source_chunk_count: int,
    mode: str,
    stats: Dict[str, Any]
) -> None:
    """Print processing statistics.

    Args:
        input_path: Input file path
        output_path: Output file path
        source_chunk_count: Number of source chunks
        mode: Chunking mode (retrieval/recommendation/balanced)
        stats: Statistics dictionary
    """
    print(f"\nProcessed: {input_path.name} (mode: {mode})")
    print(f"  Source chunks: {source_chunk_count:,} (word-based)")
    print(f"  Output chunks: {stats['total_chunks']:,} (token-based)")
    print(f"  Total tokens: {stats['total_tokens']:,}")
    print(f"  Avg tokens/chunk: {stats['avg_tokens']:.1f}")
    print(f"  Min: {stats['min_tokens']}, Max: {stats['max_tokens']}")
    print(f"  Avg sentences/chunk: {stats['avg_sentences']:.1f}")

    if stats['hierarchy_crossings'] > 0:
        pct = (stats['hierarchy_crossings'] / stats['total_chunks']) * 100
        print(f"  Chunks with hierarchy crossing: {stats['hierarchy_crossings']} ({pct:.1f}%)")

    print(f"\nOutput: {output_path}")


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Re-chunk extraction library output for embedding-based applications (RAG, search, recommendations)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Retrieval/RAG mode (256-400 tokens, 15%% overlap)
  token-rechunk document.json --mode retrieval

  # Recommendation mode (512-700 tokens, 10%% overlap)
  token-rechunk document.json --mode recommendation

  # Custom chunk size
  token-rechunk document.json --min-tokens 300 --max-tokens 500

  # With statistics
  token-rechunk document.json --stats --verbose
        """
    )

    parser.add_argument(
        'input',
        type=Path,
        help="Input JSON file from extraction library"
    )

    parser.add_argument(
        '--output', '-o',
        type=Path,
        help="Output JSONL file (default: <input>_tokenized.jsonl)"
    )

    parser.add_argument(
        '--mode',
        choices=['retrieval', 'recommendation', 'balanced'],
        default='balanced',
        help="Chunking mode preset (default: balanced)"
    )

    parser.add_argument(
        '--min-tokens',
        type=int,
        help="Minimum tokens per chunk (overrides mode preset)"
    )

    parser.add_argument(
        '--max-tokens',
        type=int,
        help="Maximum tokens per chunk (overrides mode preset)"
    )

    parser.add_argument(
        '--overlap-percent',
        type=float,
        help="Overlap percentage between chunks (0.0-1.0, overrides mode preset)"
    )

    parser.add_argument(
        '--no-overlap',
        action='store_true',
        help="Disable chunk overlap"
    )

    parser.add_argument(
        '--preserve-metadata',
        action='store_true',
        help="Preserve scripture_references, cross_references, etc."
    )

    parser.add_argument(
        '--stats',
        action='store_true',
        help="Print statistics after processing"
    )

    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help="Verbose logging"
    )

    args = parser.parse_args()

    # Setup logging
    setup_logging(args.verbose)

    # Validate input
    if not args.input.exists():
        LOGGER.error(f"Input file not found: {args.input}")
        sys.exit(1)

    # Determine output path
    if args.output:
        output_path = args.output
    else:
        output_path = args.input.parent / f"{args.input.stem}_tokenized.jsonl"

    # Select config preset
    if args.mode == 'retrieval':
        config = RETRIEVAL_PRESET
    elif args.mode == 'recommendation':
        config = RECOMMENDATION_PRESET
    else:
        config = BALANCED_PRESET

    # Apply overrides
    if args.min_tokens:
        config.min_tokens = args.min_tokens
    if args.max_tokens:
        config.max_tokens = args.max_tokens
    if args.overlap_percent is not None:
        config.overlap_percent = args.overlap_percent
    if args.no_overlap:
        config.overlap_percent = 0.0

    LOGGER.info(f"Loading tokenizer: {config.tokenizer_name}")
    tokenizer = load_tokenizer(config.tokenizer_name)

    # Count source chunks for statistics
    with open(args.input) as f:
        data = json.load(f)
        source_chunk_count = len(data.get('chunks', []))

    # Process and write
    LOGGER.info(f"Processing {args.input} → {output_path}")
    chunks = process_extraction_output(
        args.input,
        config,
        tokenizer,
        preserve_metadata=args.preserve_metadata
    )

    chunk_count = write_jsonl(chunks, output_path)
    LOGGER.info(f"✓ Wrote {chunk_count:,} chunks to {output_path}")

    # Print statistics
    if args.stats:
        stats = calculate_statistics(output_path)
        print_statistics(
            args.input,
            output_path,
            source_chunk_count,
            args.mode,
            stats
        )

    print(f"\n✅ {args.input.name}")
    print(f"   • chunks: {chunk_count:,}")
    print(f"   • output: {output_path}")


if __name__ == '__main__':
    main()
