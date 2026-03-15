# Token-Based Re-chunking

This guide shows you how to transform word-based extraction output into token-optimized chunks for embedding models.

## When to Use Token Re-chunking

Use `token-rechunk` when:

- Preparing content for embedding models (OpenAI, embeddinggemma, BERT)
- Building RAG systems with strict token limits
- Creating semantic search indexes
- Optimizing for specific embedding model context windows

**Don't use token re-chunking when**:

- You're already satisfied with word-based RAG chunks
- You don't need exact token counts
- You're not using embeddings

## Quick Start

```bash
# Install finetuning dependencies
uv pip install -e ".[finetuning]"

# Extract document first
extract book.epub --output book.json

# Re-chunk for retrieval (256-400 tokens)
token-rechunk book.json --mode retrieval

# Re-chunk for recommendations (512-700 tokens)
token-rechunk book.json --mode recommendation

# Output: book.jsonl (one chunk per line)
```

## Three Modes

The `token-rechunk` tool provides three presets optimized for different use cases.

### Retrieval Mode

Optimized for **RAG systems and semantic search**.

```bash
token-rechunk document.json --mode retrieval
```

**Configuration**:

- Target: 320 tokens
- Range: 256-400 tokens
- Overlap: 15% (better precision)

**Use cases**:

- Question answering systems
- Semantic search
- Citation finding
- Precise retrieval

**Why smaller chunks?**

- Better precision (fewer false positives)
- Faster search (more focused matches)
- Less context dilution

### Recommendation Mode

Optimized for **recommendation engines and context-heavy applications**.

```bash
token-rechunk document.json --mode recommendation
```

**Configuration**:

- Target: 600 tokens
- Range: 512-700 tokens
- Overlap: 10% (sufficient for context)

**Use cases**:

- Document recommendations ("similar documents")
- Content clustering
- Topic modeling
- Context-heavy retrieval

**Why larger chunks?**

- More context per chunk
- Better topic coherence
- Fewer chunks overall

### Balanced Mode (Default)

General-purpose middle ground.

```bash
token-rechunk document.json  # No mode flag
token-rechunk document.json --mode balanced
```

**Configuration**:

- Target: 450 tokens
- Range: 400-512 tokens
- Overlap: 10%

**Use cases**:

- General-purpose embeddings
- Mixed use cases (search + recommendations)
- When you're not sure which mode to use

## Custom Configuration

Override preset with custom token sizes:

```bash
# Custom range
token-rechunk document.json --min-tokens 300 --max-tokens 500

# Custom overlap
token-rechunk document.json --overlap-percent 0.12  # 12% overlap

# Disable overlap
token-rechunk document.json --no-overlap

# Combine custom settings
token-rechunk document.json \
    --min-tokens 200 \
    --max-tokens 400 \
    --overlap-percent 0.20
```

## Workflow: Extract → Re-chunk → Embed

Complete pipeline for building a vector database:

### 1. Extract Corpus

```bash
# Extract all documents
extract corpus/*.epub -r --output-dir extractions/

# Or extract with RAG strategy first
extract corpus/*.epub -r --output-dir extractions/ --chunking-strategy rag
```

### 2. Re-chunk for Embeddings

```bash
# Create token-optimized chunks for retrieval
mkdir rag_corpus/
for file in extractions/*.json; do
    token-rechunk "$file" --mode retrieval \
        --output "rag_corpus/$(basename $file .json).jsonl"
done

# Or for recommendations
mkdir recommendation_corpus/
for file in extractions/*.json; do
    token-rechunk "$file" --mode recommendation \
        --output "recommendation_corpus/$(basename $file .json).jsonl"
done
```

### 3. Combine Output

```bash
# Combine all JSONL files
cat rag_corpus/*.jsonl > rag_content.jsonl

# Count total chunks
wc -l rag_content.jsonl
```

### 4. Embed Chunks

```python
import json
from sentence_transformers import SentenceTransformer

# Load model
model = SentenceTransformer('all-MiniLM-L6-v2')

# Load re-chunked content
chunks = []
with open('rag_content.jsonl') as f:
    for line in f:
        chunk = json.loads(line)
        chunks.append(chunk)

# Embed chunks
texts = [chunk['text'] for chunk in chunks]
embeddings = model.encode(texts, show_progress_bar=True)

# Store in vector database
# (example with Pinecone, Weaviate, etc.)
```

## Output Format

