# Annotation & Capture Tools

Interactive TUI tools for labeling chunk quality and selecting chunks for review. Both tools are built with [Textual](https://textual.textualize.io/) and persist sessions to disk for resume support.

---

## `annotate-chunks`

### Synopsis

```bash
annotate-chunks CHUNKS_FILE [OPTIONS]
```

### Description

Interactive terminal UI for labeling extraction chunk quality. Supports GOOD/BAD/SKIP labels, issue tracking, chunk text editing, and ML-ready dataset export. Sessions auto-save every 10 annotations and on quit. The interface uses a split-panel layout with chunk text display, metadata sidebar, issue tracker, and quality label controls.

### Arguments

| Argument | Description |
|----------|-------------|
| `CHUNKS_FILE` | Path to chunks JSON or JSONL file. |

### Options

| Option | Description | Default |
|--------|-------------|---------|
| `--session-file PATH` | Path to session file for save/resume. | `.annotation_sessions/<filename>.json` |
| `--resume` | Resume an existing session. Without this flag, the tool exits if a session file already exists. | Disabled |
| `--annotator-id ID` | Annotator identifier stored with each annotation. Useful for multi-annotator setups. | `default` |
| `--export-only` | Export annotations without opening the TUI. Requires an existing session file. | Disabled |
| `--export-type TYPE` | Export type when using `--export-only`. Choices: `jsonl`, `split`, `issues`, `labels`, `edited`, `audit`, `diff`. | `jsonl` |
| `--output PATH` | Output path for export. | `annotations.jsonl` |
| `--stats-only` | Print annotation statistics without opening the TUI. | Disabled |

### Keyboard Shortcuts

#### Navigation

| Key | Action |
|-----|--------|
| `j` | Next chunk |
| `k` | Previous chunk |
| `Tab` | Focus next panel |
| `Shift+Tab` | Focus previous panel |

#### Labeling

| Key | Action |
|-----|--------|
| `g` | Label chunk as GOOD (label=0) |
| `b` | Label chunk as BAD (label=1) |
| `s` | Skip chunk (no label) |

#### View Management

| Key | Action |
|-----|--------|
| `i` | Toggle controls — hide/show the Issues and Quality panels for fullscreen chunk view |

#### Session Management

| Key | Action |
|-----|--------|
| `u` | Undo last annotation (50-deep stack) |
| `e` | Edit current chunk text (opens edit modal) |
| `c` | Copy chunk ID to clipboard |
| `r` | Copy full chunk info to clipboard (for bug reports) |
| `x` | Open export/statistics screen |
| `Ctrl+S` | Save session |
| `?` | Show help screen |
| `q` | Save and quit |

### Issue Types

The issue tracker supports multi-select from six predefined issue types plus custom entries:

| Issue | Description |
|-------|-------------|
| `missing_hierarchy` | Chunk lacks proper heading context |
| `formatting_lost` | Structure (poetry, lists, quotes) lost during extraction |
| `noise_index_toc` | Chunk is index entry, TOC fragment, or navigation |
| `mixed_topics` | Chunk combines multiple unrelated topics |
| `mid_sentence_truncation` | Chunk starts or ends mid-sentence |
| `missing_context` | Chunk lacks context needed to understand it |
| `other:custom` | Custom issue with free-text description |

### Session Management

- Sessions persist to `.annotation_sessions/` directory by default
- Each session tracks: chunk labels, edits, issues, timestamps, annotator ID
- Auto-saves every 10 annotations and on quit
- Resume previous sessions with `--resume`
- Undo stack holds 50 operations

### Export Types

| Type | Description |
|------|-------------|
| `jsonl` | All annotations in a single JSONL file |
| `split` | Train/test split (80/20) for ML training |
| `issues` | Separate files per issue type |
| `labels` | Separate files for good (`label=0`) and bad (`label=1`) |
| `edited` | JSONL with edited chunk text applied |
| `audit` | JSONL with full edit lineage and audit trail |
| `diff` | Markdown report showing diffs for edited chunks |

#### Output Schema

Each exported JSONL record contains:

```json
{
  "chunk_id": "chunk_001",
  "source_file": "sample.epub",
  "text": "The full chunk text...",
  "label": 0,
  "confidence": 5,
  "rationale": "Good chunk: coherent, proper hierarchy",
  "issues": ["missing_context"],
  "metadata": {
    "word_count": 250,
    "sentence_count": 12,
    "hierarchy_depth": 4,
    "quality_score": 0.89,
    "noise_filter_flagged": false
  },
  "annotation_timestamp": "2026-01-18T12:34:56Z",
  "annotator_id": "default"
}
```

Labels: `0` = GOOD, `1` = BAD, `null` = SKIPPED.

### Examples

Start annotating chunks from an extraction:

```bash
annotate-chunks extractions/prayer_primer.json
```

Resume a previous session:

```bash
annotate-chunks extractions/prayer_primer.json --resume
```

Multi-annotator setup:

```bash
annotate-chunks corpus/catechism.json --annotator-id alice --session-file .sessions/alice.json
annotate-chunks corpus/catechism.json --annotator-id bob --session-file .sessions/bob.json
```

Export annotations as JSONL:

```bash
annotate-chunks extractions/prayer_primer.json --export-only --output annotations.jsonl
```

Export train/test split for ML:

```bash
annotate-chunks extractions/prayer_primer.json --export-only --export-type split --output training_data/
```

Export by issue type:

```bash
annotate-chunks extractions/prayer_primer.json --export-only --export-type issues
```

View statistics without opening the TUI:

```bash
annotate-chunks extractions/prayer_primer.json --stats-only
```

Export with edits applied:

```bash
annotate-chunks extractions/prayer_primer.json --export-only --export-type edited --output edited_chunks.jsonl
```

Generate a diff report for edited chunks:

```bash
annotate-chunks extractions/prayer_primer.json --export-only --export-type diff --output edit_report.md
```

---

## `capture-chunks`

### Synopsis

```bash
capture-chunks DOCUMENT [OPTIONS]
```

### Description

Interactive terminal UI for selecting and capturing text regions from documents. Uses vim-style navigation and visual mode for precise text selection. Supports multi-range selection — mark multiple non-contiguous regions and capture them as a single chunk. Includes real-time token counting via a gRPC tokenizer service, a chunk list sidebar, and a review screen for inspecting captured chunks before export.

### Arguments

| Argument | Description |
|----------|-------------|
| `DOCUMENT` | Path to EPUB, extraction JSON, JSONL, or text file. |

### Options

| Option | Description | Default |
|--------|-------------|---------|
| `--session-file PATH` | Path to session file for save/resume. | `.capture_sessions/<filename>.json` |
| `--resume` | Resume an existing session. Without this flag, the tool exits if a session file already exists. | Disabled |
| `--grpc-target ADDRESS` | gRPC server address for token counting. | `localhost:50051` |
| `--export-only` | Export captured chunks without opening the TUI. Requires an existing session file. | Disabled |
| `--export-format FORMAT` | Export format. Choices: `jsonl` (flat), `json` (extraction-compatible). | `jsonl` |
| `--output PATH` | Output path for export. | `<document>.captured.jsonl` or `<document>.captured.json` |

### Keyboard Shortcuts

#### Movement

| Key | Action |
|-----|--------|
| `h` / `l` | Left / right |
| `j` / `k` | Down / up |
| `w` / `b` | Word forward / back |
| `0` / `$` | Line start / end |
| `gg` / `G` | Top / bottom of document |
| `Ctrl+D` / `Ctrl+U` | Half-page down / up |
| `Ctrl+F` / `Ctrl+B` | Full page down / up |

#### Selection

| Key | Action |
|-----|--------|
| `v` | Enter visual mode (anchor + extend) |
| `V` | Visual line (select current line) |
| `m` | Mark current selection and start a new range |
| `Escape` | Cancel all selections and marks |

#### Capture

| Key | Action |
|-----|--------|
| `y` | Yank all marked + active selection as one chunk |
| `dd` | Delete last captured chunk |
| `u` | Undo last delete |

#### Chunk List

| Key | Action |
|-----|--------|
| `Tab` | Switch focus to chunk list |
| `j` / `k` | Navigate chunks in list |
| `Enter` / `l` | View chunk detail |
| `dd` | Delete selected chunk |
| `u` | Undo delete |
| `h` / `Escape` | Return focus to document |

#### Session

| Key | Action |
|-----|--------|
| `r` | Review captured chunks |
| `x` | Export (in review screen) |
| `Ctrl+S` | Save session |
| `?` | Show help |
| `q` | Save and quit |

### Multi-Range Workflow

The capture tool supports selecting multiple non-contiguous text regions and combining them into a single chunk:

1. Press `v` to enter visual mode
2. Move the cursor to extend the selection
3. Press `m` to mark the range (anchors it)
4. Move to the next region you want to capture
5. Press `v` to start another visual range
6. Move to extend, press `m` to mark again (repeat as needed)
7. Press `y` to capture all marked ranges as one chunk

Marked ranges are joined with paragraph breaks. The token count reflects the combined text.

### Session Management

- Sessions persist to `.capture_sessions/` directory by default
- Auto-saves every 5 captured chunks and on quit
- Resume previous sessions with `--resume`

### Examples

Capture chunks from an EPUB:

```bash
capture-chunks book.epub
```

Capture from an extraction JSON file:

```bash
capture-chunks extractions/prayer_primer.json
```

Resume a previous capture session:

```bash
capture-chunks book.epub --resume
```

Export captured chunks as JSONL:

```bash
capture-chunks book.epub --export-only --output captured.jsonl
```

Export in extraction-compatible JSON format:

```bash
capture-chunks book.epub --export-only --export-format json --output captured.json
```

Use a custom gRPC token counter:

```bash
capture-chunks book.epub --grpc-target localhost:9090
```

---

## See Also

- [Annotation Workflow](../../how-to/annotation-workflow.md) — end-to-end guide
- [Corpus Tools](corpus-tools.md) — build datasets from annotations
- [Working with Quality Flags](../../how-to/quality-flags.md)
