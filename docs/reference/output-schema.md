# Output Schema Reference

Complete reference for JSON output format produced by all extractors.

## Overview

All extractors produce identical JSON output regardless of input format (EPUB, PDF, HTML, Markdown, JSON). The output consists of three top-level sections:

```json
{
  "metadata": { ... },
  "chunks": [ ... ],
  "extraction_info": { ... }
}
```

## Document Structure

### Top-Level Fields

| Field | Type | Description |
|-------|------|-------------|
| `metadata` | `object` | Document-level metadata (title, author, quality, provenance) |
| `chunks` | `array` | List of text chunks (paragraphs or merged chunks) |
| `extraction_info` | `object` | Extraction statistics and processing metadata |

## Metadata Object

Document-level metadata with automatic domain enrichment.

### Core Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `title` | `string` | Yes | Document title (from EPUB metadata, PDF metadata, or filename) |
| `author` | `string` | Yes | Document author (may be "Unknown" if not available) |
| `description` | `string` | No | Document description or abstract |
| `language` | `string` | No | Language code (e.g., "en", "la", "fr") |
| `publisher` | `string` | No | Publisher name |
| `pages` | `string` | No | Estimated page count (e.g., "approximately 150") |
| `word_count` | `string` | No | Total word count (e.g., "approximately 42,000") |
| `md_schema_version` | `string` | Yes | Metadata schema version (e.g., "2025-09-08") |

### Domain-Enriched Fields

Added by analyzers (Catholic, Generic):

| Field | Type | Description |
|-------|------|-------------|
| `document_type` | `string` | Document classification (e.g., "Encyclical", "Apostolic Exhortation", "Book") |
| `date_promulgated` | `string` | Publication or promulgation date (e.g., "December 25, 2015") |
| `subject` | `array[string]` | Subject areas (e.g., `["Liturgy", "Sacraments", "Prayer"]`) |
| `key_themes` | `array[string]` | Major themes extracted from headings (max 10) |
| `related_documents` | `array[string]` | Related documents mentioned in text |
| `time_period` | `string` | Historical time period (if applicable) |
| `geographic_focus` | `string` | Geographic focus (e.g., "Vatican City (Rome)", "Universal Church") |

### Provenance Object

Tracking information for document origin and processing:

| Field | Type | Description |
|-------|------|-------------|
| `doc_id` | `string` | Stable document ID (SHA1 hash of path + mtime) |
| `source_file` | `string` | Original filename |
| `parser_version` | `string` | Extractor version (e.g., "2.0.0-refactored") |
| `md_schema_version` | `string` | Metadata schema version |
| `ingestion_ts` | `string` | ISO 8601 timestamp of processing |
| `content_hash` | `string` | SHA1 hash of raw source bytes |
| `normalized_hash` | `string` | SHA1 hash of normalized text (may differ from content_hash) |

### Quality Object

Quality scoring and routing information:

| Field | Type | Description |
|-------|------|-------------|
| `signals` | `object` | Quality signal values (see below) |
| `score` | `number` | Overall quality score (0.0 - 1.0) |
| `route` | `string` | Quality route: "A" (high), "B" (medium), "C" (low) |

**Quality Signals** (in `signals` object):

| Signal | Range | Description |
|--------|-------|-------------|
| `avg_para_len` | 0.0 - 1.0 | Average paragraph length (normalized) |
| `heading_density` | 0.0 - 1.0 | Ratio of headings to total paragraphs |
| `vocabulary_richness` | 0.0 - 1.0 | Unique words / total words |
| `scripture_density` | 0.0 - 1.0 | Scripture references per 1000 words (Catholic analyzer) |
| `cross_ref_density` | 0.0 - 1.0 | Cross-references per 1000 words |

### Source Identifiers Object

Format-specific identifiers:

| Field | Type | Description |
|-------|------|-------------|
| `toc_map` | `object` | EPUB: Mapping of hrefs to TOC titles |
| `isbn` | `string` | ISBN if available |
| `doi` | `string` | DOI if available |

### Example Metadata

