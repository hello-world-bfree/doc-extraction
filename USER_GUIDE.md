# Document Extraction Library - User Guide

Comprehensive guide to using the document extraction library for processing EPUB, PDF, HTML, Markdown, and JSON documents.

## Table of Contents

1. [Getting Started](#getting-started)
2. [Command Line Usage](#command-line-usage)
3. [Python API](#python-api)
4. [Configuration Guide](#configuration-guide)
5. [Understanding Output](#understanding-output)
6. [Advanced Topics](#advanced-topics)
7. [Troubleshooting](#troubleshooting)

## Getting Started

### Installation

```bash
# Clone and setup
git clone <repository-url>
cd extraction
uv venv
source .venv/bin/activate
uv pip install -e .
```

### Your First Extraction

```bash
# Extract an EPUB file
extract my_book.epub

# Check the output
ls *.json
# my_book.json                  # Main extraction data
# my_book_metadata.json         # Metadata only
# my_book_hierarchy_report.txt  # Human-readable structure
```

## Command Line Usage

### Basic Extraction

```bash
# Single file
extract document.epub

# With custom output name
extract document.epub --output my_custom_name

# With output directory
extract document.epub --output-dir ./outputs/

# Multiple files in directory
extract ./books/ --output-dir ./outputs/

# Recursive directory processing
extract ./library/ -r --output-dir ./outputs/
```

### Format-Specific Examples

#### EPUB Documents

```bash
# Basic EPUB extraction
extract book.epub

# With TOC hierarchy at level 2 (h1, h2 only)
extract book.epub --toc-level 2

# Require minimum 10 words per paragraph
extract book.epub --min-words 10

# Preserve hierarchy across spine documents
extract book.epub --preserve-hierarchy

# Enable debug dump for troubleshooting
extract book.epub --debug-dump -v
```

#### PDF Documents

```bash
# Basic PDF extraction
extract document.pdf

# With verbose logging to see extraction details
extract document.pdf -v

# Batch process PDF directory
extract ./pdfs/ -r --output-dir ./pdf_outputs/
```

#### HTML Documents

```bash
# Extract from HTML
extract webpage.html

# Batch process HTML files
extract ./html_docs/ -r --output-dir ./html_outputs/
```

#### Markdown Documents

```bash
# Extract from Markdown (with frontmatter)
extract article.md

# Batch process documentation
extract ./docs/ -r --output-dir ./md_outputs/
```

#### JSON Import

```bash
# Re-process existing extraction output
extract previous_extraction.json --output-dir ./reimport/

# Useful for format conversion or re-analysis
extract old_output.json --analyzer generic
```

### Domain Analyzers

```bash
# Use Catholic analyzer (default)
extract religious_text.epub --analyzer catholic

# Use Generic analyzer
extract general_book.epub --analyzer generic

# Catholic analyzer enriches metadata with:
# - document_type detection (encyclical, apostolic letter, etc.)
# - feast days and saints
# - theological themes
# - scripture reference analysis
```

### Output Formats

```bash
# JSON only (default)
extract document.epub

# JSON + NDJSON (for streaming)
extract document.epub --ndjson

# NDJSON is useful for:
# - Streaming large datasets
# - Line-by-line processing
# - Database imports
```

### Batch Processing

```bash
# Process all supported formats in directory
extract ./mixed_documents/ -r --output-dir ./all_outputs/
# Processes: .epub, .pdf, .html, .htm, .md, .markdown, .json

# Process specific subdirectories
extract ./library/fiction/ -r --output-dir ./fiction_outputs/
extract ./library/non-fiction/ -r --output-dir ./nonfiction_outputs/
```

### Logging Control

```bash
# Verbose logging (DEBUG level)
extract document.epub -v

# Quiet mode (warnings only)
extract document.epub -q

# Normal mode (INFO level)
extract document.epub
```

## Python API

### Basic Usage Pattern

All extractors follow the same pattern:

```python
from src.extraction.extractors import EpubExtractor

# 1. Initialize with path
extractor = EpubExtractor("book.epub")

# 2. Load the document
extractor.load()

# 3. Parse and extract chunks
extractor.parse()

# 4. Extract metadata
metadata = extractor.extract_metadata()

# 5. Access results
print(f"Title: {metadata.title}")
print(f"Chunks: {len(extractor.chunks)}")
print(f"Quality: {extractor.quality_score} (route {extractor.route})")
```

### Format-Specific Examples

#### EPUB Extraction

```python
from src.extraction.extractors import EpubExtractor

# With configuration
config = {
    "toc_hierarchy_level": 3,
    "min_paragraph_words": 6,
    "preserve_hierarchy_across_docs": True,
}

extractor = EpubExtractor("book.epub", config=config)
extractor.load()
extractor.parse()
metadata = extractor.extract_metadata()

# Access TOC
print(f"TOC entries: {len(extractor.toc_map)}")

# Access chunks
for chunk in extractor.chunks[:5]:
    print(f"[{chunk.paragraph_id}] {chunk.text[:80]}...")
    print(f"  Hierarchy: {chunk.heading_path}")
    print(f"  Scripture refs: {chunk.scripture_references}")
```

#### PDF Extraction

```python
from src.extraction.extractors import PdfExtractor

config = {
    "min_paragraph_words": 5,
    "heading_font_threshold": 1.2,
}

extractor = PdfExtractor("document.pdf", config=config)
extractor.load()
extractor.parse()
metadata = extractor.extract_metadata()

# PDF-specific attributes
print(f"Pages: {metadata.pages}")
print(f"Publisher: {metadata.publisher}")

# Page-based chunks
for chunk in extractor.chunks:
    print(f"Page {chunk.chapter_href}: {chunk.word_count} words")
```

#### HTML Extraction

```python
from src.extraction.extractors import HtmlExtractor

config = {
    "min_paragraph_words": 1,
    "preserve_links": False,
}

extractor = HtmlExtractor("webpage.html", config=config)
extractor.load()
extractor.parse()
metadata = extractor.extract_metadata()

# HTML-specific
print(f"HTML Title: {extractor.html_title}")

# Hierarchy from h1-h6 tags
for chunk in extractor.chunks:
    depth = chunk.hierarchy_depth
    heading = chunk.heading_path
    print(f"{'  ' * depth}→ {chunk.text[:60]}...")
```

#### Markdown Extraction

```python
from src.extraction.extractors import MarkdownExtractor

config = {
    "preserve_code_blocks": True,
    "extract_frontmatter": True,
}

extractor = MarkdownExtractor("article.md", config=config)
extractor.load()

# Access frontmatter
print("Frontmatter:", extractor.frontmatter)
print(f"Title: {extractor.frontmatter.get('title')}")
print(f"Author: {extractor.frontmatter.get('author')}")

extractor.parse()
metadata = extractor.extract_metadata()

# Markdown heading hierarchy
for chunk in extractor.chunks:
    print(f"{chunk.hierarchy_depth}# {chunk.heading_path}")
    print(f"   {chunk.text[:80]}...")
```

### Working with Chunks

```python
# Access chunk data
for chunk in extractor.chunks:
    # Basic info
    print(f"ID: {chunk.stable_id}")
    print(f"Text: {chunk.text}")
    print(f"Words: {chunk.word_count}")

    # Hierarchy
    print(f"Path: {chunk.heading_path}")
    print(f"Depth: {chunk.hierarchy_depth}")
    print(f"Levels: {chunk.hierarchy}")

    # References
    print(f"Scripture: {chunk.scripture_references}")
    print(f"Cross-refs: {chunk.cross_references}")
    print(f"Dates: {chunk.dates_mentioned}")

    # Sentences
    print(f"Sentence count: {chunk.sentence_count}")
    for i, sent in enumerate(chunk.sentences, 1):
        print(f"  {i}. {sent}")
```

### Generating Output Files

```python
from src.extraction.core.output import write_outputs

# Write all output files
write_outputs(
    extractor,
    base_filename="my_output",
    ndjson=True,
    output_dir="./outputs/"
)

# This creates:
# - ./outputs/my_output.json
# - ./outputs/my_output_metadata.json
# - ./outputs/my_output_hierarchy_report.txt
# - ./outputs/my_output.ndjson (if ndjson=True)
```

### Custom Processing Pipeline

```python
from src.extraction.extractors import MarkdownExtractor
from src.extraction.analyzers import CatholicAnalyzer
import json

# Extract document
extractor = MarkdownExtractor("document.md")
extractor.load()
extractor.parse()

# Custom analysis
analyzer = CatholicAnalyzer()
full_text = " ".join(c.text for c in extractor.chunks)
chunks_dict = [c.to_dict() for c in extractor.chunks]
metadata_dict = extractor.extract_metadata().to_dict()

enriched = analyzer.enrich_metadata(metadata_dict, full_text, chunks_dict)

# Custom output
output = {
    "custom_metadata": enriched,
    "chunk_count": len(extractor.chunks),
    "scripture_refs": sum(len(c.scripture_references) for c in extractor.chunks),
    "quality": {
        "score": extractor.quality_score,
        "route": extractor.route
    }
}

with open("custom_output.json", "w") as f:
    json.dump(output, f, indent=2)
```

## Configuration Guide

### EPUB Configuration

```python
epub_config = {
    # TOC hierarchy level (1-6): how deep to treat TOC entries as headings
    "toc_hierarchy_level": 3,  # h1, h2, h3 from TOC

    # Minimum words for a paragraph to be included
    "min_paragraph_words": 6,

    # Minimum words for generic block tags (div, section)
    "min_block_words": 30,

    # Preserve hierarchy across spine documents
    "preserve_hierarchy_across_docs": True,

    # On document boundary, clear levels >= this depth
    "reset_depth": 2,  # Reset h2 and below

    # Regex for CSS class denylist (exclude elements)
    "class_denylist": r"^(?:calibre\d+|note|footnote)$"
}
```

### PDF Configuration

```python
pdf_config = {
    # Minimum words for paragraph inclusion
    "min_paragraph_words": 5,

    # Font size threshold for heading detection (ratio)
    "heading_font_threshold": 1.2,  # 20% larger than body text

    # Enable OCR for scanned PDFs (future feature)
    "use_ocr": False
}
```

### HTML Configuration

```python
html_config = {
    # Minimum words for paragraph inclusion
    "min_paragraph_words": 1,

    # Preserve link text (future feature)
    "preserve_links": False
}
```

### Markdown Configuration

```python
md_config = {
    # Minimum words for paragraph inclusion
    "min_paragraph_words": 1,

    # Preserve code blocks as chunks
    "preserve_code_blocks": True,

    # Extract YAML frontmatter
    "extract_frontmatter": True
}
```

## Understanding Output

### JSON Output Structure

```json
{
  "metadata": {
    // Basic metadata
    "title": "Document Title",
    "author": "Author Name",
    "language": "en",
    "word_count": "approximately 5,432",

    // Domain-specific (Catholic analyzer)
    "document_type": "encyclical",
    "date_promulgated": "1891-05-15",
    "subject": ["social justice", "labor rights"],

    // Provenance
    "provenance": {
      "doc_id": "a1b2c3d4...",
      "source_file": "document.epub",
      "parser_version": "2.0.0-refactored",
      "ingestion_ts": "2025-12-28T10:00:00",
      "content_hash": "sha1hash..."
    },

    // Quality assessment
    "quality": {
      "signals": {
        "garble_rate": 0.01,
        "mean_conf": 0.95,
        "line_len_std_norm": 0.2,
        "lang_prob": 0.98
      },
      "score": 0.95,
      "route": "A"
    }
  },

  "chunks": [
    {
      "stable_id": "xyz789...",
      "paragraph_id": 1,
      "text": "Full paragraph text...",
      "hierarchy": {
        "level_1": "Chapter 1",
        "level_2": "Section A",
        "level_3": "Subsection i",
        "level_4": "",
        "level_5": "",
        "level_6": ""
      },
      "heading_path": "Chapter 1 / Section A / Subsection i",
      "hierarchy_depth": 3,
      "word_count": 42,
      "sentence_count": 3,
      "sentences": ["First.", "Second.", "Third."],
      "scripture_references": ["John 3:16"],
      "cross_references": ["See Chapter 5"],
      "dates_mentioned": ["1891-05-15"]
    }
  ],

  "extraction_info": {
    "total_chunks": 156,
    "quality_route": "A",
    "quality_score": 0.95
  }
}
```

### Quality Routes

- **Route A**: High quality (score >= 0.8)
  - Clean text, good structure
  - Low garble rate
  - Suitable for production use

- **Route B**: Medium quality (0.5 <= score < 0.8)
  - Some formatting issues
  - May need review
  - Usable with caution

- **Route C**: Low quality (score < 0.5)
  - Significant extraction issues
  - May be scanned/OCR needed
  - Requires manual review

### Hierarchy Report

```
DOCUMENT HIERARCHICAL STRUCTURE REPORT
======================================================================
Source: document.epub
Generated: 2025-12-28 10:00:00

DOCUMENT METADATA:
--------------------
Title: Sample Document
Author: John Doe
Language: en
Word Count: approximately 5,432

STRUCTURE TREE:
---------------
Chapter 1: Introduction
  [¶ 1-5, ~523 words]

Chapter 1: Introduction
  └─ Section A: Background
    [¶ 6-12, ~687 words]

Chapter 1: Introduction
  └─ Section A: Background
    └─ Subsection i: Historical Context
      [¶ 13-15, ~342 words]

SUMMARY:
----------
Total unique hierarchy paths: 24
Total paragraphs: 156
Total words: 5,432
```

## Advanced Topics

### Batch Processing with Custom Logic

```python
from pathlib import Path
from src.extraction.extractors import (
    EpubExtractor, PdfExtractor, HtmlExtractor, MarkdownExtractor
)

def process_directory(input_dir, output_dir):
    """Process all supported files in directory."""
    input_path = Path(input_dir)
    output_path = Path(output_dir)
    output_path.mkdir(exist_ok=True)

    extractor_map = {
        '.epub': EpubExtractor,
        '.pdf': PdfExtractor,
        '.html': HtmlExtractor,
        '.htm': HtmlExtractor,
        '.md': MarkdownExtractor,
        '.markdown': MarkdownExtractor,
    }

    for file_path in input_path.rglob('*'):
        if file_path.suffix in extractor_map:
            print(f"Processing: {file_path.name}")

            # Get appropriate extractor
            ExtractorClass = extractor_map[file_path.suffix]
            extractor = ExtractorClass(str(file_path))

            try:
                extractor.load()
                extractor.parse()
                extractor.extract_metadata()

                # Custom output
                output_file = output_path / f"{file_path.stem}.json"
                import json
                with open(output_file, 'w') as f:
                    json.dump(extractor.get_output_data(), f, indent=2)

                print(f"  ✓ {len(extractor.chunks)} chunks, quality: {extractor.quality_score}")

            except Exception as e:
                print(f"  ✗ Error: {e}")

# Usage
process_directory("./library", "./outputs")
```

### Custom Analyzer

```python
from src.extraction.analyzers.base import BaseAnalyzer
import re

class AcademicAnalyzer(BaseAnalyzer):
    """Analyzer for academic papers."""

    def enrich_metadata(self, metadata_dict, full_text, chunks):
        """Add academic-specific metadata."""

        # Detect citations
        citations = re.findall(r'\[(\d+)\]|\(([A-Z][a-z]+ et al\., \d{4})\)', full_text)
        metadata_dict['citation_count'] = len(citations)

        # Detect sections
        sections = set()
        for chunk in chunks:
            if chunk['hierarchy']['level_1']:
                sections.add(chunk['hierarchy']['level_1'])
        metadata_dict['section_count'] = len(sections)
        metadata_dict['sections'] = list(sections)

        # Detect keywords
        common_academic = ['methodology', 'results', 'discussion', 'conclusion',
                          'introduction', 'abstract', 'hypothesis']
        found_keywords = [kw for kw in common_academic if kw in full_text.lower()]
        metadata_dict['academic_keywords'] = found_keywords

        return metadata_dict

# Usage
from src.extraction.extractors import PdfExtractor

extractor = PdfExtractor("paper.pdf")
extractor.load()
extractor.parse()

analyzer = AcademicAnalyzer()
full_text = " ".join(c.text for c in extractor.chunks)
chunks_dict = [c.to_dict() for c in extractor.chunks]
metadata_dict = extractor.extract_metadata().to_dict()

enriched = analyzer.enrich_metadata(metadata_dict, full_text, chunks_dict)
print(f"Citations: {enriched['citation_count']}")
print(f"Sections: {enriched['sections']}")
```

## Troubleshooting

### Common Issues

#### PDF Extraction Returns Few Chunks

**Problem**: PDF extractor only returns 1-2 chunks for a multi-page document.

**Solution**: This is expected for PDFs without explicit formatting. PDFs group text by page. To get better granularity:

```python
# Adjust minimum word threshold
config = {"min_paragraph_words": 3}  # Lower threshold
extractor = PdfExtractor("document.pdf", config=config)
```

#### HTML Missing Some Paragraphs

**Problem**: Some paragraph text is not extracted from HTML.

**Solution**: Check if paragraphs are in excluded elements (scripts, styles). Verify they're within main/article/body tags.

```python
# Inspect the parsed structure
extractor = HtmlExtractor("page.html")
extractor.load()
print(f"Main content tag: {extractor.soup.find('main')}")
```

#### Markdown Code Blocks Not Preserved

**Problem**: Code blocks are missing from output.

**Solution**: Ensure `preserve_code_blocks` is enabled:

```python
config = {"preserve_code_blocks": True}
extractor = MarkdownExtractor("doc.md", config=config)
```

#### EPUB Hierarchy Not Preserved

**Problem**: All chunks have empty hierarchy.

**Solution**: Check TOC level and ensure `preserve_hierarchy_across_docs` is set:

```python
config = {
    "toc_hierarchy_level": 3,
    "preserve_hierarchy_across_docs": True
}
extractor = EpubExtractor("book.epub", config=config)
```

#### Low Quality Score

**Problem**: Quality score is low (< 0.5) but text looks fine.

**Solution**: This may indicate:
- Unusual character distributions
- Short line lengths
- Non-English text (language detection)

Check quality signals:
```python
print(extractor.quality_signals)
# {'garble_rate': 0.05, 'mean_conf': 0.6, ...}
```

### Debug Mode

Enable verbose logging to see extraction details:

```bash
extract document.epub -v

# For EPUB, enable debug dump
extract document.epub --debug-dump -v
# Creates ./debug/ directory with intermediate files
```

### Getting Help

1. Check logs for errors
2. Verify input file is not corrupted
3. Try with verbose logging (-v)
4. Check configuration values
5. Review quality signals for hints

## Examples Repository

See `tests/fixtures/sample_data/` for example documents:
- `test_document.pdf` - Sample PDF with multiple pages
- `test_document.html` - Sample HTML with hierarchy
- `test_document.md` - Sample Markdown with frontmatter

Run extraction on these to see expected behavior:

```bash
extract tests/fixtures/sample_data/test_document.md -v
```
