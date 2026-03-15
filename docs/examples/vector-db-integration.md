# Vector Database Integration

**Complete examples for integrating extraction library with popular vector databases**

This guide provides production-ready code for building semantic search systems using the extraction library with ChromaDB, LanceDB, Pinecone, and Weaviate. Each example includes setup, extraction, embedding, storage, and querying.

## Overview

The typical pipeline:

```
Documents (EPUB, PDF, HTML, etc.)
    ↓ extract (RAG mode)
Structured Chunks (100-500 words)
    ↓ token-rechunk (optional)
Token-Optimized Chunks (256-512 tokens)
    ↓ embed (Sentence Transformers, OpenAI, Cohere)
Vector Embeddings (384-1536 dimensions)
    ↓ store
Vector Database (ChromaDB, LanceDB, Pinecone, Weaviate)
    ↓ query
Relevant Chunks for RAG
```

We'll walk through each vector DB with complete working code.

## Prerequisites

Install the extraction library:

```bash
uv pip install doc-extraction

# For token rechunking (optional but recommended)
uv pip install "doc-extraction[finetuning]"
```

## ChromaDB: Local, Simple Setup

**Best for**: Local development, prototyping, small-to-medium datasets (<1M chunks)

**Pros**: Zero setup, pure Python, persistent storage

**Cons**: No production clustering, limited scalability

### Installation

```bash
uv pip install chromadb sentence-transformers
```

### Complete Example

```python
import json
import chromadb
from chromadb.config import Settings
from sentence_transformers import SentenceTransformer
from pathlib import Path

from extraction.extractors import EpubExtractor, PdfExtractor, HtmlExtractor
from extraction.core.strategies import ChunkConfig


class ChromaDBPipeline:
    """Extract documents and build ChromaDB collection."""

    def __init__(
        self,
        collection_name: str = "documents",
        persist_directory: str = "./chroma_db",
        embedding_model: str = "all-MiniLM-L6-v2"
    ):
        self.client = chromadb.Client(Settings(
            persist_directory=persist_directory,
            anonymized_telemetry=False
        ))

        self.collection = self.client.get_or_create_collection(
            name=collection_name,
            metadata={"description": "Document chunks for semantic search"}
        )

        self.encoder = SentenceTransformer(embedding_model)

    def extract_document(self, file_path: str) -> list[dict]:
        """Extract chunks from document using RAG strategy."""
        if file_path.endswith(".epub"):
            extractor = EpubExtractor(file_path, config={
                "chunking_strategy": "rag",
                "min_chunk_words": 100,
                "max_chunk_words": 500,
            })
        elif file_path.endswith(".pdf"):
            extractor = PdfExtractor(file_path, config={
                "chunking_strategy": "rag",
                "min_chunk_words": 100,
                "max_chunk_words": 500,
            })
        elif file_path.endswith(".html"):
            extractor = HtmlExtractor(file_path, config={
                "chunking_strategy": "rag",
                "min_chunk_words": 100,
                "max_chunk_words": 500,
            })
        else:
            raise ValueError(f"Unsupported format: {file_path}")

        extractor.load()
        extractor.parse()
        metadata = extractor.extract_metadata()

        chunks = []
        for chunk in extractor.chunks:
            chunk_dict = chunk.to_dict()
            chunk_dict["source_file"] = file_path
            chunk_dict["title"] = metadata.title
            chunk_dict["author"] = metadata.author
            chunks.append(chunk_dict)

        return chunks

    def add_chunks(self, chunks: list[dict]) -> None:
        """Embed and store chunks in ChromaDB."""
        texts = [chunk["text"] for chunk in chunks]
        embeddings = self.encoder.encode(texts, show_progress_bar=True)

        ids = [chunk["stable_id"] for chunk in chunks]

        metadatas = []
        for chunk in chunks:
            metadata = {
                "source_file": chunk.get("source_file", ""),
                "title": chunk.get("title", ""),
                "author": chunk.get("author", ""),
                "word_count": chunk.get("word_count", 0),
                "hierarchy_path": chunk.get("heading_path", ""),
            }

            if chunk.get("scripture_references"):
                metadata["scripture_refs"] = ",".join(chunk["scripture_references"][:5])

            metadatas.append(metadata)

        self.collection.add(
            ids=ids,
            embeddings=embeddings.tolist(),
            documents=texts,
            metadatas=metadatas
        )

        print(f"Added {len(chunks)} chunks to ChromaDB")

    def query(self, query_text: str, n_results: int = 5) -> dict:
        """Query the collection."""
        query_embedding = self.encoder.encode([query_text])[0]

        results = self.collection.query(
            query_embeddings=[query_embedding.tolist()],
            n_results=n_results,
            include=["documents", "metadatas", "distances"]
        )

        return results

    def search(self, query_text: str, n_results: int = 5) -> None:
        """Search and print results."""
        results = self.query(query_text, n_results)

        print(f"\nQuery: {query_text}")
        print(f"Found {len(results['documents'][0])} results\n")

        for i, (doc, metadata, distance) in enumerate(zip(
            results['documents'][0],
            results['metadatas'][0],
            results['distances'][0]
        )):
            print(f"Result {i+1} (distance: {distance:.4f}):")
            print(f"  Source: {metadata['title']} - {metadata['hierarchy_path']}")
            print(f"  Text: {doc[:200]}...")
            if metadata.get('scripture_refs'):
                print(f"  Scripture: {metadata['scripture_refs']}")
            print()


def main():
    pipeline = ChromaDBPipeline(
        collection_name="catholic_documents",
        persist_directory="./chroma_db",
        embedding_model="all-MiniLM-L6-v2"
    )

    documents = [
        "corpus/catechism.epub",
        "corpus/prayer_book.pdf",
        "corpus/encyclical.html",
    ]

    for doc_path in documents:
        print(f"Processing {doc_path}...")
        chunks = pipeline.extract_document(doc_path)
        pipeline.add_chunks(chunks)

    pipeline.search("What is prayer?", n_results=5)
    pipeline.search("sacraments of initiation", n_results=3)


if __name__ == "__main__":
    main()
```

