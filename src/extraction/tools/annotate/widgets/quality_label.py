"""Quality labeling widget."""

from textual.app import ComposeResult
from textual.containers import VerticalScroll, Horizontal
from textual.widget import Widget
from textual.widgets import Static, Button, Input, Select
from textual.message import Message
from typing import Optional


class QualityLabel(VerticalScroll):
    """Widget for labeling chunk quality."""

    DEFAULT_CSS = """
    QualityLabel {
        border: solid $primary;
        padding: 1;
        height: 1fr;
    }

    QualityLabel Static {
        margin: 0 1 1 1;
    }

    QualityLabel Horizontal {
        height: auto;
        align: center middle;
    }

    QualityLabel Button {
        margin: 0 1;
    }

    QualityLabel .good {
        background: $success;
    }

    QualityLabel .bad {
        background: $error;
    }

    QualityLabel .skip {
        background: $warning;
    }

    QualityLabel Input {
        margin: 1;
    }

    QualityLabel Select {
        margin: 0 1;
        width: 20;
    }
    """

    class LabelSubmitted(Message):
        """Message emitted when label is submitted."""

        def __init__(
            self,
            label: Optional[int],
            rationale: str,
            confidence: Optional[int],
        ):
            super().__init__()
            self.label = label
            self.rationale = rationale
            self.confidence = confidence

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.rationale_input: Input | None = None
        self.confidence_select: Select | None = None

    def compose(self) -> ComposeResult:
        """Compose quality label widgets."""
        yield Static("[bold]Quality Label[/bold]")

        button_container = Horizontal()
        with button_container:
            yield Button("GOOD for RAG (g)", id="label_good", classes="good")
            yield Button("BAD for RAG (b)", id="label_bad", classes="bad")
            yield Button("SKIP (s)", id="label_skip", classes="skip")

        yield Static("Confidence (optional):")
        self.confidence_select = Select(
            [
                ("Not set", None),
                ("1 star - Very uncertain", 1),
                ("2 stars - Uncertain", 2),
                ("3 stars - Neutral", 3),
                ("4 stars - Confident", 4),
                ("5 stars - Very confident", 5),
            ],
            id="confidence_select",
            allow_blank=False,
        )
        yield self.confidence_select

        yield Static("Rationale (optional):")
        self.rationale_input = Input(
            placeholder="Why is this good/bad for RAG?",
            id="rationale_input",
        )
        yield self.rationale_input

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button press."""
        if event.button.id == "label_good":
            self._submit_label(0)
        elif event.button.id == "label_bad":
            self._submit_label(1)
        elif event.button.id == "label_skip":
            self._submit_label(None)

    def _submit_label(self, label: Optional[int]) -> None:
        """Submit label with rationale and confidence.

        Args:
            label: 0=GOOD, 1=BAD, None=SKIP
        """
        rationale = self.rationale_input.value if self.rationale_input else ""
        confidence = self.confidence_select.value if self.confidence_select else None

        self.post_message(
            self.LabelSubmitted(
                label=label,
                rationale=rationale,
                confidence=confidence,
            )
        )

    def clear(self) -> None:
        """Clear rationale and confidence."""
        if self.rationale_input:
            self.rationale_input.value = ""

        if self.confidence_select:
            self.confidence_select.value = None

    def set_annotation(
        self,
        label: Optional[int],
        rationale: str = "",
        confidence: Optional[int] = None,
    ) -> None:
        """Set existing annotation values.

        Args:
            label: 0=GOOD, 1=BAD, None=SKIP
            rationale: Annotation rationale
            confidence: 1-5 stars
        """
        if self.rationale_input:
            self.rationale_input.value = rationale

        if self.confidence_select and confidence is not None:
            self.confidence_select.value = confidence