`token-rechunk` outputs JSONL (JSON Lines) with one chunk per line.

### Example Output

```json
{
  "text": "First paragraph merged with second paragraph under same heading. This continues for multiple sentences until we reach the target token count...",
  "metadata": {
    "doc_id": "catechism_abc123",
    "source_file": "catechism.epub",
    "hierarchy": {
      "level_1": "Part I: The Liturgy",
      "level_2": "Chapter 1: The Nature of Liturgy",
      "level_3": "Article 1: What is Liturgy?"
    },
    "token_count": 312,
    "source_chunk_id": "abc123def456",
    "sentence_count": 8,
    "is_overlap": false
  }
}
```

### Fields

- **text**: The re-chunked text (optimized for embedding)
- **metadata.doc_id**: Original document ID
- **metadata.source_file**: Original file path
- **metadata.hierarchy**: Heading hierarchy (preserved from source)
- **metadata.token_count**: Exact token count for this chunk
- **metadata.source_chunk_id**: ID of source chunk in extraction output
- **metadata.sentence_count**: Number of sentences in chunk
- **metadata.is_overlap**: True if this chunk is an overlap chunk

### Overlap Chunks

When overlap is enabled, the tool creates additional chunks for better retrieval:

```json
{
  "text": "...last few sentences from previous chunk. First sentences from next chunk...",
  "metadata": {
    "token_count": 245,
    "is_overlap": true,
    ...
  }
}
```

**Why overlap?**

- Prevents information loss at chunk boundaries
- Improves retrieval of split concepts
- Enables better context matching

**Recommended overlap**:

- Retrieval mode: 15% (better precision)
- Recommendation mode: 10% (less important)
- Balanced mode: 10%

## Statistics and Logging

### View Statistics

```bash
# Show detailed statistics
token-rechunk document.json --stats
```

Example output:

```
Processed: catechism.json (mode: retrieval)
  Source chunks: 1,234 (word-based)
  Output chunks: 1,890 (token-based)
  Total tokens: 601,200
  Avg tokens/chunk: 318
  Min: 258, Max: 399
  Avg sentences/chunk: 8.5
  Chunks with hierarchy crossing: 18 (0.95%)

Output: catechism.jsonl
```

### Verbose Logging

```bash
# Enable debug logging
token-rechunk document.json --verbose
```

Shows:

- Tokenizer loading
- Chunk-by-chunk processing
- Overlap creation
- Validation warnings

## Hierarchy Preservation

Token chunks may span multiple source chunks. The tool preserves hierarchy intelligently:

### Single Source Chunk

If token chunk comes from one source chunk, hierarchy is preserved exactly:

```json
{
  "text": "...",
  "metadata": {
    "hierarchy": {
      "level_1": "Chapter 1",
      "level_2": "Section 1.1"
    }
  }
}
```

### Multiple Source Chunks

If token chunk spans multiple source chunks, the tool:

1. Finds the chunk contributing the most tokens
2. Uses that chunk's hierarchy
3. Logs a warning if hierarchies differ

```
WARNING: Token chunk crosses hierarchy boundaries. Using primary: {"level_1": "Chapter 1"}
```

**In statistics**:

```
Chunks with hierarchy crossing: 18 (0.95%)
```

**This is normal** for large token sizes (recommendation mode). Keep crossings below 5% for best results.

## Metadata Preservation

### Default Behavior

By default, only essential metadata is preserved:

- doc_id
- source_file
- hierarchy
- token_count
- source_chunk_id
- sentence_count
- is_overlap

### Full Metadata Preservation

Preserve all source metadata (scripture references, cross-references, etc.):

```bash
token-rechunk document.json --preserve-metadata
```

Adds to output:

- scripture_references
- cross_references
- word_count
- paragraph_id
- Any custom fields from source chunks

**Trade-off**: Larger output files, but preserves full context.

## Advanced Usage

### Embedding Model Compatibility

Different models have different optimal chunk sizes:

| Model | Context Window | Recommended Mode |
|-------|---------------|------------------|
| **OpenAI text-embedding-3** | 8191 tokens | Retrieval or Balanced |
| **embeddinggemma-300m** | 2048 tokens | Retrieval |
| **all-MiniLM-L6-v2** | 256 tokens | Custom (100-200 tokens) |
| **BERT base** | 512 tokens | Retrieval |

### Custom Configuration for BERT

