# Configuration Reference

Complete reference for all configuration dataclasses used by extractors.

## Overview

All extractors accept a configuration dataclass that controls extraction behavior. Configuration classes follow an inheritance hierarchy:

```
BaseExtractorConfig (all formats)
├── EpubExtractorConfig (EPUB-specific)
├── PdfExtractorConfig (PDF-specific)
├── HtmlExtractorConfig (HTML-specific)
├── MarkdownExtractorConfig (Markdown-specific)
└── JsonExtractorConfig (JSON-specific)
```

## BaseExtractorConfig

Base configuration inherited by all format-specific configs.

**Module**: `extraction.extractors.configs`

**Class**: `BaseExtractorConfig`

### Fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `chunking_strategy` | `Literal["rag", "nlp", "semantic", "embeddings", "paragraph"]` | `"rag"` | Chunking strategy. `rag`/`semantic`/`embeddings`: Merge paragraphs (100-500 words). `nlp`/`paragraph`: One paragraph per chunk. |
| `min_chunk_words` | `int` | `100` | Minimum words per chunk (RAG strategy only). |
| `max_chunk_words` | `int` | `500` | Maximum words per chunk (RAG strategy only). |
| `preserve_hierarchy_levels` | `int` | `3` | Number of hierarchy levels to preserve when merging chunks (0-6). |
| `filter_noise` | `bool` | `True` | Filter index pages, TOC, and copyright boilerplate. |

### Validation Rules

- `chunking_strategy`: Must be one of `["rag", "nlp", "semantic", "embeddings", "paragraph"]`
  - Aliases: `semantic` → `rag`, `embeddings` → `rag`, `paragraph` → `nlp`
- `min_chunk_words`: Must be ≥ 1
- `max_chunk_words`: Must be ≥ `min_chunk_words`
- `preserve_hierarchy_levels`: Must be 0-6

### Example

```python
from extraction.extractors.configs import BaseExtractorConfig

config = BaseExtractorConfig(
    chunking_strategy="rag",
    min_chunk_words=150,
    max_chunk_words=400,
    preserve_hierarchy_levels=3,
    filter_noise=True
)
```

---

## EpubExtractorConfig

Configuration for EPUB extraction.

**Module**: `extraction.extractors.configs`

**Class**: `EpubExtractorConfig`

**Inherits**: `BaseExtractorConfig`

### Additional Fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `toc_hierarchy_level` | `int` | `3` | Hierarchy level (1-6) where TOC titles are inserted. `1` = top-level, `6` = deepest. |
| `min_paragraph_words` | `int` | `6` | Minimum words to consider text as a paragraph. Paragraphs below this are skipped. |
| `min_block_words` | `int` | `30` | Minimum words to chunk generic block tags (div, section, etc.). |
| `preserve_hierarchy_across_docs` | `bool` | `False` | Whether to preserve heading hierarchy across EPUB spine documents. `False` = reset at doc boundaries. |
| `reset_depth` | `int` | `2` | When not preserving hierarchy, clear levels ≥ this depth (1-6) at document boundaries. |
| `class_denylist` | `str` | `r"^(?:calibre\d+\|note\|footnote)$"` | Regex pattern for CSS classes to exclude (footnotes, calibre artifacts). |
| `filter_tiny_chunks` | `Literal["off", "conservative", "standard", "aggressive"]` | `"conservative"` | Tiny chunk filtering level. `conservative` = index/TOC/punctuation (-47.6%), `standard` = +bullets/refs (-48.8%), `aggressive` = +appendixes (-60%), `off` = disabled. |

### Validation Rules

All base rules plus:

- `toc_hierarchy_level`: Must be 1-6
- `min_paragraph_words`: Must be ≥ 1
- `min_block_words`: Must be ≥ 1
- `reset_depth`: Must be 1-6
- `class_denylist`: Must be valid regex pattern
- `filter_tiny_chunks`: Must be one of `["off", "conservative", "standard", "aggressive"]`

### Example

```python
from extraction.extractors.configs import EpubExtractorConfig

config = EpubExtractorConfig(
    # Base config
    chunking_strategy="rag",
    min_chunk_words=100,
    max_chunk_words=500,
    filter_noise=True,

    # EPUB-specific
    toc_hierarchy_level=3,
    min_paragraph_words=6,
    min_block_words=30,
    preserve_hierarchy_across_docs=False,
    reset_depth=2,
    class_denylist=r"^(?:calibre\d+|note|footnote)$",
    filter_tiny_chunks="conservative"
)
```

