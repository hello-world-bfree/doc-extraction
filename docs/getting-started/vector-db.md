# Building a Vector Database

This end-to-end guide shows you how to transform documents into a queryable vector database for RAG (Retrieval-Augmented Generation) systems and semantic search.

**Pipeline**: Extract → Token-Rechunk → Embed → Store → Query

## Overview

The complete workflow has four stages:

1. **Extract**: Transform documents into structured chunks (word-based)
2. **Token-Rechunk**: Optimize chunks for embedding models (token-based)
3. **Embed**: Generate vector embeddings for each chunk
4. **Store**: Insert chunks and vectors into a vector database
5. **Query**: Retrieve relevant chunks using semantic search

This guide uses ChromaDB as the example vector database, but the principles apply to LanceDB, Pinecone, Weaviate, and others.

## Prerequisites

Install dependencies:

```bash
# Extraction library with PDF support
uv pip install "doc-extraction[pdf]"

# Token rechunking (optional but recommended)
uv pip install "doc-extraction[finetuning]"

# Vector database (choose one)
uv pip install chromadb  # ChromaDB (local, easy to start)
# uv pip install lancedb  # LanceDB (fast, production-ready)
# uv pip install pinecone-client  # Pinecone (cloud, managed)

# Embedding model
uv pip install sentence-transformers
```

## Stage 1: Extract Documents

Extract all documents into structured chunks:

```bash
# Process all documents in a directory
extract documents/ -r \
    --output-dir outputs/extracted \
    --chunking-strategy rag \
    --min-chunk-words 100 \
    --max-chunk-words 500 \
    --ndjson

# This creates:
# - outputs/extracted/book1.json (full metadata)
# - outputs/extracted/book1.ndjson (one chunk per line)
# - outputs/extracted/book2.json
# - outputs/extracted/book2.ndjson
# ...
```

**What happens**:

- Detects format (EPUB, PDF, HTML, Markdown, JSON) automatically
- Extracts hierarchical chunks (100-500 words each)
- Filters noise (index pages, copyright, navigation)
- Generates both JSON (full) and NDJSON (streaming) outputs

**Programmatic extraction**:

```python
from extraction.extractors import EpubExtractor, PdfExtractor
from pathlib import Path

documents = [
    ("books/catechism.epub", EpubExtractor),
    ("papers/vatican_ii.pdf", PdfExtractor),
]

config = {
    'chunking_strategy': 'rag',
    'min_chunk_words': 100,
    'max_chunk_words': 500,
}

for doc_path, ExtractorClass in documents:
    extractor = ExtractorClass(doc_path, config=config)
    extractor.load()
    extractor.parse()

    # Save NDJSON for next stage
    output_path = Path("outputs/extracted") / f"{Path(doc_path).stem}.ndjson"
    # ... save logic here
```

## Stage 2: Token-Based Re-Chunking (Optional)

The extraction library produces **word-based chunks** (100-500 words). For embedding models, we need **token-based chunks** with strict limits.

### Why Re-Chunk?

Embedding models have token limits:

- `sentence-transformers/all-MiniLM-L6-v2`: 256 tokens
- `sentence-transformers/all-mpnet-base-v2`: 384 tokens
- `text-embedding-ada-002` (OpenAI): 8,191 tokens
- `embeddinggemma-300m`: 2,048 tokens

Word-based chunks may exceed these limits. Re-chunking ensures compliance.

### Run Token-Rechunk

```bash
# Re-chunk for retrieval (256-400 tokens)
mkdir outputs/rechunked

for file in outputs/extracted/*.json; do
    token-rechunk "$file" \
        --mode retrieval \
        --output "outputs/rechunked/$(basename $file .json).jsonl"
done

# Combine all chunks
cat outputs/rechunked/*.jsonl > corpus_ready_for_embedding.jsonl
```

**Modes**:

