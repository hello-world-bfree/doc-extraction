# Corpus & Training Tools

Build production-ready JSONL datasets from extraction outputs and annotation sessions. Two complementary tools serve different downstream needs: `corpus-builder` aggregates good chunks for embedding and RAG pipelines, while `training-builder` creates labeled train/test splits for ML classification models.

---

## `corpus-builder`

### Synopsis

```bash
corpus-builder [OPTIONS]
```

### Description

Aggregates "good" labeled chunks (label=0) across multiple annotation sessions into a single JSONL corpus file. Matches each annotation session to its corresponding extraction output, applies text edits from annotation sessions, filters by quality score, and optionally generates a statistics manifest.

The tool uses recursive directory search to find chunks files, supporting both flat and nested directory structures. Session-to-chunks matching is case-insensitive and searches subdirectories automatically.

### Options

#### Required

| Option | Description |
|--------|-------------|
| `--chunks-dir DIR` | Directory containing extracted chunks JSON files. Searched recursively. |
| `--output FILE` | Output JSONL file path for the corpus. Parent directories are created automatically. |

#### Optional

| Option | Description | Default |
|--------|-------------|---------|
| `--sessions-dir DIR` | Directory containing annotation session JSON files. | `.annotation_sessions` |
| `--apply-edits` | Apply chunk text edits from annotation sessions. | `True` |
| `--no-apply-edits` | Skip applying annotation edits; use original chunk text. | — |
| `--min-quality SCORE` | Minimum quality score (0.0-1.0) for inclusion. Chunks below this threshold are excluded. | No filter |
| `--no-metadata` | Exclude corpus metadata (annotation provenance info) from output chunks. | Metadata included |
| `--manifest` | Export a statistics manifest JSON file alongside the corpus. | Disabled |

### Output Format

Each line in the output JSONL file is a complete chunk object. When edits are applied, the `text` field contains the edited version and additional edit tracking fields are added. When metadata is included, a `corpus_metadata` field provides annotation provenance.

```json
{
  "stable_id": "abc123...",
  "text": "Chunk text (edited if applicable)...",
  "edited": true,
  "edited_chunk_id": "ed_xyz789",
  "edit_reason": "Fixed OCR error",
  "edit_timestamp": "2026-01-19T12:34:56Z",
  "edit_version": 1,
  "metadata": {
    "word_count": 250,
    "hierarchy": { "level_1": "Chapter 1", "level_2": "Section 1.1" },
    "quality": { "score": 0.95 },
    "provenance": { "source_file": "book1.epub" }
  },
  "corpus_metadata": {
    "source_session": "book1",
    "annotation_timestamp": "2026-01-19T10:00:00Z",
    "annotator_id": "default",
    "confidence": null,
    "rationale": ""
  }
}
```

When `--manifest` is used, a `{output_stem}_manifest.json` file is written to the same directory as the output:

```json
{
  "sessions_processed": 12,
  "sessions_skipped": 0,
  "good_chunks": 3456,
  "edited_chunks": 89,
  "quality_filtered": 23
}
```

### Examples

Build a corpus from annotated extractions:

```bash
corpus-builder --chunks-dir extractions/ --output corpus.jsonl
```

Include a statistics manifest:

```bash
corpus-builder --sessions-dir .annotation_sessions \
  --chunks-dir extractions/ \
  --output corpus.jsonl \
  --manifest
```

Filter to high-quality chunks only:

```bash
corpus-builder --chunks-dir extractions/ \
  --output premium.jsonl \
  --min-quality 0.9
```

Skip edit application and strip annotation metadata:

```bash
corpus-builder --chunks-dir extractions/ \
  --output raw_corpus.jsonl \
  --no-apply-edits \
  --no-metadata
```

---

## `training-builder`

### Synopsis

```bash
training-builder [OPTIONS]
```

### Description

Builds ML training datasets from annotation sessions with stratified train/test splits and optional class balancing. Collects all labeled chunks (both good and bad) across multiple sessions, extracts numeric features from chunk metadata, and produces JSONL files suitable for training binary classification models.

Each training record includes the chunk text, its label, extracted features (word count, quality score, garble rate, hierarchy depth, reference counts), and annotation metadata. The tool uses `scikit-learn` for splitting and requires the `annotation` extra.

### Options

#### Required

| Option | Description |
|--------|-------------|
| `--chunks-dir DIR` | Directory containing extracted chunks JSON files. Searched recursively. |
| `--output-dir DIR` | Output directory for `train.jsonl`, `test.jsonl`, and `manifest.json`. Created automatically. |

#### Optional

| Option | Description | Default |
|--------|-------------|---------|
| `--sessions-dir DIR` | Directory containing annotation session JSON files. | `.annotation_sessions` |
| `--test-size RATIO` | Proportion of data reserved for the test set (0.0-1.0). | `0.2` |
| `--no-stratify` | Disable stratified splitting. By default, splits preserve label distribution. | Stratified |
| `--balanced` | Balance classes by undersampling the majority class. Retains highest-quality-score samples. | Disabled |
| `--random-state SEED` | Random seed for reproducible train/test splits. | `42` |

### Output Format

Three files are written to `--output-dir`:

| File | Description |
|------|-------------|
| `train.jsonl` | Training split (default 80% of records) |
| `test.jsonl` | Test split (default 20% of records) |
| `manifest.json` | Dataset statistics and metadata |

Each line in `train.jsonl` and `test.jsonl` is a training record:

```json
{
  "chunk_id": "abc123...",
  "text": "Chunk text...",
  "label": 0,
  "source_file": "book1.epub",
  "source_session": "book1",
  "features": {
    "word_count": 250,
    "sentence_count": 8,
    "hierarchy_depth": 2,
    "quality_score": 0.95,
    "scripture_refs_count": 1,
    "cross_refs_count": 0,
    "noise_filter_flagged": false,
    "garble_rate": 0.001,
    "mean_conf": 0.98
  },
  "annotation_metadata": {
    "confidence": null,
    "rationale": "",
    "issues": [],
    "timestamp": "2026-01-19T10:00:00Z",
    "annotator_id": "default"
  }
}
```

Labels: `0` = good chunk, `1` = bad chunk.

The `manifest.json` contains dataset statistics:

```json
{
  "sessions_processed": 12,
  "sessions_skipped": 0,
  "total_annotations": 3567,
  "label_distribution": { "0": 3456, "1": 111 },
  "balanced": false,
  "sources": ["book1", "book2", "book3"]
}
```

### Examples

Build training data with default 80/20 split:

```bash
training-builder --chunks-dir extractions/ --output-dir training_data/
```

Custom test split with class balancing:

```bash
training-builder --sessions-dir .annotation_sessions \
  --chunks-dir extractions/ \
  --output-dir training_data/ \
  --balanced \
  --test-size 0.3
```

Disable stratification with a fixed seed:

```bash
training-builder --chunks-dir extractions/ \
  --output-dir training_data/ \
  --no-stratify \
  --random-state 123
```

## See Also

- [Annotation Workflow](../../how-to/annotation-workflow.md) - End-to-end guide
- [Annotation Tools](annotation-tools.md) - Label chunks before building
- [extract](extract.md) - Generate extraction outputs
