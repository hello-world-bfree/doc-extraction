"""Split modal screen for chunk splitting."""

from textual.app import ComposeResult
from textual.screen import ModalScreen
from textual.containers import Horizontal, Vertical, Container
from textual.widgets import Static, TextArea, Input, Button
from textual.binding import Binding
from typing import Optional, List, Dict

SPLIT_MARKER = "---SPLIT---"


def parse_segments(text: str) -> List[str]:
    """Parse split markers, return list of non-empty stripped segments."""
    parts = text.split(SPLIT_MARKER)
    return [p for p in (s.strip() for s in parts) if p]


class SplitModal(ModalScreen[Optional[Dict]]):
    """Modal for splitting a chunk into N segments via marker line."""

    DEFAULT_CSS = """
    SplitModal {
        align: center middle;
    }

    #split_dialog {
        width: 90%;
        height: 90%;
        border: thick $primary;
        background: $surface;
        padding: 1;
    }

    #split_title {
        text-align: center;
        text-style: bold;
        color: $accent;
        height: 3;
    }

    #split_help {
        text-align: center;
        color: $text-muted;
        height: 2;
    }

    #editor_section {
        height: 1fr;
        border: solid $accent;
        margin-bottom: 1;
    }

    #segment_status {
        height: 3;
        padding: 0 1;
        background: $boost;
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

    Button {
        margin: 0 1;
    }
    """

    BINDINGS = [
        Binding("ctrl+s", "save_split", "Save", show=True, priority=True),
        Binding("escape", "cancel_split", "Cancel", show=True, priority=True),
        Binding("ctrl+n", "focus_next_widget", "Next Field", show=True),
    ]

    def __init__(
        self,
        chunk_id: str,
        source_text: str,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.chunk_id = chunk_id
        self.source_text = source_text

        self.text_area: Optional[TextArea] = None
        self.reason_input: Optional[Input] = None
        self.status: Optional[Static] = None

    def compose(self) -> ComposeResult:
        with Container(id="split_dialog"):
            yield Static(
                "Split Chunk | Insert lines containing only '---SPLIT---' between segments",
                id="split_title",
            )
            yield Static(
                "Ctrl+N: next field | Ctrl+S: save | Esc: cancel",
                id="split_help",
            )

            with Vertical(id="editor_section"):
                yield Static("Text (insert ---SPLIT--- between segments)", classes="section-title")
                self.text_area = TextArea(self.source_text, show_line_numbers=True)
                yield self.text_area

            self.status = Static(self._status_text(self.source_text), id="segment_status")
            yield self.status

            with Vertical(id="reason_section"):
                yield Static(
                    "Split Reason (Optional - auto-generated if blank)",
                    classes="section-title",
                )
                self.reason_input = Input(
                    placeholder="Why split? (leave blank to auto-generate)",
                )
                yield self.reason_input

            with Horizontal(id="button_row"):
                yield Button("Save (Ctrl+S)", variant="primary", id="save_btn")
                yield Button("Cancel (Esc)", variant="default", id="cancel_btn")

    def _status_text(self, text: str) -> str:
        segs = parse_segments(text)
        if not segs:
            return "0 segments (empty)"
        if len(segs) < 2:
            return f"{len(segs)} segment — insert '{SPLIT_MARKER}' on its own line to split"
        word_counts = [len(s.split()) for s in segs]
        return f"{len(segs)} segments | words: {word_counts}"

    def on_mount(self) -> None:
        if self.text_area:
            self.text_area.focus()

    def on_text_area_changed(self, event: TextArea.Changed) -> None:
        if self.status and self.text_area:
            self.status.update(self._status_text(self.text_area.text))

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "save_btn":
            self.action_save_split()
        elif event.button.id == "cancel_btn":
            self.action_cancel_split()

    def action_save_split(self) -> None:
        if not self.text_area or not self.reason_input:
            return

        segments = parse_segments(self.text_area.text)
        if len(segments) < 2:
            self.app.notify(
                f"Need at least 2 segments — insert '{SPLIT_MARKER}' on its own line",
                severity="warning",
            )
            return

        reason = self.reason_input.value.strip()
        if not reason:
            word_counts = [len(s.split()) for s in segments]
            reason = f"Split into {len(segments)} segments (words: {word_counts})"

        self.dismiss({
            "chunk_id": self.chunk_id,
            "segments": segments,
            "reason": reason,
        })

    def action_cancel_split(self) -> None:
        self.dismiss(None)

    def action_focus_next_widget(self) -> None:
        self.screen.focus_next()