### Usage

```bash
python chroma_pipeline.py
```

Output persists to `./chroma_db` directory. Restart the script and the collection is reloaded automatically.

### Error Handling

Add retry logic for embedding failures:

```python
def add_chunks_with_retry(self, chunks: list[dict], max_retries: int = 3) -> None:
    """Add chunks with exponential backoff on failures."""
    import time

    for attempt in range(max_retries):
        try:
            self.add_chunks(chunks)
            return
        except Exception as e:
            if attempt == max_retries - 1:
                raise
            wait_time = 2 ** attempt
            print(f"Error: {e}. Retrying in {wait_time}s...")
            time.sleep(wait_time)
```

## LanceDB: Serverless, Python-Native

**Best for**: Embedded applications, serverless functions, medium-to-large datasets

**Pros**: Serverless (no daemon), SQL-like queries, automatic versioning, fast

**Cons**: Newer ecosystem, fewer integrations

### Installation

```bash
uv pip install lancedb sentence-transformers pyarrow
```

### Complete Example

```python
import lancedb
import pyarrow as pa
from sentence_transformers import SentenceTransformer
from pathlib import Path

from extraction.extractors import EpubExtractor


class LanceDBPipeline:
    """Extract documents and build LanceDB table."""

    def __init__(
        self,
        db_path: str = "./lance_db",
        table_name: str = "documents",
        embedding_model: str = "all-MiniLM-L6-v2"
    ):
        self.db = lancedb.connect(db_path)
        self.table_name = table_name
        self.encoder = SentenceTransformer(embedding_model)

        self.schema = pa.schema([
            pa.field("id", pa.string()),
            pa.field("text", pa.string()),
            pa.field("vector", pa.list_(pa.float32(), 384)),  # all-MiniLM-L6-v2 dim
            pa.field("source_file", pa.string()),
            pa.field("title", pa.string()),
            pa.field("author", pa.string()),
            pa.field("hierarchy_path", pa.string()),
            pa.field("word_count", pa.int32()),
            pa.field("scripture_refs", pa.string()),
        ])

    def extract_and_embed_document(self, file_path: str) -> list[dict]:
        """Extract chunks and generate embeddings."""
        extractor = EpubExtractor(file_path, config={
            "chunking_strategy": "rag",
            "min_chunk_words": 150,
            "max_chunk_words": 500,
        })

        extractor.load()
        extractor.parse()
        metadata = extractor.extract_metadata()

        texts = [chunk.text for chunk in extractor.chunks]
        embeddings = self.encoder.encode(texts, show_progress_bar=True)

        records = []
        for chunk, embedding in zip(extractor.chunks, embeddings):
            record = {
                "id": chunk.stable_id,
                "text": chunk.text,
                "vector": embedding.tolist(),
                "source_file": file_path,
                "title": metadata.title,
                "author": metadata.author,
                "hierarchy_path": chunk.heading_path,
                "word_count": chunk.word_count,
                "scripture_refs": ",".join(chunk.scripture_references[:5]),
            }
            records.append(record)

        return records

    def create_table(self, records: list[dict]) -> None:
        """Create LanceDB table from records."""
        self.table = self.db.create_table(
            self.table_name,
            data=records,
            schema=self.schema,
            mode="overwrite"
        )
        print(f"Created table '{self.table_name}' with {len(records)} records")

    def add_records(self, records: list[dict]) -> None:
        """Add records to existing table."""
        self.table = self.db.open_table(self.table_name)
        self.table.add(records)
        print(f"Added {len(records)} records")

    def search(self, query_text: str, limit: int = 5) -> pa.Table:
        """Vector similarity search."""
        query_embedding = self.encoder.encode([query_text])[0]

        self.table = self.db.open_table(self.table_name)
        results = self.table.search(query_embedding.tolist()).limit(limit).to_arrow()

        return results

    def print_results(self, results: pa.Table, query_text: str) -> None:
        """Pretty-print search results."""
        print(f"\nQuery: {query_text}")
        print(f"Found {len(results)} results\n")

        for i in range(len(results)):
            row = results.slice(i, 1)
            print(f"Result {i+1} (score: {row['_distance'][0].as_py():.4f}):")
            print(f"  Source: {row['title'][0].as_py()} - {row['hierarchy_path'][0].as_py()}")
            print(f"  Text: {row['text'][0].as_py()[:200]}...")
            if row['scripture_refs'][0].as_py():
                print(f"  Scripture: {row['scripture_refs'][0].as_py()}")
            print()

    def filter_search(
        self,
        query_text: str,
        where_clause: str,
        limit: int = 5
    ) -> pa.Table:
        """Search with SQL-like filtering."""
        query_embedding = self.encoder.encode([query_text])[0]

        self.table = self.db.open_table(self.table_name)
        results = (
            self.table.search(query_embedding.tolist())
            .where(where_clause)
            .limit(limit)
            .to_arrow()
        )

        return results


def main():
    pipeline = LanceDBPipeline(
        db_path="./lance_db",
        table_name="catholic_docs"
    )

    doc = "corpus/catechism.epub"
    print(f"Processing {doc}...")
    records = pipeline.extract_and_embed_document(doc)
    pipeline.create_table(records)

    # Add more documents
    for doc in ["corpus/prayer_book.epub", "corpus/encyclical.epub"]:
        print(f"Processing {doc}...")
        records = pipeline.extract_and_embed_document(doc)
        pipeline.add_records(records)

    # Basic search
    results = pipeline.search("What is the Eucharist?", limit=5)
    pipeline.print_results(results, "What is the Eucharist?")

    # Filtered search (SQL-like WHERE clause)
    results = pipeline.filter_search(
        "prayer and worship",
        "word_count > 200",
        limit=3
    )
    pipeline.print_results(results, "prayer and worship (long chunks only)")


if __name__ == "__main__":
    main()
```

