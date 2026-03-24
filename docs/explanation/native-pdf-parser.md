# Native PDF Parser

**Understanding the Zig/MuPDF native layer for high-fidelity PDF extraction**

The extraction library includes a high-performance PDF parsing layer built with Zig and MuPDF, providing font-level metadata that enables statistical heading detection and multi-level hierarchy extraction. This page explains its architecture, the font statistics algorithm, and how it integrates with the Python extraction pipeline.

## Why a Native Parser?

The pure-Python pdfplumber backend (`PdfExtractor`) provides basic text extraction but has limited access to font metadata. This makes heading detection unreliable -- it must rely on heuristic font-size thresholds that don't adapt to individual documents.

The native parser addresses four problems:

- **Font statistics**: MuPDF provides per-span font data (name, size, bold/italic/mono flags) enabling statistical analysis of document typography
- **Heading accuracy**: A statistical approach (modal font size, heading level ranking) produces better hierarchy than fixed thresholds
- **Performance**: Native code is significantly faster for large documents with high span counts
- **Outline integration**: Direct access to PDF outline (table of contents) entries with page-level mapping

## Architecture

The native parser spans three layers: Zig shared library, Python ctypes bindings, and the extractor that uses them.

```
┌─────────────────────────────────────────┐
│  Python Layer                           │
│  ┌──────────────────┐                   │
│  │ MuPdfPdfExtractor│ (extractors/)     │
│  └────────┬─────────┘                   │
│           │                             │
│  ┌────────▼─────────┐                   │
│  │ MuPdfDocument     │ (_native/mupdf/) │
│  │ MuPdfPage         │                  │
│  │ SpanData          │                  │
│  └────────┬─────────┘                   │
│           │ ctypes                      │
├───────────┼─────────────────────────────┤
│  Native Layer                           │
│  ┌────────▼─────────┐                   │
│  │ libde_mupdf.dylib│ (cores/)         │
│  │ (Zig + shim.c)   │                  │
│  └────────┬─────────┘                   │
│           │                             │
│  ┌────────▼─────────┐                   │
│  │ MuPDF C Library   │ (/opt/homebrew/) │
│  └──────────────────┘                   │
└─────────────────────────────────────────┘
```

### Zig Shared Library (`cores/`)

The `cores/` directory contains a Zig project that builds `libde_mupdf.dylib`. The Zig code wraps MuPDF's C API and exports a flat C ABI for Python to consume via ctypes.

Key source modules:

| Module | Purpose |
|--------|---------|
| `root.zig` | Exported C ABI functions (`de_init`, `de_open_document`, `de_get_all_spans`, etc.) |
| `context.zig` | MuPDF context lifecycle with optional memory limits |
| `document.zig` | Document open/close, page count, metadata access |
| `page.zig` | Page loading and dimensions |
| `stext.zig` | Structured text extraction -- spans with font metadata |
| `outline.zig` | PDF outline (table of contents) extraction |
| `shim.c` | C shim for MuPDF macros that Zig cannot call directly |

A C shim file (`shim.c`) bridges MuPDF macros that Zig's `@cImport` cannot handle. The build links against MuPDF's static library at `/opt/homebrew/opt/mupdf`.

### Python Bindings (`_native/`)

The Python side has three layers of its own:

**`_loader.py`** -- Finds the `.dylib`/`.so`/`.dll` in `_native/lib/`, loads it with `ctypes.CDLL`, and validates the ABI version.

**`_bindings.py`** -- Declares ctypes prototypes for every exported function (argument types and return types). Also validates struct sizes at load time by comparing `ctypes.sizeof(DeTextSpan)` against `de_sizeof_span()` from the Zig side.

**`_types.py`** -- Defines ctypes `Structure` subclasses that mirror the Zig struct layouts:

| Struct | Fields |
|--------|--------|
| `DeTextSpan` | bbox, font_name (128 bytes), font_size, font_flags (bold/italic/mono as bitfield), color, block_idx, line_idx, text_ptr, text_len |
| `DeTextBlock` | bbox, block_type, line_count |
| `DeOutlineEntry` | level, title (512 bytes), page_num |
| `DeImageInfo` | bbox, width, height, image_type |

**`mupdf/__init__.py`** -- High-level Python wrappers (`MuPdfDocument`, `MuPdfPage`, `SpanData`) that provide context manager support and convert raw ctypes data into frozen dataclasses.

## ABI Versioning

The native library uses a two-level safety mechanism to prevent crashes from incompatible library versions.

### Version Check

The Zig library exports `de_abi_version()` returning a `u32` (currently `1`). Python's `_loader.py` checks this at load time against the expected version constant `ABI_VERSION = 1`. A mismatch raises `LibraryLoadError`:

```
ABI version mismatch: library=2, expected=1
```

Version bumps are required when changing function signatures, struct layouts, or adding/removing exported functions.

### Struct Size Validation

