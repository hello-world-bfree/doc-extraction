# extraction

Multi-format document extraction library for processing EPUB, PDF, HTML, Markdown, and JSON documents into structured, hierarchical chunks with domain-specific metadata enrichment.

**Version**: 2.1.0 (Formatting Preservation Release)

## Features

- **Multi-format support**: EPUB, PDF, HTML, Markdown, JSON
- **Hierarchical chunking**: Maintains 6-level heading hierarchy across documents
- **Domain analyzers**: Catholic literature and generic analyzers
- **Quality scoring**: Automatic quality assessment with routing (A/B/C)
- **Reference extraction**: Scripture references, cross-references, dates
- **Formatting preservation**: Poetry, blockquotes, lists, tables, emphasis (v2.1+)
- **Vatican pipeline**: Specialized pipeline for vatican.va document processing

## Installation

### Editable Install (Development/Local Projects)

For personal projects that need to stay in sync with the latest extraction library code:

```bash
cd ~/bjf/extraction
uv pip install -e .
```

This creates a "live" installation - any changes to `~/bjf/extraction` are immediately visible to all projects using it.

### With Optional Dependencies

```bash
# PDF support + testing
uv pip install -e ".[pdf,dev]"

# Add Vatican pipeline S3 upload
uv pip install -e ".[pdf,dev,vatican]"

# Add fine-tuning tools (token-rechunk CLI)
uv pip install -e ".[finetuning]"
```

## Quick Start

### Basic Usage

```python
from extraction.extractors import EpubExtractor
from extraction.analyzers import CatholicAnalyzer

# Extract chunks from EPUB
extractor = EpubExtractor("book.epub")
extractor.load()
extractor.parse()
metadata = extractor.extract_metadata()

# Enrich with domain-specific analysis
analyzer = CatholicAnalyzer()
enriched = analyzer.enrich_metadata(
    metadata.to_dict(),
    extractor.full_text,
    [c.to_dict() for c in extractor.chunks]
)

# Get output
output = extractor.get_output_data()
output['metadata'].update(enriched)
```

### CLI Usage

```bash
# Extract single document
extract document.epub

# Batch processing with custom analyzer
extract documents/ -r --output-dir outputs/ --analyzer catholic

# Enable formatting preservation (v2.1+)
extract book.epub --preserve-formatting

# Vatican archive pipeline
vatican-extract --sections BIBLE CATECHISM --upload

# Token-based re-chunking for embeddings (v2.3+)
token-rechunk document.json --mode retrieval
token-rechunk document.json --mode recommendation --stats
```

## Token-Based Re-Chunking for Embedding Applications

The `token-rechunk` tool transforms extraction library output (word-based chunks) into token-optimized chunks for embedding-based applications. Use this to prepare content for RAG systems, semantic search, and recommendation engines with embedding models like embeddinggemma-300m.

### Features

- **Task-specific chunk sizes**:
  - Retrieval mode: 256-400 tokens (precision-optimized)
  - Recommendation mode: 512-700 tokens (context-optimized)
  - Balanced mode: 400-512 tokens (default)
- **Sentence-aware overlap**: 10-20% overlap respecting sentence boundaries
- **Actual tokenization**: Uses embeddinggemma-300m tokenizer for exact token counts
- **2048 token validation**: Hard limit with automatic sentence-boundary splitting
- **Hierarchy preservation**: Maintains document structure metadata across chunks

### Usage

```bash
# Retrieval mode (256-400 tokens, 15% overlap)
token-rechunk catechism.json --mode retrieval

# Recommendation mode (512-700 tokens, 10% overlap)
token-rechunk catechism.json --mode recommendation

# Custom chunk sizes
token-rechunk document.json --min-tokens 300 --max-tokens 500 --overlap-percent 0.12

# With statistics
token-rechunk document.json --stats --verbose

# Batch processing
for file in extractions/*.json; do
    token-rechunk "$file" --mode retrieval --output "corpus/$(basename $file .json).jsonl"
done
```

### Multi-Application Workflow

