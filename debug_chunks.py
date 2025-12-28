#!/usr/bin/env python3

import sys
from book_parser_no_footnotes import EpubParser
from src.extraction.extractors import EpubExtractor
from collections import defaultdict
import logging

logging.basicConfig(level=logging.WARNING)

epub_path = 'catholic_sources/Into_the_Deep.epub'

old_parser = EpubParser(epub_path)
old_parser.load()
old_parser.parse()

new_extractor = EpubExtractor(epub_path)
new_extractor.load()
new_extractor.parse()

# Group chunks by chapter_href
old_by_href = defaultdict(int)
for ch in old_parser.chunks:
    old_by_href[ch['chapter_href']] += 1

new_by_href = defaultdict(int)
for ch in new_extractor.chunks_dict:
    new_by_href[ch['chapter_href']] += 1

# Find differences
print(f"\nTotal: old={len(old_parser.chunks)}, new={len(new_extractor.chunks_dict)}")
print("\nDifferences by href:")
all_hrefs = set(old_by_href.keys()) | set(new_by_href.keys())
for href in sorted(all_hrefs):
    old_count = old_by_href.get(href, 0)
    new_count = new_by_href.get(href, 0)
    if old_count != new_count:
        print(f'  {href}: old={old_count}, new={new_count} (diff={new_count - old_count})')

# Check for extra chunk in new version
print("\nFinding the extra chunk...")
for i, new_ch in enumerate(new_extractor.chunks_dict):
    matching_old = [ch for ch in old_parser.chunks if ch['stable_id'] == new_ch['stable_id']]
    if not matching_old:
        print(f"\nExtra chunk in new version (index {i}):")
        print(f"  stable_id: {new_ch['stable_id']}")
        print(f"  paragraph_id: {new_ch['paragraph_id']}")
        print(f"  chapter_href: {new_ch['chapter_href']}")
        print(f"  text: {new_ch['text'][:100]}...")
        break