### Hierarchy Preservation Behavior

**`preserve_hierarchy_across_docs=False`** (default):

When processing multi-document EPUBs (e.g., each chapter is a separate HTML file):

1. Hierarchy levels ≥ `reset_depth` are cleared at document boundaries
2. Hierarchy levels &lt; `reset_depth` are preserved
3. TOC titles are inserted at `toc_hierarchy_level`

**Example** with `reset_depth=2`:

```
Document 1:
  level_1: "Part I"      ← Preserved
  level_2: "Chapter 1"   ← RESET at boundary
  level_3: "Section 1.1" ← RESET at boundary

Document 2:
  level_1: "Part I"      ← Still set
  level_2: ""            ← Cleared
  level_3: ""            ← Cleared
  (TOC title inserted at level_3)
```

**`preserve_hierarchy_across_docs=True`**:

Hierarchy flows continuously across all spine documents (no reset).

---

## PdfExtractorConfig

Configuration for PDF extraction.

**Module**: `extraction.extractors.configs`

**Class**: `PdfExtractorConfig`

**Inherits**: `BaseExtractorConfig`

### Additional Fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `min_paragraph_words` | `int` | `5` | Minimum words to consider text as a paragraph. |
| `heading_font_threshold` | `float` | `1.2` | Font size multiplier to detect headings. Text with font size ≥ `avg_font_size * threshold` is treated as heading. Range: 1.0-3.0. |
| `use_ocr` | `bool` | `False` | Whether to use OCR for image-based PDFs (requires Tesseract). |
| `ocr_lang` | `str` | `"eng"` | OCR language code. Common values: `"eng"` (English), `"fra"` (French), `"spa"` (Spanish), `"deu"` (German). |

### Validation Rules

All base rules plus:

- `min_paragraph_words`: Must be ≥ 1
- `heading_font_threshold`: Must be 1.0-3.0
- `ocr_lang`: Must be valid language code (≥ 2 characters)

### Example

```python
from extraction.extractors.configs import PdfExtractorConfig

config = PdfExtractorConfig(
    # Base config
    chunking_strategy="rag",
    min_chunk_words=100,
    max_chunk_words=500,

    # PDF-specific
    min_paragraph_words=5,
    heading_font_threshold=1.2,
    use_ocr=False,
    ocr_lang="eng"
)
```

### Heading Detection

The `heading_font_threshold` controls sensitivity of heading detection:

- **1.1** - Very sensitive (may detect emphasized text as headings)
- **1.2** - Default (balanced)
- **1.5** - Conservative (only very large text becomes headings)

**Example**:

```python
# Sensitive heading detection (for PDFs with subtle font differences)
config = PdfExtractorConfig(heading_font_threshold=1.1)

# Conservative (for PDFs where body text varies in size)
config = PdfExtractorConfig(heading_font_threshold=1.5)
```

---

## HtmlExtractorConfig

Configuration for HTML extraction.

**Module**: `extraction.extractors.configs`

**Class**: `HtmlExtractorConfig`

**Inherits**: `BaseExtractorConfig`

### Additional Fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `min_paragraph_words` | `int` | `1` | Minimum words to consider text as a paragraph. |
| `preserve_links` | `bool` | `False` | Whether to preserve hyperlinks in output text (experimental). |

### Validation Rules

All base rules plus:

- `min_paragraph_words`: Must be ≥ 0

### Example

```python
from extraction.extractors.configs import HtmlExtractorConfig

config = HtmlExtractorConfig(
    chunking_strategy="rag",
    min_paragraph_words=1,
    preserve_links=False,
    filter_noise=True
)
```

---

## MarkdownExtractorConfig

Configuration for Markdown extraction.

**Module**: `extraction.extractors.configs`

**Class**: `MarkdownExtractorConfig`

**Inherits**: `BaseExtractorConfig`

### Additional Fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `min_paragraph_words` | `int` | `1` | Minimum words to consider text as a paragraph. |
| `preserve_code_blocks` | `bool` | `True` | Whether to preserve code blocks as separate chunks. |
| `extract_frontmatter` | `bool` | `True` | Whether to extract YAML frontmatter as metadata. |

### Validation Rules

All base rules plus:

- `min_paragraph_words`: Must be ≥ 0

### Example

