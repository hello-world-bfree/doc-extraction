# BaseExtractor API Reference

Base class for all document extractors. Defines the extraction interface and state machine.

## Module

`extraction.extractors.base`

## Class

```python
class BaseExtractor(ABC)
```

Abstract base class that all format-specific extractors must inherit from.

## Overview

`BaseExtractor` provides:

- **Unified interface**: `load()` → `parse()` → `extract_metadata()` → `get_output_data()`
- **State machine**: Ensures methods are called in correct order
- **Quality scoring**: Automatic quality analysis and routing
- **Chunking strategies**: Supports RAG and NLP chunking modes
- **Error handling**: Type-safe exceptions with clear error messages

## Constructor

```python
def __init__(
    self,
    source_path: str,
    config: Optional[BaseExtractorConfig] = None,
    analyzer: Optional[BaseAnalyzer] = None
)
```

### Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `source_path` | `str` | Required | Path to source document file |
| `config` | `BaseExtractorConfig` | `None` | Configuration dataclass (format-specific). If `None`, uses `BaseExtractorConfig()` |
| `analyzer` | `BaseAnalyzer` | `None` | Domain analyzer for metadata enrichment. If `None`, uses `GenericAnalyzer()` |

### Raises

- `ConfigError`: If `config` is not a `BaseExtractorConfig` instance

### Example

```python
from extraction.extractors import EpubExtractor
from extraction.extractors.configs import EpubExtractorConfig
from extraction.analyzers import CatholicAnalyzer

config = EpubExtractorConfig(
    chunking_strategy="rag",
    min_chunk_words=150
)

analyzer = CatholicAnalyzer()

extractor = EpubExtractor(
    source_path="prayer_primer.epub",
    config=config,
    analyzer=analyzer
)
```

## State Machine

Extractors follow a strict state progression:

```
CREATED → LOADED → PARSED → METADATA_READY → OUTPUT_READY
```

### States

| State | Description | Methods Available |
|-------|-------------|-------------------|
| `CREATED` | Initial state after construction | `load()` |
| `LOADED` | Document loaded, provenance created | `parse()`, `provenance` |
| `PARSED` | Chunks extracted, quality computed | `extract_metadata()`, `chunks`, `quality`, `quality_score`, `route` |
| `METADATA_READY` | Metadata enriched | `get_output_data()`, `metadata` |
| `OUTPUT_READY` | Final output generated | All properties |

### State Validation

Attempting to call methods or access properties out of order raises `MethodOrderError`:

```python
extractor = EpubExtractor("book.epub")

# ERROR: Must call load() first
extractor.parse()  # Raises MethodOrderError

# Correct order:
extractor.load()
extractor.parse()
extractor.extract_metadata()
output = extractor.get_output_data()
```

## Public Methods

### `load()`

Load the source document and create provenance.

```python
def load(self) -> None
```

**State transition**: `CREATED` → `LOADED`

**Raises**:

- `MethodOrderError`: If not in `CREATED` state
- `FileNotFoundError`: If document file does not exist
- `ParseError`: If document cannot be loaded

**Example**:

```python
extractor = EpubExtractor("book.epub")
extractor.load()  # Now in LOADED state
```

---

### `parse()`

Parse the document and extract chunks.

```python
def parse(self) -> None
```

**State transition**: `LOADED` → `PARSED`

**Side effects**:

- Populates `chunks` property
- Computes quality score and route
- Applies configured chunking strategy (RAG or NLP)
- Applies noise filtering (if enabled)

**Raises**:

- `MethodOrderError`: If not in `LOADED` state
- `ParseError`: If parsing fails

**Example**:

```python
extractor.load()
extractor.parse()  # Now in PARSED state

# Chunks are now available
print(f"Extracted {len(extractor.chunks)} chunks")
print(f"Quality: {extractor.quality_score} (route {extractor.route})")
```

---

### `extract_metadata()`

Extract and enrich document-level metadata.

```python
def extract_metadata(self) -> Metadata
```

**State transition**: `PARSED` → `METADATA_READY`

**Returns**: `Metadata` object with all fields populated

**Side effects**:

- Calls analyzer to enrich metadata with domain-specific fields
- Populates `metadata` property

**Raises**:

