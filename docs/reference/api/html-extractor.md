# HtmlExtractor API Reference

HTML-specific extractor with DOM-based processing and heading hierarchy extraction.

## Module

`extraction.extractors.html`

## Class

```python
class HtmlExtractor(BaseExtractor)
```

Extracts text from standalone HTML files, preserving heading hierarchy from h1-h6 tags.

## Overview

`HtmlExtractor` provides:

- **DOM traversal**: Uses BeautifulSoup to parse HTML structure
- **Heading hierarchy**: Extracts 6-level hierarchy from h1-h6 tags
- **Tag-based extraction**: Processes paragraphs, divs, lists, blockquotes
- **Clean text extraction**: Removes scripts, styles, and HTML artifacts
- **Quality scoring**: Same quality analysis as other extractors
- **Chunking strategies**: RAG and NLP modes supported

## Constructor

```python
def __init__(
    self,
    source_path: str,
    config: Optional[HtmlExtractorConfig] = None,
    analyzer: Optional[BaseAnalyzer] = None
)
```

### Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `source_path` | `str` | Required | Path to `.html` or `.htm` file |
| `config` | `HtmlExtractorConfig` | `None` | HTML-specific configuration. If `None`, uses `HtmlExtractorConfig()` |
| `analyzer` | `BaseAnalyzer` | `None` | Domain analyzer. If `None`, uses `GenericAnalyzer()` |

### Example

```python
from extraction.extractors import HtmlExtractor
from extraction.extractors.configs import HtmlExtractorConfig
from extraction.analyzers import GenericAnalyzer

config = HtmlExtractorConfig(
    min_paragraph_words=5,
    preserve_links=True
)

extractor = HtmlExtractor(
    source_path="document.html",
    config=config,
    analyzer=GenericAnalyzer()
)
```

## HTML-Specific Configuration

