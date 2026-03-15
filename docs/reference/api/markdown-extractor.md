# MarkdownExtractor API Reference

Markdown-specific extractor with frontmatter parsing and heading hierarchy extraction.

## Module

`extraction.extractors.markdown`

## Class

```python
class MarkdownExtractor(BaseExtractor)
```

Extracts text from Markdown files, preserving heading hierarchy and optional frontmatter metadata.

## Overview

`MarkdownExtractor` provides:

- **Frontmatter parsing**: Extracts YAML frontmatter (title, author, date, etc.)
- **Heading hierarchy**: Extracts 6-level hierarchy from # headings
- **Code block preservation**: Optionally preserves fenced code blocks
- **Link extraction**: Detects and extracts markdown links
- **Quality scoring**: Same quality analysis as other extractors
- **Chunking strategies**: RAG and NLP modes supported

## Constructor

```python
def __init__(
    self,
    source_path: str,
    config: Optional[MarkdownExtractorConfig] = None,
    analyzer: Optional[BaseAnalyzer] = None
)
```

### Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `source_path` | `str` | Required | Path to `.md` or `.markdown` file |
| `config` | `MarkdownExtractorConfig` | `None` | Markdown-specific configuration. If `None`, uses `MarkdownExtractorConfig()` |
| `analyzer` | `BaseAnalyzer` | `None` | Domain analyzer. If `None`, uses `GenericAnalyzer()` |

### Example

```python
from extraction.extractors import MarkdownExtractor
from extraction.extractors.configs import MarkdownExtractorConfig
from extraction.analyzers import GenericAnalyzer

config = MarkdownExtractorConfig(
    extract_frontmatter=True,
    preserve_code_blocks=True,
    min_paragraph_words=5
)

extractor = MarkdownExtractor(
    source_path="document.md",
    config=config,
    analyzer=GenericAnalyzer()
)
```

## Markdown-Specific Configuration

