"""Custom Textual widgets for the Arbiter TUI.

Provides six main widgets:
- ArbiterHeader: top bar with colored state dot, team name, elapsed timer
- EventLog: scrolling, color-coded event stream with alternating row tint
- StatusSidebar: live counters with mini bars, sparkline, state indicators
- DefensePanel: last roast, injection/clean counts, shield bar
- CommandInput: single-line input with ❯ prompt and state coloring
- BusEvent / CommandSubmitted: Textual messages for event bridging
"""

from __future__ import annotations

import time
from typing import ClassVar

from rich.text import Text
from textual.app import ComposeResult
from textual.message import Message
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import Input, RichLog, Sparkline, Static

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


class BusEvent(Message, bubble=False):
    """Wraps a CaptureEvent from the event bus for Textual dispatch.

    bubble=False prevents infinite re-dispatch through the App→Screen cycle.
    """

    def __init__(self, event: CaptureEvent) -> None:
        self.event = event
        super().__init__()


class LogRecord(Message, bubble=False):
    """Routes a logging record into the TUI event log via the message loop.

    bubble=False because this is posted directly to the App, not a child widget.
    """

    def __init__(self, text: str, style: str) -> None:
        self.text = text
        self.style = style
        super().__init__()


# ---------------------------------------------------------------------------
# ArbiterHeader
# ---------------------------------------------------------------------------


class ArbiterHeader(Widget):
    """Top bar showing branding, capture state, team, and elapsed time."""

    state: reactive[str] = reactive("IDLE")
    team_name: reactive[str] = reactive("")
    elapsed: reactive[float] = reactive(0.0)
    _pulse: reactive[bool] = reactive(False)

    STATE_DOTS: ClassVar[dict[str, tuple[str, str]]] = {
        "IDLE": ("○", "dim"),
        "CAPTURING": ("◉", "bold green"),
        "STOPPED": ("◆", "bold yellow"),
    }

    def on_mount(self) -> None:
        self.border_title = "ARBITER ── v0.1"

    def render(self) -> Text:
        dot, style = self.STATE_DOTS.get(self.state, ("○", "white"))
        # Pulse between green shades when capturing
        if self.state == "CAPTURING":
            style = "bold bright_green" if self._pulse else "bold green"

        mins, secs = divmod(int(self.elapsed), 60)

        parts = Text.assemble(
            ("  ", ""),
            (f"{dot} {self.state}", style),
        )
        if self.team_name:
            parts.append_text(
                Text.assemble(("    Team: ", "dim"), (self.team_name, "bold cyan"))
            )
        parts.append_text(
            Text.assemble(("    ⏱ ", "dim"), (f"{mins:02d}:{secs:02d}", "bold white"))
        )
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


def _format_event(event: CaptureEvent, line_count: int) -> Text:
    """Convert a CaptureEvent into a color-coded Rich Text line."""
    ts = time.strftime("%H:%M:%S", time.localtime(event.timestamp))
    style, icon = _EVENT_STYLES.get(event.event_type, ("white", " "))

    # Alternating row tint: dim left-bar on even lines, space on odd
    prefix = "[dim]▎[/dim] " if line_count % 2 == 0 else "  "

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

    return Text.from_markup(
        f"{prefix}[dim]{ts}[/dim] [{style}]{icon} {detail}[/{style}]"
    )


class EventLog(Widget):
    """Scrolling, color-coded event stream with alternating row tint."""

    _line_count: int = 0

    def compose(self) -> ComposeResult:
        yield RichLog(highlight=True, markup=True, auto_scroll=True, id="event-rich-log")

    def on_mount(self) -> None:
        self.border_title = "Event Log"

    def append_event(self, event: CaptureEvent) -> None:
        """Append a color-coded event line to the log."""
        rich_log = self.query_one(RichLog)
        rich_log.write(_format_event(event, self._line_count))
        self._line_count += 1

    def append_text(self, text: str, style: str = "white") -> None:
        """Append an arbitrary styled text line."""
        prefix = "▎ " if self._line_count % 2 == 0 else "  "
        rich_log = self.query_one(RichLog)
        rich_log.write(Text.assemble((prefix, "dim"), (text, style)))
        self._line_count += 1


# ---------------------------------------------------------------------------
# StatusSidebar
# ---------------------------------------------------------------------------


def _mini_bar(value: int, max_val: int, width: int = 8) -> str:
    """Render a mini Unicode bar chart: █ for filled, ░ for empty."""
    if max_val <= 0:
        return "░" * width
    filled = round(value / max_val * width)
    filled = min(filled, width)
    return "█" * filled + "░" * (width - filled)


