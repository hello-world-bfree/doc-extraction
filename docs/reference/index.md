# Reference Documentation

Comprehensive technical reference for the extraction library.

## Overview

This section provides detailed technical documentation for:

- **CLI commands** - Complete command-line interface reference
- **Configuration** - All config dataclasses and options
- **Output schema** - JSON output format specification
- **API reference** - Programmatic interface documentation

## Reference Sections

### [CLI Reference](cli/extract.md)

Complete reference for the `extract` command:

- All command-line flags and options
- Usage patterns and examples
- Exit codes
- Output files

**Quick links**:

- [Chunking strategies](cli/extract.md#chunking-strategies)
- [Tiny chunk filtering](cli/extract.md#tiny-chunk-filtering)
- [Noise filtering](cli/extract.md#noise-filtering)
- [Quality routing](cli/extract.md#quality-routing)

---

### [Configuration Reference](configuration.md)

All configuration dataclasses with validation rules:

- `BaseExtractorConfig` - Base options for all formats
- `EpubExtractorConfig` - EPUB-specific options
- `PdfExtractorConfig` - PDF-specific options
- `HtmlExtractorConfig` - HTML-specific options
- `MarkdownExtractorConfig` - Markdown-specific options
- `JsonExtractorConfig` - JSON import/rechunk options

**Quick links**:

- [Default values summary](configuration.md#default-values-summary)
- [Config inheritance](configuration.md#configuration-inheritance)
- [Validation rules](configuration.md#validation-rules)

---

### [Output Schema Reference](output-schema.md)

Complete JSON output format specification:

- Document structure (metadata, chunks, extraction_info)
- Metadata fields (core + domain-enriched)
- Chunk fields (all 20+ fields)
- Provenance and quality objects

**Quick links**:

- [Chunk fields](output-schema.md#chunk-fields)
- [Metadata object](output-schema.md#metadata-object)
- [Quality object](output-schema.md#quality-object)
- [Complete example](output-schema.md#complete-example)

---

### API Reference

#### [BaseExtractor](api/base-extractor.md)

Base class for all extractors:

- Constructor and state machine
- Public methods: `load()`, `parse()`, `extract_metadata()`, `get_output_data()`
- Properties: `chunks`, `metadata`, `quality`, `provenance`
- Protected methods for subclassing

**Quick links**:

- [State machine](api/base-extractor.md#state-machine)
- [Complete usage example](api/base-extractor.md#complete-usage-example)
- [Error handling](api/base-extractor.md#error-handling)
- [Subclassing guide](api/base-extractor.md#subclassing-baseextractor)

#### [EpubExtractor](api/epub-extractor.md)

EPUB-specific extractor:

- TOC hierarchy mapping
- Spine document processing
- Hierarchy preservation options
- Tiny chunk filtering
- Footnote detection

**Quick links**:

- [TOC hierarchy mapping](api/epub-extractor.md#toc-hierarchy-mapping)
- [Hierarchy preservation](api/epub-extractor.md#hierarchy-preservation)
- [Tiny chunk filtering](api/epub-extractor.md#tiny-chunk-filtering)
- [Debug output](api/epub-extractor.md#debug-output)

#### [PdfExtractor](api/pdf-extractor.md)

PDF-specific extractor:

- Page-by-page extraction
- Font-based heading detection
- OCR support (experimental)
- Paragraph detection

**Quick links**:

- [Heading detection](api/pdf-extractor.md#heading-detection)
- [Page processing](api/pdf-extractor.md#page-processing)
- [OCR support](api/pdf-extractor.md#ocr-support-experimental)
- [Limitations](api/pdf-extractor.md#limitations)

---

## Quick Reference Tables

### Configuration Defaults

| Config Class | Key Defaults |
|--------------|--------------|
| `BaseExtractorConfig` | `chunking_strategy="rag"`, `min_chunk_words=100`, `max_chunk_words=500` |
| `EpubExtractorConfig` | + `toc_hierarchy_level=3`, `filter_tiny_chunks="conservative"` |
| `PdfExtractorConfig` | + `heading_font_threshold=1.2`, `use_ocr=False` |

[Full defaults →](configuration.md#default-values-summary)

### Quality Routes

| Route | Score | Meaning | Action |
|-------|-------|---------|--------|
| A | ≥ 0.7 | High quality | Automatic processing |
| B | 0.4 - 0.7 | Medium quality | Review recommended |
| C | &lt; 0.4 | Low quality | Manual review required |

[Quality routing details →](cli/extract.md#quality-routing)

### Chunking Strategies

| Strategy | Aliases | Behavior | Use Case |
|----------|---------|----------|----------|
| RAG | `semantic`, `embeddings` | Merge paragraphs (100-500 words) | Embeddings, vector search |
| NLP | `paragraph` | One paragraph per chunk | Fine-grained NLP tasks |

[Chunking strategies details →](cli/extract.md#chunking-strategies)

### File Extensions

| Extension | Format | Extractor |
|-----------|--------|-----------|
| `.epub` | EPUB | `EpubExtractor` |
| `.pdf` | PDF | `PdfExtractor` |
| `.html`, `.htm` | HTML | `HtmlExtractor` |
| `.md`, `.markdown`, `.txt` | Markdown | `MarkdownExtractor` |
| `.json` | JSON | `JsonExtractor` |

[Format detection →](cli/extract.md#format-detection)

## Common Tasks

### How do I...

**...process a single document?**

```bash
extract document.epub
```

[CLI Reference →](cli/extract.md)

**...batch process a directory?**

```bash
extract documents/ -r --output-dir outputs/
```

See [CLI Reference](cli/extract.md#batch-processing) for details.

**...configure chunking for embeddings?**

```python
from extraction.extractors.configs import EpubExtractorConfig

config = EpubExtractorConfig(
    chunking_strategy="rag",
    min_chunk_words=150,
    max_chunk_words=400
)
```

[Configuration Reference →](configuration.md)

**...access chunks programmatically?**

```python
extractor.load()
extractor.parse()

for chunk in extractor.chunks:
    print(f"{chunk.paragraph_id}: {chunk.text[:50]}")
```

[BaseExtractor API →](api/base-extractor.md)

**...understand the output JSON?**

See [Output Schema Reference](output-schema.md) for complete specification.

**...filter noise chunks?**

```bash
extract document.epub --filter-tiny-chunks standard --no-filter-noise
```

[Tiny Chunk Filtering →](cli/extract.md#tiny-chunk-filtering)

## Navigation

**By Topic**:

- [CLI usage](cli/extract.md) - Command-line interface
- [Configuration](configuration.md) - All config options
- [Output format](output-schema.md) - JSON schema
- [Programmatic usage](api/base-extractor.md) - API interface

**By Format**:

- [EPUB extraction](api/epub-extractor.md) - EPUB-specific features
- [PDF extraction](api/pdf-extractor.md) - PDF-specific features

**By Task**:

- Batch processing → [CLI Reference](cli/extract.md#batch-processing)
- Custom chunking → [Chunking Strategies How-To](../how-to/chunking-strategy.md)
- Quality analysis → [Quality Routing](cli/extract.md#quality-routing)
- Error handling → [BaseExtractor Error Handling](api/base-extractor.md#error-handling)

## External Resources

- [Source Code](https://github.com/hello-world-bfree/extraction) - GitHub repository
- [PyPI Package](https://pypi.org/project/doc-extraction/) - Python package
- [Issue Tracker](https://github.com/hello-world-bfree/extraction/issues) - Bug reports

## Related Documentation

- [Getting Started](../getting-started/quickstart.md) - Quickstart guide
- [How-To Guides](../how-to/chunking-strategy.md) - Task-focused guides
- [Explanation](../explanation/architecture.md) - Architecture overview
