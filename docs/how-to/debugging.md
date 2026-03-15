# Debugging Extraction Issues

This guide helps you diagnose and fix common extraction problems.

## Quick Diagnostics

Start here when something goes wrong:

```bash
# Enable verbose logging
extract document.epub --verbose

# Enable debug dumps (EPUB only)
extract book.epub --debug-dump

# Check output files were created
ls -lh output.json

# Validate JSON structure
jq '.metadata.title' output.json
jq '.chunks | length' output.json
```

## Common Issues

### Empty or Missing Output

**Symptom**: No output file created or empty JSON.

#### Diagnosis

```bash
# Run with verbose logging
extract document.epub --verbose

# Check for error messages
extract document.epub 2>&1 | grep -i error
```

#### Common Causes

**1. File format not supported**

```bash
# Check file extension
file document.epub
# Output: document.epub: Zip archive data

# Try explicit format
extract document.epub  # Auto-detects EPUB
```

**2. Corrupted file**

```bash
# For EPUB (should be valid zip)
unzip -t document.epub

# For PDF
pdfinfo document.pdf
```

**3. Empty document**

```python
from extraction.extractors import EpubExtractor

extractor = EpubExtractor("document.epub")
extractor.load()
extractor.parse()

print(f"Chunks: {len(extractor.chunks)}")
print(f"Full text length: {len(extractor.full_text)}")
```

**Solution**: If chunks is 0, the document may have:

- No extractable text (images only)
- Content in unsupported format
- Extraction filter removing all chunks (try `--no-filter-noise`)

### Missing Hierarchy

**Symptom**: All chunks have empty hierarchy fields.

#### Diagnosis

```bash
# Check hierarchy in output
jq '.chunks[0].hierarchy' output.json
# {"level_1": "", "level_2": "", ...}

# Enable debug dump (EPUB only)
extract book.epub --debug-dump
cat debug/toc_structure.txt
```

#### Common Causes

**1. EPUB: Hierarchy not preserved across spine documents**

```bash
# Fix: Enable hierarchy preservation
extract book.epub --preserve-hierarchy
```

**2. PDF: Heading detection failed**

PDFs have no semantic structure. Headings are detected by font size.

```python
from extraction.extractors import PdfExtractor

# Default threshold may be too high
extractor = PdfExtractor("document.pdf", config={
    'heading_font_threshold': 1.2  # Default
})

# Try lower threshold
extractor = PdfExtractor("document.pdf", config={
    'heading_font_threshold': 1.1  # More sensitive
})
```

**3. HTML: No heading tags**

```bash
# Check HTML structure
grep -i '<h[1-6]' document.html

# If no headings, hierarchy will be empty (expected)
```

**Solution**:

```python
# For documents without headings, use flat structure
extractor = HtmlExtractor("document.html")
extractor.load()
extractor.parse()

# Chunks will have empty hierarchy (this is correct)
for chunk in extractor.chunks[:5]:
    print(f"Text: {chunk.text[:50]}...")
    print(f"Hierarchy: {chunk.hierarchy}")  # All empty
```

### Quality Score Too Low

**Symptom**: `metadata.quality.score` is below 0.7 (Route B or C).

#### Diagnosis

```bash
# Check quality signals
jq '.metadata.quality' output.json
```

Example output:

```json
{
  "score": 0.42,
  "route": "C",
  "signals": {
    "avg_para_len": 15.2,
    "heading_density": 0.45,
    "vocabulary_richness": 0.23,
    "scripture_density": 0.0,
    "cross_ref_density": 0.0
  }
}
```

#### Common Causes

**1. Very short paragraphs** (avg_para_len < 20)

Symptom: Many tiny chunks, low average paragraph length.

```python
# Increase minimum paragraph filter
extractor = EpubExtractor("book.epub", config={
    'min_paragraph_words': 10  # Filter out paragraphs < 10 words
})
```

**2. Too many or too few headings** (heading_density)

Optimal: 0.05-0.15 (1 heading per 6-20 paragraphs)

- Too high: Document is mostly headings (TOC, index)
- Too low: Flat structure, no organization