See [HtmlExtractorConfig](../configuration.md#htmlextractorconfig) for full reference.

### Key Options

| Option | Default | Description |
|--------|---------|-------------|
| `min_paragraph_words` | `5` | Minimum words to consider text as a paragraph |
| `preserve_links` | `False` | Preserve link URLs in extracted text |

## Public Methods

Inherits all methods from [BaseExtractor](base-extractor.md):

- `load()` - Load HTML and parse DOM
- `parse()` - Extract chunks from HTML elements
- `extract_metadata()` - Extract HTML metadata + domain enrichment
- `get_output_data()` - Get complete output structure

## Heading Hierarchy

Extracts 6-level hierarchy from HTML heading tags.

### How It Works

1. **Tag detection**: Identifies h1-h6 tags in DOM order
2. **Hierarchy update**: Updates corresponding level (h1 → level_1, h2 → level_2, etc.)
3. **Level clearing**: When a heading is found, clears all deeper levels
4. **Inheritance**: Paragraphs inherit current hierarchy state

### Example

```html
<h1>Chapter 1: Introduction</h1>
<p>First paragraph...</p>
<h2>Section 1.1: Background</h2>
<p>Second paragraph...</p>
<h1>Chapter 2: Methods</h1>
<p>Third paragraph...</p>
```

**Resulting hierarchy**:

- Chunk 1 (First paragraph): `{level_1: "Chapter 1: Introduction"}`
- Chunk 2 (Second paragraph): `{level_1: "Chapter 1: Introduction", level_2: "Section 1.1: Background"}`
- Chunk 3 (Third paragraph): `{level_1: "Chapter 2: Methods"}`

## Element Processing

Processes specific HTML elements to extract text content.

### Supported Elements

| Element | Behavior |
|---------|----------|
| `<h1>` - `<h6>` | Updates hierarchy (not extracted as chunks) |
| `<p>` | Extracted as chunk |
| `<div>` | Extracted if contains text content |
| `<li>` | Extracted as chunk (list items) |
| `<blockquote>` | Extracted as chunk |
| `<main>`, `<article>` | Container elements (children processed) |

### Processing Order

1. **Find container**: Searches for `<main>`, `<article>`, or `<body>` (in that order)
2. **Traverse DOM**: Processes elements in document order
3. **Extract text**: Calls `get_text()` on each element
4. **Clean text**: Removes extra whitespace, normalizes characters
5. **Check word count**: Skips elements below `min_paragraph_words`
6. **Create chunks**: Builds `Chunk` objects with current hierarchy

## Metadata Extraction

HTML metadata is extracted from meta tags and document structure.

### Meta Tag Mapping

| Meta Tag | Mapped To | Example |
|----------|-----------|---------|
| `<title>` | `metadata.title` | `<title>Document Title</title>` |
| `<meta name="author">` | `metadata.author` | `<meta name="author" content="John Doe">` |
| `<meta name="description">` | `metadata.description` | `<meta name="description" content="Summary">` |
| `<html lang="">` | `metadata.language` | `<html lang="en">` |

### Fallback Values

| Field | Fallback |
|-------|----------|
| `title` | Filename (without extension) |
| `author` | `"Unknown"` |
| `language` | `"en"` |

### Example

```python
extractor.load()
extractor.parse()
metadata = extractor.extract_metadata()

print(f"Title: {metadata.title}")
print(f"Author: {metadata.author}")
print(f"Language: {metadata.language}")
```

## Text Cleaning

Text is cleaned to remove HTML artifacts and normalize content.

### Cleaning Steps

1. **Get raw text**: Extract text from element
2. **Separator handling**: Use space as separator between inline elements
3. **Strip whitespace**: Remove leading/trailing whitespace
4. **Normalize ASCII**: Convert Unicode to ASCII-compatible characters
5. **Collapse whitespace**: Replace multiple spaces/newlines with single space

### Example

```html
<p>
  This is    a paragraph
  with   extra    whitespace
</p>
```

**Cleaned text**: `"This is a paragraph with extra whitespace"`

## Complete Example

```python
from extraction.extractors import HtmlExtractor
from extraction.extractors.configs import HtmlExtractorConfig
from extraction.analyzers import GenericAnalyzer
import json

# Configure HTML extraction
config = HtmlExtractorConfig(
    # Chunking
    chunking_strategy="rag",
    min_chunk_words=100,
    max_chunk_words=500,

    # HTML-specific
    min_paragraph_words=5,
    preserve_links=False,

    # Filtering
    filter_noise=True
)

# Create extractor
extractor = HtmlExtractor(
    source_path="article.html",
    config=config,
    analyzer=GenericAnalyzer()
)

# Process document
extractor.load()
print(f"Title: {extractor._HtmlExtractor__html_title}")

extractor.parse()
print(f"Chunks: {len(extractor.chunks)}")
print(f"Quality: {extractor.quality_score} (route {extractor.route})")

metadata = extractor.extract_metadata()
print(f"Author: {metadata.author}")
print(f"Language: {metadata.language}")

# Get output
output = extractor.get_output_data()

# Write to file
with open("article.json", "w") as f:
    json.dump(output, f, indent=2, ensure_ascii=False)

# Print chunk hierarchy
for chunk in extractor.chunks[:5]:
    hierarchy_path = " > ".join([
        v for v in chunk.hierarchy.values() if v
    ])
    print(f"Chunk {chunk.paragraph_id}: {hierarchy_path}")
    print(f"  Words: {chunk.word_count}")
    print(f"  Text: {chunk.text[:80]}...")
    print()
```

## Error Handling

### HTML-Specific Errors

| Error | When Raised | Example |
|-------|-------------|---------|
| `FileNotFoundError` | HTML file not found | Non-existent path |
| `ParseError` | HTML cannot be parsed | Malformed HTML, encoding issues |

### Example

```python
from extraction.exceptions import ParseError, FileNotFoundError

try:
    extractor = HtmlExtractor("document.html")
    extractor.load()
    extractor.parse()

except FileNotFoundError as e:
    print(f"File not found: {e.filepath}")

except ParseError as e:
    print(f"HTML parsing failed: {e.message}")
    print(f"File: {e.filepath}")
```

## Limitations

### Current Limitations

1. **Ignored elements**: Scripts, styles, and hidden elements are skipped
2. **Link preservation**: Links are not preserved by default (set `preserve_links=True`)
3. **Table extraction**: Tables are processed as plain text (no structure preservation)
4. **Image extraction**: Images are not extracted (alt text may be included)

### Best Practices

1. **Use semantic HTML**: Proper heading tags (h1-h6) for best hierarchy extraction
2. **Main content**: Use `<main>` or `<article>` tags to identify primary content
3. **Clean HTML**: Remove scripts and styles before extraction for best results
4. **Word count**: Adjust `min_paragraph_words` based on content density

## Comparison with Markdown

| Feature | HTML | Markdown |
|---------|------|----------|
| **Hierarchy** | 6 levels (h1-h6) | 6 levels (# - ######) |
| **Formatting** | DOM-based | Text-based |
| **Frontmatter** | Meta tags | YAML frontmatter |
| **Complexity** | Handles complex layouts | Simple structure |
| **Speed** | Medium | Fast |

**Recommendation**: Use Markdown for simple documents. HTML for complex layouts or web pages.

## See Also

- [BaseExtractor API](base-extractor.md) - Parent class reference
- [Configuration Reference](../configuration.md#htmlextractorconfig) - Full config options
- [Output Schema Reference](../output-schema.md) - Understanding chunk output
- [Multi-Format Extraction](../../getting-started/multi-format.md) - Advanced techniques
- [Chunking Strategies How-To](../../how-to/chunking-strategy.md) - RAG vs NLP
