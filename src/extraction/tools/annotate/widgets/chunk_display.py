"""Chunk text display widget with context."""

from textual.app import ComposeResult
from textual.containers import VerticalScroll
from textual.widget import Widget
from textual.widgets import Static
from rich.text import Text
from typing import Optional, Dict


class ChunkDisplay(VerticalScroll):
    """Display chunk text with surrounding context."""

    DEFAULT_CSS = """
    ChunkDisplay {
        height: 1fr;
        border: solid $primary;
    }

    .chunk-preview {
        color: $text-muted;
        background: $surface-darken-1;
        padding: 1;
        margin: 1;
    }

    .chunk-current {
        color: $text;
        background: $surface;
        border: heavy $accent;
        padding: 1;
        margin: 1;
    }

    .chunk-label-good {
        border: heavy $success;
    }

    .chunk-label-bad {
        border: heavy $error;
    }

    .chunk-edited {
        border: heavy $accent;
    }
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.current_chunk: Optional[Dict] = None
        self.prev_chunk: Optional[Dict] = None
        self.next_chunk: Optional[Dict] = None
        self.annotation: Optional[Dict] = None
        self.current_chunk_widget: Optional[Static] = None

    def update_chunks(
        self,
        current: Optional[Dict],
        prev: Optional[Dict] = None,
        next_chunk: Optional[Dict] = None,
        annotation: Optional[Dict] = None,
    ) -> None:
        """Update displayed chunks.

        Args:
            current: Current chunk to display
            prev: Previous chunk (for context)
            next_chunk: Next chunk (for context)
            annotation: Current annotation if any
        """
        self.current_chunk = current
        self.prev_chunk = prev
        self.next_chunk = next_chunk
        self.annotation = annotation

        self.remove_children()

        if prev:
            prev_text = Text("...previous chunk...\n\n", style="dim")
            prev_text.append(self._format_chunk_text(prev, max_lines=3))
            self.mount(Static(prev_text, classes="chunk-preview"))

        if current:
            current_classes = "chunk-current"

            if annotation and annotation.get('label') == 0:
                current_classes += " chunk-label-good"
            elif annotation and annotation.get('label') == 1:
                current_classes += " chunk-label-bad"
            elif current.get('is_edited'):
                current_classes += " chunk-edited"

            current_text = self._format_chunk_text(current)
            self.current_chunk_widget = Static(current_text, classes=current_classes)
            self.mount(self.current_chunk_widget)

        if next_chunk:
            next_text = Text("\n\n...next chunk...\n\n", style="dim")
            next_text.append(self._format_chunk_text(next_chunk, max_lines=10))
            self.mount(Static(next_text, classes="chunk-preview"))
        else:
            # Add padding at the end if no next chunk
            padding_text = Text("\n" * 15, style="dim")
            self.mount(Static(padding_text, classes="chunk-preview"))

        if self.current_chunk_widget is not None:
            self.call_after_refresh(self._scroll_to_current)

    def _format_chunk_text(self, chunk: Dict, max_lines: Optional[int] = None) -> Text:
        """Format chunk text for display.

        Args:
            chunk: Chunk dictionary
            max_lines: Maximum lines to show (None = all)

        Returns:
            Rich Text object
        """
        text_content = chunk.get('text', '[No text]')

        if max_lines is not None:
            lines = text_content.split('\n')
            if len(lines) > max_lines:
                lines = lines[:max_lines]
                text_content = '\n'.join(lines) + '\n...'

        formatted = Text()

        hierarchy = chunk.get('hierarchy') or chunk.get('metadata', {}).get('hierarchy', {})
        if hierarchy:
            breadcrumb = ' > '.join([v for v in hierarchy.values() if v])
            if breadcrumb:
                formatted.append(f"[{breadcrumb}] ", style="italic dim")

        if chunk.get('is_edited'):
            version = chunk.get('edit_version', 1)
            formatted.append(f"📝 v{version}", style="bold cyan")

        if hierarchy or chunk.get('is_edited'):
            formatted.append("\n\n")

        formatted.append(text_content)
        return formatted

    def _scroll_to_current(self) -> None:
        """Scroll to make current chunk visible and centered."""
        if self.current_chunk_widget is not None:
            self.scroll_to_widget(self.current_chunk_widget, animate=False, center=True)
