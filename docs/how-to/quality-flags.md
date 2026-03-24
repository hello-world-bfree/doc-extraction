# Working with Quality Flags

Quality flags are soft labels on chunks that signal conditions like below-minimum size, front/back matter, or reference blocks. They allow downstream systems to make filtering decisions without losing data during extraction.

## What Are Quality Flags?

- The `quality_flags` field on each chunk is an optional list of strings
- Flags are added during extraction when certain conditions are detected
- Chunks are preserved in output (not removed) --- flags enable post-extraction filtering
- Only present in JSON output when non-empty (stripped by `to_dict()` when `None`)

## Available Quality Flags

### Small Chunk Flags

| Flag | Condition |
|------|-----------|
| `below_rag_minimum` | Chunk word count is below `min_chunk_words` (default 100 for RAG strategy) |

Enabled by default (`preserve_small_chunks=True`). To filter instead:

```bash
extract book.epub --filter-small-chunks
```

### Front/Back Matter Flags

| Flag | Condition |
|------|-----------|
| `likely_noncore_matter_dedication_phrase` | Contains dedication phrases ("Dedicated to...", "For my...") |
| `likely_noncore_matter_endorsement_section` | Contains endorsement phrases ("Praise for...", "What readers are saying...") |
| `likely_noncore_matter_front_matter_toc_label` | Hierarchy matches front matter TOC labels (dedication, praise, title page, etc.) |
| `likely_noncore_matter_back_matter_toc_label` | Hierarchy matches back matter TOC labels (glossary, index, bibliography, etc.) |
| `likely_noncore_matter_book_outline` | Hierarchy level_1 contains "outline" |

!!! note
    Front/back matter detection is EPUB-only and disabled by default.

Enable with:

```bash
extract book.epub --detect-front-matter
```

Hard filter (remove flagged chunks):

```bash
extract book.epub --detect-front-matter --filter-front-matter
```

### Reference Block Flags

| Flag | Condition |
|------|-----------|
| `contains_reference_block_N_refs` | Contains N sequential numbered citations (N >= 3) |

Detection requires 3+ sequential numbered citations starting from 1, with citation indicators such as years in parentheses `(2005)`, `Ibid.`, `ed.`, `trans.`, `vol.`, or page ranges. Normal numbered lists without citation indicators are not flagged.

Enable with:

```bash
extract book.epub --detect-references
```

## Output Examples

A small chunk below the RAG minimum:

```json
{
  "word_count": 15,
  "quality_flags": ["below_rag_minimum"],
  "text": "Short paragraph...",
  "hierarchy": {"level_1": "Chapter One"}
}
```

A detected dedication:

```json
{
  "text": "Dedicated to my loving wife Sarah",
  "quality_flags": ["likely_noncore_matter_dedication_phrase"],
  "hierarchy": {"level_1": "Dedication"}
}
```

A chunk with end-of-chapter references:

```json
{
  "text": "Chapter content here...\n\n1. Author Name, Book Title (Publisher, 2005), 100.\n\n2. Ibid., 45-46.",
  "quality_flags": ["contains_reference_block_5_refs"],
  "hierarchy": {"level_1": "Chapter One"}
}
```

## Filtering in Python

```python
import json

with open("output.json") as f:
    data = json.load(f)

clean_chunks = [
    c for c in data["chunks"]
    if not c.get("quality_flags")
]

content_chunks = [
    c for c in data["chunks"]
    if not any(
        f.startswith("likely_noncore_matter_")
        for f in (c.get("quality_flags") or [])
    )
]

rag_chunks = [
    c for c in data["chunks"]
    if "below_rag_minimum" not in (c.get("quality_flags") or [])
]
```

## Configuration

### CLI Flags

```bash
extract book.epub --filter-small-chunks
extract book.epub --detect-front-matter
extract book.epub --detect-front-matter --filter-front-matter
extract book.epub --detect-references
```

### Python API

```python
from extraction.extractors import EpubExtractor
from extraction.extractors.configs import EpubExtractorConfig

config = EpubExtractorConfig(
    preserve_small_chunks=True,
    detect_front_matter=True,
    filter_front_matter=False,
    detect_references=True,
)

extractor = EpubExtractor("book.epub", config)
extractor.load()
extractor.parse()
chunks = extractor.chunks
```

### Config File

```toml
# extraction.toml
preserve_small_chunks = true
detect_front_matter = true
filter_front_matter = false
detect_references = true
```

## When to Use Each Mode

| Use Case | Recommended Approach |
|----------|---------------------|
| Embedding/RAG pipeline | Default (preserve) + filter `below_rag_minimum` in code |
| Metadata extraction | Default (preserve all) --- small chunks still have structural value |
| Clean corpus building | `--detect-front-matter --filter-front-matter --filter-small-chunks` |
| Debugging extraction | Default (preserve all) --- see what was flagged |

!!! tip "Combining with chunking strategies"
    Quality flags work with both RAG and NLP chunking strategies. The `below_rag_minimum` flag uses `min_chunk_words` from your active strategy configuration.

## See Also

- [Output Schema: Quality Flags](../reference/output-schema.md)
- [Configuration: preserve_small_chunks](../reference/configuration.md)
- [Annotation Workflow](annotation-workflow.md)
