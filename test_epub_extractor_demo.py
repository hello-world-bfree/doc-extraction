#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Demo showing the refactored EpubExtractor in action.
"""

import json
from pathlib import Path
from src.extraction.extractors import EpubExtractor


def main():
    # Test file
    epub_path = "catholic_sources/Prayer_Primer.epub"

    if not Path(epub_path).exists():
        print(f"❌ Test file not found: {epub_path}")
        return 1

    print("=" * 70)
    print("EPUB Extractor Demo - Refactored Version")
    print("=" * 70)

    # Initialize extractor
    print(f"\n📖 Loading: {epub_path}")
    extractor = EpubExtractor(epub_path)

    # Load EPUB
    extractor.load()
    print(f"✓ Loaded EPUB with {len(extractor.href_to_toc_title)} TOC entries")
    print(f"✓ Document ID: {extractor.provenance.doc_id}")
    print(f"✓ Content hash: {extractor.provenance.content_hash[:16]}...")

    # Parse and extract chunks
    print("\n⚙️  Parsing document...")
    extractor.parse()
    print(f"✓ Extracted {len(extractor.chunks_dict)} chunks")
    print(f"✓ Quality route: {extractor.route}")
    print(f"✓ Quality score: {extractor.quality_score:.4f}")

    # Extract metadata
    print("\n📋 Extracting metadata...")
    metadata = extractor.extract_metadata()
    print(f"✓ Title: {metadata.title}")
    print(f"✓ Author: {metadata.author}")
    print(f"✓ Language: {metadata.language}")
    print(f"✓ Publisher: {metadata.publisher}")
    print(f"✓ Subjects: {', '.join(metadata.subject[:3])}{'...' if len(metadata.subject) > 3 else ''}")
    print(f"✓ Key themes: {len(metadata.key_themes)} identified")

    # Get full output
    print("\n📦 Building output data...")
    output = extractor.get_output_data()
    print(f"✓ Output structure keys: {list(output.keys())}")
    print(f"✓ Metadata fields: {len(output['metadata'])}")
    print(f"✓ Chunks: {len(output['chunks'])}")

    # Show sample chunk
    if output['chunks']:
        chunk = output['chunks'][0]
        print("\n📄 Sample chunk:")
        print(f"   ID: {chunk['stable_id']}")
        print(f"   Paragraph: {chunk['paragraph_id']}")
        print(f"   Words: {chunk['word_count']}")
        print(f"   Hierarchy depth: {chunk['hierarchy_depth']}")
        print(f"   Heading path: {chunk['heading_path'] or '(root level)'}")
        print(f"   Text preview: {chunk['text'][:100]}...")

    # Show extraction info
    print("\n📊 Extraction info:")
    for key, value in output['extraction_info'].items():
        if isinstance(value, str) and len(value) > 50:
            value = value[:47] + "..."
        print(f"   {key}: {value}")

    # Verify backward compatibility markers
    print("\n✅ Backward compatibility checks:")
    print(f"   ✓ Parser version: {output['extraction_info']['parser_version']}")
    print(f"   ✓ Schema version: {output['extraction_info']['md_schema_version']}")
    print(f"   ✓ Provenance present: {'provenance' in output['metadata']}")
    print(f"   ✓ Quality present: {'quality' in output['metadata']}")

    # Check chunk structure
    if output['chunks']:
        expected_keys = {
            'stable_id', 'paragraph_id', 'text', 'hierarchy', 'chapter_href',
            'source_order', 'source_tag', 'text_length', 'word_count',
            'cross_references', 'scripture_references', 'dates_mentioned',
            'heading_path', 'hierarchy_depth', 'doc_stable_id',
            'sentence_count', 'sentences', 'normalized_text'
        }
        actual_keys = set(output['chunks'][0].keys())
        missing = expected_keys - actual_keys
        extra = actual_keys - expected_keys

        if not missing and not extra:
            print(f"   ✓ Chunk structure: all expected fields present")
        else:
            if missing:
                print(f"   ⚠ Missing chunk fields: {missing}")
            if extra:
                print(f"   + Extra chunk fields: {extra}")

    print("\n" + "=" * 70)
    print("✅ Demo completed successfully!")
    print("=" * 70)
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
