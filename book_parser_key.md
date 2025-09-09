# EPUB Parser Field Key Documentation

This document provides a comprehensive field reference for the EPUB parser script outputs, organized by object structure.

## Metadata (top-level) — `data["metadata"]`

| Field | Type | Meaning / How it's derived | Example |
|-------|------|---------------------------|---------|
| `title` | string | EPUB DC:title (cleaned) | `"Laudis Canticum"` |
| `author` | string | EPUB DC:creator (cleaned) | `"Pope Paul VI"` |
| `document_type` | string | Heuristic from body text (e.g., matches "Encyclical", "Apostolic Constitution", etc.) | `"Apostolic Constitution"` |
| `date_promulgated` | string | First detected date, preferring contexts like "promulgated … <date>" | `"November 1, 1970"` |
| `subject` | string[] | Thematic tags matched in text (liturgy, sacraments, canon law, etc.) | `["Divine Office","Liturgy"]` |
| `key_themes` | string[] | Up to 10 distinct headings seen in hierarchy (level_1…level_4) | `["Historical development of the Breviary", …]` |
| `related_documents` | string[] | Named magisterial works referenced | `["Sacrosanctum Concilium","Missale Romanum"]` |
| `time_period` | string | (reserved; not currently populated) | `""` |
| `geographic_focus` | string | Heuristic (e.g., "Vatican City (Rome)", "Universal Church") | `"Vatican City (Rome)"` |
| `language` | string | EPUB DC:language | `"en"` |
| `publisher` | string | EPUB DC:publisher | `"Libreria Editrice Vaticana"` |
| `pages` | string | Approx pages from word count ÷ 250 | `"approximately 180"` |
| `word_count` | string | Total word count across chunks (formatted) | `"approximately 45,200"` |
| `source_identifiers` | object | IDs that help map back into EPUB | `{ "toc_map": { "<href>": "<title>", … } }` |
| `md_schema_version` | string | Schema version constant | `"2025-09-08"` |
| `provenance` | object | See "Provenance" below | `{…}` |
| `quality` | object | See "Quality" below | `{ "signals":{…}, "score":0.87, "route":"A" }` |
| `footnote_index_stats` | object | Summary of globally indexed footnotes (if any) | `{ "unique_indexed": 132, "by_source": {"Text/Notes.xhtml": 98} }` |
| `footnotes_summary` | object | Rollup of cited footnote numbers across chunks | `{ "unique_citations":[1,2,5], "counts":{"1":12,"2":9,"5":3} }` |

### Provenance — `metadata.provenance`

| Field | Type | Meaning |
|-------|------|---------|
| `doc_id` | string | Stable 16-char hash derived from absolute path + mtime |
| `source_file` | string | Basename of the EPUB on disk |
| `parser_version` | string | `PARSER_VERSION` constant |
| `md_schema_version` | string | Copy of schema version |
| `ingestion_ts` | ISO datetime | When this run ingested the file |
| `content_hash` | hex string | SHA-1 of the raw EPUB bytes |
| `normalized_hash` | hex string | SHA-1 of concatenated, cleaned full text |

### Quality — `metadata.quality`

| Field | Type | Meaning |
|-------|------|---------|
| `signals.garble_rate` | number (0–1) | Fraction of "weird" (non-Latin) code points |
| `signals.mean_conf` | number (0–1) | Proxy confidence from garble + length |
| `signals.line_len_std_norm` | number (0–1) | Normalized line length variability |
| `signals.lang_prob` | number (0–1) | Heuristic "Latin/Churchy" signal presence |
| `score` | number (0–1) | Weighted composite quality score |
| `route` | "A" \| "B" \| "C" | Routing bucket for chunking strategy |

## Chunks — `data["chunks"][]`

Each chunk is an atomic paragraph-ish unit.

| Field | Type | Meaning / Notes |
|-------|------|-----------------|
| `stable_id` | string | 16-char stable hash of (href, order, pid, text head) |
| `paragraph_id` | int | Monotonic counter across the whole book |
| `text` | string | Cleaned paragraph text |
| `normalized_text` | string | ASCII-normalized version of `text` |
| `text_length` | int | Character count of `text` |
| `word_count` | int | Word count of `text` |
| `sentence_count` | int | Number of sentences detected |
| `sentences` | string[] | Up to first 6 sentences (preview/debug) |
| `hierarchy` | object | Current heading snapshot, keys `level_1`…`level_6` |
| `heading_path` | string | Joined non-empty hierarchy levels: `"Book / Part / Chapter …"` |
| `hierarchy_depth` | int | Deepest level number that's non-empty (0–6) |
| `chapter_href` | string | Spine item href (no fragment) that produced the chunk |
| `source_order` | int | Order index in spine |
| `source_tag` | string | Source HTML tag or windowing mode (`"p"`, `"li"`, `"fixed_window"`, etc.) |
| `doc_stable_id` | string | Copy of `metadata.provenance.doc_id` |
| `cross_references` | string[] | "cf./see/§/can." and similar refs (Catholic-focused) |
| `scripture_references` | string[] | Bible references found (`"Jn 3:16-18"`, …) |
| `dates_mentioned` | string[] | Dates found in the paragraph |
| `footnote_citations` | object | (optional) See below |
| `footnotes_attached` | object[] | (optional) Resolved note texts; see below |

### Footnotes inside a chunk

**`footnote_citations`:**
- `all`: `int[]` — unique note numbers cited in this chunk (sentence-final markers like `… 12`, `…[12]`, `…(12)`)
- `by_sentence`: `{ index: number, numbers: int[] }[]` — which sentence(s) carried which numbers

**`footnotes_attached`:**
Array of `{ n: int, text: string, source_href: string, id: string }` — resolved note bodies, preferring a local list/aside in the same href, falling back to the global index.

## Extraction Info — `data["extraction_info"]`

| Field | Type | Meaning |
|-------|------|---------|
| `total_paragraphs` | int | Number of chunks emitted |
| `extraction_date` | ISO datetime | When outputs were written |
| `source_file` | string | Basename of the input EPUB |
| `parser_version` | string | Same as in provenance |
| `md_schema_version` | string | Same as in metadata |
| `route` | "A" \| "B" \| "C" | Same as `metadata.quality.route` |
| `quality_score` | number | Same as `metadata.quality.score` |

## Files written by `write_outputs()`

- `<base>.json` — `{ metadata, chunks, extraction_info }`
- `<base>_metadata.json` — just `metadata`
- `<base>_hierarchy_report.txt` — human-readable outline + rollups
- (optional) `<base>.ndjson` — one chunk per line

## Controlled Vocabulary / Notes

### `document_type` (detected)
`"Dogmatic Constitution"`, `"Pastoral Constitution"`, `"Apostolic Constitution"`, `"Encyclical"`, `"Apostolic Exhortation"`, `"Apostolic Letter"`, `"Motu Proprio"`, `"Decree"`, `"Instruction"`, `"Declaration"`, `"Constitution"`. If none match, empty string.

### `geographic_focus`
Likely `"Vatican City (Rome)"`, `"Universal Church"`, `"Diocese"`, `"Parish"`. First match wins.

### `route`
- `"A"` = high quality, fine-grained block chunking
- `"B"` = medium quality, standard block thresholds  
- `"C"` = lower quality, fixed-window chunking fallback