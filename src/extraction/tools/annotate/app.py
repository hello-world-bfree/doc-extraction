"""Main Textual application for chunk annotation."""

from textual.app import App
from textual.binding import Binding
from pathlib import Path
from typing import Optional

from .core.session import AnnotationSession
from .core.chunk_loader import ChunkLoader
from .screens import AnnotationScreen, StatisticsScreen, HelpScreen


class AnnotationApp(App):
    """Interactive TUI for annotating chunk quality."""

    CSS = """
    #main_container {
        height: 1fr;
    }

    #top_section {
        height: 50%;
        max-height: 50%;
    }

    #top_section.fullscreen {
        height: 100%;
        max-height: 100%;
    }

    #bottom_section {
        height: 50%;
        max-height: 50%;
    }

    #bottom_section.hidden {
        display: none;
    }

    #chunk_display {
        width: 70%;
    }

    #metadata_panel {
        width: 30%;
    }

    #left_controls {
        width: 50%;
    }

    #right_controls {
        width: 50%;
    }

    #status_bar {
        dock: bottom;
        height: 1;
        background: $panel;
        color: $text;
        padding: 0 1;
    }

    #title {
        padding: 1;
        text-align: center;
    }

    #export_status {
        padding: 1;
    }

    #export_label {
        padding: 1 0 0 1;
    }

    #export_path {
        margin: 0 1 1 1;
    }
    """

    TITLE = "Chunk Quality Annotation Tool"

    def __init__(
        self,
        chunks_file: Path,
        session_file: Optional[Path] = None,
        resume: bool = False,
        annotator_id: str = "default",
    ):
        """Initialize annotation app.

        Args:
            chunks_file: Path to chunks JSON/JSONL
            session_file: Path to session file (for save/resume)
            resume: Whether to resume existing session
            annotator_id: Identifier for annotator
        """
        super().__init__()

        self.chunks_file = chunks_file
        self.session_file = session_file
        self.resume = resume
        self.annotator_id = annotator_id

        self.session: Optional[AnnotationSession] = None

    def on_mount(self) -> None:
        """Handle app mount."""
        chunks, doc_metadata = ChunkLoader.load_with_metadata(self.chunks_file)

        if self.session_file is None:
            session_name = self.chunks_file.stem
            self.session_file = Path(f".annotation_sessions/{session_name}.json")

        if not self.resume and self.session_file.exists():
            self.exit(
                message=f"Session file exists: {self.session_file}\n"
                "Use --resume to continue or delete the session file."
            )
            return

        self.session = AnnotationSession(
            chunks=chunks,
            session_file=self.session_file,
            annotator_id=self.annotator_id,
            doc_metadata=doc_metadata,
        )

        self.install_screen(AnnotationScreen(self.session), name="annotation")
        self.install_screen(StatisticsScreen(self.session), name="statistics")
        self.install_screen(HelpScreen(), name="help")

        self.push_screen("annotation")
