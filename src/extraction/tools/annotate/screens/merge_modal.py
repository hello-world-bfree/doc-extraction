"""Merge modal screen for merging adjacent chunks."""

from textual.app import ComposeResult
from textual.screen import ModalScreen
from textual.containers import Horizontal, Vertical, Container
from textual.widgets import Static, TextArea, Input, Button, RadioSet, RadioButton
from textual.binding import Binding
from typing import Optional, List, Dict


SEPARATOR_CHOICES = [
    ("Blank line (\\n\\n)", "\n\n"),
    ("Newline (\\n)", "\n"),
    ("Space ( )", " "),
    ("None ()", ""),
]


class MergeModal(ModalScreen[Optional[Dict]]):
    """Modal for merging N adjacent chunks into one."""

    DEFAULT_CSS = """
    MergeModal {
        align: center middle;
    }

    #merge_dialog {
        width: 90%;
        height: 90%;
        border: thick $primary;
        background: $surface;
        padding: 1;
    }

    #merge_title {
        text-align: center;
        text-style: bold;
        color: $accent;
        height: 3;
    }

    #merge_help {
        text-align: center;
        color: $text-muted;
        height: 2;
    }

    #sources_section {
        height: 40%;
        border: solid $primary;
        margin-bottom: 1;
    }

    #preview_section {
        height: 30%;
        border: solid $accent;
        margin-bottom: 1;
    }

    #separator_section {
        height: auto;
        margin-bottom: 1;
    }

    #reason_section {
        height: auto;
        margin-bottom: 1;
    }

    #button_row {
        height: auto;
        align: center middle;
        padding: 1;
    }

    .section-title {
        text-style: bold;
        background: $boost;
        padding: 0 1;
        height: 1;
    }

    TextArea {
        height: 1fr;
        border: none;
    }

    Input {
        width: 100%;
        margin: 1 0;
    }

    RadioSet {
        layout: horizontal;
        width: 100%;
        height: auto;
    }

    Button {
        margin: 0 1;
    }
    """

    BINDINGS = [
        Binding("ctrl+s", "save_merge", "Save", show=True, priority=True),
        Binding("escape", "cancel_merge", "Cancel", show=True, priority=True),
        Binding("ctrl+n", "focus_next_widget", "Next Field", show=True),
    ]

    def __init__(
        self,
        chunk_ids: List[str],
        source_texts: List[str],
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.chunk_ids = chunk_ids
        self.source_texts = source_texts

        self.separator: str = "\n\n"
        self.preview_area: Optional[TextArea] = None
        self.reason_input: Optional[Input] = None

    def _render_preview(self) -> str:
        return self.separator.join(self.source_texts)

    def _render_sources(self) -> str:
        parts = []
        for i, (cid, txt) in enumerate(zip(self.chunk_ids, self.source_texts), start=1):
            parts.append(f"--- Chunk {i} ({cid}) [{len(txt.split())} words] ---\n{txt}")
        return "\n\n".join(parts)

    def compose(self) -> ComposeResult:
        with Container(id="merge_dialog"):
            yield Static(
                f"Merge {len(self.chunk_ids)} Chunks | Choose separator and reason",
                id="merge_title",
            )
            yield Static(
                "Ctrl+N: next field | Ctrl+S: save | Esc: cancel",
                id="merge_help",
            )

            with Vertical(id="sources_section"):
                yield Static("Source Chunks (read-only)", classes="section-title")
                yield TextArea(self._render_sources(), read_only=True)

            with Vertical(id="preview_section"):
                yield Static("Merged Preview", classes="section-title")
                self.preview_area = TextArea(self._render_preview(), read_only=True)
                yield self.preview_area

            with Vertical(id="separator_section"):
                yield Static("Separator", classes="section-title")
                with RadioSet(id="separator_radio"):
                    for label, _ in SEPARATOR_CHOICES:
                        yield RadioButton(label, value=(label == SEPARATOR_CHOICES[0][0]))

            with Vertical(id="reason_section"):
                yield Static(
                    "Merge Reason (Optional - auto-generated if blank)",
                    classes="section-title",
                )
                self.reason_input = Input(
                    placeholder="Why merge? (leave blank to auto-generate)",
                )
                yield self.reason_input

            with Horizontal(id="button_row"):
                yield Button("Save (Ctrl+S)", variant="primary", id="save_btn")
                yield Button("Cancel (Esc)", variant="default", id="cancel_btn")

    def on_mount(self) -> None:
        if self.reason_input:
            self.reason_input.focus()

    def on_radio_set_changed(self, event: RadioSet.Changed) -> None:
        if event.radio_set.id != "separator_radio":
            return
        idx = event.index
        if 0 <= idx < len(SEPARATOR_CHOICES):
            self.separator = SEPARATOR_CHOICES[idx][1]
            if self.preview_area:
                self.preview_area.text = self._render_preview()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "save_btn":
            self.action_save_merge()
        elif event.button.id == "cancel_btn":
            self.action_cancel_merge()

    def action_save_merge(self) -> None:
        if not self.reason_input:
            return
        reason = self.reason_input.value.strip()
        if not reason:
            word_counts = [len(t.split()) for t in self.source_texts]
            reason = f"Merged {len(self.chunk_ids)} chunks (words: {word_counts})"
        self.dismiss({
            "chunk_ids": list(self.chunk_ids),
            "separator": self.separator,
            "reason": reason,
        })

    def action_cancel_merge(self) -> None:
        self.dismiss(None)

    def action_focus_next_widget(self) -> None:
        self.screen.focus_next()