- `MethodOrderError`: If not in `PARSED` state

**Example**:

```python
extractor.load()
extractor.parse()
metadata = extractor.extract_metadata()

print(f"Title: {metadata.title}")
print(f"Author: {metadata.author}")
print(f"Document type: {metadata.document_type}")
print(f"Subjects: {metadata.subject}")
```

---

### `get_output_data()`

Get complete output data structure (metadata + chunks + extraction_info).

```python
def get_output_data(self) -> Dict[str, Any]
```

**State transition**: `METADATA_READY` → `OUTPUT_READY`

**Returns**: Dictionary with keys:

- `metadata`: Metadata dict (includes provenance and quality)
- `chunks`: List of chunk dicts
- `extraction_info`: Processing statistics

**Raises**:

- `MethodOrderError`: If not in `METADATA_READY` or `OUTPUT_READY` state

**Example**:

```python
extractor.load()
extractor.parse()
extractor.extract_metadata()
output = extractor.get_output_data()

# Write to JSON
import json
with open("output.json", "w") as f:
    json.dump(output, f, indent=2, ensure_ascii=False)
```

## Properties

### `chunks`

Get extracted chunks (available after `parse()`).

```python
@property
def chunks(self) -> List[Chunk]
```

**Available in states**: `PARSED`, `METADATA_READY`, `OUTPUT_READY`

**Raises**: `MethodOrderError` if accessed before `parse()`

**Example**:

```python
extractor.load()
extractor.parse()

for chunk in extractor.chunks:
    print(f"Chunk {chunk.paragraph_id}: {chunk.word_count} words")
```

---

### `metadata`

Get document metadata (available after `extract_metadata()`).

```python
@property
def metadata(self) -> Optional[Metadata]
```

**Available in states**: `METADATA_READY`, `OUTPUT_READY`

**Returns**: `Metadata` object or `None` if not yet extracted

**Example**:

```python
extractor.load()
extractor.parse()
extractor.extract_metadata()

print(f"Title: {extractor.metadata.title}")
print(f"Subjects: {extractor.metadata.subject}")
```

---

### `provenance`

Get provenance information (available after `load()`).

```python
@property
def provenance(self) -> Provenance
```

**Available in states**: `LOADED`, `PARSED`, `METADATA_READY`, `OUTPUT_READY`

**Raises**: `MethodOrderError` if accessed before `load()`

**Example**:

```python
extractor.load()

print(f"Document ID: {extractor.provenance.doc_id}")
print(f"Source file: {extractor.provenance.source_file}")
print(f"Content hash: {extractor.provenance.content_hash}")
```

---

### `quality`

Get quality metrics (available after `parse()`).

```python
@property
def quality(self) -> Quality
```

**Available in states**: `PARSED`, `METADATA_READY`, `OUTPUT_READY`

**Raises**: `MethodOrderError` if accessed before `parse()`

**Example**:

```python
extractor.load()
extractor.parse()

q = extractor.quality
print(f"Score: {q.score}")
print(f"Route: {q.route}")
print(f"Signals: {q.signals}")
```

---

### `quality_score`

Get quality score (0.0 - 1.0, available after `parse()`).

```python
@property
def quality_score(self) -> float
```

**Available in states**: `PARSED`, `METADATA_READY`, `OUTPUT_READY`

**Raises**: `MethodOrderError` if accessed before `parse()`

---

### `route`

Get quality route ("A", "B", or "C", available after `parse()`).

```python
@property
def route(self) -> str
```

**Available in states**: `PARSED`, `METADATA_READY`, `OUTPUT_READY`

**Raises**: `MethodOrderError` if accessed before `parse()`

**Quality Routes**:

- **A** (score ≥ 0.7): High quality, automatic processing
- **B** (0.4 ≤ score &lt; 0.7): Medium quality, review recommended
- **C** (score &lt; 0.4): Low quality, manual review required

---

### `state`

Get current extractor state.

```python
@property
def state(self) -> ExtractorState
```

**Available in**: All states

**Returns**: Current `ExtractorState` enum value

**Example**:

```python
print(f"Current state: {extractor.state.name}")
# Output: "CREATED", "LOADED", "PARSED", etc.
```

---

### `config`

