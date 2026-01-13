#!/usr/bin/env python3
"""
Scan Vatican HTML corpus for noise chunks.
"""
import sys
sys.path.insert(0, 'src')

from extraction.core.noise_filter import scan_corpus_for_noise

def main():
    corpus_file = 'vatican_archive/outputs/db_ready_vatican_html/vatican_corpus_all_with_prefix.jsonl'

    print("🔍 Scanning Vatican HTML corpus for noise...")
    print(f"   File: {corpus_file}\n")

    stats = scan_corpus_for_noise(corpus_file)

    print(f"📊 Results:")
    print(f"   Total chunks: {stats['total_scanned']:,}")
    print(f"   Noise detected: {stats['noise_detected']:,}")
    print(f"   Noise rate: {stats['noise_rate']:.2%}")

    if stats['noise_chunks']:
        print(f"\n🗑️  Noise chunks found:")
        for i, chunk in enumerate(stats['noise_chunks'][:20], 1):
            print(f"   {i}. {chunk['chunk_id']}")
            print(f"      Reason: {chunk['reason']}")
            print(f"      Words: {chunk['word_count']}, Tokens: {chunk['token_count']}")
            print(f"      Preview: {chunk['text_preview']}")
            print()

        if len(stats['noise_chunks']) > 20:
            print(f"   ... and {len(stats['noise_chunks']) - 20} more")

        # Save full list
        import json
        output_file = 'vatican_archive/outputs/noise_chunks.jsonl'
        with open(output_file, 'w') as f:
            for chunk in stats['noise_chunks']:
                f.write(json.dumps(chunk) + '\n')
        print(f"\n📁 Full list saved to: {output_file}")

if __name__ == '__main__':
    main()
