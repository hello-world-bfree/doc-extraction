"""Metadata display panel widget."""

from textual.app import ComposeResult
from textual.containers import VerticalScroll
from textual.widget import Widget
from textual.widgets import TextArea
from textual.binding import Binding
from typing import Optional, Dict


class CopyableTextArea(TextArea):
    """TextArea that supports copying selected text to clipboard."""

    BINDINGS = [
        Binding("ctrl+c", "copy_selection", "Copy", show=False),
        Binding("cmd+c", "copy_selection", "Copy", show=False),
    ]

    def action_copy_selection(self) -> None:
        """Copy selected text to clipboard."""
        selection = self.selected_text
        if selection:
            try:
                import pyperclip
                pyperclip.copy(selection)
                self.app.notify("Copied to clipboard", severity="information")
            except ImportError:
                self.app.notify(f"Copied: {selection[:50]}... (pyperclip not installed)", severity="information")
        else:
            self.app.notify("No text selected", severity="warning")


class MetadataPanel(VerticalScroll):
    """Display chunk metadata."""

    DEFAULT_CSS = """
    MetadataPanel {
        width: 40;
        border: solid $primary;
        padding: 0;
    }

    MetadataPanel TextArea {
        height: 1fr;
    }
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.current_chunk: Optional[Dict] = None
        self.text_area: Optional[TextArea] = None

    def compose(self) -> ComposeResult:
        """Compose metadata panel widgets."""
        self.text_area = CopyableTextArea(read_only=True, show_line_numbers=False)
        self.text_area.cursor_blink = False
        yield self.text_area

    def update_chunk(self, chunk: Optional[Dict]) -> None:
        """Update displayed metadata.

        Args:
            chunk: Chunk dictionary
        """
        self.current_chunk = chunk

        if self.text_area is None:
            return

        if chunk is None:
            self.text_area.text = "No chunk selected"
            return

        metadata = chunk.get('metadata', {})

        lines = []

        chunk_id = chunk.get('stable_id') or chunk.get('chunk_id') or chunk.get('paragraph_id', 'N/A')
        lines.append(f"CHUNK ID: {chunk_id}")

        paragraph_id = chunk.get('paragraph_id')
        if paragraph_id is not None:
            lines.append(f"Paragraph ID: {paragraph_id}")

        lines.append("")

        word_count = chunk.get('word_count') or metadata.get('word_count', 0)
        sentence_count = chunk.get('sentence_count') or metadata.get('sentence_count', 0)

        lines.append(f"Word count: {word_count}")
        lines.append(f"Sentence count: {sentence_count}")

        hierarchy = chunk.get('hierarchy') or metadata.get('hierarchy', {})
        hierarchy_depth = len([v for v in hierarchy.values() if v]) if hierarchy else 0
        lines.append(f"Hierarchy depth: {hierarchy_depth}")

        scripture_refs = chunk.get('scripture_references', [])
        if scripture_refs:
            refs_text = ', '.join(scripture_refs[:3])
            if len(scripture_refs) > 3:
                refs_text += f' (+{len(scripture_refs) - 3} more)'
            lines.append(f"Scripture refs: {refs_text}")

        cross_refs = chunk.get('cross_references', [])
        if cross_refs:
            lines.append(f"Cross refs: {len(cross_refs)}")

        quality = metadata.get('quality', {})
        if quality:
            score = quality.get('score', 0.0)
            lines.append(f"Quality score: {score:.3f}")

            signals = quality.get('signals', {})
            if signals:
                lines.append("")
                lines.append("Quality Signals:")

                garble = signals.get('garble_rate', 0.0)
                lines.append(f"  Garble rate: {garble:.3f}")

                mean_conf = signals.get('mean_conf', 0.0)
                lines.append(f"  Mean conf: {mean_conf:.3f}")

        noise_flagged = metadata.get('noise_filter_flagged', False)
        lines.append("")
        if noise_flagged:
            lines.append("Noise filter: FLAGGED")
        else:
            lines.append("Noise filter: NOT FLAGGED")

        if hierarchy:
            lines.append("")
            lines.append("Hierarchy:")
            for level, value in hierarchy.items():
                if value:
                    lines.append(f"  {level}: {value}")

        self.text_area.text = '\n'.join(lines)