### Advanced: FTS + Vector Hybrid Search

LanceDB supports hybrid search (full-text + vector):

```python
def hybrid_search(
    self,
    query_text: str,
    limit: int = 5,
    fts_weight: float = 0.3,
    vector_weight: float = 0.7
) -> pa.Table:
    """Combine FTS and vector search."""
    self.table = self.db.open_table(self.table_name)

    # Create FTS index if not exists
    self.table.create_fts_index("text")

    query_embedding = self.encoder.encode([query_text])[0]

    results = (
        self.table.search(query_embedding.tolist(), vector_column_name="vector")
        .rerank(fts_weight=fts_weight, vector_weight=vector_weight)
        .limit(limit)
        .to_arrow()
    )

    return results
```

## Pinecone: Cloud, Managed Service

**Best for**: Production systems, large datasets (>1M chunks), serverless deployments

**Pros**: Fully managed, scalable, low latency, serverless tier available

**Cons**: Paid service (free tier available), network dependency

### Installation

```bash
uv pip install pinecone-client sentence-transformers
```

### Complete Example

```python
import os
from pinecone import Pinecone, ServerlessSpec
from sentence_transformers import SentenceTransformer
from tqdm import tqdm

from extraction.extractors import EpubExtractor


class PineconePipeline:
    """Extract documents and build Pinecone index."""

    def __init__(
        self,
        index_name: str = "documents",
        embedding_model: str = "all-MiniLM-L6-v2",
        dimension: int = 384,
        cloud: str = "aws",
        region: str = "us-east-1"
    ):
        api_key = os.getenv("PINECONE_API_KEY")
        if not api_key:
            raise ValueError("PINECONE_API_KEY environment variable required")

        self.pc = Pinecone(api_key=api_key)
        self.index_name = index_name
        self.encoder = SentenceTransformer(embedding_model)

        if index_name not in self.pc.list_indexes().names():
            self.pc.create_index(
                name=index_name,
                dimension=dimension,
                metric="cosine",
                spec=ServerlessSpec(
                    cloud=cloud,
                    region=region
                )
            )
            print(f"Created index '{index_name}'")

        self.index = self.pc.Index(index_name)

    def extract_document(self, file_path: str) -> list[dict]:
        """Extract chunks from document."""
        extractor = EpubExtractor(file_path, config={
            "chunking_strategy": "rag",
            "min_chunk_words": 100,
            "max_chunk_words": 500,
        })

        extractor.load()
        extractor.parse()
        metadata = extractor.extract_metadata()

        chunks = []
        for chunk in extractor.chunks:
            chunk_dict = chunk.to_dict()
            chunk_dict["source_file"] = file_path
            chunk_dict["title"] = metadata.title
            chunk_dict["author"] = metadata.author
            chunks.append(chunk_dict)

        return chunks

    def upsert_chunks(self, chunks: list[dict], batch_size: int = 100) -> None:
        """Embed and upsert chunks to Pinecone."""
        texts = [chunk["text"] for chunk in chunks]
        embeddings = self.encoder.encode(texts, show_progress_bar=True)

        vectors = []
        for chunk, embedding in zip(chunks, embeddings):
            metadata = {
                "text": chunk["text"][:1000],  # Pinecone metadata limit
                "source_file": chunk.get("source_file", ""),
                "title": chunk.get("title", ""),
                "author": chunk.get("author", ""),
                "word_count": chunk.get("word_count", 0),
                "hierarchy_path": chunk.get("heading_path", ""),
            }

            if chunk.get("scripture_references"):
                metadata["scripture_refs"] = ",".join(chunk["scripture_references"][:5])

            vectors.append({
                "id": chunk["stable_id"],
                "values": embedding.tolist(),
                "metadata": metadata
            })

        for i in tqdm(range(0, len(vectors), batch_size), desc="Upserting"):
            batch = vectors[i:i + batch_size]
            self.index.upsert(vectors=batch)

        print(f"Upserted {len(chunks)} chunks to Pinecone")

    def query(
        self,
        query_text: str,
        top_k: int = 5,
        filter: dict = None
    ) -> dict:
        """Query the index."""
        query_embedding = self.encoder.encode([query_text])[0]

        results = self.index.query(
            vector=query_embedding.tolist(),
            top_k=top_k,
            filter=filter,
            include_metadata=True
        )

        return results

    def search(self, query_text: str, top_k: int = 5, filter: dict = None) -> None:
        """Search and print results."""
        results = self.query(query_text, top_k, filter)

        print(f"\nQuery: {query_text}")
        print(f"Found {len(results['matches'])} results\n")

        for i, match in enumerate(results['matches']):
            metadata = match['metadata']
            print(f"Result {i+1} (score: {match['score']:.4f}):")
            print(f"  Source: {metadata['title']} - {metadata['hierarchy_path']}")
            print(f"  Text: {metadata['text'][:200]}...")
            if metadata.get('scripture_refs'):
                print(f"  Scripture: {metadata['scripture_refs']}")
            print()

    def delete_all(self) -> None:
        """Delete all vectors (use with caution)."""
        self.index.delete(delete_all=True)
        print("Deleted all vectors from index")


def main():
    pipeline = PineconePipeline(
        index_name="catholic-documents",
        embedding_model="all-MiniLM-L6-v2"
    )

    documents = [
        "corpus/catechism.epub",
        "corpus/prayer_book.epub",
        "corpus/encyclical.epub",
    ]

    for doc_path in documents:
        print(f"Processing {doc_path}...")
        chunks = pipeline.extract_document(doc_path)
        pipeline.upsert_chunks(chunks)

    # Basic search
    pipeline.search("What are the sacraments?", top_k=5)

    # Filtered search
    pipeline.search(
        "prayer practices",
        top_k=3,
        filter={"title": {"$eq": "Catechism of the Catholic Church"}}
    )


if __name__ == "__main__":
    main()
```

