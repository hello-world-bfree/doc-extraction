# extraction

[![PyPI version](https://badge.fury.io/py/doc-extraction.svg)](https://pypi.org/project/doc-extraction/)
[![Python 3.13+](https://img.shields.io/badge/python-3.13+-blue.svg)](https://www.python.org/downloads/)
[![Documentation](https://img.shields.io/badge/docs-mkdocs-blue.svg)](https://hello-world-bfree.github.io/extraction/)

Multi-format document extraction library for processing EPUB, PDF, HTML, Markdown, and JSON documents into structured, hierarchical chunks with domain-specific metadata enrichment.

**Version**: 0.0.1 (First Public Release)

## Features

- **Multi-format support**: EPUB, PDF, HTML, Markdown, JSON
- **Chunking strategies**: RAG/embeddings mode (100-500 words) and NLP/paragraph mode
- **Hierarchical structure**: Maintains 6-level heading hierarchy across documents
- **Quality scoring**: Automatic document quality assessment with routing (A/B/C)
- **Noise filtering**: Removes index pages, copyright boilerplate, navigation fragments
- **Domain analyzers**: Catholic literature and generic analyzers
- **Formatting preservation**: Poetry, blockquotes, lists, tables, emphasis
- **Reference extraction**: Scripture references, cross-references, dates
- **Vatican pipeline**: Specialized pipeline for vatican.va document processing
- **Token re-chunking**: Optimize chunks for embedding models (embeddinggemma-300m)

## Installation

### From PyPI (Recommended)

```bash
pip install doc-extraction

# With optional dependencies
pip install doc-extraction[pdf]              # PDF support
pip install doc-extraction[vatican]          # Vatican pipeline with S3
pip install doc-extraction[images]           # Image scraping + EPUB creation
pip install doc-extraction[finetuning]       # Token re-chunking tools
pip install doc-extraction[dev]              # Testing tools
```

### From Source (Development)

```bash
git clone https://github.com/hello-world-bfree/extraction.git
cd extraction
uv pip install -e ".[pdf,dev]"
```

## Quick Start

### Basic Usage

```python
from extraction.extractors import EpubExtractor
from extraction.analyzers import GenericAnalyzer

# Extract chunks from EPUB
extractor = EpubExtractor("book.epub")
extractor.load()
extractor.parse()
metadata = extractor.extract_metadata()

# Get output
output = extractor.get_output_data()
print(f"Extracted {len(output['chunks'])} chunks")
```

### With Domain Analysis

```python
from extraction.extractors import EpubExtractor
from extraction.analyzers import CatholicAnalyzer

extractor = EpubExtractor("encyclical.epub")
extractor.load()
extractor.parse()
metadata = extractor.extract_metadata()

# Enrich with Catholic-specific metadata
analyzer = CatholicAnalyzer()
enriched = analyzer.enrich_metadata(
    metadata.to_dict(),
    extractor.full_text,
    [c.to_dict() for c in extractor.chunks]
)

output = extractor.get_output_data()
output['metadata'].update(enriched)
```

### CLI Usage

```bash
# Extract single document (default: RAG chunking, noise filtering enabled)
extract document.epub

# Batch processing
extract documents/ -r --output-dir outputs/

# Custom chunking strategy
extract book.epub --chunking-strategy rag --min-chunk-words 200 --max-chunk-words 800
extract document.pdf --chunking-strategy nlp  # Paragraph-level chunks

# Disable noise filtering (keep index pages, copyright, etc.)
extract document.html --no-filter-noise

# Enable formatting preservation
extract book.epub --preserve-formatting

# With Catholic domain analysis
extract encyclical.epub --analyzer catholic

# Vatican archive pipeline
vatican-extract --sections BIBLE CATECHISM --upload
```

## Chunking Strategies

Choose between two chunking modes across **all formats** (EPUB, PDF, HTML, Markdown, JSON):

### RAG/Semantic Mode (Default)
- Merges paragraphs under same heading hierarchy
- Target: 100-500 words per chunk (optimal for embeddings)
- Use for: Vector search, RAG systems, semantic retrieval
- ~60-80% reduction in chunk count vs paragraph mode

```bash
extract document.epub  # Default
extract document.pdf --min-chunk-words 200 --max-chunk-words 800
```

### NLP/Paragraph Mode
- Paragraph-level chunks (one paragraph = one chunk)
- Use for: Fine-grained NLP tasks, sentence classification, NER
- Preserves exact paragraph boundaries

```bash
extract document.epub --chunking-strategy nlp
```

## Token-Based Re-Chunking for Embeddings

Transform word-based extraction output into token-optimized chunks for embedding models:

```bash
# Install finetuning dependencies
pip install doc-extraction[finetuning]

# Retrieval mode: 256-400 tokens (precision-optimized)
token-rechunk document.json --mode retrieval

# Recommendation mode: 512-700 tokens (context-optimized)
token-rechunk document.json --mode recommendation

# Custom configuration
token-rechunk document.json --min-tokens 300 --max-tokens 500 --overlap-percent 0.12

# Batch processing for RAG applications
mkdir rag_corpus/
for file in extractions/*.json; do
    token-rechunk "$file" --mode retrieval --output "rag_corpus/$(basename $file .json).jsonl"
done
```

**Features:**
- Sentence-aware overlap (10-20%)
- Actual tokenization using embeddinggemma-300m tokenizer
- 2048 token hard limit with automatic splitting
- Hierarchy preservation across chunks

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
   - `CatholicAnalyzer`: Document type, subjects, themes, related documents, geographic focus
   - `GenericAnalyzer`: Basic metadata extraction for general content

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

## Noise Filtering

Automatic detection and removal of content with zero semantic value:

- **Index pages**: Reference lists, number sequences
- **Copyright boilerplate**: Legal notices, ISBN numbers, publisher info
- **Navigation fragments**: TOC entries, page numbers, "Next/Previous" links

**Impact**: ~3-5% chunk reduction with zero false positives (tested on 72k+ chunks)

```bash
# Enabled by default
extract document.html

# Disable if needed
extract document.html --no-filter-noise
```

## Formatting Preservation

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

## Image Extraction to EPUB

Scrape images from websites and create EPUB photo galleries:

```bash
# Install image dependencies
pip install doc-extraction[images]

# Basic usage - scrape and build EPUB
extract-images https://example.com/gallery --title "Gallery" --output gallery.epub

# Just download images (no EPUB)
extract-images https://example.com/photos --output-dir ./images --no-epub

# With S3 backup
extract-images https://example.com --title "Photos" \
  --output photos.epub \
  --upload-s3 --s3-bucket my-bucket --s3-prefix "galleries/"
```

## Configuration

Each extractor accepts a `config` dict with format-specific options:

```python
from extraction.extractors import EpubExtractor

extractor = EpubExtractor("book.epub", config={
    'chunking_strategy': 'rag',           # 'rag' or 'nlp'
    'min_chunk_words': 100,               # Minimum chunk size
    'max_chunk_words': 500,               # Maximum chunk size
    'filter_noise': True,                 # Enable noise filtering
    'preserve_formatting': True,          # Preserve structure
    'preserve_hierarchy_across_docs': True,  # EPUB: hierarchy flows across spine
    'toc_hierarchy_level': 1,             # EPUB: TOC level to use
})
```

See [documentation](https://hello-world-bfree.github.io/extraction/reference/configuration/) for all options.

## Testing

```bash
# Run all tests
uv run pytest

# Skip integration tests
uv run pytest -m "not integration"

# Run with coverage
uv run pytest --cov=src/extraction --cov-report=html
```

**Current status**: 228 tests, 41% coverage

## Requirements

- **Python 3.13+** (required)
- **uv** for package management (recommended)

## Documentation

- **Homepage**: https://hello-world-bfree.github.io/extraction/
- **PyPI**: https://pypi.org/project/doc-extraction/
- **GitHub**: https://github.com/hello-world-bfree/extraction
- **Issues**: https://github.com/hello-world-bfree/extraction/issues

For detailed documentation on architecture, adding extractors/analyzers, testing strategy, and common patterns, see [CLAUDE.md](CLAUDE.md).

## Use Cases

### Catholic Literature Processing
- Encyclicals, catechisms, prayer books
- Vatican archive document extraction
- Scripture reference extraction

### General Document Processing
- Multi-format document conversion
- Hierarchical chunking for large documents
- Quality-based routing for document review

### RAG/Embedding Applications
- Vector database population
- Semantic search corpus preparation
- Token-optimized chunk generation

## Project Structure

```
extraction/
├── src/extraction/
│   ├── core/          # Core utilities (chunking, quality, extraction)
│   ├── extractors/    # Format-specific extractors
│   ├── analyzers/     # Domain analyzers
│   ├── builders/      # EPUB builder for image galleries
│   ├── scrapers/      # Image scraping utilities
│   ├── storage/       # S3 upload support
│   ├── cli/           # CLI entry points
│   ├── tools/         # Token re-chunking
│   └── pipelines/     # Specialized pipelines (Vatican)
├── tests/             # Test suite
├── docs/              # MkDocs documentation
├── examples/          # Example scripts
├── pyproject.toml     # Package configuration
└── CLAUDE.md          # Detailed development guide
```

