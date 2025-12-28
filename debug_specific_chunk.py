#!/usr/bin/env python3

import sys
from book_parser_no_footnotes import EpubParser
from src.extraction.extractors import EpubExtractor
import logging

logging.basicConfig(level=logging.WARNING)

epub_path = 'catholic_sources/Into_the_Deep.epub'

old_parser = EpubParser(epub_path)
old_parser.load()
old_parser.parse()

new_extractor = EpubExtractor(epub_path)
new_extractor.load()
new_extractor.parse()

# Get chunks from the specific href
href = 'OPS/intro_split_001.html'

old_chunks = [ch for ch in old_parser.chunks if ch['chapter_href'] == href]
new_chunks = [ch for ch in new_extractor.chunks_dict if ch['chapter_href'] == href]

print(f"Old parser: {len(old_chunks)} chunks from {href}")
print(f"New extractor: {len(new_chunks)} chunks from {href}")

# Compare paragraph IDs
old_ids = [ch['paragraph_id'] for ch in old_chunks]
new_ids = [ch['paragraph_id'] for ch in new_chunks]

print(f"\nOld paragraph IDs: {old_ids}")
print(f"New paragraph IDs: {new_ids}")

# Find the different chunk
print("\n" + "=" * 70)
print("Comparing chunk contents...")
print("=" * 70)

for i in range(min(len(old_chunks), len(new_chunks))):
    old_text = old_chunks[i]['text']
    new_text = new_chunks[i]['text']
    if old_text != new_text:
        print(f"\nChunk {i} differs:")
        print(f"  Old: {old_text[:200]}...")
        print(f"  New: {new_text[:200]}...")
        print(f"  Old word count: {old_chunks[i]['word_count']}")
        print(f"  New word count: {new_chunks[i]['word_count']}")

# Show the extra chunk
if len(new_chunks) > len(old_chunks):
    print(f"\nExtra chunk in new version (index {len(old_chunks)}):")
    extra = new_chunks[len(old_chunks)]
    print(f"  Text: {extra['text'][:200]}...")
    print(f"  Word count: {extra['word_count']}")
    print(f"  Source tag: {extra['source_tag']}")
