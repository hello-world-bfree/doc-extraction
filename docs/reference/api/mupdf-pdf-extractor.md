# MuPdfPdfExtractor API Reference

High-performance PDF text extraction using a native Zig/MuPDF shared library via ctypes. Provides per-span font metadata (sizes, bold/italic/mono flags) enabling statistical heading detection and multi-level hierarchy.

## Module

`extraction.extractors.pdf_mupdf`

## Class

```python
class MuPdfPdfExtractor(BaseExtractor)
```

Extracts text from PDF files using the native `libde_mupdf` shared library. Font size statistics across the entire document drive automatic heading detection, producing a full multi-level hierarchy (up to 6 levels).

- **Parser version**: `3.0.0-mupdf`
- **Native dependency**: `libde_mupdf` shared library (Zig/MuPDF)
- **Config**: `MuPdfPdfExtractorConfig`

## When It's Used

The CLI auto-selects `MuPdfPdfExtractor` when the native library is available (`NATIVE_AVAILABLE = True`). When the library is not found, extraction falls back to [PdfExtractor](pdf-extractor.md) (pdfplumber).

You can also use it directly via the Python API:

```python
from extraction.extractors.pdf_mupdf import MuPdfPdfExtractor, NATIVE_AVAILABLE

if NATIVE_AVAILABLE:
    extractor = MuPdfPdfExtractor("document.pdf")
```

## Constructor

```python
def __init__(
    self,
    source_path: str,
    config: Optional[MuPdfPdfExtractorConfig] = None,
    analyzer: Optional[BaseAnalyzer] = None,
)
```

### Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `source_path` | `str` | Required | Path to `.pdf` file |
| `config` | `MuPdfPdfExtractorConfig` | `None` | MuPDF-specific configuration. If `None`, uses `MuPdfPdfExtractorConfig()` |
| `analyzer` | `BaseAnalyzer` | `None` | Domain analyzer. If `None`, uses `GenericAnalyzer()` |

### Raises

- `DependencyError`: If the native `libde_mupdf` library is not available

### Example

```python
from extraction.extractors.pdf_mupdf import MuPdfPdfExtractor
from extraction.extractors.configs import MuPdfPdfExtractorConfig
from extraction.analyzers import GenericAnalyzer

config = MuPdfPdfExtractorConfig(
    heading_font_threshold=1.2,
    min_paragraph_words=5,
    max_memory_mb=1024,
)

extractor = MuPdfPdfExtractor(
    source_path="document.pdf",
    config=config,
    analyzer=GenericAnalyzer(),
)
```

## Font-Based Heading Detection

`MuPdfPdfExtractor` uses a statistical algorithm to identify headings from raw font metrics. No heuristics based on capitalization or formatting are needed.

### Algorithm

1. **Collect font stats** (`_collect_font_stats`): Scans every page, recording font size weighted by character count (`size_by_chars`) and by span count keyed on `(size, is_bold, is_mono)` (`size_by_spans`).

2. **Compute modal font size** (`_compute_modal_font_size`): The most common font size by character count is the body text size. Falls back to `12.0` if no spans are found.

3. **Rank heading sizes** (`_rank_heading_sizes`): Font sizes above `body_size * heading_font_threshold` are candidates. Bold text slightly above body size also qualifies. Monospaced fonts are excluded. Candidates with very low occurrence (below `max(5, top_count // 10)`) are pruned. Remaining sizes are sorted largest-first and assigned heading levels 1 through 6.

4. **Classify blocks during parsing**: Each text block's dominant font size is checked against the ranked heading sizes. A block is classified as a heading when:
    - Its font size appears in the heading rank map
    - It contains fewer than 15 words
    - It is not monospaced
    - It is bold or its font size is >= 1.5x body size

### Heading Hierarchy

Detected headings update the hierarchy at their assigned level and clear all deeper levels:

```
Page 1:
  "PART ONE" (24pt)       → level_1 = "PART ONE"
  "Chapter 1" (18pt)      → level_2 = "Chapter 1"
  "First paragraph..."    → inherits level_1 + level_2

Page 2:
  "Chapter 2" (18pt)      → level_2 = "Chapter 2", clears level_3-6
  "Section A" (14pt)      → level_3 = "Section A"
  "Body text..."          → inherits level_1 + level_2 + level_3
```