### Environment Setup

```bash
export PINECONE_API_KEY="your-api-key-here"
python pinecone_pipeline.py
```

### Metadata Filtering

Pinecone supports rich metadata filters:

```python
# Equality
filter = {"title": {"$eq": "Catechism"}}

# Range (word count > 200)
filter = {"word_count": {"$gt": 200}}

# Multiple conditions (AND)
filter = {
    "$and": [
        {"word_count": {"$gte": 150}},
        {"title": {"$eq": "Catechism"}}
    ]
}

# Contains (substring match)
filter = {"hierarchy_path": {"$contains": "Prayer"}}
```

## Weaviate: Self-Hosted or Cloud

**Best for**: Advanced RAG systems, multi-modal search, complex schemas

**Pros**: Built-in vectorization modules, GraphQL API, multi-tenancy, cloud or self-hosted

**Cons**: More complex setup, overkill for simple use cases

### Installation

```bash
# Python client
uv pip install weaviate-client sentence-transformers

# Docker Compose for local Weaviate instance
# Create docker-compose.yml (see below)
docker-compose up -d
```

**docker-compose.yml**:

```yaml
version: '3.4'
services:
  weaviate:
    image: semitechnologies/weaviate:latest
    ports:
      - "8080:8080"
    environment:
      QUERY_DEFAULTS_LIMIT: 25
      AUTHENTICATION_ANONYMOUS_ACCESS_ENABLED: 'true'
      PERSISTENCE_DATA_PATH: '/var/lib/weaviate'
      DEFAULT_VECTORIZER_MODULE: 'none'
      CLUSTER_HOSTNAME: 'node1'
```

