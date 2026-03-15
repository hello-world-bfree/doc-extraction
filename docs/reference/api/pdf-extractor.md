# PdfExtractor API Reference

PDF-specific extractor with page-based processing and heading detection.

## Module

`extraction.extractors.pdf`

## Class

```python
class PdfExtractor(BaseExtractor)
```

Extracts text from PDF files page-by-page with font-based heading detection and optional OCR support.

## Overview

`PdfExtractor` provides:

- **Page-by-page extraction**: Processes PDF pages sequentially
- **Font-based heading detection**: Uses font size to identify headings
- **Paragraph detection**: Splits text on double newlines
- **OCR support**: Optional Tesseract OCR for image-based PDFs
- **Quality scoring**: Same quality analysis as other extractors
- **Chunking strategies**: RAG and NLP modes supported

## Constructor

```python
def __init__(
    self,
    source_path: str,
    config: Optional[PdfExtractorConfig] = None,
    analyzer: Optional[BaseAnalyzer] = None
)
```

### Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `source_path` | `str` | Required | Path to `.pdf` file |
| `config` | `PdfExtractorConfig` | `None` | PDF-specific configuration. If `None`, uses `PdfExtractorConfig()` |
| `analyzer` | `BaseAnalyzer` | `None` | Domain analyzer. If `None`, uses `GenericAnalyzer()` |

### Raises

- `DependencyError`: If `pdfplumber` is not installed

### Example

```python
from extraction.extractors import PdfExtractor
from extraction.extractors.configs import PdfExtractorConfig
from extraction.analyzers import GenericAnalyzer

config = PdfExtractorConfig(
    heading_font_threshold=1.2,
    min_paragraph_words=5,
    use_ocr=False
)

extractor = PdfExtractor(
    source_path="document.pdf",
    config=config,
    analyzer=GenericAnalyzer()
)
```

## Dependencies

**Required**:

- `pdfplumber` - PDF text extraction with layout preservation

**Installation**:

```bash
uv pip install pdfplumber
```

Or with optional PDF support:

```bash
uv pip install -e ".[pdf]"
```

## PDF-Specific Configuration