```python
from extraction.extractors.configs import MarkdownExtractorConfig

config = MarkdownExtractorConfig(
    chunking_strategy="nlp",
    preserve_code_blocks=True,
    extract_frontmatter=True
)
```

### Frontmatter Extraction

When `extract_frontmatter=True`, YAML frontmatter is parsed and merged into document metadata:

```markdown
---
title: My Document
author: Jane Doe
date: 2025-01-10
---

# Content here
```

Extracted as:

```python
metadata.title = "My Document"
metadata.author = "Jane Doe"
# ... other fields ...
```

---

## JsonExtractorConfig

Configuration for JSON import/re-chunking.

**Module**: `extraction.extractors.configs`

**Class**: `JsonExtractorConfig`

**Inherits**: `BaseExtractorConfig`

### Additional Fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `mode` | `Literal["import", "rechunk"]` | `"import"` | Import mode. `import`: Load existing chunks/metadata. `rechunk`: Re-apply chunking strategy to imported paragraphs. |
| `import_chunks` | `bool` | `True` | Whether to import chunks from JSON. |
| `import_metadata` | `bool` | `True` | Whether to import metadata from JSON. |

### Validation Rules

All base rules plus:

- `mode`: Must be one of `["import", "rechunk"]`

### Example

```python
from extraction.extractors.configs import JsonExtractorConfig

# Import existing extraction output as-is
config = JsonExtractorConfig(
    mode="import",
    import_chunks=True,
    import_metadata=True
)

# Re-chunk existing output with new strategy
config = JsonExtractorConfig(
    mode="rechunk",
    chunking_strategy="nlp",
    import_metadata=True
)
```

---

## Configuration Inheritance

All format-specific configs inherit base fields:

```python
from extraction.extractors.configs import EpubExtractorConfig

# Base fields are always available
config = EpubExtractorConfig(
    # Base fields
    chunking_strategy="rag",
    min_chunk_words=200,
    max_chunk_words=600,
    filter_noise=True,

    # EPUB-specific fields
    toc_hierarchy_level=3,
    preserve_hierarchy_across_docs=True
)
```

## Using Configs Programmatically

### Basic Usage

```python
from extraction.extractors import EpubExtractor
from extraction.extractors.configs import EpubExtractorConfig

config = EpubExtractorConfig(
    chunking_strategy="rag",
    min_chunk_words=150,
    filter_tiny_chunks="standard"
)

extractor = EpubExtractor("book.epub", config)
extractor.load()
extractor.parse()
extractor.extract_metadata()

output = extractor.get_output_data()
```

### Config from Dict

```python
from extraction.extractors.configs import PdfExtractorConfig

config_dict = {
    "chunking_strategy": "nlp",
    "heading_font_threshold": 1.5,
    "use_ocr": True
}

config = PdfExtractorConfig(**config_dict)
```

### Validation Errors

All configs validate on initialization:

```python
from extraction.extractors.configs import BaseExtractorConfig
from extraction.exceptions import InvalidConfigValueError

try:
    config = BaseExtractorConfig(
        chunking_strategy="invalid",  # Invalid strategy
        min_chunk_words=-10           # Invalid value
    )
except InvalidConfigValueError as e:
    print(f"Config error: {e}")
```

## Default Values Summary

Quick reference for all default values:

| Config Class | Key Defaults |
|--------------|--------------|
| `BaseExtractorConfig` | `chunking_strategy="rag"`, `min_chunk_words=100`, `max_chunk_words=500`, `filter_noise=True` |
| `EpubExtractorConfig` | All base + `toc_hierarchy_level=3`, `min_paragraph_words=6`, `filter_tiny_chunks="conservative"` |
| `PdfExtractorConfig` | All base + `min_paragraph_words=5`, `heading_font_threshold=1.2`, `use_ocr=False` |
| `HtmlExtractorConfig` | All base + `min_paragraph_words=1`, `preserve_links=False` |
| `MarkdownExtractorConfig` | All base + `preserve_code_blocks=True`, `extract_frontmatter=True` |
| `JsonExtractorConfig` | All base + `mode="import"`, `import_chunks=True`, `import_metadata=True` |

## See Also

- [CLI Reference](cli/extract.md) - Command-line flag mapping
- [BaseExtractor API](api/base-extractor.md) - Using configs with extractors
- [Output Schema](output-schema.md) - Understanding chunk metadata
- [Chunking Strategies How-To](../how-to/chunking-strategy.md) - Choosing RAG vs NLP
