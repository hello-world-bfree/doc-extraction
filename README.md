# Document Extraction Library

A robust, multi-format document processing library for extracting structured text, metadata, and hierarchical information from EPUB, PDF, HTML, Markdown, and JSON documents.

## Features

### Multi-Format Support
- **EPUB**: Full support for EPUB documents with TOC hierarchy and footnote detection
- **PDF**: Text extraction with heading detection and page-based chunking
- **HTML**: BeautifulSoup-based extraction preserving h1-h6 hierarchy
- **Markdown**: Native parsing with YAML frontmatter support
- **JSON**: Import mode for re-processing existing extraction outputs

### Intelligent Processing
- **Hierarchical Chunking**: Preserves document structure across heading levels
- **Domain Analysis**: Pluggable analyzers for domain-specific metadata enrichment
  - Catholic analyzer for religious documents
  - Generic analyzer for general content
- **Reference Detection**:
  - Scripture references (e.g., "John 3:16", "Matthew 5:1-12")
  - Cross-references (e.g., "See Chapter 7", "Section 3.2")
  - Date mentions
- **Quality Scoring**: Automatic quality assessment and routing (A/B/C grades)

### Output Formats
- **JSON**: Structured output with metadata, chunks, and provenance
- **NDJSON**: Newline-delimited JSON for streaming processing
- **Hierarchy Reports**: Human-readable text structure summaries

## Installation

```bash
# Clone repository
git clone <repository-url>
cd extraction

# Create virtual environment (using uv)
uv venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
uv pip install -e .
```

### Dependencies

- **Core**: `python >= 3.10`, `beautifulsoup4`, `lxml`, `ebooklib`
- **PDF Support**: `pdfplumber`
- **Markdown Support**: `markdown`
- **Testing**: `pytest`, `pytest-cov`

## Quick Start

### Command Line Interface

```bash
# Extract a single document
extract document.epub

# Extract with output directory
extract document.pdf --output-dir outputs/

# Batch process a directory
extract documents/ -r --output-dir outputs/

# Use domain analyzer
extract book.epub --analyzer catholic --ndjson
```

### Python API

```python
from src.extraction.extractors import EpubExtractor, PdfExtractor, HtmlExtractor, MarkdownExtractor

# EPUB Extraction
extractor = EpubExtractor("book.epub")
extractor.load()
extractor.parse()
metadata = extractor.extract_metadata()

# Access extracted data
print(f"Title: {metadata.title}")
print(f"Chunks: {len(extractor.chunks)}")
print(f"Quality: {extractor.quality_score}")

# Get output data
output = extractor.get_output_data()
```

### Configuration

All extractors support configuration dictionaries:

```python
# EPUB Configuration
epub_config = {
    "toc_hierarchy_level": 3,
    "min_paragraph_words": 6,
    "preserve_hierarchy_across_docs": True,
    "class_denylist": r"^(?:calibre\d+|note|footnote)$"
}

# PDF Configuration
pdf_config = {
    "min_paragraph_words": 5,
    "heading_font_threshold": 1.2,
    "use_ocr": False
}

# HTML Configuration
html_config = {
    "min_paragraph_words": 1,
    "preserve_links": False
}

# Markdown Configuration
md_config = {
    "min_paragraph_words": 1,
    "preserve_code_blocks": True,
    "extract_frontmatter": True
}

extractor = EpubExtractor("book.epub", config=epub_config)
```

## Architecture

### Core Components

```
src/extraction/
├── core/              # Core utilities
│   ├── chunking.py    # Text chunking and hierarchy
│   ├── extraction.py  # Reference and date extraction
│   ├── identifiers.py # Stable ID generation
│   ├── models.py      # Data models (Chunk, Metadata, etc.)
│   ├── output.py      # Output file generation
│   ├── quality.py     # Quality scoring
│   └── text.py        # Text processing utilities
├── extractors/        # Format-specific extractors
│   ├── base.py        # BaseExtractor abstract class
│   ├── epub.py        # EPUB extractor
│   ├── pdf.py         # PDF extractor
│   ├── html.py        # HTML extractor
│   ├── markdown.py    # Markdown extractor
│   └── json.py        # JSON import extractor
├── analyzers/         # Domain analyzers
│   ├── base.py        # BaseAnalyzer abstract class
│   ├── catholic.py    # Catholic document analyzer
│   └── generic.py     # Generic document analyzer
└── cli/               # Command-line interface
    └── extract.py     # Unified extraction CLI
```

### Extractor Interface

All extractors inherit from `BaseExtractor` and implement:

1. **load()**: Load the source document
2. **parse()**: Extract chunks with hierarchy
3. **extract_metadata()**: Extract document metadata

```python
from src.extraction.extractors.base import BaseExtractor

class CustomExtractor(BaseExtractor):
    def load(self):
        # Load document
        pass

    def parse(self):
        # Extract chunks
        pass

    def extract_metadata(self):
        # Extract metadata
        pass
```

### Analyzer Interface

Domain analyzers enrich metadata with domain-specific information:

```python
from src.extraction.analyzers.base import BaseAnalyzer

class CustomAnalyzer(BaseAnalyzer):
    def enrich_metadata(self, metadata_dict, full_text, chunks):
        # Add domain-specific fields
        return metadata_dict
```

## Output Format

### JSON Output Structure

