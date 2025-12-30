# Vatican Archive Extraction Pipeline

Complete implementation of a pipeline to extract all English HTML documents from the Vatican archive (https://www.vatican.va/archive/index.htm) for use as LLM chatbot context.

## Features

### Core Components

1. **Document Index** (`src/extraction/pipelines/vatican/index.py`)
   - Persistent JSON-based document tracking
   - Tracks discovery, download, processing, and upload status
   - Resume capability for interrupted extractions

2. **Vatican Archive Scraper** (`src/extraction/pipelines/vatican/scraper.py`)
   - Multi-layered English document detection
   - Respectful rate-limited crawling (1 req/sec default)
   - Automatic section discovery and navigation

3. **HTML Downloader** (`src/extraction/pipelines/vatican/downloader.py`)
   - Retry logic with exponential backoff
   - Content validation (HTML structure, size)
   - Progress tracking with tqdm

4. **R2 Storage Manager** (`src/extraction/pipelines/vatican/storage.py`)
   - Cloudflare R2 integration via boto3
   - Organized path structure by section
   - Upload for JSON and NDJSON outputs

5. **Pipeline Processor** (`src/extraction/pipelines/vatican/processor.py`)
   - Orchestrates: discover → download → extract → upload
   - Integrates with existing HTML extractor and Catholic analyzer
   - Section filtering and batch processing

6. **CLI Interface** (`src/extraction/cli/vatican_extract.py`)
   - User-friendly command-line interface
   - Multiple operation modes (discover, download, process, upload)
   - Resume capability

## Installation

```bash
# Install with Vatican pipeline dependencies
uv pip install -e ".[vatican]"
```

This installs:
- `requests>=2.31.0` - HTTP client for web scraping
- `boto3>=1.34.0` - S3/R2 client for cloud storage

## Usage

### Quick Start

```bash
# Set R2 credentials (required for upload)
export R2_ACCESS_KEY_ID="your_key"
export R2_SECRET_ACCESS_KEY="your_secret"
export R2_ENDPOINT_URL="https://[account-id].r2.cloudflarestorage.com"
export R2_BUCKET_NAME="vatican-documents"

# Run complete pipeline with R2 upload
vatican-extract --upload-to-r2 --verbose
```

### Common Workflows

**Test with small sample:**
```bash
vatican-extract --limit 10 --verbose
```

**Discovery only:**
```bash
vatican-extract --discover-only
cat vatican_archive/index.json | jq '.statistics'
```

**Process specific sections:**
```bash
vatican-extract --sections CATECHISM COUNCILS --upload-to-r2
```

**Resume interrupted extraction:**
```bash
vatican-extract --resume --upload-to-r2
```

**Process locally without R2:**
```bash
vatican-extract
# Outputs to: vatican_archive/outputs/temp/
```

### Pipeline Stages

The pipeline runs in 4 stages:

1. **Discovery**: Scrape Vatican archive for English HTML documents
2. **Download**: Download HTML files to local temp directory
3. **Processing**: Extract using existing HTML extractor + Catholic analyzer
4. **Upload**: Upload JSON/NDJSON to R2 (optional)

Each stage can be run independently with flags like `--discover-only`, `--download-only`, `--process-only`.

## Output Format

### For RAG (Vector Database)
Use NDJSON files - each line is a standalone chunk:

```json
{
  "stable_id": "abc123...",
  "text": "Full paragraph text...",
  "hierarchy": {
    "level_1": "Part One",
    "level_2": "Section Two",
    "level_3": "Chapter One"
  },
  "scripture_references": ["John 3:16"],
  "cross_references": ["CCC 1234"],
  "word_count": 142,
  "metadata": {
    "title": "Catechism of the Catholic Church",
    "section": "CATECHISM",
    "document_type": "Catechism"
  }
}
```

### For Direct Context
Use JSON files with complete document structure and metadata.

### R2 Organization

```
vatican/
├── bible/
│   ├── genesis/
│   │   ├── chapter_01.json
│   │   └── chapter_01.ndjson
├── catechism/
│   ├── ccc.json
│   └── ccc.ndjson
├── councils/
│   ├── vatican_ii/
│   │   ├── lumen_gentium.json
│   │   └── lumen_gentium.ndjson
├── magisterium/
│   └── encyclicals/
└── index.json  # Master index
```

## Expected Results

- **Documents**: 1,000+ English documents
- **Sections**: 6 main categories (Bible, Catechism, Councils, Canon Law, Magisterium, Social Doctrine)
- **Size**: ~18 GB in R2 (9 GB JSON, 9 GB NDJSON)
- **Runtime**: 24-30 hours for complete extraction
- **Success Rate**: Expected 95%+ (some documents may be missing or moved)

## Testing

```bash
# Run all tests
uv run pytest tests/test_vatican_pipeline.py -v

# Run without integration tests
uv run pytest tests/test_vatican_pipeline.py -v -m "not integration"

# Test coverage
uv run pytest tests/test_vatican_pipeline.py --cov=src/extraction/pipelines/vatican
```

**Test Results**: 19 passed, 1 skipped (network-dependent test)

## Monitoring

The pipeline creates several monitoring files:

- `vatican_archive/index.json` - Complete document index with statistics
- `vatican_archive/progress.json` - Real-time progress updates
- `vatican_archive/logs/` - Detailed logs
- `vatican_archive/summary.json` - Final run summary

## Troubleshooting

### No R2 credentials

```
ValueError: Missing required R2 environment variables
```

**Solution**: Set all required R2 environment variables (see Quick Start above)

### Network timeout

The scraper uses 30-second timeouts and automatic retry with exponential backoff. If timeouts persist, increase rate limit:

```bash
vatican-extract --rate-limit 2.0  # Slower, more conservative
```

### Disk space

Downloads require ~10 GB local storage. Use `--cleanup-downloads` to remove after upload:

```bash
vatican-extract --upload-to-r2 --cleanup-downloads
```

### Resume after interruption

The index is saved after each batch. Simply run:

```bash
vatican-extract --resume
```

## Architecture Details

### English Detection Strategy

Multi-layered approach:
1. URL pattern matching (`/ENG####/`, `*_en.html`)
2. HTML `lang` attribute
3. Meta tags (`content-language`)
4. Content keywords ("English", "New American Bible")

### Document Type Inference

Pattern matching on titles:
- Encyclical, Apostolic Letter, Constitution, Decree
- Catechism, Scripture, Canon Law
- Falls back to "Document" if unrecognized

### Rate Limiting

- Default: 1 request/second
- Configurable via `--rate-limit`
- Respects server load and avoids blocking

## Next Steps

1. **Set up R2 bucket** and obtain credentials
2. **Test with small sample**: `vatican-extract --limit 10`
3. **Run discovery**: `vatican-extract --discover-only`
4. **Execute full extraction**: `vatican-extract --upload-to-r2`
5. **Monitor progress**: Check `vatican_archive/progress.json`
6. **Verify outputs**: Review `vatican_archive/index.json` statistics

## Integration with Existing Tools

The Vatican pipeline integrates seamlessly with the existing extraction infrastructure:

- Uses `HtmlExtractor` for document processing
- Uses `CatholicAnalyzer` for metadata enrichment
- Generates same output format as other extractors (JSON + NDJSON)
- Leverages existing `write_outputs()` function

No changes needed to existing extractors or analyzers.

## Development

### Adding New Features

The modular design makes it easy to extend:

- **New document sources**: Subclass `scraper.py` and modify URL patterns
- **New storage backends**: Implement interface similar to `storage.py`
- **Custom analyzers**: Already supported via `--analyzer` flag

### File Structure

```
src/extraction/pipelines/vatican/
├── __init__.py          # Package exports
├── index.py             # Document tracking (~250 LOC)
├── scraper.py           # Web scraping (~400 LOC)
├── downloader.py        # Download manager (~300 LOC)
├── processor.py         # Pipeline orchestrator (~500 LOC)
└── storage.py           # R2 upload (~200 LOC)

src/extraction/cli/
└── vatican_extract.py   # CLI interface (~200 LOC)

tests/
└── test_vatican_pipeline.py  # Tests (~500 LOC)
```

**Total**: ~2,350 lines of new code (implementation + tests)

## License

Same as parent project.
