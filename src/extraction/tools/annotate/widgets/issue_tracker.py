"""Issue tracking widget with checkboxes."""

from textual.app import ComposeResult
from textual.containers import VerticalScroll
from textual.widget import Widget
from textual.widgets import Static, Checkbox, Input
from typing import List, Set


class IssueTracker(VerticalScroll):
    """Track issues with multi-select checkboxes."""

    DEFAULT_CSS = """
    IssueTracker {
        border: solid $primary;
        padding: 1;
        height: 1fr;
    }

    IssueTracker Static {
        margin: 0 1 1 1;
    }

    IssueTracker Checkbox {
        margin: 0 1;
    }

    IssueTracker Input {
        margin: 0 1;
    }
    """

    ISSUE_TYPES = [
        ("missing_hierarchy", "Missing hierarchy"),
        ("formatting_lost", "Formatting lost"),
        ("noise_index_toc", "Noise (index/TOC)"),
        ("mixed_topics", "Mixed topics"),
        ("mid_sentence_truncation", "Mid-sentence truncation"),
        ("missing_context", "Missing context"),
    ]

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.checkboxes: dict[str, Checkbox] = {}
        self.other_input: Input | None = None

    def compose(self) -> ComposeResult:
        """Compose issue tracker widgets."""
        yield Static("[bold]Issues[/bold]")

        for issue_id, issue_label in self.ISSUE_TYPES:
            checkbox = Checkbox(issue_label, id=f"issue_{issue_id}")
            self.checkboxes[issue_id] = checkbox
            yield checkbox

        yield Static("Other:")
        self.other_input = Input(placeholder="Describe custom issue...", id="issue_other")
        yield self.other_input

    def get_selected_issues(self) -> List[str]:
        """Get list of selected issue types.

        Returns:
            List of issue type IDs
        """
        selected = []

        for issue_id, checkbox in self.checkboxes.items():
            if checkbox.value:
                selected.append(issue_id)

        if self.other_input and self.other_input.value.strip():
            selected.append(f"other:{self.other_input.value.strip()}")

        return selected

    def set_selected_issues(self, issues: List[str]) -> None:
        """Set selected issues.

        Args:
            issues: List of issue type IDs
        """
        for issue_id, checkbox in self.checkboxes.items():
            checkbox.value = issue_id in issues

        other_issues = [i for i in issues if i.startswith("other:")]
        if other_issues and self.other_input:
            self.other_input.value = other_issues[0].replace("other:", "", 1)
        elif self.other_input:
            self.other_input.value = ""

    def clear(self) -> None:
        """Clear all selections."""
        for checkbox in self.checkboxes.values():
            checkbox.value = False

        if self.other_input:
            self.other_input.value = ""
