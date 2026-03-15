# JsonExtractor API Reference

JSON-specific extractor for importing or re-chunking existing extraction output.

## Module

`extraction.extractors.json`

## Class

```python
class JsonExtractor(BaseExtractor)
```

Imports JSON files containing previously extracted document data, with optional re-chunking support.

## Overview

`JsonExtractor` provides:

- **Import mode**: Import existing extraction output (metadata + chunks)
- **Re-chunk mode**: Re-apply chunking strategies to existing chunks
- **Schema validation**: Validates JSON structure matches expected format
- **Metadata preservation**: Preserves original provenance and quality data
- **Chunking strategies**: Can apply RAG or NLP strategies during import

## Constructor

```python
def __init__(
    self,
    source_path: str,
    config: Optional[JsonExtractorConfig] = None,
    analyzer: Optional[BaseAnalyzer] = None
)
```

### Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `source_path` | `str` | Required | Path to `.json` file |
| `config` | `JsonExtractorConfig` | `None` | JSON-specific configuration. If `None`, uses `JsonExtractorConfig()` |
| `analyzer` | `BaseAnalyzer` | `None` | Domain analyzer. If `None`, uses `GenericAnalyzer()` |

### Example

```python
from extraction.extractors import JsonExtractor
from extraction.extractors.configs import JsonExtractorConfig
from extraction.analyzers import GenericAnalyzer

config = JsonExtractorConfig(
    mode="import",
    import_chunks=True,
    import_metadata=True
)

extractor = JsonExtractor(
    source_path="document.json",
    config=config,
    analyzer=GenericAnalyzer()
)
```

## JSON-Specific Configuration

