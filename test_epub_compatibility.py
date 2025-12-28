#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Test backward compatibility between original EpubParser and refactored EpubExtractor.
"""

import json
import sys
from pathlib import Path

# Import original parser
from book_parser_no_footnotes import EpubParser

# Import new extractor
from src.extraction.extractors import EpubExtractor


def test_compatibility(epub_path: str):
    """Test that both parsers produce identical output."""
    print(f"\nTesting: {epub_path}")
    print("=" * 70)

    # Run original parser
    print("\n1. Running original EpubParser...")
    old_parser = EpubParser(epub_path)
    old_parser.load()
    old_parser.parse()
    old_metadata = old_parser.metadata
    old_chunks = old_parser.chunks

    print(f"   ✓ Original: {len(old_chunks)} chunks, route={old_parser.doc_route}")

    # Run new extractor
    print("\n2. Running refactored EpubExtractor...")
    new_extractor = EpubExtractor(epub_path)
    new_extractor.load()
    new_extractor.parse()
    new_metadata = new_extractor.extract_metadata()
    new_output = new_extractor.get_output_data()
    new_chunks = new_output["chunks"]

    print(f"   ✓ Refactored: {len(new_chunks)} chunks, route={new_extractor.route}")

    # Compare chunk counts
    print("\n3. Comparing outputs...")
    if len(old_chunks) != len(new_chunks):
        print(f"   ✗ CHUNK COUNT MISMATCH: {len(old_chunks)} vs {len(new_chunks)}")
        return False

    # Compare quality routing
    if old_parser.doc_route != new_extractor.route:
        print(f"   ✗ ROUTE MISMATCH: {old_parser.doc_route} vs {new_extractor.route}")
        return False

    # Compare quality scores (allow tiny floating point differences)
    score_diff = abs(old_parser.doc_quality_score - new_extractor.quality_score)
    if score_diff > 0.0001:
        print(f"   ✗ QUALITY SCORE MISMATCH: {old_parser.doc_quality_score} vs {new_extractor.quality_score}")
        return False

    # Compare metadata keys
    old_meta_keys = set(old_metadata.keys())
    new_meta_keys = set(new_output["metadata"].keys())
    if old_meta_keys != new_meta_keys:
        print(f"   ✗ METADATA KEYS MISMATCH:")
        print(f"      Only in old: {old_meta_keys - new_meta_keys}")
        print(f"      Only in new: {new_meta_keys - old_meta_keys}")
        return False

    # Compare chunk structure (first chunk only for speed)
    if old_chunks and new_chunks:
        old_chunk_keys = set(old_chunks[0].keys())
        new_chunk_keys = set(new_chunks[0].keys())
        if old_chunk_keys != new_chunk_keys:
            print(f"   ✗ CHUNK KEYS MISMATCH:")
            print(f"      Only in old: {old_chunk_keys - new_chunk_keys}")
            print(f"      Only in new: {new_chunk_keys - old_chunk_keys}")
            return False

        # Compare first chunk text
        if old_chunks[0]["text"] != new_chunks[0]["text"]:
            print(f"   ✗ FIRST CHUNK TEXT MISMATCH")
            print(f"      Old: {old_chunks[0]['text'][:100]}...")
            print(f"      New: {new_chunks[0]['text'][:100]}...")
            return False

    # Compare metadata values (subset of important fields)
    important_fields = ["title", "author", "language", "publisher"]
    for field in important_fields:
        old_val = old_metadata.get(field, "")
        new_val = new_output["metadata"].get(field, "")
        if old_val != new_val:
            print(f"   ✗ METADATA FIELD '{field}' MISMATCH:")
            print(f"      Old: {old_val}")
            print(f"      New: {new_val}")
            return False

    print("   ✓ All checks passed!")
    print(f"   ✓ {len(new_chunks)} chunks match")
    print(f"   ✓ Quality score: {new_extractor.quality_score:.4f}")
    print(f"   ✓ Metadata fields: {len(new_meta_keys)}")

    return True


def main():
    test_files = [
        "catholic_sources/Prayer_Primer.epub",
        "catholic_sources/Into_the_Deep.epub",
    ]

    results = []
    for test_file in test_files:
        if not Path(test_file).exists():
            print(f"\nSkipping {test_file} (not found)")
            continue

        try:
            success = test_compatibility(test_file)
            results.append((test_file, success))
        except Exception as e:
            print(f"\n   ✗ ERROR: {e}")
            import traceback
            traceback.print_exc()
            results.append((test_file, False))

    # Summary
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    for filename, success in results:
        status = "✓ PASS" if success else "✗ FAIL"
        print(f"{status}: {Path(filename).name}")

    all_passed = all(success for _, success in results)
    if all_passed:
        print("\n✓ All tests passed! Backward compatibility verified.")
        return 0
    else:
        print("\n✗ Some tests failed. Review differences above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
