# EpubExtractor API Reference

EPUB-specific extractor with TOC hierarchy and formatting preservation.

## Module

`extraction.extractors.epub`

## Class

```python
class EpubExtractor(BaseExtractor)
```

Extracts hierarchical chunks from EPUB files with TOC-aware hierarchy and optional formatting preservation.

## Overview

`EpubExtractor` provides:

- **TOC hierarchy mapping**: Maps TOC entries to heading levels
- **Spine document processing**: Processes EPUB spine in reading order
- **Hierarchy preservation**: Optional cross-document hierarchy flow
- **Tiny chunk filtering**: Removes index/TOC/punctuation noise
- **Footnote detection**: Extracts footnote citations
- **Debug dumps**: Optional extraction debugging

## Constructor

```python
def __init__(
    self,
    epub_path: str,
    config: Optional[EpubExtractorConfig] = None,
    analyzer: Optional[BaseAnalyzer] = None
)
```

### Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `epub_path` | `str` | Required | Path to `.epub` file |
| `config` | `EpubExtractorConfig` | `None` | EPUB-specific configuration. If `None`, uses `EpubExtractorConfig()` |
| `analyzer` | `BaseAnalyzer` | `None` | Domain analyzer. If `None`, uses `GenericAnalyzer()` |

### Example

```python
from extraction.extractors import EpubExtractor
from extraction.extractors.configs import EpubExtractorConfig
from extraction.analyzers import CatholicAnalyzer

config = EpubExtractorConfig(
    toc_hierarchy_level=3,
    preserve_hierarchy_across_docs=True,
    filter_tiny_chunks="standard"
)

extractor = EpubExtractor(
    epub_path="prayer_primer.epub",
    config=config,
    analyzer=CatholicAnalyzer()
)
```

## EPUB-Specific Configuration