class StatusSidebar(Widget):
    """Right sidebar showing live state, team, elapsed time, counters with mini bars, and sparkline."""

    state: reactive[str] = reactive("IDLE")
    team_name: reactive[str] = reactive("")
    elapsed: reactive[float] = reactive(0.0)
    frame_count: reactive[int] = reactive(0)
    transcript_count: reactive[int] = reactive(0)
    attack_count: reactive[int] = reactive(0)

    _start_time: float | None = None
    _event_history: list[float] = []
    _current_second_count: int = 0

    STATE_DOTS: ClassVar[dict[str, tuple[str, str]]] = {
        "IDLE": ("○", "dim"),
        "CAPTURING": ("◉", "bold green"),
        "STOPPED": ("◆", "bold yellow"),
    }

    def compose(self) -> ComposeResult:
        yield Static(id="sidebar-content")
        yield Sparkline([], id="sidebar-sparkline")

    def on_mount(self) -> None:
        self.border_title = "Status"
        self._event_history = [0.0] * 30

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
        """Called every second to update elapsed time and sparkline."""
        if self._start_time is not None:
            self.elapsed = time.time() - self._start_time

        # Rotate sparkline: shift left, append current second's count
        self._event_history.append(float(self._current_second_count))
        if len(self._event_history) > 30:
            self._event_history = self._event_history[-30:]
        self._current_second_count = 0

        # Update sparkline widget
        try:
            sparkline = self.query_one("#sidebar-sparkline", Sparkline)
            sparkline.data = self._event_history
        except Exception:
            pass

    def increment_event_count(self) -> None:
        """Increment the current second's event counter for sparkline."""
        self._current_second_count += 1

    def reset_counters(self) -> None:
        """Reset all counters for next demo."""
        self.frame_count = 0
        self.transcript_count = 0
        self.attack_count = 0
        self.elapsed = 0.0
        self._start_time = None
        self._event_history = [0.0] * 30
        self._current_second_count = 0

    def _refresh_content(self) -> None:
        """Rebuild the sidebar text with colored dots and mini bars."""
        dot, dot_style = self.STATE_DOTS.get(self.state, ("○", "white"))
        mins, secs = divmod(int(self.elapsed), 60)

        # Dynamic max for bar scaling
        max_val = max(self.frame_count, self.transcript_count, self.attack_count, 10)

        # Calculate percentages for display
        total = self.frame_count + self.transcript_count + self.attack_count
        frame_pct = round(self.frame_count / total * 100) if total > 0 else 0
        script_pct = round(self.transcript_count / total * 100) if total > 0 else 0
        attack_pct = round(self.attack_count / total * 100) if total > 0 else 0

        content = self.query_one("#sidebar-content", Static)
        lines = [
            f"  [dim]State[/dim]  [{dot_style}]{dot} {self.state}[/{dot_style}]",
            f"  [dim]Team[/dim]   [cyan]{self.team_name or '—'}[/cyan]",
            f"  [dim]Time[/dim]   [bold white]{mins:02d}:{secs:02d}[/bold white]",
            "",
            "  [dim]Events/sec[/dim]",
            "",
            f"  [dim]Frames[/dim]  [bold]{self.frame_count:>3}[/bold]  [green]{_mini_bar(self.frame_count, max_val)}[/green] [dim]{frame_pct}%[/dim]",
            f"  [dim]Scripts[/dim] [bold]{self.transcript_count:>3}[/bold]  [cyan]{_mini_bar(self.transcript_count, max_val)}[/cyan] [dim]{script_pct}%[/dim]",
            f"  [dim]Attacks[/dim] [bold]{self.attack_count:>3}[/bold]  [red]{_mini_bar(self.attack_count, max_val)}[/red] [dim]{attack_pct}%[/dim]",
        ]
        content.update("\n".join(lines))


# ---------------------------------------------------------------------------
# DefensePanel
# ---------------------------------------------------------------------------


class DefensePanel(Widget):
    """Bottom panel showing last roast, injection/clean counts, and shield bar."""

    last_roast: reactive[str] = reactive("")
    injection_count: reactive[int] = reactive(0)
    clean_count: reactive[int] = reactive(0)

    def compose(self) -> ComposeResult:
        yield Static(id="defense-content")

    def on_mount(self) -> None:
        self.border_title = "Defense"
        self._refresh_content()

    def watch_last_roast(self) -> None:
        self._refresh_content()

    def watch_injection_count(self) -> None:
        self._refresh_content()

    def watch_clean_count(self) -> None:
        self._refresh_content()

    def _refresh_content(self) -> None:
        """Rebuild the defense panel content."""
        content = self.query_one("#defense-content", Static)

        roast_display = self.last_roast if self.last_roast else "[dim]No roasts yet[/dim]"
        if len(roast_display) > 90:
            roast_display = roast_display[:87] + "..."

        total = self.injection_count + self.clean_count
        clean_pct = round(self.clean_count / total * 100) if total > 0 else 100
        shield_width = 20
        filled = round(clean_pct / 100 * shield_width)
        shield_bar = "█" * filled + "░" * (shield_width - filled)

        shield_color = "green" if clean_pct >= 80 else ("yellow" if clean_pct >= 50 else "red")

        lines = [
            f"  [dim]Last roast:[/dim] [magenta]{roast_display}[/magenta]",
            f"  [dim]Injections blocked:[/dim] [bold red]{self.injection_count}[/bold red]"
            f"    [dim]Clean observations:[/dim] [bold green]{self.clean_count}[/bold green]"
            f"    [dim]Shield:[/dim] [{shield_color}]{shield_bar}[/{shield_color}] [bold]{clean_pct}%[/bold]",
        ]
        content.update("\n".join(lines))


# ---------------------------------------------------------------------------
# CommandInput
# ---------------------------------------------------------------------------


class CommandInput(Widget):
    """Single-line command input with ❯ prompt and state coloring."""

    def compose(self) -> ComposeResult:
        yield Input(
            placeholder="❯ start <team> │ stop │ qa │ reset │ quit",
            id="cmd-input",
        )

    def on_mount(self) -> None:
        self.border_title = "Command"
        self.query_one("#cmd-input", Input).focus()

    def on_click(self) -> None:
        """Focus the input when clicking anywhere in the command panel."""
        self.query_one("#cmd-input", Input).focus()

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
