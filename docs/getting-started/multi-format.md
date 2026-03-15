# Multi-Format Extraction

The Extraction Library supports EPUB, PDF, HTML, Markdown, and JSON documents with a **unified API**. All formats produce the same output schema and support the same features (RAG/NLP chunking, noise filtering, hierarchy preservation).

## Format Overview

| Format | Best For | Hierarchy Source | Common Use Cases |
|--------|----------|------------------|------------------|
| **EPUB** | Books, publications | Table of Contents | eBooks, religious texts, novels |
| **PDF** | Reports, papers | Font size heuristics | Academic papers, reports, scanned documents |
| **HTML** | Web content | HTML heading tags | Documentation sites, articles, web archives |
| **Markdown** | Documentation | Markdown headings | README files, technical docs, notes |
| **JSON** | Re-import | Preserved from original | Re-chunking, post-processing |

## EPUB Extraction

EPUBs are the primary format for book extraction. The library parses the table of contents to build a hierarchical structure.

### CLI

```bash
# Basic extraction
extract book.epub

# With Catholic domain analysis
extract encyclical.epub --analyzer catholic

# Preserve hierarchy across spine documents
extract book.epub --preserve-hierarchy

# Custom chunking
extract book.epub --chunking-strategy rag --min-chunk-words 150
```

### Python API

```python
from extraction.extractors import EpubExtractor

# Basic usage
extractor = EpubExtractor("book.epub")
extractor.load()
extractor.parse()

# With configuration
config = {
    'chunking_strategy': 'rag',
    'min_chunk_words': 100,
    'max_chunk_words': 500,
    'preserve_hierarchy_across_docs': True,
    'toc_hierarchy_level': 2,  # TOC titles populate level_2
}

extractor = EpubExtractor("book.epub", config=config)
extractor.load()
extractor.parse()

# Access chunks
for chunk in extractor.chunks:
    print(f"Section: {chunk.hierarchy.get('level_1', 'Unknown')}")
    print(f"Text: {chunk.text[:100]}...")
```

### EPUB-Specific Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `toc_hierarchy_level` | int | 1 | Which hierarchy level TOC titles populate |
| `preserve_hierarchy_across_docs` | bool | False | Keep hierarchy across spine documents |
| `class_denylist` | list | See code | CSS classes to exclude from extraction |
| `preserve_formatting` | bool | False | Preserve poetry, blockquotes, lists, tables |

**Example with all options**:

```python
config = {
    'chunking_strategy': 'rag',
    'min_chunk_words': 100,
    'max_chunk_words': 500,
    'toc_hierarchy_level': 1,
    'preserve_hierarchy_across_docs': True,
    'preserve_formatting': True,
    'filter_noise': True,
    'filter_tiny_chunks': 'conservative',
}

extractor = EpubExtractor("book.epub", config=config)
```

## PDF Extraction

PDF extraction uses font size heuristics to detect headings and build hierarchy.

### CLI

```bash
# Basic extraction
extract document.pdf

# Lower heading threshold (detect more headings)
extract document.pdf --heading-font-threshold 1.1

# Disable OCR (for text-based PDFs)
extract document.pdf --no-use-ocr
```

### Python API

```python
from extraction.extractors import PdfExtractor

# Basic usage
extractor = PdfExtractor("document.pdf")
extractor.load()
extractor.parse()

# With configuration
config = {
    'chunking_strategy': 'rag',
    'min_chunk_words': 100,
    'max_chunk_words': 500,
    'heading_font_threshold': 1.2,  # Font size ratio for heading detection
    'use_ocr': False,  # Disable OCR for text-based PDFs
}

extractor = PdfExtractor("document.pdf", config=config)
extractor.load()
extractor.parse()
```

### PDF-Specific Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `heading_font_threshold` | float | 1.2 | Font size ratio for heading detection (1.2 = 20% larger) |
| `use_ocr` | bool | True | Enable OCR for scanned PDFs |
| `min_paragraph_words` | int | 3 | Minimum words to be considered a paragraph |

!!! warning "Heading Detection"
    PDF heading detection relies on font size differences. If your PDF uses the same font size for headings and body text, headings won't be detected. Try lowering `heading_font_threshold` to 1.1 or 1.05.

## HTML Extraction

