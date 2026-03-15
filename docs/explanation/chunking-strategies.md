# Chunking Strategies

**Understanding RAG vs NLP chunking modes**

The extraction library provides two fundamentally different chunking strategies optimized for different use cases. Choosing the right strategy is critical for downstream performance in embeddings, vector search, or NLP analysis.

## Why Two Strategies?

Different applications require different chunk granularities:

**RAG Systems & Embeddings** need semantic coherence

- Chunks should be 100-500 words (optimal for embedding models)
- Context should be preserved (paragraphs under same heading belong together)
- Fewer, larger chunks reduce vector DB size
- Example: Searching for "prayer practices" should return a complete explanation, not just a sentence fragment

**NLP Analysis** needs fine-grained precision

- One paragraph = one unit of analysis
- Exact paragraph boundaries preserved for sentence classification, NER, sentiment
- More, smaller chunks enable granular operations
- Example: Labeling each paragraph with a topic for training data

The library supports both through pluggable strategies applied **after** format-specific parsing.

## Strategy Comparison

| Aspect | RAG/Semantic Strategy | NLP/Paragraph Strategy |
|--------|----------------------|----------------------|
| **Target chunk size** | 100-500 words | Paragraph-level (40-80 words avg) |
| **Merging behavior** | Merges paragraphs under same heading | No merging, preserves boundaries |
| **Chunk count** | ~60-80% fewer chunks | Original paragraph count |
| **Use cases** | Vector search, RAG, semantic retrieval | Sentence classification, NER, sentiment analysis |
| **Hierarchy preservation** | Maintained across merges | Inherited per paragraph |
| **Metadata** | `merged_paragraph_ids`, `source_paragraph_count` | Original paragraph metadata |
| **Aliases** | `rag`, `semantic`, `embeddings` | `nlp`, `paragraph` |
| **Default** | ✅ Yes | No |

## RAG/Semantic Strategy

### Algorithm Overview

The semantic chunking strategy merges paragraphs into larger semantic units while respecting hierarchy boundaries:

```
Input: Paragraph chunks from extractor
  ↓
Group by heading hierarchy (first N levels)
  ↓
Sort each group by document order
  ↓
Merge paragraphs within group (up to max_words)
  ↓
Output: Semantic chunks (100-500 words each)
```

### Detailed Steps

**1. Group by hierarchy**

Paragraphs are grouped using the first N hierarchy levels (default: 3):

```python
# Example hierarchy keys
("Part I", "Chapter 1", "Section A")  # level_1, level_2, level_3
("Part I", "Chapter 1", "Section B")  # Different group
("Part I", "Chapter 2", "Section A")  # Different group
```

All paragraphs with the same hierarchy key go into the same group.

**2. Skip index/TOC sections**

Certain sections are excluded from merging:

```python
SKIPPABLE_SECTIONS = {
    "index",
    "table of contents",
    "contents",
    "toc"
}
```

These typically contain references or navigation that shouldn't be merged.

**3. Merge within groups**

Within each hierarchy group:

```python
for paragraph in group (sorted by paragraph_id):
    if (current_chunk_words + paragraph_words > max_words
            and current_chunk has content):
        # Save current chunk
        merged_chunks.append(finalize_chunk(current_chunk))
        # Start new chunk
        current_chunk = new_empty_chunk()

    # Add paragraph to current chunk
    current_chunk.add(paragraph)

# Save final chunk if it meets minimum
if current_chunk.word_count >= min_words:
    merged_chunks.append(finalize_chunk(current_chunk))
```

Key rules:

- Never exceed `max_words` (default: 500)
- Only save chunks that meet `min_words` (default: 100)
- Maintain document order within each group

**4. Finalize chunks**

For each merged chunk:

```python
merged_chunk = {
    "text": "\n\n".join(paragraph_texts),  # Double newline separator
    "word_count": sum(paragraph_word_counts),
    "hierarchy": group_hierarchy,
    "merged_paragraph_ids": [p1_id, p2_id, p3_id],
    "source_paragraph_count": 3,
    "scripture_references": deduplicated_refs,
    "cross_references": deduplicated_refs,
    # ... other aggregated fields
}
```

References and dates are deduplicated across source paragraphs.

### Configuration