See [JsonExtractorConfig](../configuration.md#jsonextractorconfig) for full reference.

### Key Options

| Option | Default | Description |
|--------|---------|-------------|
| `mode` | `"import"` | Operation mode: `"import"` or `"rechunk"` |
| `import_chunks` | `True` | Import chunks from JSON |
| `import_metadata` | `True` | Import metadata from JSON |

## Public Methods

Inherits all methods from [BaseExtractor](base-extractor.md):

- `load()` - Load and parse JSON file
- `parse()` - Import chunks (and optionally re-chunk)
- `extract_metadata()` - Import metadata + optional domain enrichment
- `get_output_data()` - Get complete output structure

## Import Mode

Default mode for importing existing extraction output.

### Usage

```python
config = JsonExtractorConfig(
    mode="import",
    import_chunks=True,
    import_metadata=True
)

extractor = JsonExtractor("document.json", config=config)
extractor.load()
extractor.parse()
metadata = extractor.extract_metadata()
output = extractor.get_output_data()
```

### Behavior

1. **Load JSON**: Parse JSON file and validate structure
2. **Import chunks**: Copy chunks from JSON (preserving all fields)
3. **Import metadata**: Copy metadata from JSON (preserving provenance)
4. **No re-chunking**: Chunks are imported as-is
5. **No re-analysis**: Metadata is preserved (analyzer not applied)

### What Gets Imported

| Field | Source | Destination |
|-------|--------|-------------|
| `chunks` | JSON `chunks` array | `extractor.chunks` |
| `metadata` | JSON `metadata` object | `extractor.metadata` |
| `provenance` | JSON `metadata.provenance` | Preserved |
| `quality` | JSON `metadata.quality` | Preserved |

## Re-chunk Mode

Advanced mode for applying new chunking strategies to existing chunks.

### Usage

```python
config = JsonExtractorConfig(
    mode="rechunk",
    chunking_strategy="rag",
    min_chunk_words=200,
    max_chunk_words=800
)

extractor = JsonExtractor("document.json", config=config)
extractor.load()
extractor.parse()  # Re-chunks using new strategy
output = extractor.get_output_data()
```

### Behavior

1. **Load JSON**: Parse JSON file and validate structure
2. **Import chunks**: Load existing chunks as "raw" chunks
3. **Re-apply strategy**: Apply new chunking strategy (RAG or NLP)
4. **Update counts**: Recalculate word counts and chunk counts
5. **Preserve metadata**: Original metadata preserved (provenance updated)

### Use Cases

- Convert NLP chunks (paragraph-level) to RAG chunks (merged)
- Adjust chunk size thresholds (min/max words)
- Re-process legacy extraction output
- Normalize chunking across multiple documents

## Expected JSON Schema

JSON files must match the extraction library output format.

### Required Structure

```json
{
  "metadata": {
    "title": "...",
    "author": "...",
    "provenance": {
      "doc_id": "...",
      "source_file": "...",
      "parser_version": "...",
      "md_schema_version": "...",
      "ingestion_ts": "...",
      "content_hash": "..."
    },
    "quality": {
      "score": 0.85,
      "route": "A",
      "signals": {}
    }
  },
  "chunks": [
    {
      "stable_id": "...",
      "paragraph_id": 1,
      "text": "...",
      "hierarchy": {},
      "word_count": 100,
      ...
    }
  ]
}
```

### Validation

The JSON extractor validates:

1. **Top-level keys**: `metadata` and `chunks` must exist
2. **Metadata fields**: `title`, `provenance`, `quality` must exist
3. **Chunks array**: Must be an array of chunk objects
4. **Chunk fields**: Each chunk must have `text`, `paragraph_id`, `hierarchy`

### Invalid JSON Handling

If JSON is invalid:

```python
from extraction.exceptions import ParseError

try:
    extractor = JsonExtractor("invalid.json")
    extractor.load()
except ParseError as e:
    print(f"Invalid JSON: {e.message}")
```

## Metadata Handling

### Import Metadata (Default)

```python
config = JsonExtractorConfig(import_metadata=True)
```

**Behavior**: Metadata copied from JSON, preserving:
- Original title, author, description
- Original provenance (doc_id, source_file, content_hash)
- Original quality score and route

### Skip Metadata Import

```python
config = JsonExtractorConfig(import_metadata=False)
```

**Behavior**: Metadata not imported, analyzer creates new metadata:
- Analyzer infers document_type, subjects, themes
- New provenance created (JSON file as source)
- Quality recalculated from imported chunks

## Chunk Handling

### Import Chunks (Default)

```python
config = JsonExtractorConfig(import_chunks=True)
```

**Behavior**: All chunks imported preserving:
- Text content
- Hierarchy levels
- Word counts
- Scripture/cross-references
- Sentences
- All custom fields

### Skip Chunks Import

```python
config = JsonExtractorConfig(import_chunks=False)
```

**Behavior**: Chunks not imported, empty output:
- Metadata imported (if `import_metadata=True`)
- No chunks in output
- Useful for metadata-only extraction

## Complete Example

```python
from extraction.extractors import JsonExtractor
from extraction.extractors.configs import JsonExtractorConfig
import json

# Import existing extraction
config = JsonExtractorConfig(
    mode="import",
    import_chunks=True,
    import_metadata=True
)

extractor = JsonExtractor(
    source_path="original_extraction.json",
    config=config
)

# Process
extractor.load()
extractor.parse()

print(f"Imported chunks: {len(extractor.chunks)}")
print(f"Quality: {extractor.quality_score} (route {extractor.route})")

metadata = extractor.extract_metadata()
print(f"Title: {metadata.title}")
print(f"Original source: {metadata.provenance['source_file']}")

# Get output
output = extractor.get_output_data()

# Verify provenance preserved
original_provenance = extractor._JsonExtractor__original_provenance
print(f"Original doc_id: {original_provenance['doc_id']}")
print(f"Original parser: {original_provenance['parser_version']}")

# Write to new file
with open("re_imported.json", "w") as f:
    json.dump(output, f, indent=2, ensure_ascii=False)
```

## Re-chunking Example

```python
from extraction.extractors import JsonExtractor
from extraction.extractors.configs import JsonExtractorConfig

# Re-chunk with different strategy
config = JsonExtractorConfig(
    mode="rechunk",
    chunking_strategy="rag",
    min_chunk_words=200,
    max_chunk_words=800,
    import_metadata=True
)

extractor = JsonExtractor("nlp_chunks.json", config=config)
extractor.load()

# Original chunks (paragraph-level)
original_count = len(extractor._JsonExtractor__imported_chunks)
print(f"Original chunks: {original_count}")

# Re-chunk
extractor.parse()

# New chunks (merged for RAG)
new_count = len(extractor.chunks)
print(f"Re-chunked: {new_count}")
print(f"Reduction: {(original_count - new_count) / original_count * 100:.1f}%")

metadata = extractor.extract_metadata()
output = extractor.get_output_data()

# Save re-chunked output
with open("rag_chunks.json", "w") as f:
    json.dump(output, f, indent=2, ensure_ascii=False)
```

## Error Handling

### JSON-Specific Errors

| Error | When Raised | Example |
|-------|-------------|---------|
| `FileNotFoundError` | JSON file not found | Non-existent path |
| `ParseError` | Invalid JSON syntax | Malformed JSON |
| `ParseError` | Invalid schema | Missing required fields |

### Example

```python
from extraction.exceptions import ParseError, FileNotFoundError

try:
    extractor = JsonExtractor("document.json")
    extractor.load()
    extractor.parse()

except FileNotFoundError as e:
    print(f"File not found: {e.filepath}")

except ParseError as e:
    print(f"JSON parsing failed: {e.message}")
    print(f"Details: {e.details}")
```

## Limitations

### Current Limitations

1. **Schema validation**: Limited validation (doesn't check all chunk fields)
2. **No format conversion**: Only works with extraction library JSON format
3. **No merging**: Cannot merge multiple JSON files
4. **No filtering**: Cannot filter chunks during import

### Future Enhancements

- Support for other JSON schemas (Haystack, LangChain, etc.)
- Chunk filtering during import
- Multi-file merging
- Schema migration tools

## Use Cases

### Use Case 1: Archive Migration

Re-import old extraction outputs to new schema version:

```python
# Import old v1.0 extraction
extractor = JsonExtractor("old_extraction_v1.json")
extractor.load()
extractor.parse()

# Export with new v2.0 schema
output = extractor.get_output_data()
with open("new_extraction_v2.json", "w") as f:
    json.dump(output, f, indent=2)
```

### Use Case 2: Chunking Strategy Comparison

Compare RAG vs NLP chunking on same document:

```python
# Original NLP extraction (paragraph-level)
nlp_extractor = JsonExtractor("document_nlp.json")
nlp_extractor.load()
nlp_extractor.parse()
nlp_count = len(nlp_extractor.chunks)

# Re-chunk as RAG (merged paragraphs)
config = JsonExtractorConfig(
    mode="rechunk",
    chunking_strategy="rag"
)
rag_extractor = JsonExtractor("document_nlp.json", config=config)
rag_extractor.load()
rag_extractor.parse()
rag_count = len(rag_extractor.chunks)

print(f"NLP chunks: {nlp_count}")
print(f"RAG chunks: {rag_count}")
print(f"Reduction: {(nlp_count - rag_count) / nlp_count * 100:.1f}%")
```

### Use Case 3: Metadata Update

Update analyzer without re-extracting:

```python
from extraction.analyzers import CatholicAnalyzer

# Import with Catholic analyzer
extractor = JsonExtractor(
    "generic_extraction.json",
    analyzer=CatholicAnalyzer()
)
extractor.load()
extractor.parse()
metadata = extractor.extract_metadata()

# Now has Catholic-specific fields
print(f"Document type: {metadata.document_type}")
print(f"Subjects: {metadata.subject}")
```

## See Also

- [BaseExtractor API](base-extractor.md) - Parent class reference
- [Configuration Reference](../configuration.md#jsonextractorconfig) - Full config options
- [Output Schema Reference](../output-schema.md) - Understanding JSON format
- [Chunking Strategies How-To](../../how-to/chunking-strategy.md) - RAG vs NLP
