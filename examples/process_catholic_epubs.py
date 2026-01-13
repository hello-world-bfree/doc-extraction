#!/usr/bin/env python3
"""
Process Catholic EPUB documents with noise filtering.

This example demonstrates how to extract Catholic EPUB documents with
automatic noise filtering enabled by default (v2.4+).

Usage:
    python examples/process_catholic_epubs.py path/to/epubs/ output_dir/
"""

import sys
import json
from pathlib import Path

sys.path.insert(0, 'src')

from extraction.extractors import EpubExtractor
from extraction.analyzers import CatholicAnalyzer
from extraction.core.output import write_outputs


def process_epub(epub_path: Path, output_dir: Path, analyzer: CatholicAnalyzer):
    """
    Process a single EPUB with noise filtering.

    Noise filtering is ENABLED BY DEFAULT (v2.4+).
    Removes:
    - Index pages
    - Copyright boilerplate
    - Navigation fragments (TOC, page numbers)
    """
    print(f"📖 Processing: {epub_path.name}")

    # Configuration for Catholic document extraction
    config = {
        # Chunking strategy: RAG mode (optimal for embeddings)
        'chunking_strategy': 'rag',
        'min_chunk_words': 100,
        'max_chunk_words': 500,

        # Noise filtering (NEW in v2.4)
        'filter_noise': True,  # ← This is the default, can omit

        # Tiny chunk filtering (v2.2)
        'filter_tiny_chunks': 'conservative',  # Removes <5 word fragments

        # EPUB-specific settings
        'preserve_hierarchy_across_docs': True,
        'toc_hierarchy_level': 1,
    }

    # Extract
    extractor = EpubExtractor(str(epub_path), config)
    extractor.load()
    extractor.parse()
    metadata = extractor.extract_metadata()

    # Enrich with Catholic analyzer
    full_text = " ".join(c.text for c in extractor.chunks)
    enriched_metadata = analyzer.enrich_metadata(
        base_metadata=metadata.to_dict(),
        full_text=full_text,
        chunks=[c.to_dict() for c in extractor.chunks]
    )

    # Update metadata
    for key, value in enriched_metadata.items():
        setattr(metadata, key, value)

    # Write outputs
    basename = epub_path.stem
    write_outputs(
        extractor=extractor,
        output_dir=str(output_dir),
        base_filename=basename,
        ndjson=True  # For LLM/vector DB ingestion
    )

    print(f"  ✅ Extracted {len(extractor.chunks)} chunks")
    return len(extractor.chunks)


def main():
    if len(sys.argv) < 3:
        print("Usage: python examples/process_catholic_epubs.py <epub_dir> <output_dir>")
        print("Example: python examples/process_catholic_epubs.py ./catholic_epubs ./outputs")
        sys.exit(1)

    epub_dir = Path(sys.argv[1])
    output_dir = Path(sys.argv[2])

    if not epub_dir.exists():
        print(f"❌ Error: Directory not found: {epub_dir}")
        sys.exit(1)

    # Create output directory
    output_dir.mkdir(parents=True, exist_ok=True)

    # Find all EPUBs
    epub_files = list(epub_dir.glob("**/*.epub"))
    if not epub_files:
        print(f"❌ No EPUB files found in {epub_dir}")
        sys.exit(1)

    print(f"📚 Found {len(epub_files)} EPUB file(s)")
    print(f"📁 Output directory: {output_dir}")
    print()
    print("⚙️  Extraction settings:")
    print("  - Chunking: RAG mode (100-500 words)")
    print("  - Noise filtering: ENABLED (v2.4)")
    print("  - Tiny chunk filtering: Conservative (v2.2)")
    print("  - Domain analyzer: Catholic")
    print()

    # Process all EPUBs
    analyzer = CatholicAnalyzer()
    total_chunks = 0

    for epub_path in epub_files:
        try:
            chunk_count = process_epub(epub_path, output_dir, analyzer)
            total_chunks += chunk_count
        except Exception as e:
            print(f"  ❌ Error processing {epub_path.name}: {e}")
            continue

    print()
    print("✅ Processing complete!")
    print(f"  Documents: {len(epub_files)}")
    print(f"  Total chunks: {total_chunks:,}")
    print(f"  Avg chunks/doc: {total_chunks / len(epub_files):.1f}")
    print()
    print("🧹 Filters applied:")
    print("  1. Noise filter: Index pages, copyright, navigation (v2.4)")
    print("  2. Tiny chunk filter: <5 word fragments (v2.2)")
    print()
    print("📁 Output files:")
    print(f"  - JSON: {output_dir}/*.json")
    print(f"  - NDJSON: {output_dir}/*.ndjson")


if __name__ == '__main__':
    main()
