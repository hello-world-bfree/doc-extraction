from textual.widget import Widget
from textual.app import ComposeResult
from textual.widgets import Static
from textual.reactive import reactive


class SelectionInfo(Static):

    DEFAULT_CSS = """
    SelectionInfo {
        height: 1;
        background: $panel;
        color: $text;
        padding: 0 1;
    }
    """

    selection_tokens = reactive(0)
    selection_words = reactive(0)
    selection_chars = reactive(0)
    marked_ranges = reactive(0)
    total_captured = reactive(0)
    total_tokens = reactive(0)
    mode_text = reactive("-- NORMAL --")

    def on_mount(self) -> None:
        self._render_bar()

    def watch_mode_text(self, value: str) -> None:
        self._render_bar()

    def watch_selection_tokens(self, value: int) -> None:
        self._render_bar()

    def watch_selection_words(self, value: int) -> None:
        self._render_bar()

    def watch_selection_chars(self, value: int) -> None:
        self._render_bar()

    def watch_marked_ranges(self, value: int) -> None:
        self._render_bar()

    def watch_total_captured(self, value: int) -> None:
        self._render_bar()

    def watch_total_tokens(self, value: int) -> None:
        self._render_bar()

    def _render_bar(self) -> None:
        left = self.mode_text

        mid_parts = []
        if self.selection_chars > 0 or self.marked_ranges > 0:
            if self.marked_ranges > 0:
                mid_parts.append(f"{self.marked_ranges} ranges")
            mid_parts.append(f"{self.selection_tokens}t")
            mid_parts.append(f"{self.selection_words}w")

        mid = " | ".join(mid_parts) if mid_parts else ""

        right = f"{self.total_captured} chunks | {self.total_tokens:,}t"

        if mid:
            self.update(f"{left}  {mid}  │  {right}")
        else:
            self.update(f"{left}  │  {right}")
