# Chunk Quality Annotation Tool

Interactive TUI tool for annotating chunk quality, identifying parser issues, and generating labeled datasets for ML training.

## Installation

```bash
uv pip install -e ".[annotation]"
```

This installs:
- `textual>=0.80.0` - TUI framework
- `lightgbm>=4.0.0` - ML classifier
- `scikit-learn>=1.5.0` - Train/test split, metrics
- `numpy>=1.26.0` - Feature arrays

## Quick Start

```bash
# Start new annotation session
annotate-chunks document.json

# Resume previous session
annotate-chunks document.json --resume

# View statistics only
annotate-chunks document.json --stats-only

# Export annotations without opening TUI
annotate-chunks document.json --export-only --output annotations.jsonl
```

## Features

### Interactive TUI

- **Vim-style navigation**: `j`/`k` for next/previous chunk
- **Quick labeling**: `g` (good), `b` (bad), `s` (skip)
- **Issue tracking**: Multi-select checkboxes for parser issues
- **Context display**: Shows ±2 chunks around current
- **Auto-save**: Every 10 annotations + on quit
- **Undo support**: `u` to undo last annotation

### Active Learning (Coming Soon)

Reduces annotation effort by 85-92%:

1. **Bootstrap phase** (first 100 annotations): Samples diverse chunks across quality score range
2. **Model-based phase** (after 100 annotations): Prioritizes uncertain chunks using lightweight ML model

### Dataset Export

Multiple export formats:

- **JSONL**: Single file with all annotations
- **Train/Test Split**: 80/20 stratified split for ML training
- **By Issues**: Separate files per issue type
- **By Labels**: Separate files for good/bad chunks

### Quality Labeling

Binary classification:

- **GOOD (0)**: Chunk is suitable for RAG/embeddings
- **BAD (1)**: Chunk is noise, poorly formatted, or lacks context
- **SKIP (None)**: Uncertain, needs review

Optional fields:

- **Confidence**: 1-5 stars (how certain you are)
- **Rationale**: Free text explaining the label
- **Issues**: Multi-select checkboxes for parser problems

### Issue Types

Pre-defined issues for parser debugging:

1. **Missing hierarchy** - Chunk lacks proper heading context
2. **Formatting lost** - Structure (poetry, lists, quotes) was lost
3. **Noise (index/TOC)** - Chunk is index entry, TOC fragment, or navigation
4. **Mixed topics** - Chunk combines multiple unrelated topics
5. **Mid-sentence truncation** - Chunk starts or ends mid-sentence
6. **Missing context** - Chunk lacks context needed to understand it
7. **Other** - Custom issue (free text)

## Keyboard Shortcuts

### Navigation

- `j` / `↓` - Next chunk
- `k` / `↑` - Previous chunk
- `/` - Search (future feature)

### Labeling

- `g` - Mark as GOOD for RAG
- `b` - Mark as BAD for RAG
- `s` - Skip (no label)

### Session Management

- `u` - Undo last annotation
- `ctrl+s` - Save session
- `e` - Export/view statistics
- `?` - Help screen
- `q` - Quit (auto-saves)

## Output Format

### JSONL Schema

Each line is a JSON object:

```json
{
  "chunk_id": "catechism_abc123_para_17",
  "source_file": "catechism.epub",
  "text": "The full chunk text content...",
  "label": 0,
  "confidence": 5,
  "rationale": "Excellent chunk: coherent topic, proper hierarchy, good length",
  "issues": ["missing_context"],
  "metadata": {
    "word_count": 250,
    "sentence_count": 12,
    "hierarchy_depth": 4,
    "quality_score": 0.89,
    "scripture_refs": ["John 3:16"],
    "hierarchy": {"level_1": "Part I", "level_2": "Section 1"},
    "noise_filter_flagged": false
  },
  "annotation_timestamp": "2026-01-18T12:34:56Z",
  "annotator_id": "user_123"
}
```

**Label encoding**:
- `0` = GOOD for RAG
- `1` = BAD for RAG
- `null` = SKIPPED

## CLI Reference

### Basic Usage

```bash
annotate-chunks <chunks_file> [options]
```

### Options

- `--session-file PATH` - Session file path (default: `.annotation_sessions/<filename>.json`)
- `--resume` - Resume existing session
- `--annotator-id ID` - Annotator identifier (default: `default`)
- `--export-only` - Export without opening TUI
- `--export-type {jsonl,split,issues,labels}` - Export format
- `--output PATH` - Output path (default: `annotations.jsonl`)
- `--stats-only` - Show statistics without opening TUI

