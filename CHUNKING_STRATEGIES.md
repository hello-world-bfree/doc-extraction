# Chunking Strategies Implementation (v2.3)

## Overview

Version 2.3 introduces **pluggable chunking strategies** that work across **all file formats** (EPUB, PDF, HTML, Markdown, JSON) to optimize document extraction for different use cases:

- **RAG/Embeddings** (default): Semantic chunks optimized for vector search and retrieval
- **NLP**: Paragraph-level chunks for fine-grained text analysis

**Multi-Format Support**: The same chunking strategies work identically across all supported document formats, providing consistent chunk optimization regardless of input type.

This addresses the conversation from `01KDW7BZ29BQXA8P08NGF33CZE` about moving from NLP-focused paragraph splits to RAG-optimized semantic chunking.

## Motivation

**Problem**: The original paragraph-level chunking (v2.2 and earlier) was designed for NLP tasks but suboptimal for embeddings:
- 60%+ of chunks were <100 words (too small for effective embeddings)
- Many chunks were <50 words (noise in vector databases)
- Average chunk: 40-80 words (below optimal embedding range)

**Solution**: Semantic chunking that merges paragraphs under the same heading hierarchy into larger, contextually coherent chunks.

## Architecture

### Strategy Pattern

Located in `src/extraction/core/strategies.py`:

```python
class ChunkingStrategy(ABC):
    """Base interface for chunking strategies."""

    @abstractmethod
    def apply(self, chunks: List[Dict], config: ChunkConfig) -> List[Dict]:
        """Transform raw paragraph chunks according to strategy."""
        pass
```

### Implementations

1. **ParagraphChunkingStrategy** (NLP mode)
   - Returns chunks unchanged (paragraph boundaries preserved)
   - One paragraph = one chunk
   - Use case: Sentence classification, NER, fine-grained analysis

2. **SemanticChunkingStrategy** (RAG mode - DEFAULT)
   - Merges paragraphs by hierarchy (first 3 levels by default)
   - Target: 100-500 words per chunk
   - Skips index/TOC sections
   - Aggregates metadata (scripture refs, cross-refs, etc.)
   - Maintains document order

### Configuration

```python
@dataclass
class ChunkConfig:
    min_words: int = 100           # Minimum words per chunk
    max_words: int = 500           # Maximum words per chunk
    preserve_hierarchy_levels: int = 3  # Levels to use for grouping
```

## Usage

### CLI (All Formats)

```bash
# Default: RAG strategy (100-500 words) - works for ALL formats
extract book.epub
extract document.pdf
extract page.html
extract readme.md
extract data.json

# NLP mode (paragraph-level) - works for ALL formats
extract document.pdf --chunking-strategy nlp
extract page.html --chunking-strategy nlp

# Custom chunk sizes - works for ALL formats
extract document.pdf --min-chunk-words 200 --max-chunk-words 800

# Combine with other options
extract docs/ -r --chunking-strategy rag --min-chunk-words 150 --output-dir outputs/
```

### Programmatic (All Extractors)

```python
from extraction.extractors import (
    EpubExtractor, PdfExtractor, HtmlExtractor,
    MarkdownExtractor, JsonExtractor
)

# All extractors use the same interface

# EPUB with RAG mode (default)
epub_extractor = EpubExtractor("book.epub")
epub_extractor.load()
epub_extractor.parse()  # Uses RAG strategy by default

# PDF with RAG mode
pdf_extractor = PdfExtractor("document.pdf", config={
    'chunking_strategy': 'rag',
    'min_chunk_words': 100,
    'max_chunk_words': 500,
})

# HTML with NLP mode
html_extractor = HtmlExtractor("page.html", config={
    'chunking_strategy': 'nlp'
})

# Markdown with custom RAG configuration
md_extractor = MarkdownExtractor("readme.md", config={
    'chunking_strategy': 'rag',
    'min_chunk_words': 150,
    'max_chunk_words': 600,
    'preserve_hierarchy_levels': 2  # Group by level_1 and level_2 only
})

# JSON with RAG mode
json_extractor = JsonExtractor("data.json", config={
    'chunking_strategy': 'rag'
})
```

## Strategy Aliases

For convenience, multiple aliases map to the same strategy:

- **RAG/Semantic**: `rag`, `semantic`, `embeddings` → `SemanticChunkingStrategy`
- **NLP/Paragraph**: `nlp`, `paragraph` → `ParagraphChunkingStrategy`

## Output Differences

### RAG Mode (Default)

```json
{
  "stable_id": "abc123...",
  "paragraph_id": 1,
  "text": "First paragraph text.\n\nSecond paragraph text.\n\nThird paragraph text.",
  "word_count": 250,
  "source_tag": "merged_3_paragraphs",
  "merged_paragraph_ids": [1, 2, 3],
  "source_paragraph_count": 3,
  "hierarchy": {"level_1": "Chapter 1", "level_2": "Section A"},
  ...
}
```

**Characteristics**:
- ~60-80% fewer chunks than NLP mode
- Average chunk: 200-300 words
- Includes merge metadata: `merged_paragraph_ids`, `source_paragraph_count`
- Source tag indicates merging: `"merged_N_paragraphs"`

