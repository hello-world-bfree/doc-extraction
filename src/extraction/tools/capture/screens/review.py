from textual.app import ComposeResult
from textual.screen import Screen
from textual.containers import Vertical, VerticalScroll
from textual.widgets import Header, Footer, Static
from textual.binding import Binding
from textual.reactive import reactive
from textual.events import Key
from rich.text import Text

from ..core.session import CaptureSession


class ReviewScreen(Screen):

    BINDINGS = [
        Binding("j", "next_chunk", "j Next", show=True),
        Binding("k", "prev_chunk", "k Prev", show=True),
        Binding("G", "goto_last", show=False),
        Binding("u", "undo_delete", "u Undo", show=True),
        Binding("x", "export_jsonl", "x Export", show=True),
        Binding("escape", "go_back", "Esc Back", show=True),
        Binding("q", "go_back", show=False),
    ]

    current_index = reactive(0)

    def __init__(self, session: CaptureSession, **kwargs):
        super().__init__(**kwargs)
        self.session = session
        self._pending_g = False
        self._pending_d = False

    def compose(self) -> ComposeResult:
        yield Header()

        with Vertical(id="review_container"):
            self._summary = Static(id="review_summary")
            yield self._summary

            self._chunk_view = VerticalScroll(id="review_chunk_view")
            yield self._chunk_view

            self._nav_info = Static(id="review_nav")
            yield self._nav_info

        yield Footer()

    def on_mount(self) -> None:
        self._refresh_display()

    def on_key(self, event: Key) -> None:
        if event.key == "g":
            if self._pending_g:
                self._pending_g = False
                event.prevent_default()
                event.stop()
                self.current_index = 0
            else:
                self._pending_g = True
                event.prevent_default()
                event.stop()
            return

        self._pending_g = False

        if event.key == "d":
            if self._pending_d:
                self._pending_d = False
                event.prevent_default()
                event.stop()
                self._delete_current()
            else:
                self._pending_d = True
                event.prevent_default()
                event.stop()
            return

        self._pending_d = False

    def watch_current_index(self, value: int) -> None:
        self._refresh_display()

    def _refresh_display(self) -> None:
        total = len(self.session.captured)
        total_tokens = self.session.total_tokens

        summary_text = Text()
        summary_text.append(f" {total} chunks captured", style="bold")
        summary_text.append(f" | {total_tokens:,} tokens total", style="dim")
        self._summary.update(summary_text)

        children = list(self._chunk_view.children)
        for child in children:
            child.remove()

        if not self.session.captured:
            self._chunk_view.mount(Static(
                Text("No chunks captured yet", style="dim italic")
            ))
            self._nav_info.update("")
            return

        idx = min(self.current_index, total - 1)
        chunk = self.session.captured[idx]

        header = Text()
        header.append(f"\nChunk #{chunk.order}", style="bold cyan")
        header.append(f"  ({chunk.token_count} tokens, {chunk.word_count} words)", style="dim")

        if chunk.hierarchy:
            breadcrumb = " > ".join(v for v in chunk.hierarchy.values() if v)
            if breadcrumb:
                header.append(f"\n{breadcrumb}", style="italic")

        self._chunk_view.mount(Static(header))
        self._chunk_view.mount(Static(f"\n{chunk.text}\n"))

        if chunk.source_chunk_ids:
            sources = Text()
            sources.append("\nSource chunks: ", style="dim")
            sources.append(", ".join(chunk.source_chunk_ids[:5]), style="dim")
            if len(chunk.source_chunk_ids) > 5:
                sources.append(f" (+{len(chunk.source_chunk_ids) - 5} more)", style="dim")
            self._chunk_view.mount(Static(sources))

        self._nav_info.update(f" Chunk {idx + 1} / {total}  [j/k navigate | dd delete | gg/G jump]")

    def action_next_chunk(self) -> None:
        if self.current_index < len(self.session.captured) - 1:
            self.current_index += 1

    def action_prev_chunk(self) -> None:
        if self.current_index > 0:
            self.current_index -= 1

    def action_goto_last(self) -> None:
        if self.session.captured:
            self.current_index = len(self.session.captured) - 1

    def _delete_current(self) -> None:
        if not self.session.captured:
            self.notify("No chunks to delete", severity="warning")
            return

        idx = min(self.current_index, len(self.session.captured) - 1)
        chunk = self.session.captured[idx]
        removed = self.session.remove_by_id(chunk.capture_id)

        if removed:
            if self.current_index >= len(self.session.captured) and self.current_index > 0:
                self.current_index -= 1
            self._refresh_display()
            self.notify(f"Deleted chunk #{removed.order}", severity="information")

    def action_undo_delete(self) -> None:
        restored = self.session.undo_remove()
        if restored:
            self._refresh_display()
            self.notify("Restored chunk", severity="information")
        else:
            self.notify("Nothing to undo", severity="warning")

    def action_export_jsonl(self) -> None:
        if not self.session.captured:
            self.notify("No chunks to export", severity="warning")
            return

        output_path = self.session.session_file.with_suffix(".jsonl") if self.session.session_file else None
        if output_path is None:
            output_path = self.session.document_path.with_suffix(".captured.jsonl")

        count = self.session.export_jsonl(output_path)
        self.notify(f"Exported {count} chunks to {output_path}", severity="information")

    def action_go_back(self) -> None:
        self.app.pop_screen()