Even within the same ABI version, struct layout mismatches can cause memory corruption. The Zig library exports `de_sizeof_span()`, `de_sizeof_block()`, `de_sizeof_outline_entry()`, and `de_sizeof_image_info()`. At load time, `_bindings.py` compares these against `ctypes.sizeof()` for each Python struct:

```
Struct size mismatch for DeTextSpan: Python=168, Zig=172.
Rebuild the native library or regenerate _types.py.
```

This catches padding and alignment differences between the Zig and Python struct definitions.

## Font Statistics Algorithm

The heading detection pipeline in `MuPdfPdfExtractor` uses document-wide font statistics rather than fixed thresholds. This adapts to each document's typography automatically.

### Step 1: Collect Font Stats

`_collect_font_stats` scans every page and every span in the document, building two counters:

- **`size_by_chars`**: Maps rounded font size to total character count. This captures how much text exists at each size.
- **`size_by_spans`**: Maps `(size, is_bold, is_mono)` tuples to span count. This captures how many distinct text runs use each style.

### Step 2: Compute Modal Font Size

`_compute_modal_font_size` finds the font size with the most characters. This is the body text size -- the document's "normal" font. For example, if 80% of characters are 10pt, the modal size is `10.0`.

### Step 3: Rank Heading Sizes

`_rank_heading_sizes` identifies which font sizes represent headings:

1. Any font size `>= body_size * heading_font_threshold` (default 1.2x) qualifies as a heading candidate
2. Bold text slightly larger than body size also qualifies
3. Monospaced text is excluded (likely code, not headings)
4. Sizes with too few occurrences (< 5 or < 10% of the most common heading size) are pruned as noise
5. Remaining sizes are sorted largest-first and assigned heading levels: largest = h1, second = h2, up to h6

### Step 4: Classify Text

During page-by-page parsing, each text block is classified:

- If its font size appears in the heading size map, it has fewer than 15 words, and it is either bold or significantly larger than body text -- it becomes a heading at the corresponding level
- Otherwise it becomes a body paragraph

Headings update the current 6-level hierarchy tracker. Subsequent paragraphs inherit that hierarchy until the next heading resets it.

### Why This Works

Fixed thresholds (e.g., "anything above 14pt is a heading") fail across documents because font sizes vary widely. A theological treatise might use 12pt body with 16pt headings, while a legal brief uses 10pt body with 12pt headings. The statistical approach handles both by measuring the document's own typographic conventions.

## Two-Pass Extraction

The extractor opens the document twice:

1. **First pass**: Collect font statistics across all pages, then compute heading rankings. The document is closed after this pass.
2. **Second pass**: Parse each page using the heading rankings to classify text blocks and build the chunk list.

This two-pass design is necessary because heading classification requires global font statistics that aren't available until the entire document has been scanned.

Outline entries from the PDF's table of contents are also integrated during the second pass. They are indexed by page number and injected into the hierarchy at the start of each page, providing heading context even when the PDF's visual headings are ambiguous.

## Building from Source

### Prerequisites

- **Zig**: Master branch (pre-0.16.0)
- **MuPDF**: Installed at `/opt/homebrew/opt/mupdf` (Homebrew: `brew install mupdf`)

### Build

```bash
cd cores
zig build
```

The build produces `cores/zig-out/lib/libde_mupdf.dylib`.

### Install

Copy the built library to the Python package's native lib directory:

```bash
cp cores/zig-out/lib/libde_mupdf.dylib src/extraction/_native/lib/
```

### Verify

```python
from extraction._native._loader import load_library
lib = load_library("de_mupdf")
```

This raises `LibraryLoadError` if the library is not found or fails ABI validation.

### Run Zig Tests

```bash
cd cores
zig build test
```

## Fallback Behavior

When the native library is not available, the system degrades gracefully:

- `NATIVE_AVAILABLE` is set to `False` in `pdf_mupdf.py` (the import of `MuPdfDocument` is wrapped in a try/except)
- The CLI auto-selects `PdfExtractor` (pdfplumber backend) for PDF files
- No error is raised at import time -- the fallback is transparent
- Heading detection falls back to pdfplumber's simpler font-size heuristics
- Instantiating `MuPdfPdfExtractor` directly raises `DependencyError` with build instructions

## Configuration

`MuPdfPdfExtractorConfig` controls the native parser's behavior:

| Option | Default | Description |
|--------|---------|-------------|
| `heading_font_threshold` | `1.2` | Minimum ratio of font size to body size for heading candidacy (range: 1.0-3.0) |
| `min_paragraph_words` | `5` | Minimum word count for a text block to become a paragraph chunk |
| `max_memory_mb` | `512` | Memory limit passed to `de_init` for the MuPDF context (0 = unlimited) |

These can be set via `extraction.toml`, `pyproject.toml [tool.extraction]`, or CLI flags.

## See Also

- [Architecture Overview](architecture.md) -- Three-layer pipeline design
- [Chunking Strategies](chunking-strategies.md) -- How chunks are merged after extraction