```python
from extraction.extractors import EpubExtractor
from extraction.core.strategies import ChunkConfig

extractor = EpubExtractor("book.epub", config={
    "chunking_strategy": "rag",
    "min_chunk_words": 100,  # Minimum to keep
    "max_chunk_words": 500,  # Maximum before split
})
```

Or via CLI:

```bash
extract book.epub --chunking-strategy rag --min-chunk-words 200 --max-chunk-words 800
```

### Example Transformation

**Input** (3 paragraphs under "Chapter 1 > Prayer"):

```json
[
    {
        "paragraph_id": 10,
        "text": "Prayer is the raising of one's mind and heart to God.",
        "hierarchy": {"level_1": "Chapter 1", "level_2": "Prayer"},
        "word_count": 12
    },
    {
        "paragraph_id": 11,
        "text": "It is a conversation with God. Through prayer, we express our deepest longings and receive divine guidance.",
        "hierarchy": {"level_1": "Chapter 1", "level_2": "Prayer"},
        "word_count": 19
    },
    {
        "paragraph_id": 12,
        "text": "The Church recommends daily prayer as essential for spiritual growth. Morning and evening prayers frame our day in God's presence.",
        "hierarchy": {"level_1": "Chapter 1", "level_2": "Prayer"},
        "word_count": 23
    }
]
```

**Output** (1 merged chunk):

```json
{
    "paragraph_id": 10,
    "text": "Prayer is the raising of one's mind and heart to God.\n\nIt is a conversation with God. Through prayer, we express our deepest longings and receive divine guidance.\n\nThe Church recommends daily prayer as essential for spiritual growth. Morning and evening prayers frame our day in God's presence.",
    "hierarchy": {"level_1": "Chapter 1", "level_2": "Prayer"},
    "word_count": 54,
    "merged_paragraph_ids": [10, 11, 12],
    "source_paragraph_count": 3,
    "stable_id": "abc123...",
    "sentences": [
        "Prayer is the raising of one's mind and heart to God.",
        "It is a conversation with God.",
        "Through prayer, we express our deepest longings and receive divine guidance.",
        "The Church recommends daily prayer as essential for spiritual growth.",
        "Morning and evening prayers frame our day in God's presence."
    ]
}
```

Benefits:

- Single coherent chunk about prayer (good for embeddings)
- Preserves hierarchy context
- 54 words - optimal size for retrieval
- Metadata tracks merge history

### When Merging Stops

Merging does **not** cross hierarchy boundaries. If hierarchy changes, a new group starts:

```json
[
    {"text": "Para 1", "hierarchy": {"level_1": "Ch1", "level_2": "Sec A"}},
    {"text": "Para 2", "hierarchy": {"level_1": "Ch1", "level_2": "Sec A"}},
    {"text": "Para 3", "hierarchy": {"level_1": "Ch1", "level_2": "Sec B"}},  // ← New section
    {"text": "Para 4", "hierarchy": {"level_1": "Ch1", "level_2": "Sec B"}},
]
```

Result:

- Chunk 1: Para 1 + Para 2 (under "Sec A")
- Chunk 2: Para 3 + Para 4 (under "Sec B")

Hierarchy boundaries preserve semantic structure.

### Hierarchy Levels for Grouping

The `preserve_hierarchy_levels` config controls how many hierarchy levels define a group:

```python
# Level 1 only (broadest grouping)
config = ChunkConfig(preserve_hierarchy_levels=1)
# Groups: ("Part I",), ("Part II",)

# Levels 1-3 (default, fine-grained)
config = ChunkConfig(preserve_hierarchy_levels=3)
# Groups: ("Part I", "Chapter 1", "Section A"), ("Part I", "Chapter 1", "Section B")

# All 6 levels (finest grouping)
config = ChunkConfig(preserve_hierarchy_levels=6)
```

Higher values create more groups = less merging = smaller chunks.

### Performance Characteristics

**Chunk count reduction**:

```
Original paragraphs: 1,234
RAG chunks (default): 312 (74.7% reduction)
```

**Word distribution** (example from 12-EPUB corpus):

```
Min chunk: 100 words
Max chunk: 500 words
Avg chunk: 248 words
Median: 230 words
```

**Processing time**: <1% overhead compared to NLP mode (merging is lightweight).

## NLP/Paragraph Strategy

### Algorithm Overview

The paragraph strategy is **identity function** - it returns chunks unchanged:

