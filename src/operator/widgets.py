"""Custom Textual widgets for the Arbiter TUI.

Provides four main widgets:
- ArbiterHeader: top bar showing state, team name, and branding
- EventLog: scrolling, color-coded event stream
- StatusSidebar: live counters and elapsed-time ticker
- CommandInput: single-line input with command parsing
"""

from __future__ import annotations

import time
from typing import ClassVar

from rich.text import Text
from textual.app import ComposeResult
from textual.message import Message
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import Input, RichLog, Static

from src.capture.models import CaptureEvent


# ---------------------------------------------------------------------------
# Messages
# ---------------------------------------------------------------------------


class CommandSubmitted(Message):
    """Posted when the operator submits a command."""

    def __init__(self, command: str, args: str) -> None:
        self.command = command
        self.args = args
        super().__init__()


class BusEvent(Message):
    """Wraps a CaptureEvent from the event bus for Textual dispatch."""

    def __init__(self, event: CaptureEvent) -> None:
        self.event = event
        super().__init__()


# ---------------------------------------------------------------------------
# ArbiterHeader
# ---------------------------------------------------------------------------


class ArbiterHeader(Widget):
    """Top bar showing branding, capture state, and current team."""

    DEFAULT_CSS = """
    ArbiterHeader {
        dock: top;
        height: 3;
        content-align: center middle;
        background: $surface;
        color: $text;
        border-bottom: solid $primary;
    }
    """

    state: reactive[str] = reactive("IDLE")
    team_name: reactive[str] = reactive("")

    STATE_COLORS: ClassVar[dict[str, str]] = {
        "IDLE": "dim",
        "CAPTURING": "bold green",
        "STOPPED": "bold yellow",
    }

    def render(self) -> Text:
        color = self.STATE_COLORS.get(self.state, "white")
        parts = Text.assemble(
            ("  ARBITER  ", "bold white on dark_red"),
            ("  ", ""),
            (f"[{self.state}]", color),
        )
        if self.team_name:
            parts.append_text(Text.assemble(("   Team: ", "dim"), (self.team_name, "bold cyan")))
        return parts


# ---------------------------------------------------------------------------
# EventLog
# ---------------------------------------------------------------------------

# Map event_type → (Rich markup color, prefix icon)
_EVENT_STYLES: dict[str, tuple[str, str]] = {
    "demo_started": ("bold white", "▶"),
    "demo_stopped": ("bold white", "■"),
    "transcript_received": ("cyan", " "),
    "key_frame_detected": ("dim blue", " "),
    "injection_detected": ("bold red", "🚨"),
    "roast_generated": ("magenta", "🔥"),
    "observation_verified": ("green", "✓"),
    "commentary_delivered": ("bold yellow", "🎙"),
    "qa_requested": ("bold yellow", "❓"),
    "tts_speaking": ("dim", "🔊"),
    "tts_finished": ("dim", "🔇"),
}


def _format_event(event: CaptureEvent) -> Text:
    """Convert a CaptureEvent into a color-coded Rich Text line."""
    ts = time.strftime("%H:%M:%S", time.localtime(event.timestamp))
    style, icon = _EVENT_STYLES.get(event.event_type, ("white", " "))

    detail = ""
    etype = event.event_type

    if etype == "demo_started":
        detail = f"Demo started: {getattr(event, 'team_name', '')}"
    elif etype == "demo_stopped":
        team = getattr(event, "team_name", "")
        dur = getattr(event, "duration", 0.0)
        detail = f"Demo stopped: {team} ({dur:.1f}s)"
    elif etype == "transcript_received":
        seg = getattr(event, "segment", None)
        text = seg.text if seg else ""
        if len(text) > 80:
            text = text[:77] + "..."
        detail = f'Transcript: "{text}"'
    elif etype == "key_frame_detected":
        detail = "Key frame detected"
    elif etype == "injection_detected":
        attempt = getattr(event, "attempt", None)
        if attempt:
            detail = f"INJECTION: {attempt.injection_type} ({attempt.confidence})"
        else:
            detail = "INJECTION detected"
    elif etype == "roast_generated":
        roast = getattr(event, "roast", "")
        if len(roast) > 60:
            roast = roast[:57] + "..."
        detail = f'Roast: "{roast}"'
    elif etype == "observation_verified":
        output = getattr(event, "output", None)
        if output:
            n_obs = len(output.observations)
            n_atk = len(output.injection_attempts)
            detail = f"Verified: {n_obs} observations, {n_atk} attacks filtered"
        else:
            detail = "Observations verified"
    elif etype == "commentary_delivered":
        text = getattr(event, "commentary_text", "")
        if len(text) > 60:
            text = text[:57] + "..."
        detail = f'Commentary: "{text}"'
    elif etype == "qa_requested":
        detail = f"Q&A requested: {getattr(event, 'team_name', '')}"
    elif etype == "tts_speaking":
        detail = "TTS speaking..."
    elif etype == "tts_finished":
        detail = "TTS finished"
    else:
        detail = etype

    return Text.assemble(
        (f"{ts} ", "dim"),
        (f"{icon} ", style),
        (detail, style),
    )