```bash
# BERT has 512 token limit
token-rechunk document.json \
    --min-tokens 100 \
    --max-tokens 200 \
    --overlap-percent 0.15
```

### Custom Configuration for embeddinggemma-300m

```bash
# embeddinggemma has 2048 token limit but performs best <500 tokens
token-rechunk document.json --mode retrieval  # Already optimal
```

## Batch Processing

### Process Multiple Documents

```bash
# Process entire corpus
for file in extractions/*.json; do
    token-rechunk "$file" --mode retrieval \
        --output "rag_corpus/$(basename $file .json).jsonl" \
        --stats
done
```

### Parallel Processing

```bash
# Install GNU parallel
brew install parallel  # macOS
sudo apt-get install parallel  # Linux

# Process in parallel
find extractions/ -name "*.json" | parallel -j 4 \
    'token-rechunk {} --mode retrieval --output rag_corpus/{/.}.jsonl'
```

## Validation

The tool automatically validates chunks:

### Hard Token Limit

All chunks are validated against the 2048 token limit (embeddinggemma-300m context window).

**Oversized chunks are automatically split** at sentence boundaries:

```
WARNING: Chunk exceeds 2048 tokens, splitting...
```

### Quality Filtering

Chunks below `min_tokens` are dropped:

```
INFO: Filtered 23 chunks below minimum token count
```

### Empty Chunks

Empty chunks are automatically filtered out:

```
INFO: Filtered 5 empty chunks
```

## Integration with Vector Databases

### Pinecone

```python
import json
import pinecone
from sentence_transformers import SentenceTransformer

# Load chunks
chunks = []
with open('rag_content.jsonl') as f:
    for line in f:
        chunks.append(json.loads(line))

# Embed
model = SentenceTransformer('all-MiniLM-L6-v2')
texts = [c['text'] for c in chunks]
embeddings = model.encode(texts)

# Upload to Pinecone
pinecone.init(api_key="YOUR_API_KEY")
index = pinecone.Index("extraction-corpus")

vectors = [
    (
        f"{chunk['metadata']['doc_id']}_{i}",
        embedding.tolist(),
        chunk['metadata']
    )
    for i, (chunk, embedding) in enumerate(zip(chunks, embeddings))
]

index.upsert(vectors=vectors)
```

### Weaviate

```python
import json
import weaviate
from sentence_transformers import SentenceTransformer

# Load chunks
chunks = []
with open('rag_content.jsonl') as f:
    for line in f:
        chunks.append(json.loads(line))

# Connect to Weaviate
client = weaviate.Client("http://localhost:8080")

# Create schema
schema = {
    "class": "Document",
    "vectorizer": "none",  # We provide vectors
    "properties": [
        {"name": "text", "dataType": ["text"]},
        {"name": "doc_id", "dataType": ["string"]},
        {"name": "source_file", "dataType": ["string"]},
        {"name": "hierarchy", "dataType": ["object"]},
    ]
}

client.schema.create_class(schema)

# Embed and upload
model = SentenceTransformer('all-MiniLM-L6-v2')

for chunk in chunks:
    embedding = model.encode(chunk['text'])

    client.data_object.create(
        data_object={
            "text": chunk['text'],
            "doc_id": chunk['metadata']['doc_id'],
            "source_file": chunk['metadata']['source_file'],
            "hierarchy": chunk['metadata']['hierarchy'],
        },
        class_name="Document",
        vector=embedding.tolist()
    )
```

## Troubleshooting

### Import Error: transformers

```bash
# Install finetuning dependencies
uv pip install -e ".[finetuning]"

# Or install transformers directly
uv pip install transformers
```

### Tokenizer Download Issues

```bash
# Tokenizer downloads on first use
token-rechunk document.json  # Downloads gemma tokenizer

# Set cache directory
export HF_HOME=/path/to/cache
token-rechunk document.json
```

### Memory Issues

For very large documents:

```bash
# Process in smaller batches
# Split extraction output first, then re-chunk each part
```

### Slow Processing

Token counting is CPU-intensive. For faster processing:

```bash
# Process in parallel
find extractions/ -name "*.json" | parallel -j 4 token-rechunk {}
```

## Next Steps

- See [Vector Database Tutorial](../getting-started/vector-db.md) for complete RAG pipeline
- See [Chunking Strategy Guide](chunking-strategy.md) for choosing RAG vs NLP mode
- For production embedding pipelines, see [embeddinggemma documentation](https://huggingface.co/google/gemma-2-300m)