**Solution**: This is usually correct for the document. If it's a TOC/index, consider filtering it out:

```bash
# Enable noise filtering (default)
extract document.epub  # Already enabled

# Or process only specific sections
# (no built-in solution, would need custom preprocessing)
```

**3. Low vocabulary richness** (< 0.3)

Symptom: Repetitive text, few unique words.

This is often correct (e.g., legal boilerplate, form letters). No fix needed unless it's a data quality issue.

**4. Domain-specific signals missing**

Scripture/cross-reference density only matter for Catholic analyzer. For other domains:

```python
# Use generic analyzer (ignores these signals)
extract document.pdf --analyzer generic
```

### PDF Heading Detection Issues

**Symptom**: PDFs have no hierarchy or incorrect heading levels.

#### Diagnosis

```python
from extraction.extractors import PdfExtractor

# Extract with default settings
extractor = PdfExtractor("document.pdf")
extractor.load()
extractor.parse()

# Check if any headings detected
headings = [
    chunk for chunk in extractor.chunks
    if any(chunk.hierarchy.values())
]
print(f"Chunks with hierarchy: {len(headings)}/{len(extractor.chunks)}")
```

#### Solutions

**1. Lower font size threshold**

```python
# Default: 1.2 (heading font must be 20% larger than body)
extractor = PdfExtractor("document.pdf", config={
    'heading_font_threshold': 1.1  # More sensitive
})

# Or very sensitive
extractor = PdfExtractor("document.pdf", config={
    'heading_font_threshold': 1.05  # Detects small differences
})
```

**2. PDF has same font size for all text**

Some PDFs use bold/color instead of font size for headings. The library cannot detect these.

**Workaround**: Convert to HTML first:

```bash
# Use pdftohtml (install from poppler-utils)
pdftohtml -c document.pdf document.html

# Extract from HTML (preserves bold as headings in some cases)
extract document.html
```

**3. Scanned PDF (images, no text)**

```bash
# Check if PDF has text
pdftotext document.pdf - | head

# If empty, PDF is scanned images
# Solution: Enable OCR
```

```python
extractor = PdfExtractor("scanned.pdf", config={
    'use_ocr': True  # Requires tesseract
})
```

Install tesseract:

```bash
# macOS
brew install tesseract

# Ubuntu
sudo apt-get install tesseract-ocr

# Verify
tesseract --version
```

### Debug Mode (EPUB Only)

EPUB extractor supports detailed debug output.

#### Enable Debug Dump

```bash
extract book.epub --debug-dump
```

Creates `./debug/` directory with:

- `spine_structure.txt`: EPUB spine document ordering
- `toc_structure.txt`: Table of contents hierarchy
- `chunks_*.txt`: Per-document chunk dumps

#### Example: Investigating Hierarchy Issues

```bash
# Extract with debug dump
extract book.epub --debug-dump --preserve-hierarchy

# Check TOC structure
cat debug/toc_structure.txt
```

Example output:

```
Table of Contents Structure:
- Introduction (level 1)
  - Background (level 2)
  - Purpose (level 2)
- Chapter 1 (level 1)
  - Section 1.1 (level 2)
    - Subsection 1.1.1 (level 3)
```

**Compare with chunk hierarchy**:

```bash
# Check if TOC headings appear in chunks
jq '.chunks[0:10] | .[] | .hierarchy' output.json
```

**Common issues**:

- TOC headings not appearing: Wrong `toc_hierarchy_level` setting
- Hierarchy resets at chapter boundaries: Need `--preserve-hierarchy`

#### TOC Hierarchy Level

EPUBs have a separate Table of Contents. By default, TOC titles populate `level_1`.

```python
# Default: TOC titles go to level_1
extractor = EpubExtractor("book.epub", config={
    'toc_hierarchy_level': 1  # Default
})

# If TOC has chapters (level 1) and sections (level 2):
extractor = EpubExtractor("book.epub", config={
    'toc_hierarchy_level': 2  # TOC sections go to level_2
})
```

Check debug output:

```bash
cat debug/toc_structure.txt
# See how many levels TOC has

cat debug/chunks_001.txt
# See what hierarchy chunks have
```

### State Machine Errors