```json
{
  "metadata": {
    "title": "Prayer Primer",
    "author": "Thomas Dubay",
    "description": "A guide to Catholic prayer and contemplation",
    "language": "en",
    "publisher": "Ignatius Press",
    "pages": "approximately 120",
    "word_count": "approximately 35,000",
    "md_schema_version": "2025-09-08",

    "document_type": "Book",
    "date_promulgated": "",
    "subject": ["Prayer", "Liturgy", "Contemplation"],
    "key_themes": [
      "Part I: The Nature of Prayer",
      "Chapter 1: What is Prayer?",
      "Chapter 2: Vocal and Mental Prayer"
    ],
    "related_documents": ["Catechism of the Catholic Church"],
    "time_period": "",
    "geographic_focus": "Universal Church",

    "provenance": {
      "doc_id": "abc123def456...",
      "source_file": "prayer_primer.epub",
      "parser_version": "2.0.0-refactored",
      "md_schema_version": "2025-09-08",
      "ingestion_ts": "2025-01-10T14:30:00",
      "content_hash": "sha1:abc123...",
      "normalized_hash": "sha1:def456..."
    },

    "quality": {
      "signals": {
        "avg_para_len": 0.85,
        "heading_density": 0.12,
        "vocabulary_richness": 0.78,
        "scripture_density": 0.05,
        "cross_ref_density": 0.03
      },
      "score": 0.82,
      "route": "A"
    },

    "source_identifiers": {
      "toc_map": {
        "chapter1.xhtml": "Chapter 1: What is Prayer?",
        "chapter2.xhtml": "Chapter 2: Vocal and Mental Prayer"
      }
    }
  }
}
```

---

## Chunks Array

List of text chunks (paragraphs or merged chunks depending on chunking strategy).

### Chunk Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `stable_id` | `string` | Yes | Stable chunk ID (SHA1 hash of href, order, para_id, text) |
| `paragraph_id` | `integer` | Yes | Sequential paragraph number (1-indexed) |
| `text` | `string` | Yes | Chunk text content (cleaned and normalized) |
| `hierarchy` | `object` | Yes | Current heading hierarchy (6 levels) |
| `chapter_href` | `string` | Yes | Source document identifier (EPUB: href, PDF: page_N) |
| `source_order` | `integer` | Yes | Source document order (EPUB: spine position, PDF: paragraph sequence) |
| `source_tag` | `string` | Yes | HTML tag or source type (e.g., "p", "blockquote", "li") |
| `text_length` | `integer` | Yes | Character count |
| `word_count` | `integer` | Yes | Word count |
| `cross_references` | `array[string]` | Yes | Internal document references (e.g., `["See Chapter 5"]`) |
| `scripture_references` | `array[string]` | Yes | Bible references (e.g., `["John 3:16", "Matthew 5:1-12"]`) |
| `dates_mentioned` | `array[string]` | Yes | Dates found in text |
| `heading_path` | `string` | Yes | Full heading path (e.g., "Part I / Chapter 1 / Section 1.1") |
| `hierarchy_depth` | `integer` | Yes | Number of non-empty hierarchy levels (0-6) |
| `doc_stable_id` | `string` | Yes | Document ID (same as `metadata.provenance.doc_id`) |
| `sentence_count` | `integer` | Yes | Number of sentences |
| `sentences` | `array[string]` | Yes | First 6 sentences (for preview) |
| `normalized_text` | `string` | Yes | ASCII-normalized text (lowercase) |

### Optional Chunk Fields

| Field | Type | When Present | Description |
|-------|------|--------------|-------------|
| `footnote_citations` | `object` | EPUB (if footnotes detected) | Footnote citation metadata (see below) |
| `resolved_footnotes` | `object` | EPUB (future feature) | Resolved footnote text |
| `ocr` | `boolean` | PDF (if OCR used) | Whether chunk was OCR'd |
| `ocr_conf` | `number` | PDF (if OCR used) | OCR confidence (0.0 - 1.0) |
| `merged_paragraph_ids` | `array[int]` | RAG strategy | IDs of paragraphs merged into this chunk |
| `source_paragraph_count` | `integer` | RAG strategy | Number of source paragraphs merged |

### Hierarchy Object

Six-level heading hierarchy (empty strings if level not set):

```json
{
  "level_1": "Part I: The Liturgy",
  "level_2": "Chapter 1: The Sacred Liturgy",
  "level_3": "Article 1: Nature of the Liturgy",
  "level_4": "",
  "level_5": "",
  "level_6": ""
}
```

