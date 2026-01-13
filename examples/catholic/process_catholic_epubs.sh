#!/bin/bash
#
# Process Catholic EPUBs with noise filtering
#
# This script demonstrates how to extract Catholic EPUB documents
# with automatic noise filtering enabled by default.
#

set -e

# Configuration
EPUB_DIR="${1:-./catholic_epubs}"
OUTPUT_DIR="${2:-./outputs/catholic_corpus}"

echo "🔍 Processing Catholic EPUBs from: $EPUB_DIR"
echo "📁 Output directory: $OUTPUT_DIR"
echo ""

# Check if directory exists
if [ ! -d "$EPUB_DIR" ]; then
    echo "❌ Error: EPUB directory not found: $EPUB_DIR"
    echo ""
    echo "Usage: $0 [epub_directory] [output_directory]"
    echo "Example: $0 ./my_epubs ./outputs"
    exit 1
fi

# Count EPUBs
epub_count=$(find "$EPUB_DIR" -name "*.epub" -type f | wc -l | tr -d ' ')
if [ "$epub_count" -eq 0 ]; then
    echo "❌ No EPUB files found in $EPUB_DIR"
    exit 1
fi

echo "📚 Found $epub_count EPUB file(s)"
echo ""

# Create output directory
mkdir -p "$OUTPUT_DIR"

# Process with extract CLI
# Noise filtering is ENABLED BY DEFAULT (v2.4+)
echo "⚙️  Extraction settings:"
echo "  - Chunking: RAG mode (100-500 words, optimal for embeddings)"
echo "  - Noise filtering: ENABLED (removes index pages, boilerplate, navigation)"
echo "  - Tiny chunk filtering: Conservative (removes <5 word fragments)"
echo "  - Domain analyzer: Catholic (document_type, subjects, themes)"
echo ""

extract "$EPUB_DIR" \
    --recursive \
    --output-dir "$OUTPUT_DIR" \
    --analyzer catholic \
    --ndjson \
    --chunking-strategy rag \
    --min-chunk-words 100 \
    --max-chunk-words 500 \
    --filter-tiny-chunks conservative \
    --verbose

# Note: --no-filter-noise is NOT used, so noise filtering is enabled

echo ""
echo "✅ Processing complete!"
echo ""
echo "📊 Output files:"
echo "  - JSON: $OUTPUT_DIR/*.json (structured metadata + chunks)"
echo "  - NDJSON: $OUTPUT_DIR/*.ndjson (one chunk per line, for LLM ingestion)"
echo ""
echo "🧹 Filters applied:"
echo "  1. Noise filter: Index pages, copyright, navigation (v2.4)"
echo "  2. Tiny chunk filter: <5 word fragments (v2.2)"
echo ""

# Generate statistics
echo "📈 Generating corpus statistics..."
python3 -c "
import json
import os
from pathlib import Path

output_dir = Path('$OUTPUT_DIR')
total_chunks = 0
total_docs = 0
filtered_noise = 0

for json_file in output_dir.glob('*.json'):
    with open(json_file) as f:
        data = json.load(f)
        total_docs += 1
        total_chunks += len(data.get('chunks', []))

print(f'Documents processed: {total_docs}')
print(f'Total chunks: {total_chunks:,}')
print(f'Avg chunks/document: {total_chunks / total_docs if total_docs > 0 else 0:.1f}')
print('')
print('Note: Noise filtering removed index pages, copyright boilerplate, and')
print('      navigation fragments automatically. Use --no-filter-noise to disable.')
"

echo ""
echo "🎯 Next steps:"
echo "  1. Review outputs in $OUTPUT_DIR"
echo "  2. Run token-rechunker if needed for embedding optimization"
echo "  3. Ingest NDJSON files into vector database"