**Symptom**: Errors mentioning "InvalidTransitionError" or "StateMachine".

The extraction library doesn't use a state machine by default. If you see this error, you may have:

1. Custom code using `src/extraction/state.py`
2. Outdated library version

**Solution**:

```bash
# Update to latest version
uv pip install -e .

# Check version
python -c "import extraction; print(extraction.__version__)"
```

If using state machine in custom code:

```python
from extraction.state import StateMachine

# Ensure valid transitions
# See src/extraction/state.py for details
```

### Logging and Verbosity

#### Enable Verbose Logging

```bash
# CLI
extract document.epub --verbose

# See all debug messages
extract document.epub --verbose 2>&1 | less
```

#### Python Logging

```python
import logging

# Enable debug logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s %(name)s %(levelname)s: %(message)s'
)

from extraction.extractors import EpubExtractor

extractor = EpubExtractor("book.epub")
extractor.load()  # Will log detailed debug info
extractor.parse()
```

#### Logging Levels

- `DEBUG`: Detailed internal state
- `INFO`: High-level progress
- `WARNING`: Potential issues (missing metadata, etc.)
- `ERROR`: Extraction failures

### Checking Output Structure

#### Validate JSON

```bash
# Check JSON is valid
jq '.' output.json > /dev/null && echo "Valid JSON"

# Check metadata exists
jq '.metadata' output.json

# Check chunks exist
jq '.chunks | length' output.json

# Inspect first chunk
jq '.chunks[0]' output.json
```

#### Required Fields

Every extraction output should have:

```json
{
  "metadata": {
    "title": "...",
    "author": "...",
    "provenance": {
      "doc_id": "...",
      "source_file": "..."
    },
    "quality": {
      "score": 0.0-1.0,
      "route": "A|B|C"
    }
  },
  "chunks": [
    {
      "stable_id": "...",
      "text": "...",
      "hierarchy": {...},
      "word_count": 0
    }
  ]
}
```

#### Check for Missing Fields

```bash
# Check if any chunks missing hierarchy
jq '.chunks | map(select(.hierarchy == null or .hierarchy == {})) | length' output.json

# Check if any chunks missing text
jq '.chunks | map(select(.text == null or .text == "")) | length' output.json
```

### Performance Issues

**Symptom**: Extraction taking too long or using too much memory.

#### Diagnosis

```bash
# Time extraction
time extract large_document.epub

# Monitor memory (macOS)
/usr/bin/time -l extract large_document.epub

# Monitor memory (Linux)
/usr/bin/time -v extract large_document.epub
```

#### Solutions

**1. Large PDFs**

```python
# Disable OCR (if enabled)
extractor = PdfExtractor("huge.pdf", config={
    'use_ocr': False
})

# Or extract page ranges (not built-in, would need custom code)
```

**2. Many small files (batch processing)**

```bash
# Process in parallel (not built-in)
# Use GNU parallel or xargs

find documents/ -name "*.epub" | parallel -j 4 extract {} --output-dir outputs/
```

**3. Memory usage**

Large documents may use significant memory. This is expected.

**Workaround**: Process files one at a time instead of batch:

```bash
# Instead of:
# extract documents/*.epub -r  # Loads all into memory

# Do:
for file in documents/*.epub; do
    extract "$file" --output-dir outputs/
done
```

## Getting Help

If you're still stuck:

1. Check existing issues: [GitHub Issues](https://github.com/hello-world-bfree/extraction/issues)
2. Create minimal reproduction:

```python
from extraction.extractors import EpubExtractor

extractor = EpubExtractor("problem.epub")
extractor.load()
extractor.parse()

print(f"Chunks: {len(extractor.chunks)}")
print(f"Metadata: {extractor.extract_metadata()}")
```

3. Include version info:

```bash
python --version
uv --version
extract --version  # If available
```

4. Provide sample file (if possible) or describe document structure

## Next Steps

- For chunking strategy issues, see [Chunking Strategy Guide](chunking-strategy.md)
- For analyzer issues, see [Custom Analyzers Guide](custom-analyzers.md)
- For production debugging, see test suite: `tests/test_*.py`