### Complete Example

```python
import weaviate
from weaviate.classes.config import Configure, Property, DataType
from sentence_transformers import SentenceTransformer

from extraction.extractors import EpubExtractor


class WeaviatePipeline:
    """Extract documents and build Weaviate collection."""

    def __init__(
        self,
        url: str = "http://localhost:8080",
        collection_name: str = "Document",
        embedding_model: str = "all-MiniLM-L6-v2"
    ):
        self.client = weaviate.connect_to_local(host="localhost", port=8080)
        self.collection_name = collection_name
        self.encoder = SentenceTransformer(embedding_model)

        self._create_collection()

    def _create_collection(self) -> None:
        """Create Weaviate collection with schema."""
        if self.client.collections.exists(self.collection_name):
            print(f"Collection '{self.collection_name}' already exists")
            return

        self.client.collections.create(
            name=self.collection_name,
            properties=[
                Property(name="text", data_type=DataType.TEXT),
                Property(name="source_file", data_type=DataType.TEXT),
                Property(name="title", data_type=DataType.TEXT),
                Property(name="author", data_type=DataType.TEXT),
                Property(name="hierarchy_path", data_type=DataType.TEXT),
                Property(name="word_count", data_type=DataType.INT),
                Property(name="scripture_refs", data_type=DataType.TEXT),
            ],
            vectorizer_config=Configure.Vectorizer.none()  # Manual vectors
        )
        print(f"Created collection '{self.collection_name}'")

    def extract_document(self, file_path: str) -> list[dict]:
        """Extract chunks from document."""
        extractor = EpubExtractor(file_path, config={
            "chunking_strategy": "rag",
            "min_chunk_words": 100,
            "max_chunk_words": 500,
        })

        extractor.load()
        extractor.parse()
        metadata = extractor.extract_metadata()

        chunks = []
        for chunk in extractor.chunks:
            chunk_dict = chunk.to_dict()
            chunk_dict["source_file"] = file_path
            chunk_dict["title"] = metadata.title
            chunk_dict["author"] = metadata.author
            chunks.append(chunk_dict)

        return chunks

    def add_chunks(self, chunks: list[dict]) -> None:
        """Embed and add chunks to Weaviate."""
        texts = [chunk["text"] for chunk in chunks]
        embeddings = self.encoder.encode(texts, show_progress_bar=True)

        collection = self.client.collections.get(self.collection_name)

        with collection.batch.dynamic() as batch:
            for chunk, embedding in zip(chunks, embeddings):
                properties = {
                    "text": chunk["text"],
                    "source_file": chunk.get("source_file", ""),
                    "title": chunk.get("title", ""),
                    "author": chunk.get("author", ""),
                    "hierarchy_path": chunk.get("heading_path", ""),
                    "word_count": chunk.get("word_count", 0),
                    "scripture_refs": ",".join(chunk.get("scripture_references", [])[:5]),
                }

                batch.add_object(
                    properties=properties,
                    vector=embedding.tolist(),
                    uuid=chunk["stable_id"]
                )

        print(f"Added {len(chunks)} chunks to Weaviate")

    def search(
        self,
        query_text: str,
        limit: int = 5,
        where_filter: dict = None
    ) -> None:
        """Vector similarity search."""
        query_embedding = self.encoder.encode([query_text])[0]

        collection = self.client.collections.get(self.collection_name)

        response = collection.query.near_vector(
            near_vector=query_embedding.tolist(),
            limit=limit,
            return_metadata=["distance"],
            filters=where_filter
        )

        print(f"\nQuery: {query_text}")
        print(f"Found {len(response.objects)} results\n")

        for i, obj in enumerate(response.objects):
            props = obj.properties
            print(f"Result {i+1} (distance: {obj.metadata.distance:.4f}):")
            print(f"  Source: {props['title']} - {props['hierarchy_path']}")
            print(f"  Text: {props['text'][:200]}...")
            if props.get('scripture_refs'):
                print(f"  Scripture: {props['scripture_refs']}")
            print()

    def hybrid_search(
        self,
        query_text: str,
        limit: int = 5,
        alpha: float = 0.7
    ) -> None:
        """Hybrid search (vector + BM25 keyword search)."""
        query_embedding = self.encoder.encode([query_text])[0]

        collection = self.client.collections.get(self.collection_name)

        response = collection.query.hybrid(
            query=query_text,
            vector=query_embedding.tolist(),
            alpha=alpha,  # 0 = pure BM25, 1 = pure vector
            limit=limit,
            return_metadata=["score"]
        )

        print(f"\nHybrid Query: {query_text} (alpha={alpha})")
        print(f"Found {len(response.objects)} results\n")

        for i, obj in enumerate(response.objects):
            props = obj.properties
            print(f"Result {i+1} (score: {obj.metadata.score:.4f}):")
            print(f"  Text: {props['text'][:200]}...")
            print()

    def close(self) -> None:
        """Close client connection."""
        self.client.close()


def main():
    pipeline = WeaviatePipeline(
        url="http://localhost:8080",
        collection_name="CatholicDocuments"
    )

    try:
        documents = [
            "corpus/catechism.epub",
            "corpus/prayer_book.epub",
        ]

        for doc_path in documents:
            print(f"Processing {doc_path}...")
            chunks = pipeline.extract_document(doc_path)
            pipeline.add_chunks(chunks)

        # Vector search
        pipeline.search("What is the Eucharist?", limit=5)

        # Hybrid search (vector + keyword)
        pipeline.hybrid_search("sacraments of initiation", limit=3, alpha=0.7)

        # Filtered search
        from weaviate.classes.query import Filter
        pipeline.search(
            "prayer",
            limit=3,
            where_filter=Filter.by_property("word_count").greater_than(200)
        )

    finally:
        pipeline.close()


if __name__ == "__main__":
    main()
```