Get extractor configuration.

```python
@property
def config(self) -> BaseExtractorConfig
```

**Available in**: All states

**Example**:

```python
print(f"Chunking strategy: {extractor.config.chunking_strategy}")
print(f"Noise filtering: {extractor.config.filter_noise}")
```

---

### `analyzer`

Get domain analyzer.

```python
@property
def analyzer(self) -> BaseAnalyzer
```

**Available in**: All states

## Protected Methods

These methods are implemented by subclasses (format-specific extractors).

### `_do_load()`

Implementation: Load the source document.

```python
@abstractmethod
def _do_load(self) -> None
```

**Responsibilities**:

- Load document into memory
- Create provenance using `_set_provenance()`
- Validate document structure

**Called by**: `load()` method

**Example implementation** (EPUB):

```python
def _do_load(self) -> None:
    self._book = epub.read_epub(self.source_path)
    src_bytes = open(self.source_path, "rb").read()
    self._set_provenance(PARSER_VERSION, MD_SCHEMA_VERSION, src_bytes)
```

---

### `_do_parse()`

Implementation: Parse document and extract chunks.

```python
@abstractmethod
def _do_parse(self) -> None
```

**Responsibilities**:

1. Extract raw paragraph chunks
2. Store in `self._add_raw_chunk(chunk)`
3. Call `self._compute_quality(full_text)`
4. Call `self._apply_chunking_strategy()` to finalize chunks

**Called by**: `parse()` method

**Example implementation** (simplified):

```python
def _do_parse(self) -> None:
    full_text_parts = []

    for page in self._pdf.pages:
        text = page.extract_text()
        paragraphs = text.split('\n\n')

        for para in paragraphs:
            chunk = Chunk(
                stable_id=stable_id(...),
                paragraph_id=para_id,
                text=clean_text(para),
                # ... other fields ...
            )
            self._add_raw_chunk(chunk)
            full_text_parts.append(para)

    full_text = " ".join(full_text_parts)
    self._compute_quality(full_text)
    self._apply_chunking_strategy()
```

---

### `_do_extract_metadata()`

Implementation: Extract base document metadata.

```python
@abstractmethod
def _do_extract_metadata(self) -> Metadata
```

**Responsibilities**:

- Extract format-specific metadata (title, author, etc.)
- Return `Metadata` object with base fields
- **Do not** perform domain enrichment (analyzer does this automatically)

**Called by**: `extract_metadata()` method

**Example implementation** (PDF):

```python
def _do_extract_metadata(self) -> Metadata:
    pdf_metadata = self._pdf.metadata or {}

    return Metadata(
        title=pdf_metadata.get("Title", "Untitled"),
        author=pdf_metadata.get("Author", "Unknown"),
        publisher=pdf_metadata.get("Producer", ""),
        language="en",
        pages=f"approximately {self._total_pages}",
        word_count=f"approximately {sum(c.word_count for c in self.chunks):,}"
    )
```

---

### `_compute_quality()`

Compute quality metrics from full document text.

```python
def _compute_quality(self, full_text: str) -> None
```

**Parameters**:

- `full_text`: Complete normalized text of document

**Side effects**:

- Computes quality signals (avg_para_len, heading_density, etc.)
- Computes quality score (0.0 - 1.0)
- Assigns quality route (A/B/C)
- Populates `quality` property

**Called by**: Subclass `_do_parse()` implementation

---

### `_apply_chunking_strategy()`

Apply configured chunking strategy to raw paragraph chunks.

```python
def _apply_chunking_strategy(self) -> None
```

**Behavior**:

- Reads raw chunks (stored via `_add_raw_chunk()`)
- Applies `config.chunking_strategy` (RAG or NLP)
- Applies noise filtering if `config.filter_noise=True`
- Populates `chunks` property with finalized chunks

**Called by**: Subclass `_do_parse()` implementation (after extracting all raw chunks)

---

### `_set_provenance()`

Create and store provenance information.

```python
def _set_provenance(
    self,
    parser_version: str,
    md_schema_version: str,
    source_bytes: bytes
) -> None
```

**Parameters**:

- `parser_version`: Version of the parser (e.g., "2.0.0-refactored")
- `md_schema_version`: Metadata schema version (e.g., "2025-09-08")
- `source_bytes`: Raw bytes of source document (for hashing)

