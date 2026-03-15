# CLI Reference: `extract`

Complete reference for the unified extraction CLI command.

## Synopsis

```bash
extract PATH [OPTIONS]
```

## Description

The `extract` command provides a unified interface for extracting structured data from multiple document formats (EPUB, PDF, HTML, Markdown, JSON). It automatically detects the document format, processes the content, and outputs JSON files with hierarchical chunks and rich metadata.

The extractor supports:

- **Single-file mode**: Process one document and write outputs to current directory
- **Batch mode**: Process all documents in a directory with optional recursion
- **Multiple formats**: EPUB, PDF, HTML, Markdown, JSON
- **Domain analysis**: Catholic-specific or generic metadata enrichment
- **Quality routing**: Automatic quality scoring (routes A/B/C)
- **Chunking strategies**: RAG-optimized or NLP paragraph-level chunking

## Arguments

### Positional Arguments

| Argument | Description | Default |
|----------|-------------|---------|
| `PATH` | Path to document file or directory. If omitted, prompts user for input. | Interactive prompt |

## Options

### Input/Output Options

| Option | Description | Default |
|--------|-------------|---------|
| `-o, --output BASE` | Base name for output files (single-file mode only). If not specified, uses source filename. | Source filename |
| `--output-dir DIR` | Directory to write outputs. Creates directory if it doesn't exist. | Current directory |
| `--ndjson` | Also emit chunks as newline-delimited JSON (`.ndjson` file). | Disabled |

### Batch Processing

| Option | Description | Default |
|--------|-------------|---------|
| `-r, --recursive` | When processing a directory, include subdirectories. Searches for all supported file extensions recursively. | Non-recursive |

### Domain Analysis

| Option | Description | Default |
|--------|-------------|---------|
| `--analyzer {catholic\|generic}` | Domain-specific metadata enrichment. `catholic`: Detects encyclicals, liturgical documents, etc. `generic`: Minimal enrichment. | `generic` |

### Extraction Options (EPUB-specific)

These options are maintained for backward compatibility with legacy EPUB parsers. Most are EPUB-specific but some apply to other formats.