### GraphQL Queries

Weaviate also supports GraphQL (alternative to Python client):

```graphql
{
  Get {
    Document(
      nearVector: {
        vector: [0.1, 0.2, ..., 0.384]
      }
      limit: 5
    ) {
      text
      title
      hierarchy_path
      _additional {
        distance
      }
    }
  }
}
```

## Embedding Options

All examples above use **Sentence Transformers** (local, free). Here are alternatives:

### OpenAI Embeddings

```bash
uv pip install openai
export OPENAI_API_KEY="your-key"
```

```python
from openai import OpenAI

class OpenAIEmbedder:
    def __init__(self, model: str = "text-embedding-3-small"):
        self.client = OpenAI()
        self.model = model

    def encode(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings via OpenAI API."""
        response = self.client.embeddings.create(
            model=self.model,
            input=texts
        )
        return [item.embedding for item in response.data]

# Use in pipeline
embedder = OpenAIEmbedder(model="text-embedding-3-small")  # 1536 dims
embeddings = embedder.encode(texts)
```

**Models**:

- `text-embedding-3-small`: 1536 dims, $0.02/1M tokens
- `text-embedding-3-large`: 3072 dims, $0.13/1M tokens
- `text-embedding-ada-002`: 1536 dims, $0.10/1M tokens (legacy)

