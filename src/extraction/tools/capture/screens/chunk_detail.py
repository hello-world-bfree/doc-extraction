from textual.app import ComposeResult
from textual.screen import ModalScreen
from textual.containers import Vertical, VerticalScroll
from textual.widgets import Static
from textual.binding import Binding
from textual.events import Key
from rich.text import Text

from ..core.session import CapturedChunk


class ChunkDetailScreen(ModalScreen):

    BINDINGS = [
        Binding("escape", "dismiss", "Close", show=True),
        Binding("q", "dismiss", "Close", show=False),
    ]

    DEFAULT_CSS = """
    ChunkDetailScreen {
        align: center middle;
    }

    #chunk_detail_outer {
        width: 80%;
        height: 85%;
        border: thick $primary;
        background: $surface;
        padding: 1 2;
    }

    #chunk_detail_header {
        height: auto;
        margin-bottom: 1;
    }

    #chunk_detail_text {
        height: 1fr;
        border: solid $accent;
        padding: 1;
    }

    #chunk_detail_footer {
        height: auto;
        margin-top: 1;
        color: $text-muted;
    }
    """

    def __init__(self, chunk: CapturedChunk, **kwargs):
        super().__init__(**kwargs)
        self.chunk = chunk

    def compose(self) -> ComposeResult:
        with Vertical(id="chunk_detail_outer"):
            header = Text()
            header.append(f"Chunk #{self.chunk.order}", style="bold cyan")
            header.append(f"  {self.chunk.token_count} tokens", style="dim")
            header.append(f"  {self.chunk.word_count} words", style="dim")

            if self.chunk.hierarchy:
                breadcrumb = " > ".join(v for v in self.chunk.hierarchy.values() if v)
                if breadcrumb:
                    header.append(f"\n{breadcrumb}", style="italic yellow")

            yield Static(header, id="chunk_detail_header")

            self._scroll = VerticalScroll(
                Static(self.chunk.text),
                id="chunk_detail_text",
            )
            yield self._scroll

            footer_parts = []
            if self.chunk.source_chunk_ids:
                sources = ", ".join(self.chunk.source_chunk_ids[:5])
                if len(self.chunk.source_chunk_ids) > 5:
                    sources += f" (+{len(self.chunk.source_chunk_ids) - 5} more)"
                footer_parts.append(f"Sources: {sources}")

            footer_parts.append(f"Offsets: {self.chunk.start_offset}-{self.chunk.end_offset}")
            footer_parts.append(f"ID: {self.chunk.capture_id[:16]}...")

            yield Static(Text("\n".join(footer_parts), style="dim"), id="chunk_detail_footer")

    def on_key(self, event: Key) -> None:
        key = event.key
        handled = True

        if key in ("j", "down"):
            self._scroll.scroll_down()
        elif key in ("k", "up"):
            self._scroll.scroll_up()
        elif key == "ctrl+d":
            self._scroll.scroll_page_down()
        elif key == "ctrl+u":
            self._scroll.scroll_page_up()
        elif key in ("ctrl+f", "pagedown"):
            self._scroll.scroll_page_down()
        elif key in ("ctrl+b", "pageup"):
            self._scroll.scroll_page_up()
        elif key == "G":
            self._scroll.scroll_end()
        elif key == "g":
            self._scroll.scroll_home()
        else:
            handled = False

        if handled:
            event.stop()
            event.prevent_default()

    def action_dismiss(self) -> None:
        self.app.pop_screen()