- `retrieval`: 256-400 tokens, 15% overlap (precision-optimized)
- `recommendation`: 512-700 tokens, 10% overlap (context-optimized)
- `balanced`: 400-512 tokens, 10% overlap (default)

**Output format** (JSONL):

```json
{"text": "First paragraph merged with second...", "metadata": {"doc_id": "catechism_abc123", "hierarchy": {"level_1": "Part I", "level_2": "Chapter 1"}, "token_count": 384, "source_chunk_id": "orig_1", "is_overlap": false}}
```

!!! tip "Skip re-chunking if"
    - Your embedding model has a large context window (8k+ tokens)
    - Your chunks are already small (100-200 words)
    - You're okay with manual truncation

## Stage 3: Generate Embeddings

Generate vector embeddings for each chunk using an embedding model.

### Using Sentence Transformers (Local)

```python
import json
from sentence_transformers import SentenceTransformer

# Load embedding model
model = SentenceTransformer('sentence-transformers/all-mpnet-base-v2')

# Load chunks
chunks = []
with open("corpus_ready_for_embedding.jsonl") as f:
    for line in f:
        chunk = json.loads(line)
        chunks.append(chunk)

# Generate embeddings (batched for efficiency)
texts = [chunk['text'] for chunk in chunks]
embeddings = model.encode(
    texts,
    batch_size=32,
    show_progress_bar=True,
    normalize_embeddings=True  # For cosine similarity
)

print(f"Generated {len(embeddings)} embeddings")
print(f"Embedding dimension: {embeddings[0].shape}")
```

### Using OpenAI API (Cloud)

```python
import json
from openai import OpenAI

client = OpenAI(api_key="your-api-key")

chunks = []
with open("corpus_ready_for_embedding.jsonl") as f:
    for line in f:
        chunk = json.loads(line)
        chunks.append(chunk)

# Generate embeddings (batched)
embeddings = []
batch_size = 100

for i in range(0, len(chunks), batch_size):
    batch = chunks[i:i+batch_size]
    texts = [chunk['text'] for chunk in batch]

    response = client.embeddings.create(
        model="text-embedding-ada-002",
        input=texts
    )

    batch_embeddings = [item.embedding for item in response.data]
    embeddings.extend(batch_embeddings)

print(f"Generated {len(embeddings)} embeddings")
```

## Stage 4: Store in Vector Database

Insert chunks and embeddings into a vector database.

### ChromaDB (Local)

```python
import json
import chromadb
from sentence_transformers import SentenceTransformer

# Initialize ChromaDB
client = chromadb.PersistentClient(path="./chroma_db")
collection = client.get_or_create_collection(
    name="document_corpus",
    metadata={"hnsw:space": "cosine"}
)

# Load chunks
chunks = []
with open("corpus_ready_for_embedding.jsonl") as f:
    for line in f:
        chunk = json.loads(line)
        chunks.append(chunk)

# Generate embeddings
model = SentenceTransformer('sentence-transformers/all-mpnet-base-v2')
texts = [chunk['text'] for chunk in chunks]
embeddings = model.encode(texts, normalize_embeddings=True)

# Prepare data for ChromaDB
ids = [chunk['metadata']['source_chunk_id'] for chunk in chunks]
metadatas = [chunk['metadata'] for chunk in chunks]
documents = [chunk['text'] for chunk in chunks]

# Insert into ChromaDB
collection.add(
    ids=ids,
    embeddings=embeddings.tolist(),
    metadatas=metadatas,
    documents=documents
)

print(f"Inserted {len(chunks)} chunks into ChromaDB")
```

### LanceDB (Production)

