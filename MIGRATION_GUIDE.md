# Migration Guide: Legacy Parsers → New Extraction Library

This guide helps users migrate from legacy parsers to the new unified extraction library.

## ⚠️ Legacy Parsers Deprecated

The following scripts are **deprecated** and will be removed in a future version:

- `book_parser_no_footnotes.py`
- `book_parser.py`
- `book_parser_refactored.py`
- `epub_pdf_catholic_parser.py`

**Please migrate to the new extraction library as soon as possible.**

## Why Migrate?

The new extraction library offers:

✅ **Multi-format support**: EPUB, PDF, HTML, Markdown, JSON
✅ **Modular architecture**: Clean separation of extractors and analyzers
✅ **Better testing**: 146 comprehensive tests
✅ **Unified interface**: Consistent API across all formats
✅ **Better documentation**: README.md and USER_GUIDE.md
✅ **Active maintenance**: New features and bug fixes

## Breaking Changes in Version 2.1.0

### Text Spacing Fix (December 2025)

**What Changed**: Fixed a bug in the `normalize_spaced_caps()` function where heading text extraction was incorrectly concatenating words without spaces.

**Examples of Fixed Output**:
- **Before**: `"Introduction to HTMLTesting"` (missing space before "Testing")
- **After**: `"Introduction to HTML Testing"` (correct spacing)
- **Before**: `"About XMLDocuments"` (missing space before "Documents")
- **After**: `"About XML Documents"` (correct spacing)

**Impact**: This affects HTML and potentially PDF extraction output:
- Heading hierarchy text now has proper spacing
- JSON output format unchanged, but text values differ
- Quality scores and chunk counts unchanged
- Only affects text content in hierarchy fields

**Who is Affected**: You are affected if:
- You parse or compare hierarchy text values (e.g., `chunk.hierarchy["level_1"]`)
- You have assertions or logic that depends on the buggy spacing
- You process heading text for display or analysis

**Who is NOT Affected**: You are NOT affected if:
- You only use structural fields (IDs, word counts, quality scores)
- You don't process hierarchy text values
- You're using the library for the first time

**Migration**:

If you have code that depends on the buggy spacing, update your assertions/logic:

```python
# OLD (buggy behavior - update this)
if chunk.hierarchy["level_1"] == "Introduction to HTMLTesting":
    process_introduction()

# NEW (correct behavior)
if chunk.hierarchy["level_1"] == "Introduction to HTML Testing":
    process_introduction()
```

**Upgrade Command**:
```bash
# Re-extract documents with corrected spacing
extract documents/ -r --output-dir outputs/
```

## Migration Paths

### From `book_parser_no_footnotes.py`

**Old (Legacy):**
```bash
python book_parser_no_footnotes.py book.epub --output my_output --output-dir ./outputs/
```

**New (Recommended):**
```bash
extract book.epub --output my_output --output-dir ./outputs/
```

**Python API - Old:**
```python
# Not available in legacy
```

**Python API - New:**
```python
from src.extraction.extractors import EpubExtractor

extractor = EpubExtractor("book.epub")
extractor.load()
extractor.parse()
metadata = extractor.extract_metadata()

# Get output data
output = extractor.get_output_data()
```

### From `epub_pdf_catholic_parser.py`

**Old (Legacy):**
```bash
python epub_pdf_catholic_parser.py document.epub
```

**New (Recommended):**
```bash
extract document.epub --analyzer catholic
```

The Catholic analyzer is now a pluggable component that enriches metadata with domain-specific information.

### From `book_parser_refactored.py`

This was already a compatibility wrapper. Replace with direct extraction library usage:

**Old (Legacy):**
```python
from book_parser_refactored import EpubExtractor  # Old import
```

**New (Recommended):**
```python
from src.extraction.extractors import EpubExtractor  # New import
```

## Configuration Changes

### EPUB Options

Most configuration options remain the same, just use the new `--` prefix:

| Legacy Flag | New Flag | Description |
|------------|----------|-------------|
| `--toc-level N` | `--toc-level N` | TOC hierarchy level (1-6) |
| `--min-words N` | `--min-words N` | Min words per paragraph |
| `--preserve-hierarchy` | `--preserve-hierarchy` | Preserve hierarchy across docs |
| `--debug-dump` | `--debug-dump` | Write debug information |
| `-v` | `-v` | Verbose logging |
| `-q` | `-q` | Quiet logging |

**New Options:**
- `--analyzer {catholic,generic}`: Choose domain analyzer
- `--ndjson`: Also emit NDJSON output
- `-r, --recursive`: Process directories recursively

### Configuration via Python

**Old (if it existed):**
```python
# Configuration was hardcoded
```

