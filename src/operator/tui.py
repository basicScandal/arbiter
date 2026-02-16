"""Textual-based TUI for operator demo lifecycle control.

Replaces the stdin CLI with a btop-aesthetic terminal dashboard featuring
real-time event streaming, color-coded logs, live status counters, sparkline
graphs, defense panel, and keyboard shortcuts. Bridges the async EventBus
into Textual's message system.
"""

from __future__ import annotations

import logging
from pathlib import Path

from statemachine.exceptions import TransitionNotAllowed
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal
from textual.timer import Timer
from textual.widgets import Footer

from src.capture.demo_machine import DemoMachine
from src.capture.event_bus import EventBus
from src.capture.models import CaptureEvent
from src.commentary.models import QARequested
from src.memory.models import DeliberationRequested
from src.operator.widgets import (
    ArbiterHeader,
    BusEvent,
    CommandInput,
    CommandSubmitted,
    DefensePanel,
    EventLog,
    StatusSidebar,
)

logger = logging.getLogger(__name__)


class ArbiterTUI(App):
    """Textual TUI application for Arbiter operator control.

    Composes the six-panel layout (header, event log, sidebar, defense panel,
    command input, footer) and bridges the EventBus into Textual's message
    loop for live updates.

    Args:
        demo_machine: The DemoMachine controlling demo lifecycle.
        event_bus: Event bus for subscribing to capture events and publishing commands.
    """

    CSS_PATH = Path(__file__).parent / "tui.tcss"

    TITLE = "Arbiter"

    BINDINGS = [
        Binding("ctrl+s", "prefill_start", "Start", show=True),
        Binding("ctrl+x", "send_stop", "Stop", show=True),
        Binding("ctrl+r", "send_reset", "Reset", show=True),
        Binding("ctrl+q", "quit_app", "Quit", show=True),
    ]

    def __init__(
        self,
        demo_machine: DemoMachine,
        event_bus: EventBus | None = None,
    ) -> None:
        super().__init__()
        self.demo_machine = demo_machine
        self.event_bus = event_bus
        self._tick_timer: Timer | None = None

    # ------------------------------------------------------------------
    # Compose
    # ------------------------------------------------------------------

    def compose(self) -> ComposeResult:
        yield ArbiterHeader()
        with Horizontal(id="main-container"):
            yield EventLog()
            yield StatusSidebar()
        yield DefensePanel()
        yield CommandInput()
        yield Footer()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def on_mount(self) -> None:
        """Subscribe to the event bus and start the sidebar ticker."""
        if self.event_bus is not None:
            self.event_bus.subscribe_all(self._on_bus_event)

        # 1-second ticker for elapsed time, sparkline, and pulse
        self._tick_timer = self.set_interval(1.0, self._tick)

        # Welcome message
        event_log = self.query_one(EventLog)
        event_log.append_text("Arbiter TUI ready. Type 'start <team>' to begin.", "bold white")
        event_log.append_text("Type 'help' for available commands.", "dim")

    # ------------------------------------------------------------------
    # Tick handler (1-second interval)
    # ------------------------------------------------------------------

    def _tick(self) -> None:
        """Update sidebar, header elapsed, and pulse every second."""
        sidebar = self.query_one(StatusSidebar)
        sidebar.tick()

        header = self.query_one(ArbiterHeader)
        header.elapsed = sidebar.elapsed
        # Toggle pulse for CAPTURING animation
        header._pulse = not header._pulse

    # ------------------------------------------------------------------
    # Event bus bridge
    # ------------------------------------------------------------------

    async def _on_bus_event(self, event: CaptureEvent) -> None:
        """Bridge: EventBus subscriber → Textual message."""
        self.post_message(BusEvent(event))

    def on_bus_event(self, message: BusEvent) -> None:
        """Dispatch bus events to widget updates."""
        event = message.event
        etype = event.event_type

        # Always append to event log
        event_log = self.query_one(EventLog)
        event_log.append_event(event)

        # Update header, sidebar, defense panel
        header = self.query_one(ArbiterHeader)
        sidebar = self.query_one(StatusSidebar)
        defense = self.query_one(DefensePanel)

        # Increment sparkline event counter
        sidebar.increment_event_count()

        if etype == "demo_started":
            team = getattr(event, "team_name", "")
            header.state = "CAPTURING"
            header.team_name = team
            sidebar.state = "CAPTURING"
            sidebar.team_name = team
            sidebar.start_timer()

        elif etype == "demo_stopped":
            header.state = "STOPPED"
            sidebar.state = "STOPPED"
            sidebar.stop_timer()

        elif etype == "key_frame_detected":
            sidebar.frame_count += 1

        elif etype == "transcript_received":
            sidebar.transcript_count += 1

        elif etype == "injection_detected":
            sidebar.attack_count += 1
            defense.injection_count += 1

        elif etype == "roast_generated":
            roast = getattr(event, "roast", "")
            defense.last_roast = roast

        elif etype == "observation_verified":
            output = getattr(event, "output", None)
            if output:
                defense.clean_count += len(output.observations)

    # ------------------------------------------------------------------
    # Command handling
    # ------------------------------------------------------------------

    def on_command_submitted(self, message: CommandSubmitted) -> None:
        """Route operator commands to handler methods."""
        command = message.command
        args = message.args
        event_log = self.query_one(EventLog)

        try:
            if command == "start":
                self._handle_start(args)
            elif command == "stop":
                self._handle_stop()
            elif command == "reset":
                self._handle_reset()
            elif command == "qa":
                self._handle_qa()
            elif command == "status":
                self._handle_status()
            elif command == "deliberate":
                self._handle_deliberate()
            elif command in ("quit", "exit"):
                self.exit()
                return
            elif command == "help":
                self._print_help()
            else:
                event_log.append_text(
                    f"Unknown command: '{command}'. Type 'help' for commands.",
                    "bold red",
                )
        except TransitionNotAllowed:
            state_id = self.demo_machine.current_state.id
            event_log.append_text(
                f"Cannot '{command}': not allowed in state '{state_id}'.",
                "bold red",
            )
            hint = self._get_state_hint(command, state_id)
            if hint:
                event_log.append_text(f"  Hint: {hint}", "yellow")

    def _handle_start(self, args: str) -> None:
        event_log = self.query_one(EventLog)
        team_name = args.strip()
        if not team_name:
            event_log.append_text("Usage: start <team_name>", "yellow")
            return
        self.demo_machine.send("start_demo", team_name=team_name)
        logger.info("Operator started demo for team: %s", team_name)

    def _handle_stop(self) -> None:
        session = self.demo_machine.current_session
        self.demo_machine.send("stop_demo")
        logger.info("Operator stopped demo for team: %s", session.team_name if session else "Unknown")

    def _handle_reset(self) -> None:
        self.demo_machine.send("reset")
        header = self.query_one(ArbiterHeader)
        sidebar = self.query_one(StatusSidebar)
        defense = self.query_one(DefensePanel)
        header.state = "IDLE"
        header.team_name = ""
        header.elapsed = 0.0
        sidebar.state = "IDLE"
        sidebar.team_name = ""
        sidebar.reset_counters()
        defense.last_roast = ""
        defense.injection_count = 0
        defense.clean_count = 0
        event_log = self.query_one(EventLog)
        event_log.append_text("Ready for next demo.", "bold green")
        logger.info("Operator reset demo machine")

    def _handle_qa(self) -> None:
        event_log = self.query_one(EventLog)
        if self.event_bus is None:
            event_log.append_text("Q&A not available (no event bus).", "yellow")
            return

        state_id = self.demo_machine.current_state.id
        if state_id != "stopped":
            event_log.append_text(
                f"Q&A only available after demo stops (current: '{state_id}').",
                "yellow",
            )
            return

        session = self.demo_machine.current_session
        team_name = session.team_name if session else "Unknown"
        self.event_bus.publish(QARequested(team_name=team_name))
        event_log.append_text(f"Q&A mode activated for team: {team_name}", "bold yellow")
        logger.info("Operator triggered Q&A for team: %s", team_name)

    def _handle_status(self) -> None:
        event_log = self.query_one(EventLog)
        state_id = self.demo_machine.current_state.id
        session = self.demo_machine.current_session

        event_log.append_text(f"State: {state_id}", "bold white")
        if session:
            event_log.append_text(f"  Team: {session.team_name}", "cyan")
        else:
            event_log.append_text("  No active session", "dim")

    def _handle_deliberate(self) -> None:
        event_log = self.query_one(EventLog)
        if self.event_bus is None:
            event_log.append_text("Deliberation not available (no event bus).", "yellow")
            return
        self.event_bus.publish(DeliberationRequested())
        event_log.append_text("Deliberation triggered. Processing all demos...", "bold magenta")
        logger.info("Operator triggered end-of-event deliberation")

    def _print_help(self) -> None:
        event_log = self.query_one(EventLog)
        event_log.append_text("Available commands:", "bold white")
        event_log.append_text("  start <team>  Start a demo", "dim")
        event_log.append_text("  stop          Stop the current demo", "dim")
        event_log.append_text("  qa            Generate Q&A questions", "dim")
        event_log.append_text("  reset         Reset for next demo", "dim")
        event_log.append_text("  deliberate    Run final deliberation", "dim")
        event_log.append_text("  status        Show current state", "dim")
        event_log.append_text("  help          Show this message", "dim")
        event_log.append_text("  quit          Exit Arbiter", "dim")

    @staticmethod
    def _get_state_hint(command: str, state_id: str) -> str | None:
        hints = {
            ("start", "capturing"): "A demo is already in progress. Stop it first.",
            ("start", "stopped"): "Previous demo not cleared. Run 'reset' first.",
            ("stop", "idle"): "No demo in progress. Start one with 'start <team>'.",
            ("stop", "stopped"): "Demo already stopped. Run 'reset' to prepare for next.",
            ("reset", "idle"): "Already idle. Start a demo with 'start <team>'.",
            ("reset", "capturing"): "Demo still in progress. Stop it first.",
        }
        return hints.get((command, state_id))

    # ------------------------------------------------------------------
    # Keyboard actions
    # ------------------------------------------------------------------

    def action_prefill_start(self) -> None:
        """Prefill the command input with 'start '."""
        self.query_one(CommandInput).prefill("start ")

    def action_send_stop(self) -> None:
        """Send the stop command directly."""
        self.post_message(CommandSubmitted(command="stop", args=""))

    def action_send_reset(self) -> None:
        """Send the reset command directly."""
        self.post_message(CommandSubmitted(command="reset", args=""))

    def action_quit_app(self) -> None:
        """Exit the application."""
        self.exit()

    # ------------------------------------------------------------------
    # Public async interface (matches OperatorCLI.run signature)
    # ------------------------------------------------------------------

    async def run(self) -> None:  # type: ignore[override]
        """Run the TUI. Drop-in replacement for OperatorCLI.run()."""
        await self.run_async()