| Option | Description | Default |
|--------|-------------|---------|
| `--toc-level LEVEL` | Hierarchy level (1-6) where TOC titles are inserted. `1` = top-level, `6` = deepest. | `3` |
| `--min-words WORDS` | Minimum words for paragraph inclusion. Paragraphs below this threshold are skipped. | `1` |
| `--min-block-words WORDS` | Minimum words to chunk generic block tags (div, section, etc.). | `2` |
| `--preserve-hierarchy` | Preserve heading hierarchy across EPUB spine documents. By default, hierarchy resets at document boundaries. | Disabled |
| `--reset-depth DEPTH` | When hierarchy is **not** preserved, clear levels ≥ this depth (1-6) at document boundaries. | `2` |
| `--deny-class REGEX` | Regex pattern for CSS classes to exclude (e.g., footnotes, calibre artifacts). | `^(?:calibre\d+\|note\|footnote)$` |
| `--filter-tiny-chunks {off\|conservative\|standard\|aggressive}` | Filter tiny chunks (&lt;5 words) as noise. See [Tiny Chunk Filtering](#tiny-chunk-filtering). | `conservative` |
| `--no-filter-noise` | Disable semantic noise filtering (index pages, reference lists, boilerplate). By default, noise filtering is **enabled** across all formats. | Noise filtering enabled |

### Chunking Strategy

| Option | Description | Default |
|--------|-------------|---------|
| `--chunking-strategy {rag\|semantic\|embeddings\|nlp\|paragraph}` | Chunking strategy. `rag`/`semantic`/`embeddings`: Merge paragraphs (100-500 words) for embeddings. `nlp`/`paragraph`: One paragraph per chunk. | `rag` |
| `--min-chunk-words WORDS` | Minimum words per chunk for RAG/semantic strategy. | `100` |
| `--max-chunk-words WORDS` | Maximum words per chunk for RAG/semantic strategy. | `500` |

### Logging

| Option | Description | Default |
|--------|-------------|---------|
| `-v, --verbose` | Enable verbose logging (DEBUG level). Shows detailed extraction steps. | INFO level |
| `-q, --quiet` | Quiet logging (WARNING level only). Suppresses informational messages. | INFO level |
| `--debug-dump` | Write debug information to `./debug/` directory (EPUB only). Includes spine structure, TOC, and per-document chunks. | Disabled |

## Exit Codes

| Code | Meaning |
|------|---------|
| `0` | Success: All documents processed successfully |
| `1` | Partial failure: Some documents failed processing (batch mode) or single document failed |
| `2` | Invalid input: No path provided or path not found |

## Output Files

For each processed document, the extractor creates the following files:

| File | Description |
|------|-------------|
| `{base}.json` | Complete document data: metadata, chunks, extraction info |
| `{base}_metadata.json` | Metadata only (title, author, quality, provenance) |
| `{base}_hierarchy_report.txt` | Human-readable hierarchy tree visualization |
| `{base}.ndjson` | Newline-delimited JSON chunks (optional, with `--ndjson`) |

Where `{base}` is the base filename (from `--output` or source filename).

## Examples

### Single File Processing

Process a single EPUB with default settings (RAG chunking, noise filtering enabled):

```bash
extract prayer_primer.epub
```

Process with custom output name:

```bash
extract prayer_primer.epub --output prayer
```

Process PDF with NLP paragraph-level chunking:

```bash
extract document.pdf --chunking-strategy nlp
```

### Batch Processing

Process all documents in a directory:

```bash
extract documents/ --output-dir outputs/
```

Recursively process directory tree:

```bash
extract library/ -r --output-dir processed/
```

### Domain-Specific Analysis

Extract Catholic religious text with domain analyzer:

```bash
extract encyclical.epub --analyzer catholic
```

### Custom Chunking

Create larger chunks (200-800 words) for embeddings:

```bash
extract book.epub --min-chunk-words 200 --max-chunk-words 800
```

### Debugging

Enable debug logging and dump intermediate data:

```bash
extract problematic.epub -v --debug-dump
```

## Chunking Strategies

### RAG Strategy (Default)

**Aliases**: `rag`, `semantic`, `embeddings`

**Behavior**: Merges consecutive paragraphs under the same heading hierarchy until reaching target chunk size (100-500 words).

**Use for**: Vector search, RAG systems, semantic retrieval, embeddings.

**Output**: Fewer, larger chunks with `merged_paragraph_ids` and `source_paragraph_count` metadata.

**Example**:

```bash
extract book.epub
extract book.epub --chunking-strategy rag --min-chunk-words 150 --max-chunk-words 400
```

### NLP Strategy

**Aliases**: `nlp`, `paragraph`

**Behavior**: One paragraph per chunk (preserves exact paragraph boundaries).

**Use for**: Fine-grained NLP tasks, sentence classification, named entity recognition.

**Output**: More, smaller chunks (~40-80 words on average).

**Example**:

```bash
extract book.epub --chunking-strategy nlp
```

## Tiny Chunk Filtering

Filters chunks with fewer than 5 words as noise. Three tiers:

### Conservative (Default)

**Removes**:
- Index entries (`"experimentation, 17"`)
- TOC fragments (`"• References"`)
- Punctuation (`"N"`, `"◦"`)
- Figure labels (`"Listing 10.9"`)
- Page numbers (`"305"`)

**Reduction**: ~47.6% of tiny chunks

**Risk**: Zero (no false positives in validation)

```bash
extract book.epub
extract book.epub --filter-tiny-chunks conservative
```

### Standard

**Adds**:
- Answer keys (`"1. C"`)
- Single-word bullets (`"• Next"`)
- Page ranges (`"305 - 310"`)

**Reduction**: ~48.8%

**Risk**: Very low

```bash
extract book.epub --filter-tiny-chunks standard
```

### Aggressive

**Adds**:
- All appendix content
- Cross-references (`"See Chapter 7"`)

**Reduction**: ~60%

**Risk**: Medium (may remove valid short content)

```bash
extract book.epub --filter-tiny-chunks aggressive
```

### Disabled

No filtering (keep all tiny chunks):

```bash
extract book.epub --filter-tiny-chunks off
```

## Noise Filtering

**Default**: Enabled for all formats.

The `--no-filter-noise` flag disables semantic noise filtering which removes:

- **Index pages**: Reference lists, number sequences
- **Navigation**: TOC entries, "Next/Previous" links
- **Boilerplate**: Copyright notices, ISBN numbers

**When to disable**:
- Processing already-clean documents
- Need exact paragraph counts for benchmarking
- Debugging extraction issues

```bash
extract document.html --no-filter-noise
```

## Format Detection

The extractor automatically detects document format from file extension:

| Extension | Format | Extractor |
|-----------|--------|-----------|
| `.epub` | EPUB | `EpubExtractor` |
| `.pdf` | PDF | `PdfExtractor` |
| `.html`, `.htm` | HTML | `HtmlExtractor` |
| `.md`, `.markdown`, `.txt` | Markdown | `MarkdownExtractor` |
| `.json` | JSON | `JsonExtractor` |

## Environment Variables

None. All configuration is via CLI flags.

## Configuration Files

Not supported. Use CLI flags for all configuration.

## Quality Routing

All documents are automatically scored and routed:

| Route | Score | Meaning | Action |
|-------|-------|---------|--------|
| **A** | ≥ 0.7 | High quality | Automatic processing |
| **B** | 0.4 - 0.7 | Medium quality | Review recommended |
| **C** | &lt; 0.4 | Low quality | Manual review required |

Quality signals include:
- Average paragraph length
- Heading density
- Vocabulary richness
- Scripture/cross-reference density (for Catholic texts)

Route information is included in output JSON (`metadata.quality.route`).

## See Also

- [Configuration Reference](../configuration.md) - Configuration dataclass options
- [Output Schema Reference](../output-schema.md) - JSON output format
- [BaseExtractor API](../api/base-extractor.md) - Programmatic usage
- [Quick Start Tutorial](../../getting-started/quickstart.md) - Basic usage examples
- [Multi-Format Extraction](../../getting-started/multi-format.md) - Batch processing patterns
