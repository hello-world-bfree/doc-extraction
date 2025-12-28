#!/usr/bin/env python3

from book_parser_no_footnotes import EpubParser
from src.extraction.extractors import EpubExtractor
import logging

logging.basicConfig(level=logging.WARNING)

epub_path = 'catholic_sources/Prayer_Primer.epub'

old_parser = EpubParser(epub_path)
old_parser.load()
old_parser.parse()

new_extractor = EpubExtractor(epub_path)
new_extractor.load()
new_extractor.parse()
new_metadata = new_extractor.extract_metadata()
new_output = new_extractor.get_output_data()

print(f'Chunk count: old={len(old_parser.chunks)}, new={len(new_output["chunks"])}')
print(f'Quality: old={old_parser.doc_route}/{old_parser.doc_quality_score:.4f}, new={new_extractor.route}/{new_extractor.quality_score:.4f}')

# Check metadata keys
old_keys = set(old_parser.metadata.keys())
new_keys = set(new_output['metadata'].keys())

print(f'\nMetadata keys match: {old_keys == new_keys}')
if old_keys != new_keys:
    print(f'  Only in old: {old_keys - new_keys}')
    print(f'  Only in new: {new_keys - old_keys}')

# Check first chunk
if old_parser.chunks and new_output['chunks']:
    old_ch_keys = set(old_parser.chunks[0].keys())
    new_ch_keys = set(new_output['chunks'][0].keys())
    print(f'\nFirst chunk keys match: {old_ch_keys == new_ch_keys}')
    if old_ch_keys != new_ch_keys:
        print(f'  Only in old: {old_ch_keys - new_ch_keys}')
        print(f'  Only in new: {new_ch_keys - old_ch_keys}')

    # Compare first chunk text
    if old_parser.chunks[0]['text'] == new_output['chunks'][0]['text']:
        print('\n✓ First chunk text matches')
    else:
        print('\n✗ First chunk text differs')

print('\n✓ Test passed!' if old_keys == new_keys and len(old_parser.chunks) == len(new_output['chunks']) else '✗ Test failed')