**New:**
```python
config = {
    "toc_hierarchy_level": 3,
    "min_paragraph_words": 6,
    "preserve_hierarchy_across_docs": True,
    "class_denylist": r"^(?:calibre\d+|note|footnote)$"
}

extractor = EpubExtractor("book.epub", config=config)
```

## Output Format Compatibility

The new extraction library maintains **99%+ compatibility** with legacy output formats:

### JSON Structure

Both produce the same JSON structure:
- `metadata` object with title, author, provenance, quality
- `chunks` array with hierarchical paragraph data
- `extraction_info` with summary statistics

### Field Mapping

All legacy fields are preserved:
- `stable_id`, `paragraph_id`, `text`, `hierarchy`
- `scripture_references`, `cross_references`, `dates_mentioned`
- `heading_path`, `hierarchy_depth`, `sentence_count`, `sentences`
- `doc_stable_id`, `normalized_text`

## New Features Available After Migration

### Multi-Format Support

```bash
# EPUB
extract book.epub

# PDF
extract document.pdf

# HTML
extract webpage.html

# Markdown
extract article.md

# JSON (import existing extractions)
extract previous_output.json
```

### Batch Processing

```bash
# Process all supported formats in directory
extract ./documents/ -r --output-dir ./outputs/

# Supported: .epub, .pdf, .html, .htm, .md, .markdown, .json
```

### Python API for All Formats

```python
from src.extraction.extractors import (
    EpubExtractor,
    PdfExtractor,
    HtmlExtractor,
    MarkdownExtractor,
    JsonExtractor
)

# Same interface for all formats
for ExtractorClass in [EpubExtractor, PdfExtractor, HtmlExtractor]:
    extractor = ExtractorClass("document.ext")
    extractor.load()
    extractor.parse()
    metadata = extractor.extract_metadata()
```

### Domain Analyzers

```bash
# Catholic analyzer (enriches religious documents)
extract religious_text.epub --analyzer catholic

# Generic analyzer
extract general_book.epub --analyzer generic
```

## Migration Checklist

- [ ] Review README.md for new features
- [ ] Read USER_GUIDE.md for detailed usage
- [ ] Test new extraction library with your documents
- [ ] Update your scripts to use `extract` CLI
- [ ] Update Python code to use `from src.extraction.extractors import ...`
- [ ] Verify output compatibility (should be 99%+ identical)
- [ ] Remove references to legacy parsers
- [ ] Update documentation and training materials

## Testing Migration

1. **Run both versions side-by-side:**
   ```bash
   # Legacy
   python book_parser_no_footnotes.py book.epub --output legacy

   # New
   extract book.epub --output new

   # Compare
   diff legacy.json new.json
   ```

2. **Check test suite:**
   ```bash
   uv run pytest tests/test_regression.py -v
   ```

   This verifies backward compatibility.

## Timeline

- **Current**: Legacy parsers deprecated but still functional
- **Future (TBD)**: Legacy parsers will be removed
- **Recommendation**: Migrate as soon as possible

## Getting Help

1. **Documentation**: See README.md and USER_GUIDE.md
2. **Examples**: Check `tests/fixtures/sample_data/` for sample documents
3. **Issues**: Report problems with the new library
4. **Questions**: Ask about migration-specific concerns

## Backward Compatibility Guarantee

The new extraction library guarantees:

✅ **Output format compatibility**: 99%+ identical to legacy parsers
✅ **All legacy fields preserved**: No data loss
✅ **Quality parity**: Same quality scoring algorithm
✅ **Provenance tracking**: Same content hashing and IDs

Differences you might see (< 1% of cases):
- Slightly different chunk boundaries (improved accuracy)
- Additional metadata fields (enrichment from analyzers)
- Better handling of edge cases (bug fixes)

## Example Migration

### Before (Legacy):

```python
#!/usr/bin/env python3
import book_parser_no_footnotes

# Process EPUB (legacy way)
# ...no direct API available, must use CLI
```

### After (New):

```python
#!/usr/bin/env python3
from src.extraction.extractors import EpubExtractor
from src.extraction.core.output import write_outputs

# Process EPUB
extractor = EpubExtractor("book.epub")
extractor.load()
extractor.parse()
metadata = extractor.extract_metadata()

# Write outputs
write_outputs(
    extractor,
    base_filename="my_output",
    ndjson=True,
    output_dir="./outputs/"
)

print(f"Extracted {len(extractor.chunks)} chunks")
print(f"Quality: {extractor.quality_score} ({extractor.route})")
```

## Summary

Migrating to the new extraction library is straightforward:

1. Replace `python book_parser_no_footnotes.py` with `extract`
2. Update imports: `from src.extraction.extractors import ...`
3. Enjoy multi-format support and better architecture!

The new library is **production-ready** with comprehensive tests and full backward compatibility.