### Cohere Embeddings

```bash
uv pip install cohere
export COHERE_API_KEY="your-key"
```

```python
import cohere

class CohereEmbedder:
    def __init__(self, model: str = "embed-english-v3.0"):
        self.client = cohere.Client()
        self.model = model

    def encode(self, texts: list[str], input_type: str = "search_document") -> list[list[float]]:
        """Generate embeddings via Cohere API."""
        response = self.client.embed(
            texts=texts,
            model=self.model,
            input_type=input_type  # "search_document" or "search_query"
        )
        return response.embeddings

embedder = CohereEmbedder(model="embed-english-v3.0")
doc_embeddings = embedder.encode(texts, input_type="search_document")
query_embedding = embedder.encode([query], input_type="search_query")[0]
```

**Models**:

- `embed-english-v3.0`: 1024 dims, best performance
- `embed-english-light-v3.0`: 384 dims, faster/cheaper
- `embed-multilingual-v3.0`: 1024 dims, 100+ languages

### HuggingFace Embeddings

```python
from sentence_transformers import SentenceTransformer

# General purpose (English)
model = SentenceTransformer("all-MiniLM-L6-v2")  # 384 dims, fast

# Higher quality
model = SentenceTransformer("all-mpnet-base-v2")  # 768 dims, slower

# Asymmetric (query vs passage optimized)
model = SentenceTransformer("msmarco-distilbert-base-v4")  # 768 dims

# Multilingual
model = SentenceTransformer("paraphrase-multilingual-mpnet-base-v2")  # 768 dims
```

## Performance Tips

### Batch Processing

Process documents in batches to avoid memory issues:

```python
from pathlib import Path
from tqdm import tqdm

def process_corpus(corpus_dir: Path, pipeline, batch_size: int = 10):
    """Process all documents in directory."""
    documents = list(corpus_dir.glob("*.epub")) + list(corpus_dir.glob("*.pdf"))

    for i in tqdm(range(0, len(documents), batch_size), desc="Batches"):
        batch = documents[i:i + batch_size]

        all_chunks = []
        for doc_path in batch:
            try:
                chunks = pipeline.extract_document(str(doc_path))
                all_chunks.extend(chunks)
            except Exception as e:
                print(f"Error processing {doc_path}: {e}")

        if all_chunks:
            pipeline.add_chunks(all_chunks)

        # Clear memory
        del all_chunks
```