See [EpubExtractorConfig](../configuration.md#epubextractorconfig) for full reference.

### Key Options

| Option | Default | Description |
|--------|---------|-------------|
| `toc_hierarchy_level` | `3` | Hierarchy level (1-6) where TOC titles are inserted |
| `preserve_hierarchy_across_docs` | `False` | Preserve hierarchy across spine documents |
| `reset_depth` | `2` | Clear levels ≥ this depth at doc boundaries (if not preserving) |
| `filter_tiny_chunks` | `"conservative"` | Tiny chunk filtering: `off`, `conservative`, `standard`, `aggressive` |
| `class_denylist` | `r"^(?:calibre\d+\|note\|footnote)$"` | Regex for CSS classes to exclude |

## Public Methods

Inherits all methods from [BaseExtractor](base-extractor.md):

- `load()` - Load EPUB and build TOC mapping
- `parse()` - Extract chunks from spine documents
- `extract_metadata()` - Extract EPUB metadata + domain enrichment
- `get_output_data()` - Get complete output structure

## EPUB-Specific Properties

### `chunks_dict`

Get chunks in dict format (backward compatibility).

```python
@property
def chunks_dict(self) -> List[Dict[str, Any]]
```

**Available after**: `parse()`

**Returns**: List of chunk dictionaries (includes all fields from `Chunk.to_dict()`)

**Use case**: Legacy code expecting dict format instead of `Chunk` objects.

**Example**:

```python
extractor.load()
extractor.parse()

for chunk_dict in extractor.chunks_dict:
    print(f"Chunk {chunk_dict['paragraph_id']}: {chunk_dict['text'][:50]}")
```

---

### `href_to_toc_title`

Mapping of EPUB hrefs to TOC titles.

```python
@property
def href_to_toc_title(self) -> Dict[str, str]
```

**Available after**: `load()`

**Returns**: Dictionary mapping spine hrefs to TOC titles

**Example**:

```python
extractor.load()

for href, title in extractor.href_to_toc_title.items():
    print(f"{href} → {title}")

# Output:
# chapter1.xhtml → Chapter 1: What is Prayer?
# chapter2.xhtml → Chapter 2: Vocal and Mental Prayer
```

---

### `debug_dump`

Enable debug output (writes to `./debug/`).

```python
@property
def debug_dump(self) -> bool
```

**Writable**: Yes (set after construction)

**Default**: `False`

**Debug files created**:

- `{filename}_spine_structure.txt` - Spine document ordering
- `{filename}_toc_structure.txt` - TOC hierarchy
- `{filename}_{order:03d}_{href}.raw.txt` - Per-document raw text
- `{filename}_{order:03d}_{href}.stats.json` - Per-document statistics

**Example**:

```python
extractor = EpubExtractor("book.epub")
extractor.debug_dump = True  # Enable debug output

extractor.load()
extractor.parse()

# Debug files written to ./debug/
```

## TOC Hierarchy Mapping

The extractor builds a mapping from spine document hrefs to TOC titles during `load()`.

### How It Works

1. **TOC traversal**: Recursively walks EPUB TOC structure
2. **Href normalization**: Removes fragments (`#section1`) and leading `./`
3. **Title cleaning**: Normalizes whitespace and removes artifacts
4. **Mapping storage**: Stores in `href_to_toc_title` dict

### Example TOC

```xml
<nav>
  <ol>
    <li><a href="chapter1.xhtml">Chapter 1: What is Prayer?</a></li>
    <li><a href="chapter2.xhtml">Chapter 2: Vocal and Mental Prayer</a>
      <ol>
        <li><a href="chapter2.xhtml#section2.1">Section 2.1: Vocal Prayer</a></li>
      </ol>
    </li>
  </ol>
</nav>
```

**Mapping created**:

```python
{
    "chapter1.xhtml": "Chapter 1: What is Prayer?",
    "chapter2.xhtml": "Chapter 2: Vocal and Mental Prayer"
}
```

**Note**: Fragment-only TOC entries (`#section2.1`) are ignored.

### Using TOC Titles

During parsing, when processing a spine document:

1. Look up href in `href_to_toc_title`
2. If found, insert title at `toc_hierarchy_level`
3. All paragraphs in that document inherit the TOC title

**Example** with `toc_hierarchy_level=3`:

```python
# Processing chapter1.xhtml
current_hierarchy = {
    "level_1": "",
    "level_2": "",
    "level_3": "Chapter 1: What is Prayer?",  # TOC title inserted
    "level_4": "",
    "level_5": "",
    "level_6": ""
}

# All paragraphs in chapter1.xhtml get this hierarchy
```

## Hierarchy Preservation

Controls whether hierarchy flows across spine documents.

### `preserve_hierarchy_across_docs=False` (Default)

Hierarchy resets at document boundaries:

1. Levels ≥ `reset_depth` are cleared
2. Levels &lt; `reset_depth` are preserved
3. TOC title is inserted

**Example** with `reset_depth=2`:

```
Document 1 (chapter1.xhtml):
  level_1: "Part I"      ← Preserved across docs
  level_2: "Chapter 1"   ← RESET at boundary
  level_3: "Section 1.1" ← RESET at boundary

Document 2 (chapter2.xhtml):
  level_1: "Part I"      ← Still set
  level_2: ""            ← Cleared
  level_3: "Chapter 2: Vocal Prayer"  ← TOC title inserted
```

### `preserve_hierarchy_across_docs=True`

Hierarchy flows continuously:

1. No automatic reset at document boundaries
2. Hierarchy only changes when new headings encountered
3. TOC titles still inserted at `toc_hierarchy_level`

**Use case**: Books where each chapter builds on previous hierarchy.

## Tiny Chunk Filtering

Filters chunks with &lt;5 words as noise.

### Filter Levels

| Level | What's Removed | Reduction | Risk |
|-------|----------------|-----------|------|
| `off` | Nothing | 0% | N/A |
| `conservative` | Index, TOC, punctuation, figure labels | ~47.6% | Zero |
| `standard` | + Answer keys, bullets, page ranges | ~48.8% | Very low |
| `aggressive` | + Appendix content, cross-refs | ~60% | Medium |

### Examples Filtered

**Conservative** (default):

- `"experimentation, 17"` (index entry)
- `"• References"` (TOC fragment)
- `"N"` (punctuation)
- `"Listing 10.9"` (figure label)
- `"305"` (page number)

**Standard**:

- All conservative +
- `"1. C"` (answer key)
- `"• Next"` (single-word bullet)
- `"305 - 310"` (page range)

**Aggressive**:

- All standard +
- `"See Chapter 7"` (cross-reference in appendix)
- Any tiny chunk in appendix sections

### Configuration

```python
config = EpubExtractorConfig(
    filter_tiny_chunks="conservative"  # Default
)

# Disable filtering
config = EpubExtractorConfig(filter_tiny_chunks="off")

# More aggressive
config = EpubExtractorConfig(filter_tiny_chunks="aggressive")
```

## Footnote Detection

Automatically detects footnote citations in text.

### Pattern Recognition

Detects trailing footnotes in multiple formats:

- `"... text here.10"` - Bare number
- `"... text here.[10]"` - Bracketed
- `"... text here.(10)"` - Parenthesized
- `"... text here.10."`- With trailing period

### Guards

Ignores false positives:

- Bible verses: `"John 3:16"` (colon before number)
- Decimals: `"3.14"` (decimal numbers)
- Numbers &gt; 999 (too large for footnotes)

### Output

Footnote citations added to chunk metadata:

```json
{
  "footnote_citations": {
    "all": [1, 5, 10],
    "by_sentence": [
      {"index": 0, "numbers": [1]},
      {"index": 3, "numbers": [5, 10]}
    ]
  }
}
```

### Example

```python
extractor.load()
extractor.parse()

for chunk in extractor.chunks:
    if hasattr(chunk, 'footnote_citations'):
        print(f"Chunk {chunk.paragraph_id} has footnotes: {chunk.footnote_citations['all']}")
```

## Chunking Behavior

### Spine Processing Order

1. Load EPUB and read spine (reading order)
2. Skip navigation/TOC documents
3. Process each spine document in order:
   - Parse HTML with BeautifulSoup
   - Sanitize DOM (remove scripts, styles, footnote refs)
   - Extract headings (update hierarchy, don't chunk)
   - Extract block elements as paragraphs
   - Apply tiny chunk filter
4. Compute quality from full document text
5. Apply chunking strategy (RAG or NLP)

### Block Element Extraction

**Primary tags** (always chunked):

- `<p>` - Paragraphs
- `<blockquote>` - Blockquotes
- `<li>` - List items (prefixed with `"• "`)
- `<pre>` - Preformatted text
- `<figure>` - Figures

**Container tags** (chunked only if leaf nodes):

- `<div>`, `<section>`, `<article>` - Only if no nested blocks
- `<span>`, `<a>`, `<em>`, `<strong>` - Only if standalone (not inside block parent)

**Minimum word count**: Controlled by `min_paragraph_words` (default: 6)

### Quality Route Handling

**Route A/B** (quality ≥ 0.4):

- Extract block elements as paragraphs
- Natural paragraph boundaries

**Route C** (quality &lt; 0.4):

- Extract text with fixed windows (120 words, 20-word overlap)
- Ensures consistent chunk sizes for low-quality documents

## Class Denylist

Excludes elements with specific CSS classes.

### Default Pattern

```python
class_denylist = r"^(?:calibre\d+|note|footnote)$"
```

**Matches**:

- `calibre1`, `calibre2`, ... (Calibre artifacts)
- `note`, `footnote` (Footnote references)

### Custom Patterns

```python
config = EpubExtractorConfig(
    class_denylist=r"^(?:calibre\d+|note|footnote|sidebar|advertisement)$"
)
```

**Note**: Pattern is case-insensitive (`re.I` flag).

## Complete Example

```python
from extraction.extractors import EpubExtractor
from extraction.extractors.configs import EpubExtractorConfig
from extraction.analyzers import CatholicAnalyzer
import json

# Configure EPUB-specific options
config = EpubExtractorConfig(
    # Chunking
    chunking_strategy="rag",
    min_chunk_words=150,
    max_chunk_words=400,

    # Hierarchy
    toc_hierarchy_level=3,
    preserve_hierarchy_across_docs=True,
    reset_depth=2,

    # Filtering
    filter_tiny_chunks="standard",
    filter_noise=True,
    class_denylist=r"^(?:calibre\d+|note|footnote)$",

    # Extraction
    min_paragraph_words=6,
    min_block_words=30
)

# Create extractor with Catholic analyzer
extractor = EpubExtractor(
    epub_path="catechism.epub",
    config=config,
    analyzer=CatholicAnalyzer()
)

# Enable debug output
extractor.debug_dump = True

# Process document
extractor.load()
print(f"TOC entries: {len(extractor.href_to_toc_title)}")

extractor.parse()
print(f"Chunks: {len(extractor.chunks)}")
print(f"Quality: {extractor.quality_score} (route {extractor.route})")

metadata = extractor.extract_metadata()
print(f"Title: {metadata.title}")
print(f"Document type: {metadata.document_type}")
print(f"Subjects: {metadata.subject}")

# Get output
output = extractor.get_output_data()

# Write to file
with open("catechism.json", "w") as f:
    json.dump(output, f, indent=2, ensure_ascii=False)

# Also write metadata separately
with open("catechism_metadata.json", "w") as f:
    json.dump(output["metadata"], f, indent=2, ensure_ascii=False)
```

## Error Handling

### EPUB-Specific Errors

| Error | When Raised | Example |
|-------|-------------|---------|
| `ParseError` | EPUB file corrupted | Invalid ZIP structure |
| `ParseError` | No spine | Empty or malformed EPUB |
| `ParseError` | HTML parsing fails | Malformed XHTML in spine document |

### Example

```python
from extraction.exceptions import ParseError

try:
    extractor = EpubExtractor("book.epub")
    extractor.load()
    extractor.parse()

except ParseError as e:
    print(f"EPUB parsing failed: {e.message}")
    print(f"File: {e.filepath}")
```

## Debug Output

Enable with `extractor.debug_dump = True` before calling `load()` or `parse()`.

### Files Created

All files written to `./debug/` directory:

**Per-document files**:

- `{filename}_{order:03d}_{href}.raw.txt` - Raw text extract (first 2000 chars)
- `{filename}_{order:03d}_{href}.stats.json` - Document statistics

**Statistics JSON**:

```json
{
  "file": "catechism.epub",
  "href": "chapter1.xhtml",
  "order_idx": 0,
  "body_present": true,
  "total_text_len": 15234,
  "first_300_text": "Chapter 1: The Sacred Liturgy...",
  "tag_counts_top10": {
    "p": 142,
    "div": 38,
    "span": 25
  },
  "p_count": 142,
  "div_count": 38,
  "li_count": 15,
  "span_count": 25,
  "a_count": 12
}
```

### Use Cases

- **Debugging extraction**: See raw HTML text vs. extracted chunks
- **Hierarchy debugging**: Understand TOC mapping
- **Performance analysis**: Identify slow spine documents
- **Quality analysis**: Correlate tag structure with quality scores

## See Also

- [BaseExtractor API](base-extractor.md) - Parent class reference
- [Configuration Reference](../configuration.md#epubextractorconfig) - Full config options
- [Output Schema Reference](../output-schema.md) - Understanding chunk output
- [EPUB Extraction How-To](../../getting-started/multi-format.md) - Advanced techniques
- [Chunking Strategies How-To](../../how-to/chunking-strategy.md) - RAG vs NLP
