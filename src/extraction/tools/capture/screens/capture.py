from textual.app import ComposeResult
from textual.screen import Screen
from textual.containers import Horizontal, Vertical
from textual.widgets import Header, Footer

from ..widgets import DocumentView, SelectionInfo, ChunkList
from ..core.session import CaptureSession
from ..core.document_loader import DocumentText
from ..core.token_counter import TokenCounter
from ..screens.chunk_detail import ChunkDetailScreen


class CaptureScreen(Screen):

    def __init__(
        self,
        document: DocumentText,
        session: CaptureSession,
        token_counter: TokenCounter,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.document = document
        self.session = session
        self.token_counter = token_counter

    def compose(self) -> ComposeResult:
        yield Header()

        with Horizontal(id="main_layout"):
            with Vertical(id="doc_column"):
                self._doc_view = DocumentView(
                    self.document.full_text,
                    id="document_view",
                )
                yield self._doc_view

                self._selection_info = SelectionInfo(id="selection_info")
                yield self._selection_info

            self._chunk_list = ChunkList(id="chunk_list")
            yield self._chunk_list

        yield Footer()

    def on_mount(self) -> None:
        self._doc_view.focus()
        self._capture_range_counts: list[int] = [1] * len(self.session.captured)
        self._deleted_range_counts: list[int] = []
        self._deleted_ranges: list[list] = []
        self._doc_view.restore_captured_from_session(self.session.captured)
        self._update_chunk_list()
        self._update_session_stats()

    def on_document_view_selection_updated(
        self, message: DocumentView.SelectionUpdated
    ) -> None:
        in_visual = self._doc_view.in_visual_mode
        marked = self._doc_view.marked_count
        total_ranges = len(message.ranges)

        if marked > 0 and in_visual:
            self._selection_info.mode_text = f"-- VISUAL ({marked} marked) --"
        elif marked > 0:
            self._selection_info.mode_text = f"-- {marked} marked (v to add, y to yank) --"
        elif in_visual:
            self._selection_info.mode_text = "-- VISUAL --"
        else:
            self._selection_info.mode_text = "-- NORMAL --"

        self._selection_info.marked_ranges = total_ranges

        if not message.text:
            self._selection_info.selection_tokens = 0
            self._selection_info.selection_words = 0
            self._selection_info.selection_chars = 0
            return

        count = self.token_counter.count(message.text)
        self._selection_info.selection_tokens = count.tokens
        self._selection_info.selection_words = count.words
        self._selection_info.selection_chars = count.chars

    def on_document_view_capture_requested(self, message) -> None:
        all_ranges = self._doc_view.all_ranges
        combined = self._doc_view.combined_text

        if not combined or not combined.strip():
            self.notify("No text selected — press v to start visual mode", severity="warning")
            return

        text = combined.strip()
        count = self.token_counter.count(text)

        all_source_ids = []
        first_hierarchy = {}
        min_offset = float("inf")
        max_offset = 0

        for r in all_ranges:
            start_off = self._doc_view._row_col_to_offset(r.start)
            end_off = self._doc_view._row_col_to_offset(r.end)
            min_offset = min(min_offset, start_off)
            max_offset = max(max_offset, end_off)

            h, sids = self.session.find_overlapping_boundaries(
                start_off, end_off, self.document.boundaries,
            )
            if not first_hierarchy and h:
                first_hierarchy = h
            all_source_ids.extend(sids)

        if min_offset == float("inf"):
            min_offset = 0

        seen = set()
        unique_source_ids = []
        for sid in all_source_ids:
            if sid not in seen:
                seen.add(sid)
                unique_source_ids.append(sid)

        chunk = self.session.capture(
            text=text,
            start_offset=int(min_offset),
            end_offset=int(max_offset),
            token_count=count.tokens,
            hierarchy=first_hierarchy,
            source_chunk_ids=unique_source_ids,
        )

        self._capture_range_counts.append(len(all_ranges))
        self._doc_view.clear_after_capture()
        self._update_chunk_list()
        self._update_session_stats()

        range_info = f" from {len(all_ranges)} ranges" if len(all_ranges) > 1 else ""
        self.notify(
            f"Captured #{chunk.order} ({count.tokens} tokens{range_info})",
            severity="information",
        )

        if len(self.session.captured) % 5 == 0:
            self.session.save()

    def on_document_view_delete_requested(self, message) -> None:
        if not self.session.captured:
            self.notify("No chunks to delete", severity="warning")
            return

        idx = len(self.session.captured) - 1
        removed = self.session.remove_last()
        if removed:
            count = self._capture_range_counts.pop() if self._capture_range_counts else 0
            deleted = self._doc_view._captured_ranges[-count:] if count else []
            self._deleted_range_counts.append(count)
            self._deleted_ranges.append((idx, list(deleted)))
            self._doc_view.remove_last_captured_ranges(count)
            self._update_chunk_list()
            self._update_session_stats()
            self.notify(f"Removed chunk #{removed.order}", severity="information")

    def on_document_view_undo_delete_requested(self, message) -> None:
        restored = self.session.undo_remove()
        if restored:
            if self._deleted_ranges:
                idx, ranges = self._deleted_ranges.pop()
                count = self._deleted_range_counts.pop()
                flat_start = sum(self._capture_range_counts[:idx])
                self._capture_range_counts.insert(idx, count)
                self._doc_view.insert_captured_ranges_at(flat_start, ranges)
            self._update_chunk_list()
            self._update_session_stats()
            self.notify(f"Restored chunk #{restored.order}", severity="information")
        else:
            self.notify("Nothing to undo", severity="warning")

    def on_document_view_review_requested(self, message) -> None:
        self.app.push_screen("review")

    def on_document_view_save_requested(self, message) -> None:
        self.session.save()
        self.notify("Session saved", severity="information")

    def on_document_view_help_requested(self, message) -> None:
        self.app.push_screen("help")

    def on_document_view_quit_requested(self, message) -> None:
        self.session.save()
        self.app.exit()

    def on_document_view_focus_chunk_list(self, message) -> None:
        self._chunk_list.focus()

    def on_chunk_list_focus_document(self, message) -> None:
        self._doc_view.focus()

    def on_chunk_list_chunk_viewed(self, message: ChunkList.ChunkViewed) -> None:
        if 0 <= message.index < len(self.session.captured):
            chunk = self.session.captured[message.index]
            self.app.push_screen(ChunkDetailScreen(chunk))

    def on_chunk_list_chunk_deleted(self, message: ChunkList.ChunkDeleted) -> None:
        idx = message.index
        if 0 <= idx < len(self.session.captured):
            chunk = self.session.captured[idx]

            flat_start = sum(self._capture_range_counts[:idx])
            range_count = self._capture_range_counts[idx] if idx < len(self._capture_range_counts) else 0
            removed_ranges = self._doc_view.remove_captured_range_at(flat_start, range_count)

            removed = self.session.remove_by_id(chunk.capture_id)
            if removed:
                if idx < len(self._capture_range_counts):
                    del self._capture_range_counts[idx]
                self._deleted_range_counts.append(range_count)
                self._deleted_ranges.append((idx, removed_ranges))
                self._update_chunk_list()
                self._update_session_stats()
                self.notify(f"Removed chunk #{removed.order}", severity="information")

    def on_chunk_list_chunk_undo_deleted(self, message) -> None:
        restored = self.session.undo_remove()
        if restored:
            if self._deleted_ranges:
                idx, ranges = self._deleted_ranges.pop()
                count = self._deleted_range_counts.pop()
                flat_start = sum(self._capture_range_counts[:idx])
                self._capture_range_counts.insert(idx, count)
                self._doc_view.insert_captured_ranges_at(flat_start, ranges)
            self._update_chunk_list()
            self._update_session_stats()
            self.notify(f"Restored chunk #{restored.order}", severity="information")
        else:
            self.notify("Nothing to undo", severity="warning")

    def _update_chunk_list(self):
        self._chunk_list.update_chunks(self.session.captured)

    def _update_session_stats(self):
        self._selection_info.total_captured = len(self.session.captured)
        self._selection_info.total_tokens = self.session.total_tokens