```python
class ParagraphChunkingStrategy(ChunkingStrategy):
    def apply(self, chunks: List[Dict], config: ChunkConfig) -> List[Dict]:
        return chunks  # No modification
```

### Rationale

After format-specific parsing, chunks are already at paragraph-level. For NLP tasks requiring fine-grained analysis, this is the desired granularity.

### Configuration

```python
extractor = EpubExtractor("book.epub", config={
    "chunking_strategy": "nlp",
})
```

Or via CLI:

```bash
extract book.epub --chunking-strategy nlp
```

### Example Output

**Input/Output** (same - no transformation):

```json
[
    {
        "paragraph_id": 10,
        "text": "Prayer is the raising of one's mind and heart to God.",
        "hierarchy": {"level_1": "Chapter 1", "level_2": "Prayer"},
        "word_count": 12,
        "stable_id": "xyz789..."
    },
    {
        "paragraph_id": 11,
        "text": "It is a conversation with God.",
        "hierarchy": {"level_1": "Chapter 1", "level_2": "Prayer"},
        "word_count": 7,
        "stable_id": "def456..."
    }
]
```

Each paragraph is its own chunk with original boundaries preserved.

### Performance Characteristics

**Chunk count**: Same as paragraph count extracted from document.

**Word distribution** (varies by document):

```
Min chunk: 1 word (after filtering)
Max chunk: ~150 words (long paragraphs)
Avg chunk: 45 words
Median: 38 words
```

**Processing time**: Fastest (no merging overhead).

## Hierarchy Preservation Across Merges

A critical feature of RAG mode is maintaining hierarchy context even when paragraphs merge.

### How It Works

When merging paragraphs from the same hierarchy group:

```python
# All paragraphs in group share this hierarchy
hierarchy = {
    "level_1": "Part I: The Profession of Faith",
    "level_2": "Section Two: The Creeds",
    "level_3": "Chapter One: I Believe in God the Father"
}

# Merged chunk inherits this hierarchy
merged_chunk["hierarchy"] = hierarchy
```

Every chunk in the merged output has complete hierarchy context.

### Example: Long Chapter

Consider a chapter with 20 paragraphs:

```
Part I > Chapter 1 > Section A
  Paragraph 1 (30 words)
  Paragraph 2 (45 words)
  Paragraph 3 (50 words)
  ...
  Paragraph 20 (40 words)
Total: 900 words
```

RAG mode (max_words=500):

```
Merged Chunk 1:
  Text: Para 1 + Para 2 + ... + Para 10
  Word count: 480
  Hierarchy: {"level_1": "Part I", "level_2": "Chapter 1", "level_3": "Section A"}

Merged Chunk 2:
  Text: Para 11 + Para 12 + ... + Para 20
  Word count: 420
  Hierarchy: {"level_1": "Part I", "level_2": "Chapter 1", "level_3": "Section A"}
```

Both chunks retain the full hierarchy path. When embedded, searches will know both belong to "Part I > Chapter 1 > Section A".

### Cross-Document Hierarchy (EPUB)

EPUB documents have a spine - multiple XHTML files in sequence. The `preserve_hierarchy_across_docs` config controls whether hierarchy resets at file boundaries:

**preserve_hierarchy_across_docs=True** (default):

```
File: chapter1.xhtml
  <h1>Part I</h1>
  <p>Para 1</p>

File: chapter2.xhtml
  <p>Para 2</p>  ← Inherits "Part I" from previous file
```

**preserve_hierarchy_across_docs=False**:

```
File: chapter1.xhtml
  <h1>Part I</h1>
  <p>Para 1</p>  → Hierarchy: {"level_1": "Part I"}

File: chapter2.xhtml
  <p>Para 2</p>  → Hierarchy: {} (reset)
```

For well-structured EPUBs, use `True` to maintain chapter context across spine documents.

## Edge Cases and Behaviors

### Very Long Paragraphs

If a single paragraph exceeds `max_words`:

```json
{
    "text": "A 600-word paragraph...",
    "word_count": 600
}
```