### Examples

```bash
# Start annotation session
annotate-chunks corpus/catechism.json

# Resume interrupted session
annotate-chunks corpus/catechism.json --resume

# Export train/test split
annotate-chunks corpus/catechism.json --export-only --export-type split

# Export chunks with specific issues
annotate-chunks corpus/catechism.json --export-only --export-type issues

# View session statistics
annotate-chunks corpus/catechism.json --stats-only

# Multi-annotator setup
annotate-chunks corpus/catechism.json --annotator-id alice
annotate-chunks corpus/catechism.json --annotator-id bob --session-file .sessions/bob.json
```

## Workflow

### 1. Extract Chunks

First, extract chunks from your documents:

```bash
extract documents/*.epub -r --output-dir extractions/
```

### 2. Annotate

Annotate chunks interactively:

```bash
annotate-chunks extractions/catechism.json
```

Use keyboard shortcuts for rapid annotation:
- Review chunk + context
- Press `g` if good, `b` if bad
- Check issues if needed
- Press Enter or auto-advances

### 3. Export

Export annotations for ML training:

```bash
annotate-chunks extractions/catechism.json --export-only --export-type split
```

Creates:
- `train.jsonl` (80% of annotations)
- `test.jsonl` (20% of annotations)

### 4. Train Classifier (Future)

Train LightGBM classifier on annotations:

```python
from extraction.ml.chunk_classifier import ChunkQualityClassifier

# Training script coming in Week 4
```

### 5. Deploy Filter (Future)

Use trained classifier in extraction pipeline:

```bash
extract documents/*.epub --filter-ml-quality
```

## Session Management

Sessions auto-save to `.annotation_sessions/<filename>.json`.

**Session data**:
- Current chunk index
- All annotations
- Statistics (good/bad counts, issue distribution)
- Last save time

**Resume a session**:

```bash
annotate-chunks corpus/catechism.json --resume
```

**Export from existing session**:

```bash
annotate-chunks corpus/catechism.json --export-only --output annotations.jsonl
```

## Statistics

View session statistics:

```bash
annotate-chunks corpus/catechism.json --stats-only
```

Output:

```
=== Annotation Statistics ===
Total chunks: 1,234
Annotated: 456
Good: 412
Bad: 44
Skipped: 0
Progress: 37.0%
Good rate: 90.4%
Bad rate: 9.6%

=== Issue Distribution ===
Noise (Index/TOC): 18
Missing Context: 12
Mid-Sentence Truncation: 8
Missing Hierarchy: 6
```

## Architecture

```
src/extraction/tools/annotate/
├── __init__.py
├── app.py                    # Main Textual app
├── cli.py                    # CLI entry point
├── README.md                 # This file
├── screens/
│   ├── annotation.py         # Primary annotation screen
│   ├── statistics.py         # Statistics + export screen
│   └── help.py               # Help overlay
├── widgets/
│   ├── chunk_display.py      # Chunk text with context
│   ├── metadata_panel.py     # Metadata sidebar
│   ├── issue_tracker.py      # Multi-select checkboxes
│   └── quality_label.py      # Good/bad/skip buttons
└── core/
    ├── session.py            # Session state management
    ├── chunk_loader.py       # Load chunks from JSON/JSONL
    ├── active_learning.py    # Uncertainty sampling (future)
    └── dataset_export.py     # JSONL export with splits
```

## Development Status

**Week 1-2: Core TUI (COMPLETE)**
- ✅ Textual app scaffold
- ✅ Chunk display with context
- ✅ Metadata panel
- ✅ Issue tracker
- ✅ Quality labeling
- ✅ Session management
- ✅ Keyboard shortcuts
- ✅ Export functionality

**Week 3: Active Learning (TODO)**
- ⏳ Diversity sampling (bootstrap phase)
- ⏳ Model-based uncertainty sampling
- ⏳ Integration with TUI

**Week 4-5: ML Classifier (TODO)**
- ⏳ Feature engineering (28 features)
- ⏳ LightGBM training pipeline
- ⏳ Integration with extraction library

## Contributing

Report issues or suggest features:
https://github.com/hello-world-bfree/extraction/issues

## License

MIT