HTML extraction uses semantic HTML heading tags (`<h1>` through `<h6>`) to build hierarchy.

### CLI

```bash
# Basic extraction
extract page.html

# Preserve links
extract page.html --preserve-links

# Process entire site archive
extract site_archive/ -r --output-dir outputs/
```

### Python API

```python
from extraction.extractors import HtmlExtractor

# Basic usage
extractor = HtmlExtractor("page.html")
extractor.load()
extractor.parse()

# With configuration
config = {
    'chunking_strategy': 'rag',
    'min_chunk_words': 100,
    'max_chunk_words': 500,
    'preserve_links': True,  # Keep href attributes in output
}

extractor = HtmlExtractor("page.html", config=config)
extractor.load()
extractor.parse()
```

### HTML-Specific Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `preserve_links` | bool | False | Preserve hyperlink URLs in output |
| `min_paragraph_words` | int | 3 | Minimum words to be considered a paragraph |

## Markdown Extraction

Markdown extraction uses heading markers (`#`, `##`, etc.) to build hierarchy.

### CLI

```bash
# Basic extraction
extract README.md

# Preserve code blocks
extract GUIDE.md --preserve-code-blocks

# Extract YAML frontmatter
extract post.md --extract-frontmatter
```

### Python API

```python
from extraction.extractors import MarkdownExtractor

# Basic usage
extractor = MarkdownExtractor("README.md")
extractor.load()
extractor.parse()

# With configuration
config = {
    'chunking_strategy': 'rag',
    'min_chunk_words': 100,
    'max_chunk_words': 500,
    'preserve_code_blocks': True,  # Keep code blocks intact
    'extract_frontmatter': True,   # Parse YAML frontmatter
}

extractor = MarkdownExtractor("README.md", config=config)
extractor.load()
extractor.parse()

# Access frontmatter (if present)
if hasattr(extractor, 'frontmatter'):
    print(extractor.frontmatter)  # Dict of YAML frontmatter
```

### Markdown-Specific Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `preserve_code_blocks` | bool | True | Keep code blocks as separate chunks |
| `extract_frontmatter` | bool | True | Parse YAML frontmatter |
| `min_paragraph_words` | int | 3 | Minimum words to be considered a paragraph |

## JSON Extraction

JSON extraction re-imports previously extracted documents for re-chunking or post-processing.

### CLI

```bash
# Re-chunk with different settings
extract document.json --chunking-strategy nlp --output document_nlp.json

# Re-import and apply different analyzer
extract document.json --analyzer catholic --output document_enriched.json
```

### Python API

```python
from extraction.extractors import JsonExtractor

# Basic re-import
extractor = JsonExtractor("document.json")
extractor.load()
extractor.parse()

# Re-chunk with new strategy
config = {
    'chunking_strategy': 'nlp',  # Change from RAG to NLP
}

extractor = JsonExtractor("document.json", config=config)
extractor.load()
extractor.parse()

# New chunks with paragraph-level granularity
print(f"Re-chunked into {len(extractor.chunks)} chunks")
```

### JSON-Specific Options

JSON extraction uses the same options as other extractors. It's primarily used for:

1. Re-chunking with different strategies
2. Re-applying analyzers
3. Post-processing pipelines

## Side-by-Side Comparison

Let's extract the same content from different formats:

=== "EPUB"

    ```python
    from extraction.extractors import EpubExtractor

    extractor = EpubExtractor("book.epub", config={
        'chunking_strategy': 'rag',
        'min_chunk_words': 100,
        'max_chunk_words': 500,
    })
    extractor.load()
    extractor.parse()

    # Output: ~500 chunks (merged paragraphs)
    # Hierarchy: From table of contents
    # Quality: High (structured book format)
    ```

=== "PDF"

    ```python
    from extraction.extractors import PdfExtractor

    extractor = PdfExtractor("book.pdf", config={
        'chunking_strategy': 'rag',
        'min_chunk_words': 100,
        'max_chunk_words': 500,
        'heading_font_threshold': 1.2,
    })
    extractor.load()
    extractor.parse()

    # Output: ~500 chunks (merged paragraphs)
    # Hierarchy: From font size heuristics
    # Quality: Medium (depends on PDF structure)
    ```