```python
import json
import lancedb
import pyarrow as pa
from sentence_transformers import SentenceTransformer

# Load chunks
chunks = []
with open("corpus_ready_for_embedding.jsonl") as f:
    for line in f:
        chunk = json.loads(line)
        chunks.append(chunk)

# Generate embeddings
model = SentenceTransformer('sentence-transformers/all-mpnet-base-v2')
texts = [chunk['text'] for chunk in chunks]
embeddings = model.encode(texts, normalize_embeddings=True)

# Prepare data for LanceDB
data = []
for chunk, embedding in zip(chunks, embeddings):
    data.append({
        'chunk_id': chunk['metadata']['source_chunk_id'],
        'text': chunk['text'],
        'embedding': embedding,
        'doc_id': chunk['metadata']['doc_id'],
        'hierarchy': json.dumps(chunk['metadata'].get('hierarchy', {})),
        'token_count': chunk['metadata']['token_count'],
    })

# Create LanceDB table
db = lancedb.connect("./lancedb")
table = db.create_table("document_corpus", data=data, mode="overwrite")

print(f"Inserted {len(data)} chunks into LanceDB")
```

### Pinecone (Cloud)

```python
import json
from pinecone import Pinecone, ServerlessSpec
from sentence_transformers import SentenceTransformer

# Initialize Pinecone
pc = Pinecone(api_key="your-api-key")

# Create index (if not exists)
index_name = "document-corpus"
if index_name not in pc.list_indexes().names():
    pc.create_index(
        name=index_name,
        dimension=768,  # all-mpnet-base-v2 dimension
        metric="cosine",
        spec=ServerlessSpec(cloud="aws", region="us-east-1")
    )

index = pc.Index(index_name)

# Load chunks
chunks = []
with open("corpus_ready_for_embedding.jsonl") as f:
    for line in f:
        chunk = json.loads(line)
        chunks.append(chunk)

# Generate embeddings
model = SentenceTransformer('sentence-transformers/all-mpnet-base-v2')
texts = [chunk['text'] for chunk in chunks]
embeddings = model.encode(texts, normalize_embeddings=True)

# Prepare data for Pinecone
vectors = []
for chunk, embedding in zip(chunks, embeddings):
    vectors.append({
        'id': chunk['metadata']['source_chunk_id'],
        'values': embedding.tolist(),
        'metadata': {
            'text': chunk['text'],
            'doc_id': chunk['metadata']['doc_id'],
            'hierarchy': json.dumps(chunk['metadata'].get('hierarchy', {})),
        }
    })

# Upsert in batches
batch_size = 100
for i in range(0, len(vectors), batch_size):
    batch = vectors[i:i+batch_size]
    index.upsert(vectors=batch)

print(f"Inserted {len(vectors)} chunks into Pinecone")
```

## Stage 5: Query and Retrieve

Perform semantic search to retrieve relevant chunks.

### Query with ChromaDB

```python
import chromadb
from sentence_transformers import SentenceTransformer

# Connect to ChromaDB
client = chromadb.PersistentClient(path="./chroma_db")
collection = client.get_collection("document_corpus")

# Load embedding model
model = SentenceTransformer('sentence-transformers/all-mpnet-base-v2')

# User query
query = "What is the purpose of the liturgy?"

# Generate query embedding
query_embedding = model.encode([query], normalize_embeddings=True)[0]

# Search
results = collection.query(
    query_embeddings=[query_embedding.tolist()],
    n_results=5,
    include=['documents', 'metadatas', 'distances']
)

# Display results
for i, (doc, metadata, distance) in enumerate(zip(
    results['documents'][0],
    results['metadatas'][0],
    results['distances'][0]
)):
    print(f"\n--- Result {i+1} (similarity: {1 - distance:.4f}) ---")
    print(f"Document: {metadata['doc_id']}")
    print(f"Hierarchy: {metadata.get('hierarchy', {})}")
    print(f"Text: {doc[:200]}...")
```

### Query with LanceDB