```json
{
  "metadata": {
    "title": "Document Title",
    "author": "Author Name",
    "language": "en",
    "word_count": "approximately 1,234",
    "provenance": {
      "doc_id": "abc123...",
      "source_file": "document.epub",
      "parser_version": "2.0.0",
      "ingestion_ts": "2025-12-28T10:00:00"
    },
    "quality": {
      "score": 0.95,
      "route": "A"
    }
  },
  "chunks": [
    {
      "stable_id": "xyz789...",
      "paragraph_id": 1,
      "text": "Paragraph text content...",
      "hierarchy": {
        "level_1": "Chapter 1",
        "level_2": "Section A",
        "level_3": ""
      },
      "word_count": 25,
      "scripture_references": ["John 3:16"],
      "cross_references": ["See Chapter 5"],
      "sentences": ["First sentence.", "Second sentence."]
    }
  ],
  "extraction_info": {
    "total_chunks": 42,
    "quality_route": "A",
    "quality_score": 0.95
  }
}
```

## CLI Reference

### Commands

```bash
extract PATH [OPTIONS]
```

### Arguments

- `PATH`: Path to document file OR directory of files

### Options

**Output:**
- `--output, -o`: Base name for output files (single-file mode)
- `--output-dir`: Directory to write outputs (default: current directory)
- `--ndjson`: Also emit chunks as newline-delimited JSON

**Batch Processing:**
- `--recursive, -r`: Include subdirectories when processing directory

**Analysis:**
- `--analyzer`: Domain analyzer: `catholic` (default) or `generic`

**EPUB Options:**
- `--toc-level`: Hierarchy level for TOC titles (1-6, default: 3)
- `--min-words`: Minimum words for paragraph inclusion (default: 1)
- `--min-block-words`: Min words to chunk generic blocks (default: 2)
- `--preserve-hierarchy`: Preserve hierarchy across spine documents
- `--reset-depth`: Clear levels >= this depth on doc boundary (default: 2)
- `--deny-class`: Regex for class denylist

**Logging:**
- `--verbose, -v`: Verbose logging (DEBUG level)
- `--quiet, -q`: Quiet logging (WARNING level only)
- `--debug-dump`: Write debug information to ./debug/ [EPUB]

### Examples

```bash
# Basic extraction
extract document.epub

# Batch process with custom output directory
extract ./books/ -r --output-dir ./output/

# Use Catholic analyzer with NDJSON output
extract religious_text.epub --analyzer catholic --ndjson

# Custom EPUB configuration
extract book.epub --toc-level 2 --min-words 5 --preserve-hierarchy

# Verbose logging
extract document.pdf -v

# Process multiple formats
extract ./mixed_docs/ -r  # Processes .epub, .pdf, .html, .md, .json
```

## Testing

```bash
# Run all tests
uv run pytest

# Run with coverage
uv run pytest --cov=src/extraction --cov-report=html

# Run specific test file
uv run pytest tests/test_extractors.py -v

# Run integration tests
uv run pytest tests/test_integration.py -v
```

**Test Coverage:**
- 146 tests covering core utilities, extractors, analyzers, CLI, and integration scenarios
- Sample documents in `tests/fixtures/sample_data/`
- Integration tests with real PDF, HTML, and Markdown files

## Development

### Project Structure

Organized following a modular architecture:

1. **Phase 1**: Core Utilities Extraction
2. **Phase 2**: Extractor Abstraction
3. **Phase 3**: Domain Analyzers
4. **Phase 4**: Output Management & CLI
5. **Phase 5**: Testing & Validation
6. **Phase 6**: Additional Extractors (PDF, HTML, Markdown, JSON)

### Adding a New Extractor

1. Create `src/extraction/extractors/myformat.py`
2. Inherit from `BaseExtractor`
3. Implement `load()`, `parse()`, `extract_metadata()`
4. Register in `__init__.py`
5. Update CLI format detection
6. Add tests in `tests/`

### Adding a New Analyzer

1. Create `src/extraction/analyzers/mydomain.py`
2. Inherit from `BaseAnalyzer`
3. Implement `enrich_metadata()`
4. Register in CLI choices
5. Add tests in `tests/`

## Backward Compatibility

The library maintains compatibility with legacy parsers:
- `book_parser_no_footnotes.py`
- `epub_pdf_catholic_parser.py`
- `book_parser.py`

Outputs are 99%+ compatible with legacy formats (verified via regression tests).

## License

[Specify your license here]

## Contributing

[Specify contribution guidelines here]

## Changelog

### Version 2.0.0 (Current)

**Major Refactoring:**
- Modular architecture with core utilities
- Abstract base classes for extractors and analyzers
- Multi-format support (EPUB, PDF, HTML, Markdown, JSON)
- Unified CLI replacing 3 legacy parsers
- 146 comprehensive tests
- Quality scoring and routing
- Domain-specific analyzers

**Supported Formats:**
- EPUB (full support with TOC and footnotes)
- PDF (pdfplumber-based extraction)
- HTML (BeautifulSoup with hierarchy preservation)
- Markdown (YAML frontmatter support)
- JSON (import mode for re-processing)

**Features:**
- Reference detection (scripture, cross-references, dates)
- Hierarchical chunking (6 levels)
- Pluggable domain analyzers
- Provenance tracking
- Quality assessment
- Multiple output formats (JSON, NDJSON, text reports)

## Roadmap

Potential future enhancements:

- [ ] DOCX support
- [ ] OCR integration for scanned PDFs
- [ ] Enhanced PDF heading detection (font analysis)
- [ ] JSON extract mode (arbitrary JSON structures)
- [ ] Custom analyzer framework
- [ ] API server mode
- [ ] Parallel batch processing
- [ ] Additional output formats (CSV, XML, SQLite)
