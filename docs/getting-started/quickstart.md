# Quickstart Guide (5 Minutes)

This guide will get you extracting structured chunks from documents in 5 minutes.

## Installation

Install the extraction library using `uv` (recommended) or `pip`:

=== "uv (recommended)"

    ```bash
    # Basic installation
    uv pip install doc-extraction

    # With PDF support
    uv pip install "doc-extraction[pdf]"
    ```

=== "pip"

    ```bash
    # Basic installation
    pip install doc-extraction

    # With PDF support
    pip install "doc-extraction[pdf]"
    ```

=== "Development (editable)"

    ```bash
    git clone https://github.com/hello-world-bfree/extraction.git
    cd extraction
    uv pip install -e ".[dev]"
    ```

!!! tip "Why uv?"
    `uv` is significantly faster than pip and handles dependency resolution better. It's the recommended way to install Python packages in 2024+.

## Your First Extraction (CLI)

The fastest way to extract a document is using the CLI:

```bash
extract document.epub
```

This creates `document.json` in the current directory with:

- Full document metadata (title, author, quality score)
- Structured chunks with hierarchical context
- Reference extraction (scripture refs, cross-refs, dates)
- Automatic noise filtering (index pages, copyright, navigation)

### Inspect the Output

```bash
# Pretty-print the JSON
cat document.json | python -m json.tool | less

# Count chunks
cat document.json | python -c "import json, sys; print(len(json.load(sys.stdin)['chunks']))"

# See first chunk
cat document.json | python -c "import json, sys; print(json.load(sys.stdin)['chunks'][0])"
```

### Batch Processing

Process all EPUB files in a directory:

```bash
extract documents/ -r --output-dir outputs/
```

Flags:

- `-r` or `--recursive`: Process subdirectories
- `--output-dir`: Where to save JSON files (defaults to current directory)

## Your First Extraction (Python)

For programmatic access, use the Python API:

```python
from extraction.extractors import EpubExtractor

# Create extractor
extractor = EpubExtractor("document.epub")

# Load the source document
extractor.load()

# Parse into chunks
extractor.parse()

# Access chunks
print(f"Extracted {len(extractor.chunks)} chunks")

# Iterate through chunks
for chunk in extractor.chunks[:3]:  # First 3 chunks
    print(f"\nChunk ID: {chunk.stable_id}")
    print(f"Hierarchy: {chunk.hierarchy}")
    print(f"Text: {chunk.text[:100]}...")
    print(f"Word count: {chunk.word_count}")
```

### Extract Metadata

```python
# Get document-level metadata
metadata = extractor.extract_metadata()

print(f"Title: {metadata.title}")
print(f"Author: {metadata.author}")
print(f"Quality score: {metadata.quality.score}")
print(f"Quality route: {metadata.quality.route}")  # A, B, or C
```

### Get Full Output

```python
# Get complete output structure (metadata + chunks)
output = extractor.get_output_data()

# This matches the JSON file structure
print(output.keys())  # dict_keys(['metadata', 'chunks'])

# Save to file
import json

with open("output.json", "w") as f:
    json.dump(output, f, indent=2)
```

## Understanding the Output

Every chunk has the following structure:

```python
{
    "stable_id": "abc123...",           # Unique chunk ID (hash-based)
    "paragraph_id": 1,                  # Sequential ID within document
    "text": "The actual content...",    # Plain text
    "hierarchy": {                       # 6-level heading hierarchy
        "level_1": "Part I",
        "level_2": "Chapter 1",
        "level_3": "Section A"
    },
    "word_count": 42,                   # Word count
    "scripture_references": [],          # Extracted Bible references
    "cross_references": [],              # Internal cross-references
    "sentences": ["First.", "Second."],  # Split sentences
    "formatted_text": None,              # Optional (with --preserve-formatting)
    "structure_metadata": None           # Optional (with --preserve-formatting)
}
```

### Chunk Types (RAG vs NLP)

By default, the library uses **RAG chunking** which merges paragraphs under the same heading into semantic chunks (100-500 words):

```bash
# Default: RAG mode (optimal for embeddings)
extract document.epub

# Custom chunk sizes
extract document.epub --min-chunk-words 200 --max-chunk-words 800
```

For paragraph-level chunks (one paragraph = one chunk), use **NLP mode**:

```bash
extract document.epub --chunking-strategy nlp
```

!!! info "When to use each mode"
    - **RAG mode** (default): Vector databases, semantic search, embeddings
    - **NLP mode**: Fine-grained NLP tasks, sentence classification, NER

## Common Output Formats

### JSON (Full metadata)

```bash
extract document.epub --output document.json
```

Best for: Single documents, debugging, inspection

### NDJSON (One chunk per line)

```bash
extract document.epub --ndjson --output document.ndjson
```

Best for: Streaming ingestion, database imports, large-scale processing

**Example NDJSON line**:
```json
{"stable_id": "abc123", "text": "Content...", "hierarchy": {"level_1": "Part I"}, "word_count": 42}
{"stable_id": "def456", "text": "More content...", "hierarchy": {"level_1": "Part I", "level_2": "Chapter 1"}, "word_count": 38}
```

## Quick Customization

### Disable Noise Filtering

```bash
# Keep ALL chunks (including index pages, copyright, etc.)
extract document.epub --no-filter-noise
```

### Change Tiny Chunk Filter

```bash
# Conservative (default): Remove obvious noise only
extract document.epub --filter-tiny-chunks conservative

# Standard: More aggressive
extract document.epub --filter-tiny-chunks standard

# Off: Keep all tiny chunks
extract document.epub --filter-tiny-chunks off
```

### Preserve Formatting

```bash
# Preserve poetry line breaks, blockquotes, lists, tables, emphasis
extract document.epub --preserve-formatting
```

This adds `formatted_text` and `structure_metadata` fields to chunks.

## Troubleshooting

### "No module named 'extraction'"

You haven't installed the package. Run:

```bash
uv pip install doc-extraction
```

### "ModuleNotFoundError: No module named 'pypdf'"

PDF support requires optional dependencies:

```bash
uv pip install "doc-extraction[pdf]"
```

### Empty chunks or missing text

Check the quality score:

```python
metadata = extractor.extract_metadata()
print(f"Quality: {metadata.quality.score} (route {metadata.quality.route})")

# Route C = low quality, may need manual review
if metadata.quality.route == "C":
    print("Warning: Low quality document")
```

### Hierarchy not preserving across EPUB sections

Use the `--preserve-hierarchy` flag:

```bash
extract book.epub --preserve-hierarchy
```

## Next Steps

<div class="grid cards" markdown>

-   :material-file-swap:{ .lg .middle } **[Multi-Format Extraction](multi-format.md)**

    ---

    Learn how to process PDF, HTML, Markdown, and JSON documents

-   :material-database:{ .lg .middle } **[Building a Vector DB](vector-db.md)**

    ---

    End-to-end RAG pipeline: Extract → Rechunk → Embed → Store

-   :material-tune:{ .lg .middle } **[Choosing Chunking Strategy](../how-to/chunking-strategy.md)**

    ---

    RAG vs NLP mode - when to use each

-   :material-book-open-page-variant:{ .lg .middle } **[API Reference](../reference/api/base-extractor.md)**

    ---

    Complete API documentation

</div>

## Summary

You learned how to:

1. Install the extraction library
2. Extract your first document (CLI and Python)
3. Inspect the output structure
4. Customize chunking and filtering
5. Choose between JSON and NDJSON output

The library works the same way for **all formats** (EPUB, PDF, HTML, Markdown, JSON). Continue to [Multi-Format Extraction](multi-format.md) to see format-specific examples.