```bash
# 1. Extract documents
extract corpus/*.epub -r --output-dir extractions/

# 2. Create RAG/search corpus (smaller chunks for precision)
mkdir rag_corpus/
for file in extractions/*.json; do
    token-rechunk "$file" --mode retrieval --output "rag_corpus/$(basename $file .json).jsonl"
done

# 3. Create recommendation corpus (larger chunks for context)
mkdir recommendation_corpus/
for file in extractions/*.json; do
    token-rechunk "$file" --mode recommendation --output "recommendation_corpus/$(basename $file .json).jsonl"
done

# 4. Combine and embed for your application
cat rag_corpus/*.jsonl > rag_content.jsonl
cat recommendation_corpus/*.jsonl > recommendation_content.jsonl
```

### Output Format

JSONL with one chunk per line:

```json
{"text": "First paragraph merged with second paragraph...", "metadata": {"doc_id": "catechism_abc123", "hierarchy": {"level_1": "Part I", "level_2": "Chapter 1"}, "token_count": 456, "source_chunk_id": "orig_chunk_1", "is_overlap": false}}
```

## Architecture

### Three-Layer Design

1. **Core Utilities** (`src/extraction/core/`)
   - Format-agnostic text processing, chunking, quality scoring
   - Models: `Chunk`, `Metadata`, `Provenance`, `Quality`, `Hierarchy`

2. **Extractors** (`src/extraction/extractors/`)
   - Format-specific parsers: EPUB, PDF, HTML, Markdown, JSON
   - All inherit from `BaseExtractor` ABC
   - Produce uniform `Chunk` objects regardless of format

3. **Analyzers** (`src/extraction/analyzers/`)
   - Domain-specific metadata enrichment
   - Catholic analyzer: document_type, subjects, themes, related_documents, geographic_focus
   - Generic analyzer: Basic metadata extraction for non-Catholic content

## Output Format

All extractors produce identical JSON structure:

```json
{
  "metadata": {
    "title": "Document Title",
    "author": "Author Name",
    "provenance": {
      "doc_id": "unique-id",
      "source_file": "path/to/file.epub"
    },
    "quality": {
      "score": 0.95,
      "route": "A"
    },
    "document_type": "Encyclical",
    "subjects": ["Liturgy", "Sacraments"]
  },
  "chunks": [
    {
      "stable_id": "abc123...",
      "text": "Chunk text content",
      "hierarchy": {
        "level_1": "Part I",
        "level_2": "Chapter 1"
      },
      "word_count": 42,
      "scripture_references": ["John 3:16"],
      "formatted_text": "> Blockquote with *emphasis*",
      "structure_metadata": {...}
    }
  ]
}
```

## Formatting Preservation (v2.1+)

Preserve structural intent during extraction:

```bash
# Enable all formatting preservation
extract book.epub --preserve-formatting

# Fine-grained control
extract book.epub --preserve-formatting --no-preserve-tables
```

**What gets preserved:**
- Poetry/verse line breaks
- Blockquotes with attribution
- Nested lists (ordered/unordered)
- Tables (markdown format)
- Emphasis (italic/bold)
- Code blocks

## Testing

```bash
# Run all tests
uv run pytest

# Skip integration tests
uv run pytest -m "not integration"

# Run with coverage
uv run pytest --cov=src/extraction --cov-report=html
```

## Project Structure

```
extraction/
├── src/extraction/
│   ├── core/          # Core utilities (chunking, quality, extraction)
│   ├── extractors/    # Format-specific extractors
│   ├── analyzers/     # Domain analyzers
│   ├── cli/           # CLI entry points
│   └── pipelines/     # Specialized pipelines (Vatican)
├── tests/             # Test suite
├── pyproject.toml     # Package configuration
└── CLAUDE.md          # Detailed development guide
```

## Use Cases

**Catholic Literature Processing**
- Encyclicals, catechisms, prayer books
- Vatican archive document extraction
- Scripture reference extraction

**General Document Processing**
- Multi-format document conversion
- Hierarchical chunking for large documents
- Quality-based routing for document review

## Requirements

- Python 3.13+
- `uv` for package management (required)

## Documentation

For detailed documentation on architecture, adding extractors/analyzers, testing strategy, and common patterns, see [CLAUDE.md](CLAUDE.md).

## Standard Usage for Projects

**This is THE standard way to consume the extraction library:**

1. Install in editable mode: `uv pip install -e ~/bjf/extraction`
2. Import and use: `from extraction.extractors import EpubExtractor`
3. Updates happen automatically when `~/bjf/extraction` code changes

No manual syncing, rsync scripts, or git submodules needed. Just use standard Python package installation.

## License

MIT
