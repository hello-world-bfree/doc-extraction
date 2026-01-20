"""Help screen."""

from textual.app import ComposeResult
from textual.screen import Screen
from textual.containers import VerticalScroll
from textual.widgets import Static, Markdown
from textual.binding import Binding


HELP_TEXT = """
# Chunk Quality Annotation Tool - Help

## Overview

This tool helps you annotate chunks for RAG suitability and identify parser issues.

All chunks start labeled as GOOD. You only need to take action to mark chunks as BAD or SKIP.

Controls are hidden by default. Press `i` to show the Issues and Quality panels.

## Keyboard Shortcuts

### Navigation
- `j` / `↓` - Next chunk
- `k` / `↑` - Previous chunk
- `Tab` - Focus next section (cycle through panels)
- `Shift+Tab` - Focus previous section
- `/` - Search (future feature)

### Labeling
- `g` - Mark chunk as GOOD for RAG
- `b` - Mark chunk as BAD for RAG
- `s` - Skip chunk (no label)

### View Management
- `i` - Toggle controls (hide/show Issues and Quality panels for fullscreen view)

### Session Management
- `u` - Undo last annotation
- `c` - Copy chunk ID (for reporting issues)
- `r` - Copy full chunk info (for detailed bug reports)
- `ctrl+c` / `cmd+c` - Copy selected text (when focused on metadata panel)
- `ctrl+s` - Save session
- `e` - Export annotations
- `?` - Show this help
- `q` - Quit (auto-saves)

## Issue Types

Check issues that apply to the current chunk:

- **Missing hierarchy** - Chunk lacks proper heading context
- **Formatting lost** - Structure (poetry, lists, quotes) was lost during extraction
- **Noise (index/TOC)** - Chunk is index entry, TOC fragment, or navigation
- **Mixed topics** - Chunk combines multiple unrelated topics
- **Mid-sentence truncation** - Chunk starts or ends mid-sentence
- **Missing context** - Chunk lacks context needed to understand it
- **Other** - Custom issue (describe in text field)

## Quality Labeling

### GOOD for RAG (label=0)
Chunks that are:
- Coherent and self-contained
- Proper hierarchy context
- Right size for embeddings (100-500 words)
- Clear topic
- Useful for retrieval

### BAD for RAG (label=1)
Chunks that are:
- Noise (index, TOC, navigation)
- Missing context
- Too short or too long
- Mixed topics
- Formatting issues break meaning
- Poor quality text

### SKIP (label=None)
Use when uncertain or chunk needs review.

## Confidence (Optional)

Rate your confidence in the label:
- 1 star - Very uncertain
- 2 stars - Uncertain
- 3 stars - Neutral
- 4 stars - Confident
- 5 stars - Very confident

## Rationale (Optional but Recommended)

Explain why the chunk is good or bad. This helps:
- Train better ML models
- Debug parser issues
- Document edge cases

Minimum 10 characters recommended.

## Export Options

From the statistics screen (press `e`):

- **Export JSONL** - All annotations in single file
- **Export Train/Test Split** - 80/20 split for ML training
- **Export by Issues** - Separate files per issue type
- **Export by Labels** - Separate files for good/bad

## Session Management

Sessions auto-save every 10 annotations and on quit.

To resume a session:
```bash
annotate-chunks document.json --resume
```

## Active Learning

The tool prioritizes uncertain chunks to reduce annotation effort:

1. **Bootstrap phase** (first 100 annotations): Samples diverse chunks across quality score range
2. **Model-based phase** (after 100 annotations): Prioritizes chunks where ML model is uncertain

This can reduce annotation effort by 85-92% compared to random sampling.

## Tips

1. **Use keyboard shortcuts** - Much faster than clicking
2. **Fill rationale for edge cases** - Helps debug parser issues
3. **Check issues liberally** - Multiple issues can apply
4. **Save frequently** - Use `ctrl+s` during long sessions
5. **Review statistics** - Press `e` to see progress and issue distribution

## Getting Help

For bugs or feature requests:
https://github.com/anthropics/extraction/issues

Press `Escape` to return to annotation.
"""


class HelpScreen(Screen):
    """Screen for displaying help information."""

    BINDINGS = [
        Binding("escape", "back", "Back", show=True),
        Binding("q", "back", "Back", show=False),
    ]

    def compose(self) -> ComposeResult:
        """Compose help screen."""
        with VerticalScroll():
            yield Markdown(HELP_TEXT)

    def action_back(self) -> None:
        """Return to annotation screen."""
        self.app.pop_screen()
