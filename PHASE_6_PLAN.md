# Phase 6: Additional Extractors Implementation Plan

## Goal
Extend the extraction system to support PDF, HTML, and Markdown formats, completing the multi-format document extraction capability.

## Current State
- ✅ BaseExtractor abstract class (src/extraction/extractors/base.py)
- ✅ EpubExtractor fully implemented and tested
- ✅ CLI with format detection (currently only supports EPUB)
- ✅ Optional PDF dependencies already defined in pyproject.toml

## Phase 6 Extractors to Implement

### 1. PDF Extractor (`src/extraction/extractors/pdf.py`)
**Priority**: High (most requested format)

**Approach**:
- Use `pdfplumber` for primary text extraction (better than PyPDF2 for layout)
- Support OCR fallback with `pytesseract` for scanned PDFs
- Extract text page-by-page, preserving some structure
- Detect headings based on font size/style differences
- Handle multi-column layouts

**Key Features**:
- Page-based chunking (each page as a potential chunk)
- Optional OCR for images/scanned pages
- Font-based heading detection
- Table extraction support

**Configuration**:
```python
{
    "min_paragraph_words": 5,
    "use_ocr": False,  # Enable OCR for scanned PDFs
    "ocr_lang": "eng",
    "heading_font_threshold": 1.2,  # Font size ratio for heading detection
}
```

### 2. HTML Extractor (`src/extraction/extractors/html.py`)
**Priority**: Medium

**Approach**:
- Use BeautifulSoup (already used in EPUB extractor)
- Similar to EPUB but for standalone HTML files
- Respect existing HTML hierarchy (h1-h6 tags)
- Extract text from paragraphs, preserving structure

**Key Features**:
- HTML tag-based chunking
- Hierarchy extraction from h1-h6 tags
- Clean HTML entities and formatting
- Extract metadata from <meta> tags

**Configuration**:
```python
{
    "min_paragraph_words": 1,
    "preserve_links": False,
    "extract_tables": False,
}
```

### 3. Markdown Extractor (`src/extraction/extractors/markdown.py`)
**Priority**: Medium

**Approach**:
- Parse markdown structure (headings, paragraphs)
- Use markdown library or simple regex parsing
- Convert to chunks based on heading hierarchy
- Preserve code blocks, lists as separate chunks

**Key Features**:
- Markdown heading hierarchy (# ## ###)
- Preserve code blocks
- Handle lists and blockquotes
- Extract front matter (YAML/TOML) if present

**Configuration**:
```python
{
    "min_paragraph_words": 1,
    "preserve_code_blocks": True,
    "extract_frontmatter": True,
}
```

## Implementation Order

### Step 1: PDF Extractor (Most Complex)
1. Create `src/extraction/extractors/pdf.py`
2. Implement PdfExtractor class inheriting from BaseExtractor
3. Page-based extraction with pdfplumber
4. Font-based heading detection
5. Basic tests

### Step 2: HTML Extractor (Leverage EPUB code)
1. Create `src/extraction/extractors/html.py`
2. Implement HtmlExtractor (simpler than EPUB, no spine/TOC)
3. Reuse BeautifulSoup parsing logic from EPUB
4. Basic tests

### Step 3: Markdown Extractor (Simplest)
1. Create `src/extraction/extractors/markdown.py`
2. Implement MarkdownExtractor with regex-based parsing
3. Handle heading hierarchy
4. Basic tests

### Step 4: CLI Integration
1. Update `src/extraction/cli/extract.py` to instantiate new extractors
2. Update format detection (already in place)
3. Add format-specific help examples

### Step 5: Testing
1. Create test files for each extractor
2. Add integration tests with sample documents
3. Update test coverage report

## Technical Decisions

### PDF Extractor: pdfplumber vs PyPDF2
**Decision**: Use pdfplumber as primary
**Rationale**: Better layout preservation, easier table extraction, more reliable text extraction

### HTML Parser: BeautifulSoup
**Decision**: Reuse BeautifulSoup from EPUB extractor
**Rationale**: Already a dependency, proven to work, handles malformed HTML

### Markdown Parser: Custom vs Library
**Decision**: Start with simple regex parser, add markdown library if needed
**Rationale**: Markdown is simpler than HTML/PDF, regex sufficient for basic hierarchy

### OCR Support: Optional
**Decision**: Make OCR opt-in via configuration
**Rationale**: Requires Tesseract installation, adds complexity, not needed for most PDFs

## Backward Compatibility

All new extractors must:
- Follow BaseExtractor interface
- Use core utilities for text processing
- Output same chunk/metadata structure as EPUB
- Support analyzer plugins (Catholic, etc.)
- Maintain quality scoring and routing

## Success Criteria

Phase 6 is complete when:
- [ ] PDF extractor extracts text and creates chunks
- [ ] HTML extractor processes standalone HTML files
- [ ] Markdown extractor handles .md files
- [ ] CLI can process all 4 formats (EPUB, PDF, HTML, MD)
- [ ] All extractors have basic tests
- [ ] At least one sample document processed for each format
- [ ] Documentation updated with examples

## File Structure After Phase 6

```
src/extraction/extractors/
├── __init__.py
├── base.py (existing)
├── epub.py (existing)
├── pdf.py (NEW)
├── html.py (NEW)
└── markdown.py (NEW)

tests/
├── test_extractors.py (update)
├── test_pdf_extractor.py (NEW)
├── test_html_extractor.py (NEW)
└── test_markdown_extractor.py (NEW)
```

## Estimated Scope
- PDF Extractor: ~300 lines
- HTML Extractor: ~200 lines
- Markdown Extractor: ~150 lines
- CLI Updates: ~50 lines
- Tests: ~400 lines
- **Total**: ~1,100 lines of code

## Dependencies to Install

```bash
uv pip install pdfplumber  # PDF support
uv pip install markdown    # MD parsing (if using library)
# pytesseract only if OCR needed
```

## Next Steps

1. Install PDF dependencies
2. Create PDF extractor skeleton
3. Implement basic PDF text extraction
4. Add HTML extractor
5. Add Markdown extractor
6. Update CLI
7. Add tests
8. Create checkpoint