```python
import lancedb
from sentence_transformers import SentenceTransformer

# Connect to LanceDB
db = lancedb.connect("./lancedb")
table = db.open_table("document_corpus")

# Load embedding model
model = SentenceTransformer('sentence-transformers/all-mpnet-base-v2')

# User query
query = "What is the purpose of the liturgy?"

# Generate query embedding
query_embedding = model.encode([query], normalize_embeddings=True)[0]

# Search
results = table.search(query_embedding).limit(5).to_pandas()

# Display results
for i, row in results.iterrows():
    print(f"\n--- Result {i+1} (distance: {row['_distance']:.4f}) ---")
    print(f"Document: {row['doc_id']}")
    print(f"Hierarchy: {row['hierarchy']}")
    print(f"Text: {row['text'][:200]}...")
```

### Query with Pinecone

```python
from pinecone import Pinecone
from sentence_transformers import SentenceTransformer

# Connect to Pinecone
pc = Pinecone(api_key="your-api-key")
index = pc.Index("document-corpus")

# Load embedding model
model = SentenceTransformer('sentence-transformers/all-mpnet-base-v2')

# User query
query = "What is the purpose of the liturgy?"

# Generate query embedding
query_embedding = model.encode([query], normalize_embeddings=True)[0]

# Search
results = index.query(
    vector=query_embedding.tolist(),
    top_k=5,
    include_metadata=True
)

# Display results
for i, match in enumerate(results['matches']):
    print(f"\n--- Result {i+1} (score: {match['score']:.4f}) ---")
    print(f"Document: {match['metadata']['doc_id']}")
    print(f"Hierarchy: {match['metadata']['hierarchy']}")
    print(f"Text: {match['metadata']['text'][:200]}...")
```

## Complete Example: End-to-End

Here's a complete script that runs the entire pipeline:

```python
import json
from pathlib import Path
from sentence_transformers import SentenceTransformer
import chromadb
from extraction.extractors import EpubExtractor

# Configuration
DOCS_DIR = Path("documents")
OUTPUT_DIR = Path("outputs")
EMBEDDING_MODEL = "sentence-transformers/all-mpnet-base-v2"

# Stage 1: Extract
print("Stage 1: Extracting documents...")
OUTPUT_DIR.mkdir(exist_ok=True)

for epub_file in DOCS_DIR.glob("*.epub"):
    print(f"  Extracting {epub_file.name}...")

    extractor = EpubExtractor(str(epub_file), config={
        'chunking_strategy': 'rag',
        'min_chunk_words': 100,
        'max_chunk_words': 500,
    })
    extractor.load()
    extractor.parse()

    # Save NDJSON
    output_file = OUTPUT_DIR / f"{epub_file.stem}.ndjson"
    with open(output_file, 'w') as f:
        for chunk in extractor.chunks:
            chunk_dict = chunk.to_dict()
            # Add metadata for vector DB
            chunk_data = {
                'text': chunk_dict['text'],
                'metadata': {
                    'source_chunk_id': chunk_dict['stable_id'],
                    'doc_id': extractor.extract_metadata().provenance.doc_id,
                    'hierarchy': chunk_dict.get('hierarchy', {}),
                    'token_count': len(chunk_dict['text'].split()) * 1.3,  # Rough estimate
                }
            }
            f.write(json.dumps(chunk_data) + '\n')

# Stage 2: Load all chunks
print("\nStage 2: Loading chunks...")
chunks = []
for ndjson_file in OUTPUT_DIR.glob("*.ndjson"):
    with open(ndjson_file) as f:
        for line in f:
            chunks.append(json.loads(line))

print(f"  Loaded {len(chunks)} chunks")

# Stage 3: Generate embeddings
print("\nStage 3: Generating embeddings...")
model = SentenceTransformer(EMBEDDING_MODEL)
texts = [chunk['text'] for chunk in chunks]
embeddings = model.encode(
    texts,
    batch_size=32,
    show_progress_bar=True,
    normalize_embeddings=True
)
print(f"  Generated {len(embeddings)} embeddings")

# Stage 4: Store in ChromaDB
print("\nStage 4: Storing in ChromaDB...")
client = chromadb.PersistentClient(path="./chroma_db")
collection = client.get_or_create_collection(
    name="document_corpus",
    metadata={"hnsw:space": "cosine"}
)

ids = [chunk['metadata']['source_chunk_id'] for chunk in chunks]
metadatas = [chunk['metadata'] for chunk in chunks]
documents = [chunk['text'] for chunk in chunks]

collection.add(
    ids=ids,
    embeddings=embeddings.tolist(),
    metadatas=metadatas,
    documents=documents
)
print(f"  Inserted {len(chunks)} chunks")

# Stage 5: Query
print("\nStage 5: Querying...")
query = "What is the purpose of the liturgy?"
query_embedding = model.encode([query], normalize_embeddings=True)[0]

results = collection.query(
    query_embeddings=[query_embedding.tolist()],
    n_results=3,
    include=['documents', 'metadatas', 'distances']
)

print(f"\nQuery: '{query}'")
for i, (doc, metadata, distance) in enumerate(zip(
    results['documents'][0],
    results['metadatas'][0],
    results['distances'][0]
)):
    print(f"\n--- Result {i+1} (similarity: {1 - distance:.4f}) ---")
    print(f"Text: {doc[:200]}...")
```

