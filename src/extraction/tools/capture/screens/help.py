from textual.app import ComposeResult
from textual.screen import ModalScreen
from textual.containers import VerticalScroll
from textual.widgets import Static
from textual.binding import Binding
from rich.text import Text


HELP_TEXT = """\
CHUNK CAPTURE TOOL

MOVEMENT
  h / l              Left / right
  j / k              Down / up
  w / b              Word forward / back
  0 / $              Line start / end
  gg / G             Top / bottom of document
  Ctrl+d / Ctrl+u    Half-page down / up
  Ctrl+f / Ctrl+b    Full page down / up

SELECTION
  v                  Enter visual mode (anchor + extend)
  V                  Visual line (select current line)
  m                  Mark current selection and start new range
  Escape             Cancel all selections and marks

MULTI-RANGE WORKFLOW
  1. v to enter visual mode
  2. Move cursor to extend selection
  3. m to mark the range (anchors it)
  4. Move to next region you want
  5. v to start another visual range
  6. Move to extend, m to mark again (repeat)
  7. y to capture all marked ranges as one chunk

  Marked ranges are joined with paragraph breaks.
  Token count reflects the combined text.

CAPTURE
  y                  Yank all marked + active selection as one chunk
  dd                 Delete last captured chunk
  u                  Undo last delete

CHUNK LIST
  Tab                Switch focus to chunk list
  j / k              Navigate chunks
  Enter / l          View chunk detail
  dd                 Delete selected chunk
  u                  Undo delete
  h / Escape         Return focus to document

SESSION
  r                  Review captured chunks
  x                  Export (in review screen)
  Ctrl+s             Save session
  ?                  This help
  q                  Save and quit
"""


class HelpScreen(ModalScreen):

    BINDINGS = [
        Binding("escape", "dismiss", "Close", show=True),
        Binding("question_mark", "dismiss", "Close", show=False),
        Binding("q", "dismiss", "Close", show=False),
    ]

    DEFAULT_CSS = """
    HelpScreen {
        align: center middle;
    }

    #help_container {
        width: 60;
        height: 80%;
        border: thick $primary;
        background: $surface;
        padding: 1 2;
    }
    """

    def compose(self) -> ComposeResult:
        with VerticalScroll(id="help_container"):
            yield Static(Text(HELP_TEXT))

    def action_dismiss(self) -> None:
        self.app.pop_screen()