**Called by**: Subclass `_do_load()` implementation

---

### `_add_raw_chunk()`

Add a raw paragraph chunk for strategy processing.

```python
def _add_raw_chunk(self, chunk: Dict[str, Any]) -> None
```

**Parameters**:

- `chunk`: Chunk dictionary or `Chunk` object

**Called by**: Subclass `_do_parse()` implementation (for each paragraph)

## Complete Usage Example

```python
from extraction.extractors import EpubExtractor
from extraction.extractors.configs import EpubExtractorConfig
from extraction.analyzers import CatholicAnalyzer
import json

# 1. Configure extractor
config = EpubExtractorConfig(
    chunking_strategy="rag",
    min_chunk_words=150,
    max_chunk_words=400,
    filter_tiny_chunks="standard",
    filter_noise=True
)

analyzer = CatholicAnalyzer()

# 2. Create extractor
extractor = EpubExtractor(
    source_path="catechism.epub",
    config=config,
    analyzer=analyzer
)

# 3. Process document (state machine)
extractor.load()              # CREATED → LOADED
extractor.parse()             # LOADED → PARSED
extractor.extract_metadata()  # PARSED → METADATA_READY

# 4. Access results
print(f"Title: {extractor.metadata.title}")
print(f"Chunks: {len(extractor.chunks)}")
print(f"Quality: {extractor.quality_score} (route {extractor.route})")

# 5. Get output
output = extractor.get_output_data()  # METADATA_READY → OUTPUT_READY

# 6. Write to file
with open("catechism.json", "w") as f:
    json.dump(output, f, indent=2, ensure_ascii=False)
```

## Error Handling

### Common Exceptions

| Exception | When Raised | Example |
|-----------|-------------|---------|
| `MethodOrderError` | Method called out of order | Calling `parse()` before `load()` |
| `FileNotFoundError` | Source file not found | Non-existent path passed to constructor |
| `ParseError` | Document parsing fails | Corrupted EPUB, invalid PDF |
| `ConfigError` | Invalid configuration | Wrong config type passed to constructor |

### Example

```python
from extraction.exceptions import MethodOrderError, ParseError

try:
    extractor = EpubExtractor("book.epub")
    extractor.load()
    extractor.parse()
    extractor.extract_metadata()
    output = extractor.get_output_data()

except FileNotFoundError as e:
    print(f"File not found: {e.filepath}")

except ParseError as e:
    print(f"Parse error in {e.filepath}: {e.message}")

except MethodOrderError as e:
    print(f"Method order error: {e.message}")
```

## Subclassing BaseExtractor

To implement a new format extractor:

1. **Inherit from `BaseExtractor`**:

```python
from extraction.extractors.base import BaseExtractor
from extraction.extractors.configs import BaseExtractorConfig

class MyFormatExtractor(BaseExtractor):
    def __init__(self, source_path: str, config=None, analyzer=None):
        super().__init__(source_path, config or MyFormatConfig(), analyzer)
```

2. **Implement abstract methods**:

```python
def _do_load(self) -> None:
    # Load document
    # Create provenance
    pass

def _do_parse(self) -> None:
    # Extract paragraphs
    # Call _add_raw_chunk() for each
    # Call _compute_quality()
    # Call _apply_chunking_strategy()
    pass

def _do_extract_metadata(self) -> Metadata:
    # Extract title, author, etc.
    return Metadata(...)
```

3. **Register in CLI** (`src/extraction/cli/extract.py`):

```python
def detect_format(file_path: str) -> str:
    ext = os.path.splitext(file_path)[1].lower()
    format_map = {
        '.epub': 'epub',
        '.myformat': 'myformat',  # Add new format
    }
    return format_map.get(ext, 'unknown')
```

## See Also

- [Configuration Reference](../configuration.md) - Config dataclasses
- [Output Schema Reference](../output-schema.md) - Understanding output structure
- [EpubExtractor API](epub-extractor.md) - EPUB-specific implementation
- [PdfExtractor API](pdf-extractor.md) - PDF-specific implementation
- See existing extractors (`src/extraction/extractors/`) for implementation examples
