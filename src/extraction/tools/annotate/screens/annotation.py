"""Main annotation screen."""

from textual.app import ComposeResult
from textual.screen import Screen
from textual.containers import Horizontal, Vertical, Container
from textual.widgets import Header, Footer, Static
from textual.binding import Binding
from textual.reactive import reactive

from ..widgets import ChunkDisplay, MetadataPanel, IssueTracker, QualityLabel
from ..core.session import AnnotationSession


class AnnotationScreen(Screen):
    """Main screen for chunk annotation."""

    show_controls = reactive(False)

    BINDINGS = [
        Binding("j", "next_chunk", "Next", show=True),
        Binding("k", "prev_chunk", "Previous", show=True),
        Binding("g", "label_good", "Good", show=True),
        Binding("b", "label_bad", "Bad", show=True),
        Binding("s", "skip", "Skip", show=True),
        Binding("u", "undo", "Undo", show=True),
        Binding("e", "edit_chunk", "Edit", show=True),
        Binding("i", "toggle_issues", "Show Controls", show=True),
        Binding("r", "copy_chunk_info", "Report", show=True),
        Binding("tab", "focus_next", "Focus Next", show=False),
        Binding("shift+tab", "focus_previous", "Focus Prev", show=False),
        Binding("c", "copy_id", "Copy ID", show=False),
        Binding("x", "export", "Export", show=True),
        Binding("?", "help", "Help", show=True),
        Binding("q", "quit", "Quit", show=True),
        Binding("ctrl+s", "save", "Save", show=False),
    ]

    def __init__(self, session: AnnotationSession, **kwargs):
        super().__init__(**kwargs)
        self.session = session

        self.chunk_display: ChunkDisplay | None = None
        self.metadata_panel: MetadataPanel | None = None
        self.issue_tracker: IssueTracker | None = None
        self.quality_label: QualityLabel | None = None
        self.status_bar: Static | None = None

    def compose(self) -> ComposeResult:
        """Compose annotation screen layout."""
        yield Header()

        with Container(id="main_container"):
            with Horizontal(id="top_section"):
                self.chunk_display = ChunkDisplay(id="chunk_display")
                yield self.chunk_display

                self.metadata_panel = MetadataPanel(id="metadata_panel")
                yield self.metadata_panel

            with Horizontal(id="bottom_section"):
                with Vertical(id="left_controls"):
                    self.issue_tracker = IssueTracker(id="issue_tracker")
                    yield self.issue_tracker

                with Vertical(id="right_controls"):
                    self.quality_label = QualityLabel(id="quality_label")
                    yield self.quality_label

        self.status_bar = Static(id="status_bar")
        yield self.status_bar

        yield Footer()

    def on_mount(self) -> None:
        """Handle screen mount."""
        self.update_display()

    def watch_show_controls(self, show: bool) -> None:
        """React to show_controls changes."""
        top_section = self.query_one("#top_section")
        bottom_section = self.query_one("#bottom_section")

        if show:
            top_section.remove_class("fullscreen")
            bottom_section.remove_class("hidden")
        else:
            top_section.add_class("fullscreen")
            bottom_section.add_class("hidden")

    def update_display(self) -> None:
        """Update all display elements with current chunk."""
        current_chunk = self.session.get_chunk()
        if current_chunk is None:
            return

        prev_chunk = self.session.get_chunk(self.session.current_index - 1)
        next_chunk = self.session.get_chunk(self.session.current_index + 1)
        annotation = self.session.get_annotation()

        if self.chunk_display:
            self.chunk_display.update_chunks(
                current=current_chunk,
                prev=prev_chunk,
                next_chunk=next_chunk,
                annotation=annotation.to_dict() if annotation else None,
            )

        if self.metadata_panel:
            self.metadata_panel.update_chunk(current_chunk)

        if self.issue_tracker and annotation:
            self.issue_tracker.set_selected_issues(annotation.issues)
        elif self.issue_tracker:
            self.issue_tracker.clear()

        if self.quality_label and annotation:
            self.quality_label.set_annotation(
                label=annotation.label,
                rationale=annotation.rationale,
                confidence=annotation.confidence,
            )
        elif self.quality_label:
            self.quality_label.clear()

        self._update_status()

    def _update_status(self) -> None:
        """Update status bar."""
        if self.status_bar is None:
            return

        chunk = self.session.get_chunk()
        if chunk is None:
            return

        source_file = chunk.get('metadata', {}).get('source_file', 'unknown')
        progress = self.session.get_progress_percent()

        status_text = (
            f"Document: {source_file} | "
            f"Chunk {self.session.current_index + 1} / {len(self.session.chunks)} | "
            f"Annotated: {self.session.stats.annotated_count} "
            f"({progress:.1f}%) | "
            f"Good: {self.session.stats.good_count} | "
            f"Bad: {self.session.stats.bad_count}"
        )

        self.status_bar.update(status_text)

    def action_next_chunk(self) -> None:
        """Navigate to next chunk."""
        if self.session.next_chunk():
            self.update_display()

    def action_prev_chunk(self) -> None:
        """Navigate to previous chunk."""
        if self.session.prev_chunk():
            self.update_display()

    def action_label_good(self) -> None:
        """Label current chunk as GOOD."""
        self._submit_annotation(label=0)

    def action_label_bad(self) -> None:
        """Label current chunk as BAD."""
        self._submit_annotation(label=1)

    def action_skip(self) -> None:
        """Skip current chunk."""
        self._submit_annotation(label=None)

    def _submit_annotation(self, label: Optional[int]) -> None:
        """Submit annotation for current chunk.

        Args:
            label: 0=GOOD, 1=BAD, None=SKIP
        """
        if self.issue_tracker is None or self.quality_label is None:
            return

        issues = self.issue_tracker.get_selected_issues()
        rationale = self.quality_label.rationale_input.value if self.quality_label.rationale_input else ""
        confidence = self.quality_label.confidence_select.value if self.quality_label.confidence_select else None

        self.session.set_annotation(
            label=label,
            rationale=rationale,
            confidence=confidence,
            issues=issues,
        )

        if self.session.stats.annotated_count % 10 == 0:
            self.session.save()

        if not self.session.next_chunk():
            self.notify("Reached end of chunks", severity="information")

        self.update_display()

    def on_quality_label_label_submitted(
        self,
        message: QualityLabel.LabelSubmitted,
    ) -> None:
        """Handle label submission from widget.

        Args:
            message: Label submitted message
        """
        if self.issue_tracker is None:
            return

        issues = self.issue_tracker.get_selected_issues()

        self.session.set_annotation(
            label=message.label,
            rationale=message.rationale,
            confidence=message.confidence,
            issues=issues,
        )

        if self.session.stats.annotated_count % 10 == 0:
            self.session.save()

        if not self.session.next_chunk():
            self.notify("Reached end of chunks", severity="information")

        self.update_display()

    def action_undo(self) -> None:
        """Undo last annotation."""
        if self.session.undo():
            self.update_display()
            self.notify("Undone", severity="information")
        else:
            self.notify("Nothing to undo", severity="warning")

    def action_save(self) -> None:
        """Save session."""
        self.session.save()
        self.notify("Session saved", severity="information")

    def action_toggle_issues(self) -> None:
        """Toggle controls visibility (hide/show bottom section)."""
        self.show_controls = not self.show_controls
        if self.show_controls:
            self.notify("Controls shown (press 'i' to hide)", severity="information")
        else:
            self.notify("Controls hidden (press 'i' to show)", severity="information")

    def action_toggle_quality(self) -> None:
        """Toggle controls visibility (same as toggle_issues for consistency)."""
        self.action_toggle_issues()

    def action_copy_id(self) -> None:
        """Copy chunk ID to clipboard."""
        chunk = self.session.get_chunk()
        if chunk is None:
            self.notify("No chunk to copy", severity="warning")
            return

        chunk_id = chunk.get('stable_id') or chunk.get('chunk_id') or chunk.get('paragraph_id', 'N/A')

        try:
            import pyperclip
            pyperclip.copy(str(chunk_id))
            self.notify(f"Copied: {chunk_id}", severity="information")
        except ImportError:
            self.notify(f"ID: {chunk_id} (pyperclip not installed for clipboard)", severity="information")

    def action_copy_chunk_info(self) -> None:
        """Copy comprehensive chunk information for reporting issues."""
        chunk = self.session.get_chunk()
        if chunk is None:
            self.notify("No chunk to copy", severity="warning")
            return

        # Build comprehensive chunk info
        chunk_id = chunk.get('stable_id') or chunk.get('chunk_id') or chunk.get('paragraph_id', 'N/A')
        paragraph_id = chunk.get('paragraph_id', 'N/A')
        metadata = chunk.get('metadata', {})
        source_file = metadata.get('source_file', 'unknown')

        # Get hierarchy breadcrumb
        hierarchy = chunk.get('hierarchy') or metadata.get('hierarchy', {})
        breadcrumb = ' > '.join([v for v in hierarchy.values() if v]) if hierarchy else 'N/A'

        # Get text preview (first 200 chars)
        text = chunk.get('text', '')
        text_preview = text[:200] + '...' if len(text) > 200 else text

        # Format the info
        info_lines = [
            "# Chunk Information",
            f"Chunk ID: {chunk_id}",
            f"Paragraph ID: {paragraph_id}",
            f"Source: {source_file}",
            f"Hierarchy: {breadcrumb}",
            "",
            "Text preview:",
            f'"{text_preview}"',
        ]

        info_text = '\n'.join(info_lines)

        try:
            import pyperclip
            pyperclip.copy(info_text)
            self.notify("Copied chunk info to clipboard", severity="information")
        except ImportError:
            self.notify(f"Chunk: {chunk_id}, Para: {paragraph_id} (pyperclip not installed)", severity="information")

    def action_edit_chunk(self) -> None:
        """Open edit modal for current chunk."""
        from .edit_modal import EditModal

        chunk = self.session.get_chunk()
        if chunk is None:
            self.notify("No chunk to edit", severity="warning")
            return

        chunk_id = chunk.get('stable_id') or chunk.get('chunk_id')
        if not chunk_id:
            self.notify("Chunk has no ID", severity="error")
            return

        original_chunk = None
        for c in self.session.chunks:
            cid = c.get('stable_id') or c.get('chunk_id')
            if cid == chunk_id:
                original_chunk = c
                break

        if original_chunk is None:
            self.notify("Could not find original chunk", severity="error")
            return

        original_text = original_chunk.get('text', '')
        current_edit = self.session.get_current_edit(chunk_id)

        def handle_edit_result(result):
            if result is not None:
                edit = self.session.create_edit(
                    chunk_id=result['chunk_id'],
                    edited_text=result['edited_text'],
                    edit_reason=result['edit_reason'],
                )

                if edit:
                    self.notify(
                        f"Edit saved (version {edit.version})",
                        severity="information"
                    )
                    self.update_display()
                else:
                    self.notify("Failed to save edit", severity="error")

        self.app.push_screen(
            EditModal(chunk_id, original_text, current_edit),
            callback=handle_edit_result
        )

    def action_export(self) -> None:
        """Export annotations."""
        self.app.push_screen("statistics")

    def action_help(self) -> None:
        """Show help screen."""
        self.app.push_screen("help")

    def action_quit(self) -> None:
        """Quit application."""
        self.session.save()
        self.app.exit()
