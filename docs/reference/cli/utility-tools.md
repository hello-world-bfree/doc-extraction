# Utility Tools

Standalone tools for hierarchy repair, Vatican archive processing, image extraction, and token-based re-chunking. These complement the primary [`extract`](extract.md) command with specialized workflows.

---

## `fix-hierarchy`

### Synopsis

```bash
fix-hierarchy [OPTIONS] FILE
```

### Description

Repairs heading hierarchy levels in extraction JSON outputs without requiring re-extraction. When chunks were extracted with an incorrect `toc_hierarchy_level` config (e.g., old default of 3 instead of current default of 1), this tool shifts hierarchy levels down in-place, preserving all annotations and edits.

The tool:

- Shifts hierarchy levels down by a specified amount (e.g., `level_3` becomes `level_2`)
- Preserves `level_1` (book title) by default
- Updates `hierarchy_depth` and `heading_path` fields to match
- Creates a `.json.backup` file before modifying

### Options

| Option | Description | Default |
|--------|-------------|---------|
| `FILE` | Path to chunks JSON file. | Required |
| `--shift-down N` | Number of levels to shift down. For example, `1` shifts `level_3` to `level_2`. Must be >= 1. | `1` |
| `--no-backup` | Do not create a backup file before modifying. | Backup enabled |
| `--dry-run` | Show what would change without modifying the file. | Disabled |

### Examples

Preview changes without modifying:

```bash
fix-hierarchy output.json --dry-run
```

Apply a one-level shift (creates backup automatically):

```bash
fix-hierarchy output.json --shift-down 1
```

Shift two levels down without backup:

```bash
fix-hierarchy output.json --shift-down 2 --no-backup
```

---

## `vatican-extract`

### Synopsis

```bash
vatican-extract [OPTIONS]
```

### Description

Specialized pipeline for downloading and extracting English documents from the Vatican archive (vatican.va). Supports selective section processing, cloud upload to AWS S3 or Cloudflare R2, checkpoint-based resume for interrupted runs, and rate limiting.

The pipeline stages are: **discover** (find documents on vatican.va), **download** (fetch HTML), **process** (extract and chunk), and optionally **upload** (push to cloud storage).

### Options

#### Working Directory

| Option | Description | Default |
|--------|-------------|---------|
| `--work-dir DIR` | Working directory for downloads and outputs. | `./vatican_archive` |

#### Pipeline Stages

| Option | Description |
|--------|-------------|
| `--discover-only` | Only discover documents, don't download or process. |
| `--download-only` | Only download documents, don't process. |
| `--process-only` | Only process already-downloaded documents. |
| `--resume` | Resume interrupted extraction from checkpoint. |

#### Cloud Upload

| Option | Description |
|--------|-------------|
| `--upload` | Upload processed outputs to S3/R2. Requires environment variables (see below). |
| `--upload-to-r2` | Alias for `--upload`. |
| `--no-upload` | Skip upload even if cloud storage is configured. |

Cloud upload reads credentials from environment variables:

**AWS S3**: `AWS_ACCESS_KEY_ID` (or `S3_ACCESS_KEY_ID`), `AWS_SECRET_ACCESS_KEY` (or `S3_SECRET_ACCESS_KEY`), `S3_BUCKET_NAME`, `AWS_REGION` (optional, default: `us-east-1`).

