"""Statistics and export screen."""

from textual.app import ComposeResult
from textual.screen import Screen
from textual.containers import Vertical, Horizontal
from textual.widgets import Static, Button, Input, DataTable
from textual.binding import Binding
from rich.table import Table
from pathlib import Path

from ..core.session import AnnotationSession
from ..core.dataset_export import DatasetExporter


class StatisticsScreen(Screen):
    """Screen for viewing statistics and exporting data."""

    BINDINGS = [
        Binding("escape", "back", "Back", show=True),
        Binding("q", "back", "Back", show=False),
    ]

    def __init__(self, session: AnnotationSession, **kwargs):
        super().__init__(**kwargs)
        self.session = session
        self.export_path_input: Input | None = None
        self._default_export_path = self._compute_default_export_path()

    def _compute_default_export_path(self) -> str:
        """Compute default export path based on session file location."""
        if self.session.session_file:
            session_dir = self.session.session_file.parent
            session_name = self.session.session_file.stem
            return str(session_dir / f"{session_name}_export.jsonl")
        return str(Path.cwd() / "annotations.jsonl")

    def compose(self) -> ComposeResult:
        """Compose statistics screen."""
        yield Static("[bold]Annotation Statistics[/bold]", id="title")

        stats_table = self._create_stats_table()
        yield Static(stats_table)

        yield Static("\n[bold]Issue Distribution[/bold]")
        issue_table = self._create_issue_table()
        yield Static(issue_table)

        yield Static("\n[bold]Export Annotations[/bold]")

        yield Static("Output path:", id="export_label")
        self.export_path_input = Input(
            value=self._default_export_path,
            id="export_path",
        )
        yield self.export_path_input

        with Horizontal():
            yield Button("Export JSONL", id="export_jsonl")
            yield Button("Export Train/Test Split", id="export_split")
            yield Button("Export by Issues", id="export_issues")
            yield Button("Export by Labels", id="export_labels")

        yield Static("", id="export_status")

    def _create_stats_table(self) -> Table:
        """Create statistics table."""
        table = Table(show_header=False, box=None)
        table.add_column("Metric", style="bold cyan")
        table.add_column("Value", style="green")

        stats = self.session.stats

        table.add_row("Total chunks", str(stats.total_chunks))
        table.add_row("Annotated", str(stats.annotated_count))
        table.add_row("Good", str(stats.good_count))
        table.add_row("Bad", str(stats.bad_count))
        table.add_row("Skipped", str(stats.skipped_count))

        progress = self.session.get_progress_percent()
        table.add_row("Progress", f"{progress:.1f}%")

        if stats.annotated_count > 0:
            good_rate = (stats.good_count / stats.annotated_count) * 100
            bad_rate = (stats.bad_count / stats.annotated_count) * 100
            table.add_row("Good rate", f"{good_rate:.1f}%")
            table.add_row("Bad rate", f"{bad_rate:.1f}%")

        return table

    def _create_issue_table(self) -> Table:
        """Create issue distribution table."""
        table = Table(show_header=True, box=None)
        table.add_column("Issue", style="bold")
        table.add_column("Count", style="green", justify="right")

        issue_counts = self.session.stats.issue_counts

        if not issue_counts:
            table.add_row("No issues recorded", "0")
        else:
            sorted_issues = sorted(
                issue_counts.items(),
                key=lambda x: x[1],
                reverse=True,
            )

            for issue, count in sorted_issues:
                issue_display = issue.replace("_", " ").title()
                if issue.startswith("other:"):
                    issue_display = issue.replace("other:", "Other: ", 1)

                table.add_row(issue_display, str(count))

        return table

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button press."""
        if event.button.id == "export_jsonl":
            self._export_jsonl()
        elif event.button.id == "export_split":
            self._export_split()
        elif event.button.id == "export_issues":
            self._export_by_issues()
        elif event.button.id == "export_labels":
            self._export_by_labels()

    def _export_jsonl(self) -> None:
        """Export to JSONL file."""
        if self.export_path_input is None:
            return

        output_path = Path(self.export_path_input.value)

        annotations = {
            chunk_id: ann.to_dict()
            for chunk_id, ann in self.session.annotations.items()
        }

        try:
            count = DatasetExporter.export_jsonl(
                self.session.chunks,
                annotations,
                output_path,
                doc_metadata=self.session.doc_metadata,
            )

            status = self.query_one("#export_status", Static)
            status.update(f"[green]Exported {count} annotations to {output_path}[/green]")

        except Exception as e:
            status = self.query_one("#export_status", Static)
            status.update(f"[red]Export failed: {e}[/red]")

    def _export_split(self) -> None:
        """Export train/test split."""
        if self.export_path_input is None:
            return

        output_dir = Path(self.export_path_input.value).parent

        annotations = {
            chunk_id: ann.to_dict()
            for chunk_id, ann in self.session.annotations.items()
        }

        try:
            train_count, test_count = DatasetExporter.export_train_test_split(
                self.session.chunks,
                annotations,
                output_dir,
                doc_metadata=self.session.doc_metadata,
            )

            status = self.query_one("#export_status", Static)
            status.update(
                f"[green]Exported {train_count} train, {test_count} test to {output_dir}/[/green]"
            )

        except Exception as e:
            status = self.query_one("#export_status", Static)
            status.update(f"[red]Export failed: {e}[/red]")

    def _export_by_issues(self) -> None:
        """Export grouped by issues."""
        if self.export_path_input is None:
            return

        output_dir = Path(self.export_path_input.value).parent / "issues"

        annotations = {
            chunk_id: ann.to_dict()
            for chunk_id, ann in self.session.annotations.items()
        }

        try:
            counts = DatasetExporter.export_by_issues(
                self.session.chunks,
                annotations,
                output_dir,
                doc_metadata=self.session.doc_metadata,
            )

            total = sum(counts.values())
            status = self.query_one("#export_status", Static)
            status.update(
                f"[green]Exported {total} chunks across {len(counts)} issues to {output_dir}/[/green]"
            )

        except Exception as e:
            status = self.query_one("#export_status", Static)
            status.update(f"[red]Export failed: {e}[/red]")

    def _export_by_labels(self) -> None:
        """Export grouped by labels."""
        if self.export_path_input is None:
            return

        output_dir = Path(self.export_path_input.value).parent / "labels"

        annotations = {
            chunk_id: ann.to_dict()
            for chunk_id, ann in self.session.annotations.items()
        }

        try:
            counts = DatasetExporter.export_by_labels(
                self.session.chunks,
                annotations,
                output_dir,
                doc_metadata=self.session.doc_metadata,
            )

            total = sum(counts.values())
            status = self.query_one("#export_status", Static)
            status.update(
                f"[green]Exported {total} chunks: {counts.get(0, 0)} good, {counts.get(1, 0)} bad to {output_dir}/[/green]"
            )

        except Exception as e:
            status = self.query_one("#export_status", Static)
            status.update(f"[red]Export failed: {e}[/red]")

    def action_back(self) -> None:
        """Return to annotation screen."""
        self.app.pop_screen()
