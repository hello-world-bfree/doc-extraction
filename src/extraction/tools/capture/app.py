from textual.app import App
from pathlib import Path
from typing import Optional

from .core.session import CaptureSession
from .core.document_loader import DocumentLoader, DocumentText
from .core.token_counter import TokenCounter
from .screens import CaptureScreen, ReviewScreen, HelpScreen


class CaptureApp(App):

    CSS = """
    #main_layout {
        height: 1fr;
    }

    #doc_column {
        width: 70%;
    }

    #document_view {
        height: 1fr;
    }

    #selection_info {
        height: 1;
    }

    #chunk_list {
        width: 30%;
    }

    #review_container {
        height: 1fr;
        padding: 1;
    }

    #review_summary {
        height: 3;
        border: solid $accent;
        padding: 0 1;
    }

    #review_chunk_view {
        height: 1fr;
        border: solid $primary;
        padding: 1;
    }

    #review_nav {
        height: 1;
        background: $panel;
        color: $text;
    }
    """

    TITLE = "Chunk Capture Tool"

    def __init__(
        self,
        document_path: Path,
        session_file: Optional[Path] = None,
        resume: bool = False,
        grpc_target: str = "localhost:50051",
    ):
        super().__init__()
        self.document_path = document_path
        self.session_file = session_file
        self.resume = resume
        self.grpc_target = grpc_target

        self._document: Optional[DocumentText] = None
        self.token_counter: Optional[TokenCounter] = None
        self.session: Optional[CaptureSession] = None

    def load_document(self) -> None:
        self._document = DocumentLoader.load(self.document_path)

    def on_mount(self) -> None:
        if self._document is None:
            self._document = DocumentLoader.load(self.document_path)

        if self.session_file is None:
            session_name = self.document_path.stem
            self.session_file = Path(f".capture_sessions/{session_name}.json")

        if not self.resume and self.session_file.exists():
            self.exit(
                message=f"Session file exists: {self.session_file}\n"
                "Use --resume to continue or delete the session file."
            )
            return

        self.token_counter = TokenCounter(self.grpc_target)

        self.session = CaptureSession(
            document_path=self.document_path,
            doc_metadata=self._document.doc_metadata,
            session_file=self.session_file,
        )

        self.install_screen(
            CaptureScreen(self._document, self.session, self.token_counter),
            name="capture",
        )
        self.install_screen(
            ReviewScreen(self.session),
            name="review",
        )
        self.install_screen(HelpScreen(), name="help")

        self.push_screen("capture")

    def on_unmount(self) -> None:
        if self.token_counter:
            self.token_counter.close()