See [MarkdownExtractorConfig](../configuration.md#markdownextractorconfig) for full reference.

### Key Options

| Option | Default | Description |
|--------|---------|-------------|
| `extract_frontmatter` | `True` | Parse YAML frontmatter for metadata |
| `preserve_code_blocks` | `False` | Include code blocks in extracted chunks |
| `min_paragraph_words` | `5` | Minimum words to consider text as a paragraph |

## Public Methods

Inherits all methods from [BaseExtractor](base-extractor.md):

- `load()` - Load Markdown file and parse frontmatter
- `parse()` - Extract chunks from Markdown content
- `extract_metadata()` - Extract frontmatter metadata + domain enrichment
- `get_output_data()` - Get complete output structure

## Frontmatter Parsing

YAML frontmatter is extracted from the beginning of Markdown files.

### Frontmatter Format

```markdown
---
title: Document Title
author: John Doe
date: 2026-01-11
description: A sample markdown document
tags: [markdown, extraction, example]
---

# Heading 1

Content starts here...
```

### Supported Frontmatter Fields

| Field | Mapped To | Type |
|-------|-----------|------|
| `title` | `metadata.title` | string |
| `author` | `metadata.author` | string |
| `description` | `metadata.description` | string |
| `date` | `metadata.date_promulgated` | string |
| `tags` | `metadata.key_themes` | list |
| `language` | `metadata.language` | string |

### Fallback Values

If frontmatter is missing:

| Field | Fallback |
|-------|----------|
| `title` | Filename (without extension) |
| `author` | `"Unknown"` |
| `language` | `"en"` |

### Example

```python
extractor.load()

# Access frontmatter
if hasattr(extractor, '_MarkdownExtractor__frontmatter'):
    frontmatter = extractor._MarkdownExtractor__frontmatter
    print(f"Frontmatter: {frontmatter}")

extractor.parse()
metadata = extractor.extract_metadata()
print(f"Title: {metadata.title}")
print(f"Author: {metadata.author}")
print(f"Tags: {metadata.key_themes}")
```

## Heading Hierarchy

Extracts 6-level hierarchy from Markdown heading syntax.

### Heading Syntax

| Markdown | Level | Example |
|----------|-------|---------|
| `#` | 1 | `# Chapter 1` |
| `##` | 2 | `## Section 1.1` |
| `###` | 3 | `### Subsection 1.1.1` |
| `####` | 4 | `#### Topic` |
| `#####` | 5 | `##### Subtopic` |
| `######` | 6 | `###### Detail` |

### Hierarchy Behavior

1. **Heading detection**: Regex pattern `^#{1,6}\s+(.+)$`
2. **Hierarchy update**: Updates corresponding level (# → level_1, ## → level_2, etc.)
3. **Level clearing**: Clears all deeper levels when heading found
4. **Inheritance**: Paragraphs inherit current hierarchy state

### Example

```markdown
# Introduction

First paragraph under introduction.

## Background

Second paragraph under background.

## Methodology

Third paragraph under methodology.

# Results

Fourth paragraph under results.
```

**Resulting hierarchy**:

- Chunk 1: `{level_1: "Introduction"}`
- Chunk 2: `{level_1: "Introduction", level_2: "Background"}`
- Chunk 3: `{level_1: "Introduction", level_2: "Methodology"}`
- Chunk 4: `{level_1: "Results"}`

## Code Block Handling

Optional preservation of fenced code blocks.

### Configuration

```python
# Preserve code blocks (include in chunks)
config = MarkdownExtractorConfig(preserve_code_blocks=True)

# Skip code blocks (default)
config = MarkdownExtractorConfig(preserve_code_blocks=False)
```

### Code Block Syntax

**Fenced code blocks**:

    ```python
    def hello():
        print("Hello, world!")
    ```

**Indented code blocks**:

    def hello():
        print("Hello, world!")

### Behavior

| Setting | Behavior |
|---------|----------|
| `preserve_code_blocks=True` | Code blocks included as separate chunks |
| `preserve_code_blocks=False` | Code blocks skipped during extraction |

## Paragraph Detection

Paragraphs are detected by splitting on double newlines.

### Splitting Logic

```python
content.split('\n\n')  # Split on blank lines
```

### Example

```markdown
This is the first paragraph.
It spans multiple lines.

This is the second paragraph.

This is the third paragraph.
```

**Paragraphs extracted**:

1. `"This is the first paragraph. It spans multiple lines."`
2. `"This is the second paragraph."`
3. `"This is the third paragraph."`

### Minimum Word Count

Paragraphs below `min_paragraph_words` are skipped:

```python
config = MarkdownExtractorConfig(min_paragraph_words=5)

# Skipped (3 words)
"Too short text."

# Kept (7 words)
"This paragraph has enough words to keep."
```

## Link Extraction

Markdown links are detected and stored in `cross_references`.

### Link Patterns

| Syntax | Example | Extracted |
|--------|---------|-----------|
| Inline link | `[text](url)` | `url` |
| Reference link | `[text][ref]` | `ref` (if defined) |
| Autolink | `<http://example.com>` | `http://example.com` |

### Example

```markdown
See [the documentation](https://docs.example.com) for details.
Also check [reference guide][guide].

[guide]: https://guide.example.com
```

**Extracted cross-references**:
- `https://docs.example.com`
- `https://guide.example.com`

## Complete Example

```python
from extraction.extractors import MarkdownExtractor
from extraction.extractors.configs import MarkdownExtractorConfig
from extraction.analyzers import GenericAnalyzer
import json

# Configure Markdown extraction
config = MarkdownExtractorConfig(
    # Chunking
    chunking_strategy="rag",
    min_chunk_words=100,
    max_chunk_words=500,

    # Markdown-specific
    extract_frontmatter=True,
    preserve_code_blocks=False,
    min_paragraph_words=5,

    # Filtering
    filter_noise=True
)

# Create extractor
extractor = MarkdownExtractor(
    source_path="article.md",
    config=config,
    analyzer=GenericAnalyzer()
)

# Process document
extractor.load()
extractor.parse()

print(f"Chunks: {len(extractor.chunks)}")
print(f"Quality: {extractor.quality_score} (route {extractor.route})")

metadata = extractor.extract_metadata()
print(f"Title: {metadata.title}")
print(f"Author: {metadata.author}")

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

### Markdown-Specific Errors

| Error | When Raised | Example |
|-------|-------------|---------|
| `FileNotFoundError` | Markdown file not found | Non-existent path |
| `ParseError` | Markdown cannot be parsed | Encoding issues |

### Example

```python
from extraction.exceptions import ParseError, FileNotFoundError

try:
    extractor = MarkdownExtractor("document.md")
    extractor.load()
    extractor.parse()

except FileNotFoundError as e:
    print(f"File not found: {e.filepath}")

except ParseError as e:
    print(f"Markdown parsing failed: {e.message}")
```

## Limitations

### Current Limitations

1. **No HTML in Markdown**: Embedded HTML is treated as plain text
2. **Simple table handling**: Tables are converted to plain text
3. **Image extraction**: Images are not extracted (alt text may be included)
4. **Reference links**: Only defined references are extracted
5. **Nested lists**: List structure is flattened

### Best Practices

1. **Use frontmatter**: Include metadata in YAML frontmatter block
2. **Consistent headings**: Use ATX-style headings (# syntax) for best hierarchy
3. **Code blocks**: Set `preserve_code_blocks=True` for technical documentation
4. **Word count**: Adjust `min_paragraph_words` based on content density

## Comparison with HTML

| Feature | Markdown | HTML |
|---------|----------|------|
| **Hierarchy** | 6 levels (# syntax) | 6 levels (h1-h6 tags) |
| **Frontmatter** | YAML frontmatter | Meta tags |
| **Code blocks** | Native fenced blocks | `<pre><code>` tags |
| **Complexity** | Simple, readable | Complex, verbose |
| **Speed** | Fast | Medium |

**Recommendation**: Use Markdown for technical documentation, blog posts, and simple content.

## See Also

- [BaseExtractor API](base-extractor.md) - Parent class reference
- [Configuration Reference](../configuration.md#markdownextractorconfig) - Full config options
- [Output Schema Reference](../output-schema.md) - Understanding chunk output
- [Multi-Format Extraction](../../getting-started/multi-format.md) - Advanced techniques
- [Chunking Strategies How-To](../../how-to/chunking-strategy.md) - RAG vs NLP
