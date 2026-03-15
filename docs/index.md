# Extraction Library

**Multi-format document extraction for structured, hierarchical chunking**

The Extraction Library is a production-ready Python package for transforming documents (EPUB, PDF, HTML, Markdown, JSON) into clean, structured chunks optimized for vector databases, RAG systems, and semantic search applications.

## Why Extraction Library?

<div class="grid cards" markdown>

-   :material-file-document-multiple:{ .lg .middle } **Multi-Format Support**

    ---

    Process EPUB, PDF, HTML, Markdown, and JSON documents with a single, unified API. All formats produce identical output schemas.

-   :material-sitemap:{ .lg .middle } **Hierarchical Chunking**

    ---

    Maintains 6-level heading hierarchy across documents. Never lose structural context when breaking text into chunks.

-   :material-chart-bell-curve:{ .lg .middle } **Quality Scoring**

    ---

    Automatic quality assessment with A/B/C routing. Focus human review where it matters most.

-   :material-filter:{ .lg .middle } **Smart Filtering**

    ---

    Removes index pages, copyright boilerplate, and navigation fragments automatically. Clean chunks, zero noise.

-   :material-robot:{ .lg .middle } **RAG-Optimized**

    ---

    Default chunking strategy merges paragraphs into 100-500 word chunks - ideal for embedding models and vector search.

-   :material-code-braces:{ .lg .middle } **Clean API**

    ---

    Three-layer architecture: Extractors → Analyzers → Output. Extend with custom analyzers for domain-specific enrichment.

</div>

## Quick Start

Install with `uv` (recommended) or `pip`:

```bash
# Basic installation
uv pip install doc-extraction

# With PDF support
uv pip install "doc-extraction[pdf]"

# Development installation
git clone https://github.com/hello-world-bfree/extraction.git
cd extraction
uv pip install -e ".[dev]"
```

Extract your first document:

```python
from extraction.extractors import EpubExtractor

# Load and parse
extractor = EpubExtractor("book.epub")
extractor.load()
extractor.parse()

# Get structured chunks
for chunk in extractor.chunks:
    print(f"Hierarchy: {chunk.hierarchy}")
    print(f"Text: {chunk.text[:100]}...")
    print(f"Word count: {chunk.word_count}")
    print("---")
```

Or use the CLI:

```bash
# Single document
extract document.epub

# Batch processing
extract documents/ -r --output-dir outputs/

# Custom chunking for embeddings
extract book.epub --chunking-strategy rag --min-chunk-words 200
```

## Key Features

### Chunking Strategies

Choose between **RAG mode** (semantic chunks, 100-500 words) or **NLP mode** (paragraph-level chunks) across all formats:

```bash
# RAG mode (default): Optimal for vector databases
extract document.pdf --chunking-strategy rag

# NLP mode: Preserves exact paragraph boundaries
extract document.pdf --chunking-strategy nlp
```

### Domain-Specific Analyzers

Enrich metadata with domain-specific analyzers:

```python
from extraction.extractors import EpubExtractor
from extraction.analyzers import CatholicAnalyzer

extractor = EpubExtractor("encyclical.epub")
extractor.load()
extractor.parse()

analyzer = CatholicAnalyzer()
enriched = analyzer.enrich_metadata(
    extractor.extract_metadata().to_dict(),
    extractor.full_text,
    [c.to_dict() for c in extractor.chunks]
)

# Now includes: document_type, subjects, themes, related_documents
print(enriched['document_type'])  # "Encyclical"
print(enriched['subjects'])       # ["Liturgy", "Sacraments"]
```

Or create your own analyzer for custom domains (legal, medical, academic, etc.).

### Noise Filtering

Automatic removal of zero-value content:

- Index pages and reference lists
- Copyright boilerplate
- Navigation fragments ("Next", "Previous", "Home")
- Tiny chunks (<5 words) like figure labels

**Default**: Enabled. Reduces noise by 3-5% with zero false positives.

```bash
# Noise filtering is on by default
extract document.html

# Disable if needed
extract document.html --no-filter-noise
```

### Formatting Preservation

Preserve structural intent for poetry, blockquotes, lists, tables, and emphasis:

```bash
extract book.epub --preserve-formatting
```

**Before** (v2.0):
```
Two roads diverged in a yellow wood, And sorry I could not travel both
```

**After** (v2.1 with `--preserve-formatting`):
```
Two roads diverged in a yellow wood,
And sorry I could not travel both
```

Each chunk gets optional `formatted_text` and `structure_metadata` fields alongside plain `text`.

## Output Format

All extractors produce identical JSON structure:

```json
{
  "metadata": {
    "title": "Document Title",
    "author": "Author Name",
    "provenance": {
      "doc_id": "unique-id",
      "source_file": "book.epub"
    },
    "quality": {
      "score": 0.95,
      "route": "A"
    }
  },
  "chunks": [
    {
      "stable_id": "abc123...",
      "text": "Content here...",
      "hierarchy": {
        "level_1": "Part I",
        "level_2": "Chapter 1"
      },
      "word_count": 42,
      "scripture_references": ["John 3:16"],
      "cross_references": []
    }
  ]
}
```

Output as **JSON** (full metadata) or **NDJSON** (one chunk per line, optimized for database ingestion).

## Use Cases

**Vector Databases & RAG Systems**

Extract documents → Token-rechunk → Embed → Store in LanceDB/Pinecone/Weaviate/ChromaDB

**Semantic Search**

Build searchable knowledge bases from multi-format document collections

**Document Analysis**

Quality scoring, reference extraction, hierarchical structure analysis

**Domain-Specific Processing**

Catholic literature, legal documents, academic papers - extensible analyzer system

## Next Steps

<div class="grid cards" markdown>

-   :material-rocket-launch:{ .lg .middle } **[Quickstart Guide](getting-started/quickstart.md)**

    ---

    Extract your first document in 5 minutes

-   :material-file-swap:{ .lg .middle } **[Multi-Format Extraction](getting-started/multi-format.md)**

    ---

    Learn how to process EPUB, PDF, HTML, Markdown, and JSON

-   :material-database:{ .lg .middle } **[Building a Vector DB](getting-started/vector-db.md)**

    ---

    End-to-end pipeline: Extract → Rechunk → Embed → Store

-   :material-book-open-page-variant:{ .lg .middle } **[API Reference](reference/api/base-extractor.md)**

    ---

    Complete API documentation

</div>

## Philosophy

The Extraction Library follows three core principles:

1. **Format-agnostic output**: All extractors produce the same schema
2. **Opt-in complexity**: Simple by default, configurable when needed
3. **Diataxis documentation**: Tutorials, How-To guides, Reference, Explanation

Built for production use with Catholic literature processing, but designed to be domain-agnostic through the analyzer plugin system.

## Requirements

- Python 3.13+
- `uv` recommended for package management

## License

MIT License - see [LICENSE](https://github.com/hello-world-bfree/extraction/blob/master/LICENSE) for details.