=== "HTML"

    ```python
    from extraction.extractors import HtmlExtractor

    extractor = HtmlExtractor("book.html", config={
        'chunking_strategy': 'rag',
        'min_chunk_words': 100,
        'max_chunk_words': 500,
    })
    extractor.load()
    extractor.parse()

    # Output: ~500 chunks (merged paragraphs)
    # Hierarchy: From <h1>-<h6> tags
    # Quality: High (semantic HTML)
    ```

=== "Markdown"

    ```python
    from extraction.extractors import MarkdownExtractor

    extractor = MarkdownExtractor("book.md", config={
        'chunking_strategy': 'rag',
        'min_chunk_words': 100,
        'max_chunk_words': 500,
    })
    extractor.load()
    extractor.parse()

    # Output: ~500 chunks (merged paragraphs)
    # Hierarchy: From # heading markers
    # Quality: High (structured markup)
    ```

All produce the **same output schema** with `metadata` and `chunks` keys.

## Format-Specific Tips

### EPUB

- Use `--preserve-hierarchy` for books with multiple spine documents
- Set `toc_hierarchy_level` based on your TOC structure (typically 1 or 2)
- Enable `--preserve-formatting` for poetry or structured content

### PDF

- Lower `heading_font_threshold` if headings aren't detected (try 1.1 or 1.05)
- Disable OCR (`--no-use-ocr`) for text-based PDFs to speed up processing
- PDF quality depends heavily on source PDF structure

### HTML

- Works best with semantic HTML (proper heading tags)
- Enable `--preserve-links` to keep hyperlink context
- Great for processing documentation sites and web archives

### Markdown

- Ideal for technical documentation and README files
- Use `--extract-frontmatter` to capture YAML metadata
- Code blocks are preserved as separate chunks by default

### JSON

- Use for re-chunking with different strategies
- Use for applying different analyzers post-extraction
- Preserves all original metadata

## Batch Processing Multiple Formats

Process a mixed directory of documents:

```bash
# Auto-detects format by extension
extract documents/ -r --output-dir outputs/

# Contents of documents/:
# - books/*.epub
# - papers/*.pdf
# - docs/*.html
# - notes/*.md
```

The CLI automatically detects format and uses the appropriate extractor.

## Unified Configuration

All formats support the same base configuration:

```python
base_config = {
    # Chunking
    'chunking_strategy': 'rag',  # or 'nlp'
    'min_chunk_words': 100,
    'max_chunk_words': 500,

    # Filtering
    'filter_noise': True,
    'filter_tiny_chunks': 'conservative',

    # Formatting
    'preserve_formatting': False,

    # Paragraph detection
    'min_paragraph_words': 3,
}
```

Format-specific configs extend this base:

```python
# EPUB-specific
epub_config = {
    **base_config,
    'toc_hierarchy_level': 1,
    'preserve_hierarchy_across_docs': True,
}

# PDF-specific
pdf_config = {
    **base_config,
    'heading_font_threshold': 1.2,
    'use_ocr': False,
}

# HTML-specific
html_config = {
    **base_config,
    'preserve_links': True,
}

# Markdown-specific
md_config = {
    **base_config,
    'preserve_code_blocks': True,
    'extract_frontmatter': True,
}
```

## Next Steps

<div class="grid cards" markdown>

-   :material-database:{ .lg .middle } **[Building a Vector DB](vector-db.md)**

    ---

    End-to-end RAG pipeline with multi-format documents

-   :material-tune:{ .lg .middle } **[Choosing Chunking Strategy](../how-to/chunking-strategy.md)**

    ---

    RAG vs NLP mode - when to use each

-   :material-cog:{ .lg .middle } **[Configuration Reference](../reference/configuration.md)**

    ---

    Complete list of all configuration options

-   :material-api:{ .lg .middle } **[API Reference](../reference/api/base-extractor.md)**

    ---

    Detailed API documentation for all extractors

</div>

## Summary

All five formats (EPUB, PDF, HTML, Markdown, JSON) work through the same API:

1. Create extractor with optional config
2. Call `load()` to load source
3. Call `parse()` to extract chunks
4. Access `chunks` and `metadata`

The **output schema is identical** regardless of format - only the hierarchy source and format-specific options differ.