**Hierarchy Rules**:

- Levels 1-6 correspond to HTML headings h1-h6 (or equivalent)
- Once a heading at level N is encountered, levels > N are cleared
- EPUB: TOC titles can be inserted at configurable level (`toc_hierarchy_level`)
- PDF: Headings detected via font size threshold
- Hierarchy flows across chunks unless reset at document boundaries

### Footnote Citations Object

EPUB-specific footnote metadata:

```json
{
  "footnote_citations": {
    "all": [1, 5, 10],
    "by_sentence": [
      {"index": 0, "numbers": [1]},
      {"index": 3, "numbers": [5, 10]}
    ]
  }
}
```

| Field | Type | Description |
|-------|------|-------------|
| `all` | `array[int]` | All footnote numbers in chunk (deduplicated) |
| `by_sentence` | `array[object]` | Per-sentence footnote locations |
| `by_sentence[].index` | `integer` | Sentence index (0-indexed) |
| `by_sentence[].numbers` | `array[int]` | Footnote numbers in that sentence |

### Example Chunk (NLP Strategy)

```json
{
  "stable_id": "abc123def456...",
  "paragraph_id": 42,
  "text": "The sacred liturgy is above all things the worship of the divine Majesty.",
  "hierarchy": {
    "level_1": "Part I: The Liturgy",
    "level_2": "Chapter 1: The Sacred Liturgy",
    "level_3": "Article 1: Nature of the Liturgy",
    "level_4": "",
    "level_5": "",
    "level_6": ""
  },
  "chapter_href": "chapter1.xhtml",
  "source_order": 1,
  "source_tag": "p",
  "text_length": 75,
  "word_count": 13,
  "cross_references": [],
  "scripture_references": [],
  "dates_mentioned": [],
  "heading_path": "Part I: The Liturgy / Chapter 1: The Sacred Liturgy / Article 1: Nature of the Liturgy",
  "hierarchy_depth": 3,
  "doc_stable_id": "abc123def456...",
  "sentence_count": 1,
  "sentences": [
    "The sacred liturgy is above all things the worship of the divine Majesty."
  ],
  "normalized_text": "the sacred liturgy is above all things the worship of the divine majesty."
}
```

### Example Chunk (RAG Strategy)

```json
{
  "stable_id": "xyz789abc012...",
  "paragraph_id": 1,
  "text": "The sacred liturgy is above all things the worship of the divine Majesty. It also contains much instruction for the faithful. For in the liturgy God speaks to His people and Christ is still proclaiming His Gospel. And the people reply to God both by song and prayer. Moreover, the prayers addressed to God by the priest who presides over the assembly in the person of Christ are said in the name of the entire holy people and of all present.",
  "hierarchy": {
    "level_1": "Part I: The Liturgy",
    "level_2": "Chapter 1: The Sacred Liturgy",
    "level_3": "Article 1: Nature of the Liturgy",
    "level_4": "",
    "level_5": "",
    "level_6": ""
  },
  "chapter_href": "chapter1.xhtml",
  "source_order": 1,
  "source_tag": "p",
  "text_length": 412,
  "word_count": 87,
  "cross_references": [],
  "scripture_references": [],
  "dates_mentioned": [],
  "heading_path": "Part I: The Liturgy / Chapter 1: The Sacred Liturgy / Article 1: Nature of the Liturgy",
  "hierarchy_depth": 3,
  "doc_stable_id": "abc123def456...",
  "sentence_count": 5,
  "sentences": [
    "The sacred liturgy is above all things the worship of the divine Majesty.",
    "It also contains much instruction for the faithful.",
    "For in the liturgy God speaks to His people and Christ is still proclaiming His Gospel.",
    "And the people reply to God both by song and prayer.",
    "Moreover, the prayers addressed to God by the priest who presides over the assembly in the person of Christ are said in the name of the entire holy people and of all present."
  ],
  "normalized_text": "the sacred liturgy is above all things the worship of the divine majesty. it also contains much instruction for the faithful. for in the liturgy god speaks to his people and christ is still proclaiming his gospel. and the people reply to god both by song and prayer. moreover, the prayers addressed to god by the priest who presides over the assembly in the person of christ are said in the name of the entire holy people and of all present.",
  "merged_paragraph_ids": [42, 43, 44],
  "source_paragraph_count": 3
}
```

