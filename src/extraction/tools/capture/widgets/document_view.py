from dataclasses import dataclass
from textual.widgets import TextArea
from textual.widgets._text_area import Selection
from textual.message import Message
from textual import events
from rich.style import Style
from rich.text import Text


MARKED_STYLE = Style(bgcolor="dark_green", color="white")
CAPTURED_STYLE = Style(bgcolor="dark_blue", color="grey85")


@dataclass(slots=True)
class MarkedRange:
    start: tuple[int, int]
    end: tuple[int, int]
    text: str


class DocumentView(TextArea):

    BINDINGS = []

    DEFAULT_CSS = """
    DocumentView {
        height: 1fr;
        border: solid $primary;
    }
    """

    class SelectionUpdated(Message):
        def __init__(
            self,
            text: str,
            ranges: list[MarkedRange],
            active_text: str,
        ):
            super().__init__()
            self.text = text
            self.ranges = ranges
            self.active_text = active_text

    class CaptureRequested(Message):
        pass

    class ReviewRequested(Message):
        pass

    class SaveRequested(Message):
        pass

    class HelpRequested(Message):
        pass

    class QuitRequested(Message):
        pass

    class DeleteRequested(Message):
        pass

    class UndoDeleteRequested(Message):
        pass

    class FocusChunkList(Message):
        pass

    def __init__(self, document_text: str = "", **kwargs):
        super().__init__(
            document_text,
            read_only=True,
            show_line_numbers=True,
            **kwargs,
        )
        self._full_text = document_text
        self._lines = document_text.split("\n")
        self._visual_anchor: tuple[int, int] | None = None
        self._marked_ranges: list[MarkedRange] = []
        self._captured_ranges: list[MarkedRange] = []
        self._debounce_timer = None
        self._pending_g = False
        self._pending_d = False
        self._count_buf = ""

    @property
    def in_visual_mode(self) -> bool:
        return self._visual_anchor is not None

    @property
    def marked_count(self) -> int:
        return len(self._marked_ranges)

    @property
    def combined_text(self) -> str:
        parts = [r.text for r in self._marked_ranges]
        active = self.selected_text
        if active:
            parts.append(active)
        return "\n\n".join(parts)

    @property
    def all_ranges(self) -> list[MarkedRange]:
        result = list(self._marked_ranges)
        if self._visual_anchor is not None:
            active = self.selected_text
            if active:
                sel = self.selection
                result.append(MarkedRange(
                    start=min(sel.start, sel.end),
                    end=max(sel.start, sel.end),
                    text=active,
                ))
        return result

    def _stylize_ranges(
        self, line: Text, line_index: int, ranges: list[MarkedRange], style: Style,
    ) -> None:
        for mr in ranges:
            top_row, top_col = mr.start
            bot_row, bot_col = mr.end

            if top_row > line_index or bot_row < line_index:
                continue

            line_len = len(line)
            if line_index == top_row == bot_row:
                start_col = top_col
                end_col = bot_col
            elif line_index == top_row:
                start_col = top_col
                end_col = line_len
            elif line_index == bot_row:
                start_col = 0
                end_col = bot_col
            else:
                start_col = 0
                end_col = line_len

            if start_col < end_col:
                line.stylize(style, start=start_col, end=end_col)

    def get_line(self, line_index: int) -> Text:
        line = super().get_line(line_index)
        self._stylize_ranges(line, line_index, self._captured_ranges, CAPTURED_STYLE)
        self._stylize_ranges(line, line_index, self._marked_ranges, MARKED_STYLE)
        return line

    def _consume_count(self) -> int:
        n = int(self._count_buf) if self._count_buf else 1
        self._count_buf = ""
        return n

    async def _on_key(self, event: events.Key) -> None:
        key = event.key

        if key in ("1", "2", "3", "4", "5", "6", "7", "8", "9"):
            self._count_buf += key
            event.stop()
            event.prevent_default()
            return
        elif key == "0":
            if self._count_buf:
                self._count_buf += key
                event.stop()
                event.prevent_default()
                return

        if key == "g":
            if self._pending_g:
                self._pending_g = False
                count = self._consume_count()
                if count > 1:
                    self._move_to(min(count - 1, len(self._lines) - 1), 0)
                else:
                    self._move_to(0, 0)
            else:
                self._pending_g = True
            event.stop()
            event.prevent_default()
            return

        if self._pending_g:
            self._pending_g = False

        if key == "d":
            if self._pending_d:
                self._pending_d = False
                self._count_buf = ""
                self.post_message(self.DeleteRequested())
            else:
                self._pending_d = True
            event.stop()
            event.prevent_default()
            return

        if self._pending_d:
            self._pending_d = False

        handled = True
        count = self._consume_count()

        if key == "j" or key == "down":
            for _ in range(count):
                self.action_cursor_down()
            self._after_move()
        elif key == "k" or key == "up":
            for _ in range(count):
                self.action_cursor_up()
            self._after_move()
        elif key == "h" or key == "left":
            if self._visual_anchor is not None:
                row, col = self.selection.end
                for _ in range(count):
                    if col > 0:
                        col -= 1
                    elif row > 0:
                        row -= 1
                        col = len(self._lines[row])
                self.selection = Selection(start=self._visual_anchor, end=(row, col))
                self.scroll_cursor_visible()
                self._schedule_emit()
            else:
                for _ in range(count):
                    self.action_cursor_left()
                self._schedule_emit()
        elif key == "l" or key == "right":
            if self._visual_anchor is not None:
                row, col = self.selection.end
                for _ in range(count):
                    if row < len(self._lines) and col < len(self._lines[row]):
                        col += 1
                    elif row < len(self._lines) - 1:
                        row += 1
                        col = 0
                self.selection = Selection(start=self._visual_anchor, end=(row, col))
                self.scroll_cursor_visible()
                self._schedule_emit()
            else:
                for _ in range(count):
                    self.action_cursor_right()
                self._schedule_emit()
        elif key == "w":
            for _ in range(count):
                self.action_cursor_word_right()
            self._after_move()
        elif key == "b":
            for _ in range(count):
                self.action_cursor_word_left()
            self._after_move()
        elif key == "e":
            for _ in range(count):
                self.action_cursor_word_right()
            self._after_move()
        elif key == "0" or key == "home":
            self.action_cursor_line_start()
            self._after_move()
        elif key == "dollar" or key == "end":
            self.action_cursor_line_end()
            self._after_move()
        elif key == "G":
            if count > 1:
                self._move_to(min(count - 1, len(self._lines) - 1), 0)
            else:
                self._move_to(max(len(self._lines) - 1, 0), 0)
        elif key == "ctrl+d":
            row, col = self.selection.end
            target = self._visual_lines_forward(row, self.size.height // 2)
            self._move_to(target, col)
        elif key == "ctrl+u":
            row, col = self.selection.end
            target = self._visual_lines_backward(row, self.size.height // 2)
            self._move_to(target, col)
        elif key == "ctrl+f" or key == "pagedown":
            self.action_cursor_page_down()
            self._after_move()
        elif key == "ctrl+b" or key == "pageup":
            self.action_cursor_page_up()
            self._after_move()
        elif key == "v":
            if self._visual_anchor is not None:
                self._cancel_visual()
            else:
                self._start_visual()
        elif key == "V":
            self.action_cursor_line_start()
            self._start_visual()
            self.action_cursor_line_end()
            self._after_move()
        elif key == "m":
            self._mark_current()
        elif key == "y":
            self.post_message(self.CaptureRequested())
        elif key == "escape":
            self._cancel_all()
        elif key == "u":
            self.post_message(self.UndoDeleteRequested())
        elif key == "r":
            self.post_message(self.ReviewRequested())
        elif key == "ctrl+s":
            self.post_message(self.SaveRequested())
        elif key == "question_mark":
            self.post_message(self.HelpRequested())
        elif key == "q":
            self.post_message(self.QuitRequested())
        elif key == "tab":
            self.post_message(self.FocusChunkList())
        else:
            handled = False

        if handled:
            event.stop()
            event.prevent_default()

    def _start_visual(self) -> None:
        self._visual_anchor = self.selection.end
        self._schedule_emit()

    def _mark_current(self) -> None:
        if self._visual_anchor is None:
            return

        active = self.selected_text
        if not active:
            return

        sel = self.selection
        self._marked_ranges.append(MarkedRange(
            start=min(sel.start, sel.end),
            end=max(sel.start, sel.end),
            text=active,
        ))

        pos = self.selection.end
        self._visual_anchor = None
        self.selection = Selection(start=pos, end=pos)
        self._schedule_emit()
        self.call_later(self.refresh)

    def _cancel_visual(self) -> None:
        self._visual_anchor = None
        pos = self.selection.end
        self.selection = Selection(start=pos, end=pos)
        self._schedule_emit()

    def _cancel_all(self) -> None:
        self._visual_anchor = None
        self._marked_ranges.clear()
        pos = self.selection.end
        self.selection = Selection(start=pos, end=pos)
        self.refresh()
        self._schedule_emit()

    def clear_after_capture(self) -> None:
        self._captured_ranges.extend(self.all_ranges)
        self._visual_anchor = None
        self._marked_ranges.clear()
        pos = self.selection.end
        self.selection = Selection(start=pos, end=pos)
        self._schedule_emit()
        self.call_later(self.refresh)

    def remove_last_captured_ranges(self, count: int = 1) -> None:
        for _ in range(min(count, len(self._captured_ranges))):
            self._captured_ranges.pop()
        self.call_later(self.refresh)

    def remove_captured_range_at(self, flat_start: int, flat_count: int) -> list[MarkedRange]:
        removed = self._captured_ranges[flat_start:flat_start + flat_count]
        del self._captured_ranges[flat_start:flat_start + flat_count]
        self.call_later(self.refresh)
        return removed

    def insert_captured_ranges_at(self, flat_start: int, ranges: list[MarkedRange]) -> None:
        for i, r in enumerate(ranges):
            self._captured_ranges.insert(flat_start + i, r)
        self.call_later(self.refresh)

    def restore_last_captured_ranges(self, ranges: list[MarkedRange]) -> None:
        self._captured_ranges.extend(ranges)
        self.call_later(self.refresh)

    def _after_move(self) -> None:
        if self._visual_anchor is not None:
            current = self.selection.end
            self.selection = Selection(start=self._visual_anchor, end=current)
        self._schedule_emit()

    def _move_to(self, row: int, col: int) -> None:
        pos = (row, col)
        if self._visual_anchor is not None:
            self.selection = Selection(start=self._visual_anchor, end=pos)
        else:
            self.selection = Selection(start=pos, end=pos)
        self.scroll_cursor_visible()
        self._schedule_emit()

    def _schedule_emit(self) -> None:
        if self._debounce_timer is not None:
            self._debounce_timer.stop()
        self._debounce_timer = self.set_timer(0.05, self._emit_selection)

    def _on_selection_changed(self, event) -> None:
        pass

    def _emit_selection(self) -> None:
        self._debounce_timer = None

        combined = self.combined_text
        active = self.selected_text or ""

        self.post_message(self.SelectionUpdated(
            text=combined,
            ranges=self.all_ranges,
            active_text=active,
        ))

    def _visual_row_count(self, line_index: int) -> int:
        content_width = self.size.width - self.gutter.width
        if content_width <= 0:
            return 1
        line_len = len(self._lines[line_index]) if line_index < len(self._lines) else 0
        if line_len == 0:
            return 1
        return max(1, (line_len + content_width - 1) // content_width)

    def _visual_lines_forward(self, start_row: int, visual_count: int) -> int:
        last_row = len(self._lines) - 1
        if start_row >= last_row:
            return last_row
        row = start_row + 1
        remaining = visual_count - self._visual_row_count(start_row)
        while row < last_row and remaining > 0:
            remaining -= self._visual_row_count(row)
            row += 1
        return min(row, last_row)

    def _visual_lines_backward(self, start_row: int, visual_count: int) -> int:
        if start_row <= 0:
            return 0
        row = start_row - 1
        remaining = visual_count - self._visual_row_count(start_row)
        while row > 0 and remaining > 0:
            remaining -= self._visual_row_count(row)
            row -= 1
        return max(row, 0)

    def _row_col_to_offset(self, pos: tuple[int, int]) -> int:
        row, col = pos
        offset = 0
        for i in range(min(row, len(self._lines))):
            offset += len(self._lines[i]) + 1
        if row < len(self._lines):
            offset += min(col, len(self._lines[row]))
        return offset

    def _offset_to_row_col(self, offset: int) -> tuple[int, int]:
        remaining = offset
        for i, line in enumerate(self._lines):
            line_len = len(line) + 1
            if remaining < line_len:
                return (i, remaining)
            remaining -= line_len
        return (max(len(self._lines) - 1, 0), len(self._lines[-1]) if self._lines else 0)

    def restore_captured_from_session(self, chunks: list) -> None:
        for chunk in chunks:
            start = self._offset_to_row_col(chunk.start_offset)
            end = self._offset_to_row_col(chunk.end_offset)
            self._captured_ranges.append(MarkedRange(
                start=start,
                end=end,
                text=chunk.text[:50],
            ))
        if self._captured_ranges:
            self.call_later(self.refresh)