**Cloudflare R2**: `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, `R2_ENDPOINT_URL`, `R2_BUCKET_NAME`.

#### Filtering

| Option | Description | Default |
|--------|-------------|---------|
| `--sections SECTION [SECTION ...]` | Only process specific sections (see available sections below). | All sections |
| `--limit N` | Limit number of documents to process (for testing). | Unlimited |

#### Performance

| Option | Description | Default |
|--------|-------------|---------|
| `--rate-limit SECONDS` | Seconds between requests. | `1.0` |

#### Cleanup

| Option | Description |
|--------|-------------|
| `--cleanup-downloads` | Remove local downloads after successful upload. |

#### Logging

| Option | Description | Default |
|--------|-------------|---------|
| `-v, --verbose` | Verbose logging (DEBUG level). | INFO level |
| `-q, --quiet` | Quiet mode (WARNING level only). | INFO level |

### Available Sections

| Section | Description |
|---------|-------------|
| `BIBLE` | Sacred Scripture |
| `CATECHISM` | Catechism of the Catholic Church |
| `CANON_LAW` | Code of Canon Law |
| `COUNCILS` | Ecumenical Council documents |
| `MAGISTERIUM` | Magisterial documents |
| `SOCIAL` | Social doctrine |

### Examples

Process Bible and Catechism sections:

```bash
vatican-extract --sections BIBLE CATECHISM
```

Upload to cloud storage after processing:

```bash
vatican-extract --upload
```

Resume an interrupted extraction:

```bash
vatican-extract --resume
```

Download only with a document limit (for testing):

```bash
vatican-extract --download-only --limit 10
```

Process previously downloaded files and upload to R2:

```bash
vatican-extract --process-only --upload-to-r2
```

---

## `extract-images`

### Synopsis

```bash
extract-images [OPTIONS] URL
```

### Description

Scrapes images from websites and optionally creates EPUB photo galleries or uploads to S3. Supports static (Requests + BeautifulSoup), dynamic (Playwright), and auto-detecting scraper modes. Includes quality filtering by image dimensions and file size, WebP-to-PNG conversion, and SVG support.

### Options

#### Input/Output

| Option | Description | Default |
|--------|-------------|---------|
| `URL` | URL of the website to scrape images from. | Required |
| `--output PATH` | Output EPUB file path. Implies EPUB generation. | `./output.epub` |
| `--output-dir DIR` | Directory to save scraped images. | `./images` |
| `--no-epub` | Skip EPUB generation, just download images. | EPUB enabled |

#### Scraper

| Option | Description | Default |
|--------|-------------|---------|
| `--scraper-type {auto,static,dynamic}` | Type of scraper. `auto` tries static first then falls back to dynamic. `static` uses Requests + BeautifulSoup. `dynamic` uses Playwright. | `auto` |

#### EPUB Metadata

| Option | Description | Default |
|--------|-------------|---------|
| `--title TITLE` | EPUB title. | `Image Gallery` |
| `--author AUTHOR` | EPUB author. | `Web Scraper` |

#### Image Filtering

| Option | Description | Default |
|--------|-------------|---------|
| `--min-image-size KB` | Minimum image file size in KB. | `10` |
| `--max-images N` | Maximum number of images to extract. | Unlimited |
| `--min-width PX` | Minimum image width in pixels. | `200` |
| `--min-height PX` | Minimum image height in pixels. | `200` |
| `--no-quality-check` | Disable quality filtering (keep all images regardless of size). | Quality check enabled |
| `--include-svg` | Include SVG images. | SVG excluded |
| `--no-convert-webp` | Don't convert WebP images to PNG. | WebP converted |

#### S3 Upload

| Option | Description | Default |
|--------|-------------|---------|
| `--upload-s3` | Upload images to S3 (requires `--s3-bucket`). | Disabled |
| `--s3-bucket NAME` | S3 bucket name. Required if `--upload-s3` is set. | None |
| `--s3-prefix PREFIX` | S3 key prefix. | `images/` |
| `--s3-region REGION` | S3 region. | `us-east-1` |
| `--s3-public` | Make S3 uploads public. | Private |

### Examples

Scrape images and build an EPUB gallery:

```bash
extract-images https://example.com/gallery --title "Gallery" --output gallery.epub
```

Download images only without EPUB:

```bash
extract-images https://example.com/photos --output-dir ./images --no-epub
```

Use dynamic scraper with size limits:

```bash
extract-images https://example.com/gallery --scraper-type dynamic --min-image-size 50 --max-images 50
```

Scrape and upload to S3:

```bash
extract-images https://example.com --output photos.epub --upload-s3 --s3-bucket my-bucket
```

---

## `token-rechunk`

### Synopsis

```bash
token-rechunk [OPTIONS] FILE
```

### Description

Transforms word-based extraction JSON into token-optimized JSONL chunks for embedding models (default tokenizer: `google/embeddinggemma-300m`). Three preset modes optimize for different use cases. Supports sentence-aware overlap, hierarchy preservation, and custom token ranges.

Output is JSONL where each line contains `text` and `metadata` (doc_id, source_file, hierarchy, token_count, source_chunk_id, sentence_count, is_overlap).

### Modes

| Mode | Token Range | Overlap | Use Case |
|------|-------------|---------|----------|
| `retrieval` | 256-400 | 15% | Precision search, RAG |
| `recommendation` | 512-700 | 10% | Context-rich recommendations |
| `balanced` | 400-512 | 10% | General purpose (default) |

### Options

| Option | Description | Default |
|--------|-------------|---------|
| `FILE` | Input JSON file from extraction library. | Required |
| `-o, --output PATH` | Output JSONL file. | `<input>_tokenized.jsonl` |
| `--mode {retrieval,recommendation,balanced}` | Chunking mode preset. | `balanced` |
| `--min-tokens N` | Minimum tokens per chunk. Overrides mode preset. | Preset value |
| `--max-tokens N` | Maximum tokens per chunk. Overrides mode preset. | Preset value |
| `--overlap-percent FLOAT` | Overlap percentage between chunks (0.0-1.0). Overrides mode preset. | Preset value |
| `--no-overlap` | Disable chunk overlap entirely. | Overlap enabled |
| `--preserve-metadata` | Preserve scripture_references, cross_references, and dates_mentioned from source chunks. | Disabled |
| `--stats` | Print token statistics after processing. | Disabled |
| `-v, --verbose` | Verbose logging (DEBUG level). | INFO level |

### Examples

Re-chunk for RAG retrieval:

```bash
token-rechunk document.json --mode retrieval
```

Re-chunk for recommendations:

```bash
token-rechunk document.json --mode recommendation
```

Custom token range with statistics:

```bash
token-rechunk document.json --min-tokens 300 --max-tokens 500 --stats
```

Preserve domain metadata and disable overlap:

```bash
token-rechunk document.json --mode retrieval --preserve-metadata --no-overlap
```

Specify output path:

```bash
token-rechunk document.json --mode balanced -o chunks_balanced.jsonl
```

---

## See Also

- [Token Rechunking Guide](../../how-to/token-rechunking.md) -- detailed how-to
- [extract](extract.md) -- primary extraction CLI