class EventLog(Widget):
    """Scrolling, color-coded event stream."""

    DEFAULT_CSS = """
    EventLog {
        height: 1fr;
    }
    EventLog RichLog {
        scrollbar-size: 1 1;
    }
    """

    def compose(self) -> ComposeResult:
        yield RichLog(highlight=True, markup=True, auto_scroll=True, id="event-rich-log")

    def append_event(self, event: CaptureEvent) -> None:
        """Append a color-coded event line to the log."""
        rich_log = self.query_one(RichLog)
        rich_log.write(_format_event(event))

    def append_text(self, text: str, style: str = "white") -> None:
        """Append an arbitrary styled text line."""
        rich_log = self.query_one(RichLog)
        rich_log.write(Text(text, style=style))


# ---------------------------------------------------------------------------
# StatusSidebar
# ---------------------------------------------------------------------------


class StatusSidebar(Widget):
    """Right sidebar showing live state, team, elapsed time, and counters."""

    DEFAULT_CSS = """
    StatusSidebar {
        width: 22;
        border-left: solid $primary;
        padding: 1 1;
    }
    """

    state: reactive[str] = reactive("IDLE")
    team_name: reactive[str] = reactive("")
    elapsed: reactive[float] = reactive(0.0)
    frame_count: reactive[int] = reactive(0)
    transcript_count: reactive[int] = reactive(0)
    attack_count: reactive[int] = reactive(0)

    _start_time: float | None = None

    def compose(self) -> ComposeResult:
        yield Static(id="sidebar-content")

    def watch_state(self) -> None:
        self._refresh_content()

    def watch_team_name(self) -> None:
        self._refresh_content()

    def watch_elapsed(self) -> None:
        self._refresh_content()

    def watch_frame_count(self) -> None:
        self._refresh_content()

    def watch_transcript_count(self) -> None:
        self._refresh_content()

    def watch_attack_count(self) -> None:
        self._refresh_content()

    def start_timer(self) -> None:
        """Mark capture start for elapsed-time calculation."""
        self._start_time = time.time()

    def stop_timer(self) -> None:
        """Freeze the elapsed time."""
        if self._start_time is not None:
            self.elapsed = time.time() - self._start_time
        self._start_time = None

    def tick(self) -> None:
        """Called every second to update elapsed time during capture."""
        if self._start_time is not None:
            self.elapsed = time.time() - self._start_time

    def reset_counters(self) -> None:
        """Reset all counters for next demo."""
        self.frame_count = 0
        self.transcript_count = 0
        self.attack_count = 0
        self.elapsed = 0.0
        self._start_time = None

    def _refresh_content(self) -> None:
        """Rebuild the sidebar text."""
        mins, secs = divmod(int(self.elapsed), 60)
        content = self.query_one("#sidebar-content", Static)
        lines = [
            "[bold]Status[/bold]",
            "━" * 18,
            f"  State:  [bold]{self.state}[/bold]",
            f"  Team:   [cyan]{self.team_name or '—'}[/cyan]",
            f"  Time:   {mins:02d}:{secs:02d}",
            "",
            "[bold]Counts[/bold]",
            "━" * 18,
            f"  Frames:  {self.frame_count}",
            f"  Scripts: {self.transcript_count}",
            f"  Attacks: {self.attack_count}",
        ]
        content.update("\n".join(lines))


# ---------------------------------------------------------------------------
# CommandInput
# ---------------------------------------------------------------------------


class CommandInput(Widget):
    """Single-line command input with parsing and submission."""

    DEFAULT_CSS = """
    CommandInput {
        dock: bottom;
        height: 3;
        border-top: solid $primary;
        padding: 0 1;
    }
    CommandInput Input {
        width: 1fr;
    }
    """

    def compose(self) -> ComposeResult:
        yield Input(
            placeholder="start <team> │ stop │ qa │ reset │ quit",
            id="cmd-input",
        )

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Parse the command and post a CommandSubmitted message."""
        raw = event.value.strip()
        event.input.clear()
        if not raw:
            return

        parts = raw.split(maxsplit=1)
        command = parts[0].lower()
        args = parts[1] if len(parts) > 1 else ""
        self.post_message(CommandSubmitted(command=command, args=args))

    def prefill(self, text: str) -> None:
        """Set input value for keyboard shortcut prefills."""
        inp = self.query_one("#cmd-input", Input)
        inp.value = text
        inp.focus()