**Note**: RAG chunks include `merged_paragraph_ids` and `source_paragraph_count` to track merging.

---

## Extraction Info Object

Processing statistics and metadata.

| Field | Type | Description |
|-------|------|-------------|
| `total_paragraphs` | `integer` | Total number of chunks (may be fewer than paragraphs if using RAG strategy) |
| `extraction_date` | `string` | ISO 8601 timestamp of extraction |
| `source_file` | `string` | Original filename |
| `parser_version` | `string` | Extractor version |
| `md_schema_version` | `string` | Metadata schema version |
| `route` | `string` | Quality route (A/B/C) |
| `quality_score` | `number` | Quality score (0.0 - 1.0) |

### Example

```json
{
  "extraction_info": {
    "total_paragraphs": 1542,
    "extraction_date": "2025-01-10T14:30:00.123456",
    "source_file": "prayer_primer.epub",
    "parser_version": "2.0.0-refactored",
    "md_schema_version": "2025-09-08",
    "route": "A",
    "quality_score": 0.8234
  }
}
```

---

## Complete Example

Full output for a small document:

```json
{
  "metadata": {
    "title": "Sample Document",
    "author": "Jane Doe",
    "description": "",
    "language": "en",
    "publisher": "Example Press",
    "pages": "approximately 10",
    "word_count": "approximately 2,500",
    "md_schema_version": "2025-09-08",
    "document_type": "Book",
    "date_promulgated": "",
    "subject": ["Prayer"],
    "key_themes": ["Chapter 1: Introduction"],
    "related_documents": [],
    "time_period": "",
    "geographic_focus": "",
    "provenance": {
      "doc_id": "abc123def456...",
      "source_file": "sample.epub",
      "parser_version": "2.0.0-refactored",
      "md_schema_version": "2025-09-08",
      "ingestion_ts": "2025-01-10T14:30:00",
      "content_hash": "sha1:abc123...",
      "normalized_hash": "sha1:def456..."
    },
    "quality": {
      "signals": {
        "avg_para_len": 0.75,
        "heading_density": 0.15,
        "vocabulary_richness": 0.68
      },
      "score": 0.72,
      "route": "A"
    },
    "source_identifiers": {
      "toc_map": {
        "chapter1.xhtml": "Chapter 1: Introduction"
      }
    }
  },
  "chunks": [
    {
      "stable_id": "chunk001...",
      "paragraph_id": 1,
      "text": "This is the first paragraph of the document.",
      "hierarchy": {
        "level_1": "Chapter 1: Introduction",
        "level_2": "",
        "level_3": "",
        "level_4": "",
        "level_5": "",
        "level_6": ""
      },
      "chapter_href": "chapter1.xhtml",
      "source_order": 1,
      "source_tag": "p",
      "text_length": 45,
      "word_count": 8,
      "cross_references": [],
      "scripture_references": [],
      "dates_mentioned": [],
      "heading_path": "Chapter 1: Introduction",
      "hierarchy_depth": 1,
      "doc_stable_id": "abc123def456...",
      "sentence_count": 1,
      "sentences": ["This is the first paragraph of the document."],
      "normalized_text": "this is the first paragraph of the document."
    }
  ],
  "extraction_info": {
    "total_paragraphs": 1,
    "extraction_date": "2025-01-10T14:30:00.123456",
    "source_file": "sample.epub",
    "parser_version": "2.0.0-refactored",
    "md_schema_version": "2025-09-08",
    "route": "A",
    "quality_score": 0.72
  }
}
```

---

## Schema Versions

| Version | Date | Changes |
|---------|------|---------|
| `2025-09-08` | Current | Added chunking strategy metadata (`merged_paragraph_ids`, `source_paragraph_count`) |
| `2024-12-01` | Previous | Initial unified schema |

---

## See Also

- [Configuration Reference](configuration.md) - Controlling output via config
- [BaseExtractor API](api/base-extractor.md) - Accessing output programmatically
- [Chunking Strategies How-To](../how-to/chunking-strategy.md) - Understanding RAG vs NLP output
- [CLI Reference](cli/extract.md) - Output files created by CLI