PDF outline entries (bookmarks) are also incorporated into the hierarchy on the pages where they appear.

## Configuration

See [MuPdfPdfExtractorConfig](../configuration.md#mupdfpdfextractorconfig) for full reference.

### Key Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `heading_font_threshold` | `float` | `1.2` | Multiplier above body font size to detect headings (1.0-3.0) |
| `min_paragraph_words` | `int` | `5` | Minimum words to consider text as a paragraph |
| `max_memory_mb` | `int` | `512` | Maximum memory for MuPDF context in MB (0 = no limit) |
| `use_ocr` | `bool` | `False` | Enable OCR for image-based PDFs |
| `ocr_lang` | `str` | `"eng"` | OCR language code |

### Threshold Tuning

```python
config = MuPdfPdfExtractorConfig(heading_font_threshold=1.1)

config = MuPdfPdfExtractorConfig(heading_font_threshold=1.2)

config = MuPdfPdfExtractorConfig(heading_font_threshold=1.5)
```

!!! tip
    Lower thresholds detect more headings (including subtitles and sub-sections). Higher thresholds restrict detection to only the most prominent sizes.

## Public Methods

Inherits all methods from [BaseExtractor](base-extractor.md):

- `load()` - Load PDF, compute content hash, create provenance
- `parse()` - Extract spans via native library, detect headings, create chunks
- `extract_metadata()` - Extract PDF title/author metadata + domain enrichment
- `get_output_data()` - Get complete output structure

## Metadata Extraction

PDF metadata is read from the native library using `MuPdfDocument.get_metadata()`.

| PDF Key | Mapped To | Fallback |
|---------|-----------|----------|
| `info:Title` | `metadata.title` | Filename (without extension) |
| `info:Author` | `metadata.author` | `"Unknown"` |

```python
extractor.load()
extractor.parse()
metadata = extractor.extract_metadata()

print(f"Title: {metadata.title}")
print(f"Author: {metadata.author}")
print(f"Pages: {metadata.pages}")
print(f"Word count: {metadata.word_count}")
```

## Native Library

The native library is a Zig shared library wrapping the MuPDF C API for high-performance text extraction with font metadata.

### Architecture

- **Source**: `cores/` directory (Zig)
- **ABI version**: `1` (checked at load time via `de_abi_version()`)
- **Library location**: `src/extraction/_native/lib/libde_mupdf.dylib` (macOS), `.so` (Linux), `.dll` (Windows)
- **Python binding**: `src/extraction/_native/mupdf/` (ctypes)

### Build

```bash
cd cores
zig build
```

!!! note
    Requires Zig master branch (pre-0.16.0) and MuPDF installed at `/opt/homebrew/opt/mupdf` (Homebrew on macOS).

### ABI Versioning

The loader (`_loader.py`) calls `de_abi_version()` on the shared library and compares it against the expected version. A mismatch raises `LibraryLoadError`, preventing silent ABI incompatibility.

## SpanData

Each text span extracted from a PDF page is represented as a frozen dataclass:

```python
@dataclass(frozen=True, slots=True)
class SpanData:
    bbox: tuple[float, float, float, float]
    font_name: str
    font_size: float
    is_bold: bool
    is_italic: bool
    is_mono: bool
    color: int
    block_idx: int
    line_idx: int
    text: str
```

| Field | Type | Description |
|-------|------|-------------|
| `bbox` | `tuple[float, float, float, float]` | Bounding box `(x0, y0, x1, y1)` in page coordinates |
| `font_name` | `str` | Font family name |
| `font_size` | `float` | Font size in points |
| `is_bold` | `bool` | Bold flag (bit 0 of font flags) |
| `is_italic` | `bool` | Italic flag (bit 1 of font flags) |
| `is_mono` | `bool` | Monospaced flag (bit 2 of font flags) |
| `color` | `int` | Text color as integer |
| `block_idx` | `int` | Block index on the page |
| `line_idx` | `int` | Line index within the block |
| `text` | `str` | Span text content |

## MuPdfDocument

Context-managed wrapper around the native MuPDF document handle.

```python
with MuPdfDocument("document.pdf", max_memory_mb=512) as doc:
    print(doc.page_count)

    with doc.load_page(0) as page:
        spans = page.get_all_spans()

    outline = doc.get_outline()

    title = doc.get_metadata("info:Title")
```

### Methods

| Method | Return Type | Description |
|--------|-------------|-------------|
| `open()` | `None` | Initialize MuPDF context and open document |
| `load_page(page_num)` | `MuPdfPage` | Load a page (context manager) |
| `get_metadata(key)` | `str \| None` | Read a metadata key (e.g., `"info:Title"`) |
| `get_outline()` | `list[OutlineEntry]` | Get document outline (bookmarks) |
| `close()` | `None` | Release all native handles |

### Properties

| Property | Type | Description |
|----------|------|-------------|
| `page_count` | `int` | Total number of pages |

## Comparison with PdfExtractor

| Feature | MuPdfPdfExtractor | PdfExtractor |
|---------|-------------------|--------------|
| Backend | Zig/MuPDF (ctypes) | pdfplumber |
| Heading detection | Font statistics (multi-level) | Heuristic (capitalization, single-level) |
| Font metadata | Full span data (size, bold, italic, mono, bbox) | Basic |
| Hierarchy depth | Up to 6 levels | `level_1` only |
| Memory control | Configurable via `max_memory_mb` | N/A |
| OCR support | Via config flag | Via config flag |
| Install requirement | Zig build + MuPDF | `uv pip install pdfplumber` |
| Outline/bookmarks | Extracted and merged into hierarchy | Not used |

## Complete Example

```python
from extraction.extractors.pdf_mupdf import MuPdfPdfExtractor
from extraction.extractors.configs import MuPdfPdfExtractorConfig
from extraction.analyzers import GenericAnalyzer
import json

config = MuPdfPdfExtractorConfig(
    chunking_strategy="rag",
    min_chunk_words=100,
    max_chunk_words=500,
    heading_font_threshold=1.2,
    min_paragraph_words=5,
    max_memory_mb=1024,
    filter_noise=True,
)

extractor = MuPdfPdfExtractor(
    source_path="research_paper.pdf",
    config=config,
    analyzer=GenericAnalyzer(),
)

extractor.load()
extractor.parse()
print(f"Chunks: {len(extractor.chunks)}")
print(f"Quality: {extractor.quality_score} (route {extractor.route})")

metadata = extractor.extract_metadata()
print(f"Title: {metadata.title}")
print(f"Author: {metadata.author}")
print(f"Pages: {metadata.pages}")

output = extractor.get_output_data()

with open("research_paper.json", "w") as f:
    json.dump(output, f, indent=2, ensure_ascii=False)

for chunk in extractor.chunks[:5]:
    heading_path = " / ".join(
        v for v in chunk.hierarchy.values() if v
    )
    print(f"Chunk {chunk.paragraph_id}: {heading_path}")
    print(f"  Page: {chunk.chapter_href}")
    print(f"  Words: {chunk.word_count}")
    print(f"  Text: {chunk.text[:100]}...")
    print()
```

## Error Handling

| Error | When Raised | Cause |
|-------|-------------|-------|
| `DependencyError` | Constructor | Native `libde_mupdf` library not found |
| `FileNotFoundError` | `load()` | PDF file does not exist |
| `RuntimeError` | `parse()` / `extract_metadata()` | Native library call fails (corrupt PDF, memory) |

```python
from extraction.exceptions import DependencyError, FileNotFoundError

try:
    extractor = MuPdfPdfExtractor("document.pdf")
    extractor.load()
    extractor.parse()

except DependencyError as e:
    print(f"Missing dependency: {e.dependency}")
    print(f"Install with: {e.install_command}")

except FileNotFoundError as e:
    print(f"File not found: {e}")
```

## See Also

- [PdfExtractor API](pdf-extractor.md) - pdfplumber-based fallback extractor
- [BaseExtractor API](base-extractor.md) - Parent class reference
- [Configuration Reference](../configuration.md#mupdfpdfextractorconfig) - Full config options
- [Native PDF Parser Architecture](../../explanation/native-pdf-parser.md) - Zig/MuPDF design details
- [Output Schema Reference](../output-schema.md) - Understanding chunk output