See [PdfExtractorConfig](../configuration.md#pdfextractorconfig) for full reference.

### Key Options

| Option | Default | Description |
|--------|---------|-------------|
| `heading_font_threshold` | `1.2` | Font size multiplier to detect headings (1.0-3.0) |
| `min_paragraph_words` | `5` | Minimum words to consider text as a paragraph |
| `use_ocr` | `False` | Use Tesseract OCR for image-based PDFs |
| `ocr_lang` | `"eng"` | OCR language code (e.g., "eng", "fra", "spa") |

## Public Methods

Inherits all methods from [BaseExtractor](base-extractor.md):

- `load()` - Load PDF and create provenance
- `parse()` - Extract chunks from pages
- `extract_metadata()` - Extract PDF metadata + domain enrichment
- `get_output_data()` - Get complete output structure

## Heading Detection

Font-based heading detection using `heading_font_threshold`.

### How It Works

1. **Heuristic analysis**: Analyzes text to detect likely headings
2. **Font size threshold**: Compares font sizes (future enhancement)
3. **Word count check**: Headings must be ≤ 15 words
4. **Capitalization check**: Checks for ALL CAPS or Title Case

### Detection Rules

A paragraph is classified as a heading if:

1. **Word count** ≤ 15, AND
2. **ALL CAPS**, OR
3. **Title Case** (>70% of words capitalized)

### Examples

**Detected as headings**:

- `"CHAPTER 1: INTRODUCTION"` (ALL CAPS)
- `"The Nature of Prayer"` (Title Case, 4 words)
- `"Section 1.1"` (Title Case, 2 words)

**Not detected as headings**:

- `"This is a long paragraph with more than fifteen words in it"` (>15 words)
- `"this is lowercase text"` (not capitalized)
- `"The quick brown fox jumps"` (only 60% capitalized)

### Threshold Configuration

The `heading_font_threshold` parameter will be used in future versions for font-size-based detection:

```python
# Sensitive detection (lower threshold)
config = PdfExtractorConfig(heading_font_threshold=1.1)

# Default (balanced)
config = PdfExtractorConfig(heading_font_threshold=1.2)

# Conservative (higher threshold)
config = PdfExtractorConfig(heading_font_threshold=1.5)
```

**Current behavior**: Only heuristic detection is active. Font size analysis is planned for future versions.

## Page Processing

PDFs are processed page-by-page in sequential order.

### Processing Steps

For each page:

1. **Extract text**: Use `pdfplumber.Page.extract_text()`
2. **Split paragraphs**: Split on double newlines (`\n\n`)
3. **Clean text**: Normalize whitespace and ASCII characters
4. **Check word count**: Skip paragraphs below `min_paragraph_words`
5. **Detect headings**: Apply heading detection rules
6. **Create chunks**: Build `Chunk` objects with page metadata

### Hierarchy Behavior

- **Headings**: Detected headings update `level_1` hierarchy
- **Paragraphs**: Inherit current `level_1` (all other levels empty)
- **Cross-page flow**: Hierarchy flows across pages (no reset)

**Example**:

```
Page 1:
  "CHAPTER 1" → Sets level_1 = "CHAPTER 1"
  "First paragraph..." → Inherits level_1 = "CHAPTER 1"
  "Second paragraph..." → Inherits level_1 = "CHAPTER 1"

Page 2:
  "CHAPTER 2" → Sets level_1 = "CHAPTER 2"
  "First paragraph..." → Inherits level_1 = "CHAPTER 2"
```

### Chapter Href

Each chunk's `chapter_href` is set to `page_{N}` where N is the page number (1-indexed).

```python
chunk.chapter_href = "page_1"   # First page
chunk.chapter_href = "page_42"  # Page 42
```

## Metadata Extraction

PDF metadata is extracted from the PDF file's metadata dictionary.

### PDF Metadata Fields

| PDF Field | Mapped To | Fallback |
|-----------|-----------|----------|
| `Title` | `metadata.title` | Filename (without extension) |
| `Author` | `metadata.author` | `"Unknown"` |
| `Creator` | `metadata.publisher` | Empty string |
| `Producer` | `metadata.publisher` | Empty string |

### Example

```python
extractor.load()
extractor.parse()
metadata = extractor.extract_metadata()

print(f"Title: {metadata.title}")          # From PDF metadata or filename
print(f"Author: {metadata.author}")        # From PDF metadata or "Unknown"
print(f"Publisher: {metadata.publisher}")  # Producer or Creator
print(f"Pages: {metadata.pages}")          # "approximately N"
print(f"Word count: {metadata.word_count}") # "approximately M"
```

## OCR Support (Experimental)

Optional OCR for image-based PDFs using Tesseract.

### Configuration

```python
config = PdfExtractorConfig(
    use_ocr=True,
    ocr_lang="eng"  # English
)

# French OCR
config = PdfExtractorConfig(
    use_ocr=True,
    ocr_lang="fra"
)
```

### Language Codes

Common Tesseract language codes:

| Code | Language |
|------|----------|
| `eng` | English |
| `fra` | French |
| `spa` | Spanish |
| `deu` | German |
| `ita` | Italian |
| `por` | Portuguese |
| `rus` | Russian |
| `chi_sim` | Chinese (Simplified) |
| `chi_tra` | Chinese (Traditional) |
| `jpn` | Japanese |
| `ara` | Arabic |

See [Tesseract language data](https://github.com/tesseract-ocr/tessdata) for full list.

### OCR Dependencies

**Required**:

- `pytesseract` - Python wrapper for Tesseract
- `Tesseract OCR` - OCR engine (system installation)

**Installation**:

```bash
# Python package
uv pip install pytesseract

# System package (Ubuntu/Debian)
sudo apt install tesseract-ocr tesseract-ocr-eng

# System package (macOS)
brew install tesseract
```

### OCR Metadata

Chunks extracted via OCR include:

```python
chunk.ocr = True           # Indicates OCR was used
chunk.ocr_conf = 0.95      # OCR confidence (0.0 - 1.0)
```

**Note**: OCR support is experimental and currently not fully implemented.

## Chunking Behavior

### Paragraph Splitting

Paragraphs are detected by splitting on double newlines (`\n\n`):

```python
text = page.extract_text()
paragraphs = [p.strip() for p in text.split('\n\n') if p.strip()]
```

**Example PDF text**:

```
This is the first paragraph.
It spans multiple lines.

This is the second paragraph.

This is the third paragraph.
```

**Paragraphs extracted**:

1. `"This is the first paragraph. It spans multiple lines."`
2. `"This is the second paragraph."`
3. `"This is the third paragraph."`

### Minimum Word Count

Paragraphs below `min_paragraph_words` are skipped:

```python
config = PdfExtractorConfig(min_paragraph_words=5)

# Skipped (4 words)
"This is too short."

# Kept (6 words)
"This paragraph has enough words now."
```

### Sentence Detection

Sentences are detected using `split_sentences()` utility:

```python
chunk.sentences = split_sentences(chunk.text)
chunk.sentence_count = len(chunk.sentences)
```

## Complete Example

```python
from extraction.extractors import PdfExtractor
from extraction.extractors.configs import PdfExtractorConfig
from extraction.analyzers import GenericAnalyzer
import json

# Configure PDF extraction
config = PdfExtractorConfig(
    # Chunking
    chunking_strategy="rag",
    min_chunk_words=100,
    max_chunk_words=500,

    # PDF-specific
    heading_font_threshold=1.2,
    min_paragraph_words=5,

    # OCR (experimental)
    use_ocr=False,
    ocr_lang="eng",

    # Filtering
    filter_noise=True
)

# Create extractor
extractor = PdfExtractor(
    source_path="research_paper.pdf",
    config=config,
    analyzer=GenericAnalyzer()
)

# Process document
extractor.load()
print(f"Total pages: {extractor._PdfExtractor__total_pages}")

extractor.parse()
print(f"Chunks: {len(extractor.chunks)}")
print(f"Quality: {extractor.quality_score} (route {extractor.route})")

# Check for headings
headings = [
    chunk for chunk in extractor.chunks
    if chunk.hierarchy.get("level_1")
]
print(f"Detected headings: {len(headings)}")

metadata = extractor.extract_metadata()
print(f"Title: {metadata.title}")
print(f"Author: {metadata.author}")

# Get output
output = extractor.get_output_data()

# Write to file
with open("research_paper.json", "w") as f:
    json.dump(output, f, indent=2, ensure_ascii=False)

# Print chunk hierarchy
for chunk in extractor.chunks[:5]:
    print(f"Chunk {chunk.paragraph_id}: {chunk.hierarchy['level_1']}")
    print(f"  Page: {chunk.chapter_href}")
    print(f"  Words: {chunk.word_count}")
    print(f"  Text: {chunk.text[:100]}...")
    print()
```

## Error Handling

### PDF-Specific Errors

| Error | When Raised | Example |
|-------|-------------|---------|
| `DependencyError` | `pdfplumber` not installed | Missing `uv pip install pdfplumber` |
| `FileNotFoundError` | PDF file not found | Non-existent path |
| `ParseError` | PDF cannot be opened | Corrupted PDF, encrypted PDF |

### Example

```python
from extraction.exceptions import DependencyError, ParseError

try:
    extractor = PdfExtractor("document.pdf")
    extractor.load()
    extractor.parse()

except DependencyError as e:
    print(f"Missing dependency: {e.dependency}")
    print(f"Install with: {e.install_command}")

except ParseError as e:
    print(f"PDF parsing failed: {e.message}")
    print(f"File: {e.filepath}")
```

## Limitations

### Current Limitations

1. **Heading detection**: Only heuristic-based (no font size analysis yet)
2. **Single-level hierarchy**: Only `level_1` populated (no nested headings)
3. **Paragraph splitting**: Simple double-newline split (may miss some paragraphs)
4. **OCR**: Experimental, not fully implemented
5. **No layout analysis**: Columns, tables, figures not detected

### Future Enhancements

Planned improvements:

- Font-size-based heading detection
- Multi-level hierarchy (h1-h6 equivalent)
- Layout analysis (columns, tables)
- Figure/image extraction
- Table-of-contents extraction
- Full OCR implementation

## Performance

### Typical Performance

- **Small PDFs** (10-50 pages): 1-3 seconds
- **Medium PDFs** (50-200 pages): 3-10 seconds
- **Large PDFs** (200+ pages): 10-30 seconds

**Factors**:

- Page count
- Text density
- Font complexity
- OCR usage (if enabled, much slower)

### Optimization Tips

1. **Disable OCR** if not needed (default: disabled)
2. **Increase `min_paragraph_words`** to skip short fragments
3. **Use `filter_noise=True`** to remove boilerplate
4. **Use RAG strategy** to reduce chunk count

## Comparison with EPUB

| Feature | EPUB | PDF |
|---------|------|-----|
| **Hierarchy** | Multi-level (6 levels) | Single-level (level_1 only) |
| **TOC** | Automatic TOC mapping | No TOC |
| **Formatting** | Preserves HTML structure | Plain text only |
| **Headings** | `<h1>` - `<h6>` tags | Heuristic detection |
| **Quality** | High (structured) | Medium (layout-dependent) |
| **Speed** | Fast | Medium |

**Recommendation**: Use EPUB when available. PDF is a fallback for documents only available as PDF.

## See Also

- [BaseExtractor API](base-extractor.md) - Parent class reference
- [Configuration Reference](../configuration.md#pdfextractorconfig) - Full config options
- [Output Schema Reference](../output-schema.md) - Understanding chunk output
- [Multi-Format Extraction](../../getting-started/multi-format.md) - Advanced techniques
- [Chunking Strategies How-To](../../how-to/chunking-strategy.md) - RAG vs NLP