### Token Rechunking

For optimal embedding performance, use the `token-rechunk` tool:

```bash
# Extract to word-based chunks
extract corpus/*.epub -r --output-dir extractions/

# Rechunk to token-optimized (256-400 tokens for retrieval)
mkdir token_chunks/
for file in extractions/*.json; do
    token-rechunk "$file" --mode retrieval \
        --output "token_chunks/$(basename $file .json).jsonl"
done

# Now embed the JSONL files
python embed_pipeline.py token_chunks/*.jsonl
```

This ensures consistent 256-400 token chunks regardless of original paragraph size.

### Embedding Caching

Cache embeddings to avoid re-encoding:

```python
import pickle
from pathlib import Path

class CachedEmbedder:
    def __init__(self, encoder, cache_file: str = "embeddings_cache.pkl"):
        self.encoder = encoder
        self.cache_file = Path(cache_file)
        self.cache = self._load_cache()

    def _load_cache(self) -> dict:
        if self.cache_file.exists():
            with open(self.cache_file, "rb") as f:
                return pickle.load(f)
        return {}

    def encode(self, texts: list[str]) -> list:
        """Encode with caching."""
        embeddings = []
        to_encode = []
        to_encode_indices = []

        for i, text in enumerate(texts):
            if text in self.cache:
                embeddings.append(self.cache[text])
            else:
                to_encode.append(text)
                to_encode_indices.append(i)
                embeddings.append(None)  # Placeholder

        # Encode uncached texts
        if to_encode:
            new_embeddings = self.encoder.encode(to_encode)
            for idx, embedding in zip(to_encode_indices, new_embeddings):
                embeddings[idx] = embedding
                self.cache[to_encode[idx]] = embedding

        self._save_cache()
        return embeddings

    def _save_cache(self) -> None:
        with open(self.cache_file, "wb") as f:
            pickle.dump(self.cache, f)
```

### Incremental Updates

Add new documents without re-processing everything:

```python
def add_new_documents(pipeline, new_docs: list[str]):
    """Add only new documents not already in DB."""
    existing_sources = set()

    # Query all existing source files
    # (Implementation varies by vector DB)

    for doc_path in new_docs:
        if doc_path not in existing_sources:
            print(f"Adding new document: {doc_path}")
            chunks = pipeline.extract_document(doc_path)
            pipeline.add_chunks(chunks)
        else:
            print(f"Skipping existing: {doc_path}")
```

## Comparison Table

| Feature | ChromaDB | LanceDB | Pinecone | Weaviate |
|---------|----------|---------|----------|----------|
| **Deployment** | Local/embedded | Local/embedded | Cloud | Cloud or self-hosted |
| **Setup complexity** | ⭐ Minimal | ⭐ Minimal | ⭐⭐ Requires API key | ⭐⭐⭐ Docker or cloud |
| **Scalability** | <1M vectors | <10M vectors | >100M vectors | >100M vectors |
| **Query speed** | Fast (local) | Very fast | Very fast | Fast |
| **Persistence** | Disk | Disk | Cloud | Disk or cloud |
| **Metadata filtering** | Basic | SQL-like | Rich filters | GraphQL queries |
| **Hybrid search** | No | Yes (FTS) | No | Yes (BM25) |
| **Cost** | Free | Free | Free tier + paid | Free (self-hosted) or cloud pricing |
| **Best for** | Prototyping | Medium datasets | Production scale | Advanced RAG |

## Summary

Choose your vector DB based on requirements:

- **Local prototyping**: ChromaDB (zero setup)
- **Embedded apps**: LanceDB (serverless)
- **Production scale**: Pinecone (managed service)
- **Advanced RAG**: Weaviate (hybrid search, multi-modal)

All four integrate seamlessly with the extraction library:

1. Extract documents with RAG chunking strategy
2. Optionally token-rechunk for optimal embedding sizes
3. Embed with Sentence Transformers, OpenAI, or Cohere
4. Store in your chosen vector DB
5. Query for semantic search and RAG

The extraction library's consistent output format (same schema across all document types) makes it easy to swap vector DBs or use multiple in parallel for different use cases.