## Best Practices

1. **Always use RAG chunking** for vector databases
   ```bash
   extract docs/ --chunking-strategy rag --min-chunk-words 100 --max-chunk-words 500
   ```

2. **Re-chunk for strict token limits**
   ```bash
   token-rechunk output.json --mode retrieval --max-tokens 512
   ```

3. **Normalize embeddings** for cosine similarity
   ```python
   embeddings = model.encode(texts, normalize_embeddings=True)
   ```

4. **Batch processing** for efficiency
   ```python
   embeddings = model.encode(texts, batch_size=32)
   ```

5. **Include hierarchy in metadata** for context
   ```python
   metadata = {
       'hierarchy': chunk['metadata']['hierarchy'],
       'doc_id': chunk['metadata']['doc_id'],
   }
   ```

6. **Use NDJSON for streaming** large corpora
   ```bash
   extract docs/ --ndjson  # One chunk per line
   ```

## Troubleshooting

### "Embedding dimension mismatch"

Your embedding model dimension doesn't match your vector database configuration:

```python
# Check model dimension
model = SentenceTransformer('sentence-transformers/all-mpnet-base-v2')
print(model.get_sentence_embedding_dimension())  # 768

# Update vector DB configuration
collection = client.create_collection(
    name="corpus",
    dimension=768  # Match model dimension
)
```

### "Token limit exceeded"

Your chunks are too large for the embedding model:

```bash
# Re-chunk with smaller targets
token-rechunk output.json --mode retrieval --max-tokens 256
```

### "Out of memory"

Batch your embedding generation:

```python
batch_size = 32  # Reduce if still OOM
embeddings = model.encode(texts, batch_size=batch_size)
```

## Next Steps

<div class="grid cards" markdown>

-   :material-tune:{ .lg .middle } **[Token Rechunking Guide](../how-to/token-rechunking.md)**

    ---

    Deep dive into token-based re-chunking strategies

-   :material-database-cog:{ .lg .middle } **[Vector DB Examples](../examples/vector-db-integration.md)**

    ---

    More examples: LanceDB, Pinecone, Weaviate

-   :material-robot:{ .lg .middle } **[Choosing Chunking Strategy](../how-to/chunking-strategy.md)**

    ---

    RAG vs NLP mode - detailed comparison

-   :material-cog:{ .lg .middle } **[Configuration Reference](../reference/configuration.md)**

    ---

    All extractor configuration options

</div>

## Summary

You learned how to:

1. Extract documents into structured chunks (word-based)
2. Re-chunk into token-optimized chunks (optional)
3. Generate embeddings with sentence transformers or OpenAI
4. Store in ChromaDB, LanceDB, or Pinecone
5. Query using semantic search

The extraction library handles the hardest part (document → structured chunks). From there, it's straightforward to build a production RAG system.