**RAG mode**: Keep as-is (don't split). The chunk will be 600 words, exceeding max.

**Rationale**: Splitting mid-paragraph breaks semantic integrity. Better to have one oversized chunk than fragment a coherent thought.

If this is problematic, use the `token-rechunk` tool post-extraction to split at sentence boundaries.

### Very Short Paragraphs

If paragraphs are consistently short and don't reach `min_words` after merging:

```json
[
    {"text": "Short para 1", "word_count": 8},
    {"text": "Short para 2", "word_count": 9},
    {"text": "Short para 3", "word_count": 7},
]
```

With `min_words=100`, these would be dropped unless you have **many** under the same hierarchy.

**Solution**:

- Lower `min_words` (e.g., 50)
- Increase `preserve_hierarchy_levels` to merge across broader sections

### Empty Hierarchy

If a document has no headings:

```json
[
    {"text": "Para 1", "hierarchy": {}, "word_count": 50},
    {"text": "Para 2", "hierarchy": {}, "word_count": 60},
]
```

**RAG mode**: All paragraphs share the same hierarchy key (empty tuple), so they all group together and merge:

```json
{
    "text": "Para 1\n\nPara 2\n\n...",
    "hierarchy": {},
    "word_count": 110,
    "merged_paragraph_ids": [1, 2],
}
```

This may create very large chunks if the document is long. Add headings to the source document or use NLP mode.

### Hierarchy Changes Mid-Merge

If hierarchy changes while building a chunk:

```python
current_chunk = {
    "texts": ["Para 1", "Para 2"],
    "word_count": 120,
    "hierarchy": {"level_1": "Chapter 1"}
}

# Next paragraph has different hierarchy
next_para = {
    "text": "Para 3",
    "hierarchy": {"level_1": "Chapter 2"}  # ← Different
}
```

**Behavior**: The current chunk is finalized and saved. Para 3 starts a new group.

This is by design - hierarchy groups are immutable during merging.

### Special Sections (Index, TOC)

Index and TOC sections are **skipped entirely** in RAG mode:

```python
def _is_skippable_section(self, level_1: str) -> bool:
    skippable = {'index', 'table of contents', 'contents', 'toc'}
    return level_1.lower() in skippable
```

**Example**:

```json
[
    {"text": "Chapter 1 content", "hierarchy": {"level_1": "Chapter 1"}},
    {"text": "Page 1 ... 5", "hierarchy": {"level_1": "Index"}},  // ← Skipped
    {"text": "Chapter 2 content", "hierarchy": {"level_1": "Chapter 2"}},
]
```

Output includes Chapter 1 and Chapter 2 chunks, but not the Index entry.

**Rationale**: Index/TOC pages are noise for embeddings (just page numbers and cross-refs).

If you need them, use NLP mode or disable the filter.

## Strategy Selection Guidelines

### Use RAG/Semantic Strategy When:

✅ Building a vector database for semantic search

✅ Creating embeddings for RAG systems

✅ Optimizing for retrieval precision (fewer, richer chunks)

✅ Working with well-structured documents (clear headings)

✅ Want consistent 100-500 word chunks

### Use NLP/Paragraph Strategy When:

✅ Fine-grained NLP tasks (sentence classification, NER, sentiment)

✅ Training data generation (need exact paragraph boundaries)

✅ Documents with poor/no heading structure

✅ Preserving original document granularity is critical

✅ Post-processing will handle chunking (e.g., custom merging)

### Mixed Approach

You can extract with both strategies:

```bash
# RAG corpus for vector DB
extract corpus/*.epub -r --chunking-strategy rag --output-dir rag_chunks/

# NLP corpus for analysis
extract corpus/*.epub -r --chunking-strategy nlp --output-dir nlp_chunks/
```

Use the same source documents, different chunking for different applications.

## Real-World Examples

### Example 1: Catholic Encyclical

**Document structure**:

```
Encyclical Letter "Lumen Fidei" (Light of Faith)
├── Introduction (500 words)
├── Chapter I: We Have Believed in Love
│   ├── Section 1: Abraham (800 words, 5 paragraphs)
│   ├── Section 2: Faith of Israel (1200 words, 8 paragraphs)
│   └── Section 3: The Fullness of Faith (600 words, 4 paragraphs)
├── Chapter II: Unless You Believe
│   └── ...
└── Conclusion (400 words)
```

**RAG mode output**:

```
Chunk 1: Introduction (500 words, 1 chunk)
  Hierarchy: {"level_1": "Introduction"}

Chunk 2: Chapter I > Section 1 > Paragraphs 1-3 (480 words)
  Hierarchy: {"level_1": "Chapter I", "level_2": "Section 1"}

Chunk 3: Chapter I > Section 1 > Paragraphs 4-5 (320 words)
  Hierarchy: {"level_1": "Chapter I", "level_2": "Section 1"}

Chunk 4: Chapter I > Section 2 > Paragraphs 1-4 (600 words)  // ← Exceeds max but kept
  Hierarchy: {"level_1": "Chapter I", "level_2": "Section 2"}

... (24 total chunks for ~15,000 word document)
```

**NLP mode output**:

```
Chunk 1: Introduction Para 1 (120 words)
Chunk 2: Introduction Para 2 (140 words)
...
Chunk 125: Conclusion Para 3 (80 words)

(125 total paragraph-level chunks)
```

**Impact**:

- RAG: 24 chunks → 80% reduction, optimal for vector search
- NLP: 125 chunks → Fine-grained for analysis

### Example 2: Technical Manual (Poor Structure)

**Document structure**:

```
API Documentation
├── Overview (no headings, 2000 words)
├── Installation
│   └── (no subheadings, 500 words)
└── Usage Examples
    └── (no subheadings, 1500 words)
```

**RAG mode output**:

```
Chunk 1-4: Overview (4 chunks of ~500 words each)
  Hierarchy: {"level_1": "Overview"}

Chunk 5: Installation (500 words, 1 chunk)
  Hierarchy: {"level_1": "Installation"}

Chunk 6-9: Usage Examples (3-4 chunks)
  Hierarchy: {"level_1": "Usage Examples"}
```

**Problem**: Large sections with no subheadings create very large merged chunks or many chunks under broad heading.

**Solution**:

- Add subheadings to source document
- Use NLP mode for paragraph-level granularity
- Lower `preserve_hierarchy_levels` to 1 (group by top-level only)

## Performance Comparison

**Test corpus**: 12 diverse EPUBs, 37,415 paragraphs

| Metric | RAG Mode | NLP Mode | Difference |
|--------|----------|----------|------------|
| **Total chunks** | 8,932 | 37,415 | -76.1% |
| **Avg chunk size** | 248 words | 46 words | +439% |
| **Min chunk** | 100 words | 1 word | - |
| **Max chunk** | 512 words | 187 words | - |
| **Processing time** | 12.4s | 12.1s | +2.5% |
| **Quality score** | 0.897 | 0.897 | No change |

Key findings:

- **Chunk reduction**: 76% fewer chunks in RAG mode
- **Size distribution**: RAG produces consistent 100-500 word chunks
- **Performance**: Minimal overhead (<3%) for merging
- **Quality**: No change (same text content, different segmentation)

## Advanced: Custom Strategy

If neither RAG nor NLP fits your use case, implement a custom strategy:

```python
from extraction.core.strategies import ChunkingStrategy, ChunkConfig

class SentenceChunkingStrategy(ChunkingStrategy):
    """One sentence per chunk."""

    def apply(self, chunks: List[Dict], config: ChunkConfig) -> List[Dict]:
        from extraction.core.chunking import split_sentences

        sentence_chunks = []
        for chunk in chunks:
            sentences = split_sentences(chunk["text"])
            for idx, sent in enumerate(sentences):
                sentence_chunks.append({
                    "text": sent,
                    "word_count": len(sent.split()),
                    "hierarchy": chunk["hierarchy"],
                    "paragraph_id": chunk["paragraph_id"],
                    "sentence_index": idx,
                    # ... copy other fields
                })
        return sentence_chunks

    def name(self) -> str:
        return "sentence"
```

Register and use:

```python
from extraction.core.strategies import STRATEGIES
STRATEGIES["sentence"] = SentenceChunkingStrategy()

extractor = EpubExtractor("book.epub", config={"chunking_strategy": "sentence"})
```

This gives you full control over chunking logic while reusing the extraction pipeline.

## Summary

Chunking strategies determine how paragraphs are segmented after extraction:

- **RAG mode**: Merges paragraphs into 100-500 word semantic chunks (76% reduction)
- **NLP mode**: Preserves paragraph boundaries for fine-grained analysis

Choose based on your application:

- Vector search? → RAG
- NER/classification? → NLP
- Both? → Extract twice with different strategies

The strategy is applied **after** format-specific parsing, ensuring consistent behavior across EPUB, PDF, HTML, Markdown, and JSON inputs.