### NLP Mode

```json
{
  "stable_id": "def456...",
  "paragraph_id": 1,
  "text": "First paragraph text.",
  "word_count": 25,
  "source_tag": "p",
  "hierarchy": {"level_1": "Chapter 1", "level_2": "Section A"},
  ...
}
```

**Characteristics**:
- One paragraph = one chunk
- Average chunk: 40-80 words (varies by document)
- Exact paragraph boundaries preserved
- No merge metadata

## Quality Metrics (Embeddings)

Based on research and best practices:

- **Optimal range**: 100-500 words
  - Sweet spot for most embedding models (384-1536 dimensions)
  - Balances context window and specificity

- **Good range**: 50-800 words
  - Still effective but suboptimal

- **Too small**: <50 words
  - Insufficient context for embeddings
  - High noise in vector databases

- **Too large**: >800 words
  - May exceed model context windows
  - Reduces retrieval precision

## Testing

Comprehensive test suite in `tests/test_chunking_strategies.py`:

- ✅ 19 tests covering both strategies
- ✅ Merge behavior and hierarchy grouping
- ✅ Min/max word constraints
- ✅ Metadata aggregation (scripture refs, cross-refs)
- ✅ Document order preservation
- ✅ Index/TOC skipping
- ✅ Strategy registry and aliases

Run tests:
```bash
uv run pytest tests/test_chunking_strategies.py -v
```

## Evaluation Script

Use `fidelity_testing/test_rag_chunking.py` to evaluate chunking strategies on your corpus:

```bash
# Single EPUB
python fidelity_testing/test_rag_chunking.py book.epub

# Multiple EPUBs
python fidelity_testing/test_rag_chunking.py book1.epub book2.epub book3.epub

# Directory of EPUBs
python fidelity_testing/test_rag_chunking.py /path/to/epubs/
```

Output includes:
- Chunk count reduction percentage
- Optimal/good/too-small/too-large percentages
- Mean/median word counts
- Per-EPUB and aggregate statistics
- JSON results saved to `fidelity_testing/rag_chunking_results.json`

## Implementation Details

### Merging Algorithm

1. **Grouping**: Paragraphs grouped by first N hierarchy levels (default: 3)
2. **Skipping**: Index/TOC sections automatically excluded
3. **Merging**: Within each group, merge paragraphs up to `max_words`
4. **Filtering**: Discard merged chunks below `min_words`
5. **Sorting**: Final chunks sorted by first paragraph ID (maintains document order)

### Metadata Aggregation

When merging paragraphs, the strategy:
- Combines text with `\n\n` separator
- Deduplicates scripture references and cross-references
- Concatenates all sentences
- Preserves dates mentioned
- Uses first paragraph's stable_id template
- Stores merge provenance: `merged_paragraph_ids`, `source_paragraph_count`

### Hierarchy Grouping Depth

Configurable via `preserve_hierarchy_levels`:

- `1`: Group by level_1 only (e.g., chapters) → very large chunks
- `2`: Group by level_1 + level_2 (e.g., chapter + section)
- `3`: (default) Group by level_1 + level_2 + level_3
- Higher: Finer-grained grouping → smaller chunks

## Backward Compatibility

- **Default changed**: v2.3 uses RAG mode by default (breaking change)
- **NLP mode preserved**: Use `--chunking-strategy nlp` for v2.2 behavior
- **Output schema**: RAG mode adds optional fields (`merged_paragraph_ids`, `source_paragraph_count`)
- **Extractor interface**: Unchanged; strategies applied transparently in `parse()`

## Migration from v2.2

### If you need paragraph-level chunks (NLP)

**CLI**:
```bash
extract book.epub --chunking-strategy nlp
```

**Python**:
```python
extractor = EpubExtractor("book.epub", config={'chunking_strategy': 'nlp'})
```

### If you want RAG chunks (recommended)

No changes needed - RAG is now the default!

Optionally customize:
```bash
extract book.epub --min-chunk-words 150 --max-chunk-words 600
```

## Performance

- **RAG mode**: ~1-2% overhead vs paragraph mode (merging + sorting)
- **NLP mode**: Zero overhead (pass-through)
- Both modes use same extraction pipeline; strategy applied after paragraph extraction

## Future Enhancements

Possible additions for future versions:

1. **Adaptive chunking**: Dynamic chunk sizes based on content type
2. **Overlap support**: Sliding window chunks for improved retrieval
3. **Additional strategies**:
   - Sentence-level chunking
   - Fixed-size chunking (by token count)
   - Hybrid semantic+size chunking
4. **Strategy plugins**: User-defined chunking strategies via plugin system

## References

- Conversation: `01KDW7BZ29BQXA8P08NGF33CZE`
- Strategy Pattern: `src/extraction/core/strategies.py`
- Base Extractor: `src/extraction/extractors/base.py`
- CLI Implementation: `src/extraction/cli/extract.py`
- Tests: `tests/test_chunking_strategies.py`
- Evaluation: `fidelity_testing/test_rag_chunking.py`
