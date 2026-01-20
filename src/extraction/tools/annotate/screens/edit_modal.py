"""Edit modal screen for chunk editing."""

from textual.app import ComposeResult
from textual.screen import ModalScreen
from textual.containers import Horizontal, Vertical, Container
from textual.widgets import Static, TextArea, Input, Button
from textual.binding import Binding
from textual.reactive import reactive
from typing import Optional
import difflib

from ..core.session import EditedChunk


class EditModal(ModalScreen[Optional[EditedChunk]]):
    """Modal screen for editing chunk text."""

    show_diff = reactive(False)

    DEFAULT_CSS = """
    EditModal {
        align: center middle;
    }

    #edit_dialog {
        width: 90%;
        height: 90%;
        border: thick $primary;
        background: $surface;
        padding: 1;
    }

    #edit_title {
        text-align: center;
        text-style: bold;
        color: $accent;
        height: 3;
    }

    #original_section {
        height: 35%;
        border: solid $primary;
        margin-bottom: 1;
    }

    #edited_section {
        height: 35%;
        border: solid $accent;
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

    Button {
        margin: 0 1;
    }
    """

    BINDINGS = [
        Binding("ctrl+s", "save_edit", "Save", show=True, priority=True),
        Binding("escape", "cancel_edit", "Cancel", show=True, priority=True),
        Binding("ctrl+d", "toggle_diff", "View Diff", show=True, priority=True),
        Binding("ctrl+n", "focus_next_widget", "Next Field", show=True),
    ]

    def __init__(
        self,
        chunk_id: str,
        original_text: str,
        current_edit: Optional[EditedChunk] = None,
        **kwargs
    ):
        super().__init__(**kwargs)
        self.chunk_id = chunk_id
        self.original_text = original_text
        self.current_edit = current_edit

        self.edited_textarea: Optional[TextArea] = None
        self.reason_input: Optional[Input] = None

    def compose(self) -> ComposeResult:
        """Compose edit modal layout."""
        with Container(id="edit_dialog"):
            yield Static("Edit Chunk | Ctrl+N: next field | Ctrl+D: view diff | Ctrl+S: save | Esc: cancel", id="edit_title")

            with Vertical(id="original_section"):
                yield Static("Original Text (Read-Only)", classes="section-title")
                original_area = TextArea(
                    self.original_text,
                    read_only=True,
                    show_line_numbers=False,
                )
                yield original_area

            with Vertical(id="edited_section"):
                yield Static("Edited Text", classes="section-title")
                if self.current_edit:
                    initial_text = self.current_edit.edited_text
                else:
                    initial_text = self.original_text

                self.edited_textarea = TextArea(
                    initial_text,
                    show_line_numbers=False,
                )
                yield self.edited_textarea

            with Vertical(id="reason_section"):
                yield Static("Edit Reason (Optional - auto-generated from diff if blank)", classes="section-title")
                self.reason_input = Input(
                    placeholder="Why are you making this edit? (leave blank to auto-generate)",
                )
                yield self.reason_input

            with Horizontal(id="button_row"):
                yield Button("Save (Ctrl+S)", variant="primary", id="save_btn")
                yield Button("View Diff (Ctrl+D)", variant="default", id="diff_btn")
                yield Button("Cancel (Esc)", variant="default", id="cancel_btn")

    def on_mount(self) -> None:
        """Focus edited text area on mount."""
        if self.edited_textarea:
            self.edited_textarea.focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "save_btn":
            self.action_save_edit()
        elif event.button.id == "diff_btn":
            self.action_toggle_diff()
        elif event.button.id == "cancel_btn":
            self.action_cancel_edit()

    def _generate_diff_summary(self, original: str, edited: str) -> str:
        """Generate a concise diff summary."""
        if original == edited:
            return "No changes"

        original_lines = original.splitlines(keepends=True)
        edited_lines = edited.splitlines(keepends=True)

        diff = list(difflib.unified_diff(
            original_lines,
            edited_lines,
            lineterm='',
            n=0  # No context lines
        ))

        if not diff:
            return "No changes"

        # Count changes
        additions = sum(1 for line in diff if line.startswith('+') and not line.startswith('+++'))
        deletions = sum(1 for line in diff if line.startswith('-') and not line.startswith('---'))

        # Generate summary
        changes = []
        if deletions > 0:
            changes.append(f"{deletions} deletion{'s' if deletions != 1 else ''}")
        if additions > 0:
            changes.append(f"{additions} addition{'s' if additions != 1 else ''}")

        return ", ".join(changes) if changes else "Minor changes"

    def action_toggle_diff(self) -> None:
        """Toggle diff view."""
        if not self.edited_textarea:
            return

        edited_text = self.edited_textarea.text

        # Generate unified diff
        original_lines = self.original_text.splitlines(keepends=True)
        edited_lines = edited_text.splitlines(keepends=True)

        diff = list(difflib.unified_diff(
            original_lines,
            edited_lines,
            fromfile='Original',
            tofile='Edited',
            lineterm=''
        ))

        if not diff:
            diff_text = "No changes detected"
        else:
            diff_text = '\n'.join(diff)

        # Show diff in notification or modal
        self.app.notify(
            f"Diff:\n{diff_text[:500]}{'...' if len(diff_text) > 500 else ''}",
            severity="information",
            timeout=10
        )

    def action_save_edit(self) -> None:
        """Save edit and return result."""
        if not self.edited_textarea or not self.reason_input:
            return

        edited_text = self.edited_textarea.text
        edit_reason = self.reason_input.value.strip()

        if edited_text == self.original_text:
            self.app.notify("No changes made to text", severity="warning")
            return

        # Auto-generate reason from diff if not provided
        if not edit_reason:
            edit_reason = self._generate_diff_summary(self.original_text, edited_text)

        result = {
            'chunk_id': self.chunk_id,
            'edited_text': edited_text,
            'edit_reason': edit_reason,
        }
        self.dismiss(result)

    def action_cancel_edit(self) -> None:
        """Cancel edit and close modal."""
        self.dismiss(None)

    def action_focus_next_widget(self) -> None:
        """Focus next widget (Ctrl+N to navigate between fields)."""
        self.screen.focus_next()
