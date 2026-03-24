# doc-extraction

[![PyPI version](https://badge.fury.io/py/doc-extraction.svg)](https://pypi.org/project/doc-extraction/)
[![Python 3.13+](https://img.shields.io/badge/python-3.13+-blue.svg)](https://www.python.org/downloads/)
[![Documentation](https://img.shields.io/badge/docs-mkdocs-blue.svg)](https://hello-world-bfree.github.io/extraction/)

Multi-format document extraction library that turns EPUB, PDF, HTML, Markdown, and JSON documents into structured, hierarchical chunks with quality scoring, noise filtering, and domain-specific metadata enrichment.

## Installation

```bash
pip install doc-extraction            # Core (EPUB, HTML, Markdown, JSON)
pip install doc-extraction[pdf]       # + PDF support (pdfplumber)
pip install doc-extraction[finetuning] # + Token re-chunking (embeddinggemma-300m)
pip install doc-extraction[images]    # + Image scraping & EPUB gallery builder
pip install doc-extraction[vatican]   # + Vatican archive pipeline (S3)
```

From source:

```bash
git clone https://github.com/hello-world-bfree/extraction.git
cd extraction
uv pip install -e ".[pdf,dev]"
```

## Quick Start

### CLI

```bash
extract document.epub                          # RAG chunking (default)
extract document.pdf --chunking-strategy nlp   # Paragraph-level chunks
extract documents/ -r --output-dir outputs/    # Batch processing
extract book.epub --analyzer catholic          # Domain-specific metadata
```

### Python API

```python
from extraction.extractors import EpubExtractor

extractor = EpubExtractor("book.epub")
extractor.load()
extractor.parse()
extractor.extract_metadata()

output = extractor.get_output_data()
# output["chunks"] — list of Chunk dicts with stable_id, text, hierarchy, word_count, ...
# output["metadata"] — title, author, provenance, quality score/route, ...
```

## Chunking Strategies

All strategies work across every supported format.

| Strategy | Aliases | Description |
|----------|---------|-------------|
| **RAG** (default) | `rag`, `semantic`, `embeddings` | Merges paragraphs under same heading hierarchy. 100–500 words/chunk. |
| **NLP** | `nlp`, `paragraph` | One paragraph = one chunk. Preserves exact boundaries. |
| **Token-aware** | `token_aware`, `technical` | Token-count constrained (256–512 tokens). Sentence-aware overlap. |
| **Small-to-big** | `small_to_big` | Hierarchical parent-child relationships for multi-granularity retrieval. |

```bash
extract doc.epub --min-words 200 --max-words 800
extract doc.epub --chunking-strategy token_aware
```

### Token Re-Chunking

Post-process extraction output into token-optimized chunks for embedding models:

```bash
token-rechunk document.json --mode retrieval       # 256-400 tokens, 15% overlap
token-rechunk document.json --mode recommendation  # 512-700 tokens
token-rechunk document.json --mode balanced        # 400-512 tokens
```

## Quality & Filtering

**Quality scoring** assigns each document a score (0–1) and route (A/B/C) based on paragraph length, heading density, vocabulary richness, and reference density.

**Noise filtering** (enabled by default) removes index pages, copyright boilerplate, and navigation fragments. Disable with `--no-filter-noise`.

**Tiny chunk filtering** removes low-signal chunks below configurable thresholds:

```bash
extract doc.epub --filter-tiny-chunks conservative  # default
extract doc.epub --filter-tiny-chunks aggressive
```

**Front/back matter detection** (EPUB) flags or removes dedications, endorsements, glossaries, and appendices:

```bash
extract book.epub --detect-front-matter             # Soft: adds quality_flags
extract book.epub --filter-front-matter              # Hard: removes detected chunks
```

**Quality flags** are soft labels on individual chunks (`below_rag_minimum`, `likely_noncore_matter_*`, `contains_reference_block_*`) that preserve content while signaling downstream consumers.

## Extractors

| Format | Extractor | Notes |
|--------|-----------|-------|
| EPUB | `EpubExtractor` | Front-matter detection, visual heading detection, nested hierarchy, spine-aware |
| PDF | `PdfExtractor` | pdfplumber backend |
| PDF | `MuPdfPdfExtractor` | Native Zig/MuPDF backend with font metadata for heading detection |
| HTML | `HtmlExtractor` | BeautifulSoup, semantic heading hierarchy |
| Markdown | `MarkdownExtractor` | ATX/setext headings, hierarchy preservation |
| JSON | `JsonExtractor` | Ingest preprocessed chunks (JSON/JSONL) |

All extractors follow a state machine (`CREATED → load → parse → extract_metadata → get_output_data`) and produce identical `Chunk` output.

### Native PDF Parser (Zig/MuPDF)

The `cores/` directory contains a Zig shared library wrapping MuPDF for high-performance PDF text extraction with per-span font metadata (name, size, bold/italic/mono flags, bounding boxes). `MuPdfPdfExtractor` uses font statistics to auto-detect headings without relying on PDF structure tags.

Requires MuPDF installed via Homebrew and Zig master branch. Falls back to `PdfExtractor` when unavailable.

## Analyzers

Domain-specific metadata enrichment via a plugin system:

- **`GenericAnalyzer`** — Title, author, basic metadata.
- **`CatholicAnalyzer`** — Document type classification (Encyclical, Decree, etc.), subject detection (Liturgy, Sacraments, Scripture), theme extraction, related document linking, geographic focus, promulgation dates.

```bash
extract encyclical.epub --analyzer catholic
```

## Configuration

Config merges from (highest priority first):

1. CLI flags
2. `./extraction.toml`
3. `pyproject.toml [tool.extraction]`
4. `~/.config/extraction/config.toml`
5. Built-in defaults

```bash
extract --show-config     # Display active configuration
extract --init-config     # Generate extraction.toml template
```

## Tools

| Command | Description |
|---------|-------------|
| `extract` | Unified extraction CLI for all formats |
| `token-rechunk` | Token-optimized re-chunking for embedding models |
| `annotate-chunks` | TUI for labeling chunk quality (active learning with LightGBM) |
| `capture-chunks` | TUI for chunk selection and review |
| `corpus-builder` | Build JSONL corpora from extracted chunks |
| `training-builder` | Prepare ML training datasets with stratified splits |
| `fix-hierarchy` | Repair malformed document hierarchies |
| `vatican-extract` | Vatican archive pipeline (discover → download → extract → upload) |
| `extract-images` | Scrape images from URLs and build EPUB galleries |

## Output Schema

```json
{
  "metadata": {
    "title": "Document Title",
    "author": "Author Name",
    "provenance": {
      "doc_id": "sha1-based-id",
      "source_file": "path/to/file.epub",
      "content_hash": "abc123..."
    },
    "quality": { "score": 0.87, "route": "A" }
  },
  "chunks": [
    {
      "stable_id": "deterministic-sha1",
      "text": "Chunk text content...",
      "hierarchy": {
        "level_1": "Part I",
        "level_2": "Chapter 1",
        "level_3": null
      },
      "word_count": 312,
      "quality_flags": [],
      "scripture_references": ["John 3:16"],
      "cross_references": [],
      "content_type": "body"
    }
  ]
}
```

NDJSON output is also supported (`--ndjson`).

## Testing

```bash
uv run pytest                          # All tests (~500)
uv run pytest -m "not integration"     # Skip integration tests
uv run pytest -k "test_name"           # Single test
uv run pytest --cov=src/extraction     # Coverage report
```

## Project Structure

```
extraction/
├── src/extraction/
│   ├── core/           # Models, chunking strategies, quality scoring, noise filtering
│   ├── extractors/     # EPUB, PDF, MuPDF-PDF, HTML, Markdown, JSON
│   ├── analyzers/      # CatholicAnalyzer, GenericAnalyzer
│   ├── _native/        # Python ctypes bindings for Zig/MuPDF library
│   ├── tools/          # Annotation TUI, capture TUI, corpus/training builders
│   ├── cli/            # CLI entry points
│   ├── pipelines/      # Vatican archive pipeline
│   ├── builders/       # EPUB gallery builder
│   ├── scrapers/       # Image scraping (static + Playwright)
│   └── storage/        # S3/R2 upload
├── cores/              # Zig/MuPDF native library source
├── tests/              # ~500 tests across 28 files
├── docs/               # MkDocs documentation source
└── pyproject.toml
```

## Links

- [Documentation](https://hello-world-bfree.github.io/extraction/)
- [PyPI](https://pypi.org/project/doc-extraction/)
- [GitHub](https://github.com/hello-world-bfree/extraction)
- [Issues](https://github.com/hello-world-bfree/extraction/issues)
