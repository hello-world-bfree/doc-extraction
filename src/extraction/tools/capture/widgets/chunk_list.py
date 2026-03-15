from textual.containers import VerticalScroll
from textual.widgets import Static
from textual.message import Message
from textual.events import Key
from textual.reactive import reactive
from rich.text import Text


class ChunkList(VerticalScroll, can_focus=True):

    DEFAULT_CSS = """
    ChunkList {
        height: 1fr;
        border: solid $secondary;
        min-width: 30;
    }

    ChunkList:focus {
        border: solid $accent;
    }

    .chunk-item {
        padding: 0 1;
        height: auto;
        margin: 0 0 1 0;
    }

    .chunk-item-selected {
        background: $accent-darken-2;
    }

    .chunk-header {
        color: $text-muted;
    }
    """

    class ChunkViewed(Message):
        def __init__(self, index: int):
            super().__init__()
            self.index = index

    class ChunkDeleted(Message):
        def __init__(self, index: int):
            super().__init__()
            self.index = index

    class ChunkUndoDeleted(Message):
        pass

    class FocusDocument(Message):
        pass

    selected_index = reactive(-1)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._header = None
        self._chunks = []
        self._items: list[Static] = []
        self._pending_d = False

    def compose(self):
        self._header = Static(
            Text("CAPTURED CHUNKS", style="bold"),
            classes="chunk-header",
        )
        yield self._header

    def update_chunks(self, captured: list) -> None:
        self._chunks = list(captured)
        self._rebuild()

    def _rebuild(self) -> None:
        for item in self._items:
            item.remove()
        self._items.clear()

        if not self._chunks:
            placeholder = Static(
                Text("No chunks captured yet\n\nSelect text and press y", style="dim"),
                classes="chunk-item",
            )
            self.mount(placeholder)
            self._items.append(placeholder)
            self.selected_index = -1
            return

        for chunk in self._chunks:
            preview = chunk.text[:60].replace("\n", " ")
            if len(chunk.text) > 60:
                preview += "..."

            item_text = Text()
            item_text.append(f"{chunk.order}. ", style="bold cyan")
            item_text.append(f"[{chunk.token_count}t] ", style="dim")
            item_text.append(preview)

            item = Static(item_text, classes="chunk-item")
            self.mount(item)
            self._items.append(item)

        if self.selected_index >= len(self._chunks):
            self.selected_index = max(len(self._chunks) - 1, 0)
        elif self.selected_index < 0 and self._chunks:
            self.selected_index = 0

        self._highlight_selected()

    def watch_selected_index(self, value: int) -> None:
        self._highlight_selected()

    def _highlight_selected(self) -> None:
        for i, item in enumerate(self._items):
            if i == self.selected_index:
                item.add_class("chunk-item-selected")
            else:
                item.remove_class("chunk-item-selected")

        if 0 <= self.selected_index < len(self._items):
            self._items[self.selected_index].scroll_visible()

    def on_key(self, event: Key) -> None:
        if not self._chunks:
            if event.key in ("h", "left", "escape"):
                self.post_message(self.FocusDocument())
                event.stop()
                event.prevent_default()
            return

        if event.key == "d":
            if self._pending_d:
                self._pending_d = False
                if 0 <= self.selected_index < len(self._chunks):
                    self.post_message(self.ChunkDeleted(self.selected_index))
            else:
                self._pending_d = True
            event.stop()
            event.prevent_default()
            return

        self._pending_d = False

        if event.key in ("j", "down"):
            if self.selected_index < len(self._chunks) - 1:
                self.selected_index += 1
            event.stop()
            event.prevent_default()
        elif event.key in ("k", "up"):
            if self.selected_index > 0:
                self.selected_index -= 1
            event.stop()
            event.prevent_default()
        elif event.key in ("g",):
            self.selected_index = 0
            event.stop()
            event.prevent_default()
        elif event.key == "G":
            self.selected_index = len(self._chunks) - 1
            event.stop()
            event.prevent_default()
        elif event.key in ("enter", "l", "right"):
            if 0 <= self.selected_index < len(self._chunks):
                self.post_message(self.ChunkViewed(self.selected_index))
            event.stop()
            event.prevent_default()
        elif event.key in ("h", "left", "escape"):
            self.post_message(self.FocusDocument())
            event.stop()
            event.prevent_default()
        elif event.key == "u":
            self.post_message(self.ChunkUndoDeleted())
            event.stop()
            event.prevent_default()
