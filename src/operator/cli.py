"""Simple stdin-based CLI for operator demo lifecycle control.

Provides a command-line interface for the human operator to start, stop,
and reset demo sessions during the live hackathon event. Commands map
directly to DemoMachine state transitions. Supports optional track
assignment when starting a demo (e.g., start TeamName SHADOW::VECTOR).
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import TYPE_CHECKING

from statemachine.exceptions import TransitionNotAllowed

from src.capture.demo_machine import DemoMachine
from src.capture.event_bus import EventBus
from src.commentary.models import QARequested
from src.config.tracks import DEFAULT_TRACK, VALID_TRACKS
from src.memory.models import DeliberationRequested

if TYPE_CHECKING:
    from src.memory.pipeline import DeliberationPipeline
    from src.scoring.pipeline import ScoringPipeline

logger = logging.getLogger(__name__)


class OperatorCLI:
    """Interactive CLI for controlling demo lifecycle during the event.

    Reads commands from stdin and translates them into DemoMachine state
    transitions. Handles invalid transitions gracefully with user-friendly
    error messages rather than stack traces.

    Args:
        demo_machine: The DemoMachine instance controlling demo lifecycle.
        event_bus: Optional event bus for publishing Q&A and other events.
        scoring_pipeline: Optional scoring pipeline for track assignment.
    """

    def __init__(
        self,
        demo_machine: DemoMachine,
        event_bus: EventBus | None = None,
        scoring_pipeline: ScoringPipeline | None = None,
        deliberation_pipeline: DeliberationPipeline | None = None,
    ) -> None:
        self.demo_machine = demo_machine
        self.event_bus = event_bus
        self.scoring_pipeline = scoring_pipeline
        self.deliberation_pipeline = deliberation_pipeline

    async def run(self) -> None:
        """Main CLI loop: read commands from stdin and execute them.

        Uses asyncio.to_thread(input, ...) to avoid blocking the event loop.
        Handles KeyboardInterrupt, EOFError, and invalid state transitions
        with clear user feedback.
        """
        self._print_banner()

        while True:
            try:
                state_id = self.demo_machine.current_state.id
                prompt = f"[{state_id}] arbiter> "
                raw = await asyncio.to_thread(input, prompt)
            except KeyboardInterrupt:
                print("\nUse 'quit' to exit.")
                continue
            except EOFError:
                print("\nEOF received. Shutting down.")
                break

            line = raw.strip()
            if not line:
                continue

            parts = line.split(maxsplit=1)
            command = parts[0].lower()
            args = parts[1] if len(parts) > 1 else ""

            try:
                if command == "start":
                    self._handle_start(args)
                elif command == "stop":
                    self._handle_stop()
                elif command == "reset":
                    self._handle_reset()
                elif command == "qa":
                    self._handle_qa()
                elif command == "score":
                    self._handle_score()
                elif command == "deliberate":
                    self._handle_deliberate()
                elif command == "pause":
                    self._handle_pause()
                elif command == "resume":
                    self._handle_resume()
                elif command == "status":
                    self._handle_status()
                elif command in ("quit", "exit"):
                    print("Shutting down.")
                    break
                elif command == "help":
                    self._print_help()
                else:
                    print(f"Unknown command: '{command}'. Type 'help' for available commands.")
            except TransitionNotAllowed:
                state_id = self.demo_machine.current_state.id
                print(f"Cannot '{command}': not allowed in current state '{state_id}'.")
                self._print_state_hint(command, state_id)

    def _handle_start(self, args: str) -> None:
        """Handle the 'start' command to begin a demo session.

        Accepts optional track argument: start <team_name> [track]
        Valid tracks are loaded from shared/tracks.json.
        """
        parts = args.strip().split()
        if not parts:
            print("Usage: start <team_name> [track]")
            return

        team_name = parts[0]
        track = parts[1] if len(parts) > 1 else None

        # Handle track assignment
        if track is not None and self.scoring_pipeline is not None:
            if track in VALID_TRACKS:
                self.scoring_pipeline.set_track(team_name, track)
                if self.deliberation_pipeline is not None:
                    self.deliberation_pipeline.set_track(team_name, track)
                logger.info("Track %s assigned to team %s", track, team_name)
            else:
                print(f"Warning: Unknown track '{track}'. Valid tracks: {', '.join(sorted(VALID_TRACKS))}")
                print(f"  Demo will start but scoring will use default track {DEFAULT_TRACK}.")
        elif track is None:
            print(f"No track specified -- defaulting to {DEFAULT_TRACK} for scoring")

        self.demo_machine.send("start_demo", team_name=team_name)
        print(f"Demo started for team: {team_name}")
        logger.info("Operator started demo for team: %s", team_name)

    def _handle_stop(self) -> None:
        """Handle the 'stop' command to end the current demo session."""
        session = self.demo_machine.current_session
        self.demo_machine.send("stop_demo")
        duration = 0.0
        if session and session.started_at:
            duration = time.time() - session.started_at
        team = session.team_name if session else "Unknown"
        print(f"Demo stopped for team: {team} (duration: {duration:.1f}s)")
        logger.info("Operator stopped demo for team: %s (%.1fs)", team, duration)

    def _handle_pause(self) -> None:
        """Handle the 'pause' command to temporarily halt the demo."""
        session = self.demo_machine.current_session
        self.demo_machine.send("pause_demo")
        team = session.team_name if session else "Unknown"
        print(f"Demo paused for team: {team}")
        logger.info("Operator paused demo for team: %s", team)

    def _handle_resume(self) -> None:
        """Handle the 'resume' command to continue a paused demo."""
        session = self.demo_machine.current_session
        self.demo_machine.send("resume_demo")
        team = session.team_name if session else "Unknown"
        print(f"Demo resumed for team: {team}")
        logger.info("Operator resumed demo for team: %s", team)

    def _handle_reset(self) -> None:
        """Handle the 'reset' command to prepare for the next demo."""
        self.demo_machine.send("reset")
        print("Ready for next demo.")
        logger.info("Operator reset demo machine")

    def _handle_qa(self) -> None:
        """Handle the 'qa' command to trigger Q&A question generation."""
        if self.event_bus is None:
            print("Q&A not available (no event bus configured).")
            return

        state_id = self.demo_machine.current_state.id
        if state_id != "stopped":
            print(f"Q&A only available after demo stops (current state: '{state_id}').")
            if state_id == "capturing":
                print("  Hint: Stop the demo first with 'stop'.")
            elif state_id == "idle":
                print("  Hint: Start and complete a demo first.")
            return

        session = self.demo_machine.current_session
        team_name = session.team_name if session else "Unknown"
        self.event_bus.publish(QARequested(team_name=team_name))
        print(f"Q&A mode activated for team: {team_name}")
        logger.info("Operator triggered Q&A for team: %s", team_name)

    def _handle_score(self) -> None:
        """Handle the 'score' command to show scoring status."""
        if self.scoring_pipeline is None:
            print("Scoring pipeline not configured.")
            return

        pending = self.scoring_pipeline._pending_scorecards
        if pending:
            for team, sc in pending.items():
                print(f"  Pending reveal for {team}: {sc.total_score:.1f} ({sc.track})")
        else:
            print("No pending scores. Scores are displayed on screen after commentary.")

    def _handle_deliberate(self) -> None:
        """Handle the 'deliberate' command to trigger end-of-event deliberation."""
        if self.event_bus is None:
            print("Deliberation not available (no event bus configured).")
            return
        self.event_bus.publish(DeliberationRequested())
        print("Deliberation triggered. Processing all demos...")
        logger.info("Operator triggered end-of-event deliberation")

    def _handle_status(self) -> None:
        """Handle the 'status' command to show current state info."""
        state_id = self.demo_machine.current_state.id
        session = self.demo_machine.current_session

        print(f"State: {state_id}")
        if session:
            print(f"  Team: {session.team_name}")
            if session.started_at:
                elapsed = time.time() - session.started_at
                print(f"  Duration: {elapsed:.1f}s")
            if session.stopped_at:
                duration = session.stopped_at - (session.started_at or 0)
                print(f"  Final duration: {duration:.1f}s")
        else:
            print("  No active session")

    def _print_banner(self) -> None:
        """Print the CLI welcome banner."""
        print("Arbiter Operator CLI")
        print("Type 'help' for available commands.")
        print()

    def _print_help(self) -> None:
        """Print available commands."""
        print("Available commands:")
        tracks_str = ", ".join(sorted(VALID_TRACKS))
        print(f"  start <team> [track]  - Start a demo (tracks: {tracks_str})")
        print("  stop                  - Stop the current demo")
        print("  pause                 - Pause the current demo")
        print("  resume                - Resume a paused demo")
        print("  qa                    - Generate Q&A questions for the last demo")
        print("  score                 - Show scoring status")
        print("  deliberate            - Run end-of-event comparative deliberation")
        print("  reset                 - Reset for the next demo")
        print("  status                - Show current state and session info")
        print("  help                  - Show this help message")
        print("  quit / exit           - Shut down the CLI")

    @staticmethod
    def _print_state_hint(command: str, state_id: str) -> None:
        """Print a helpful hint when a transition is not allowed."""
        hints = {
            ("start", "capturing"): "A demo is already in progress. Stop it first with 'stop'.",
            ("start", "stopped"): "Previous demo not cleared. Run 'reset' first.",
            ("stop", "idle"): "No demo in progress. Start one with 'start <team_name>'.",
            ("stop", "stopped"): "Demo already stopped. Run 'reset' to prepare for next.",
            ("pause", "idle"): "No demo in progress.",
            ("pause", "stopped"): "Demo already stopped.",
            ("pause", "paused"): "Demo already paused.",
            ("resume", "idle"): "No demo to resume.",
            ("resume", "capturing"): "Demo is already running.",
            ("resume", "stopped"): "Demo is stopped. Use 'reset' to prepare next demo.",
            ("reset", "idle"): "Already in idle state. Start a demo with 'start <team_name>'.",
            ("reset", "capturing"): "Demo still in progress. Stop it first with 'stop'.",
        }
        hint = hints.get((command, state_id))
        if hint:
            print(f"  Hint: {hint}")
