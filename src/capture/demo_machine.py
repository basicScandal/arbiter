"""Demo lifecycle state machine for managing hackathon demo sessions.

Transitions: idle -> capturing -> stopped -> idle
Each transition publishes events to the event bus so downstream components
(camera capture, audio capture, Gemini session) can react to lifecycle changes.
"""

from __future__ import annotations

import time

from statemachine import State, StateMachine

from src.capture.event_bus import EventBus, default_bus
from src.capture.models import DemoPaused, DemoResumed, DemoSession, DemoStarted, DemoStopped


class DemoMachine(StateMachine):
    """State machine controlling the demo capture lifecycle.

    States:
        idle: No demo running. Ready to start a new demo.
        capturing: Demo in progress, capture active.
        paused: Demo temporarily halted, session preserved.
        stopped: Demo ended, captured data available.

    Transitions:
        start_demo: idle -> capturing (requires team_name)
        pause_demo: capturing -> paused
        resume_demo: paused -> capturing
        stop_demo: capturing -> stopped | paused -> stopped
        reset: stopped -> idle (clears session data)
    """

    # States
    idle = State(initial=True)
    capturing = State()
    paused = State()
    stopped = State()

    # Transitions
    start_demo = idle.to(capturing)
    pause_demo = capturing.to(paused)
    resume_demo = paused.to(capturing)
    stop_demo = capturing.to(stopped) | paused.to(stopped)
    reset = stopped.to(idle)

    def __init__(self, event_bus: EventBus | None = None, **kwargs) -> None:
        self.event_bus = event_bus or default_bus
        self.current_session: DemoSession | None = None
        super().__init__(**kwargs)

    def on_start_demo(self, team_name: str = "Unknown", **kwargs) -> None:
        """Create a new demo session on start_demo (idle -> capturing only).

        Uses the transition-specific action (on_<transition>) rather than
        on_enter_capturing so that resume_demo (paused -> capturing) does NOT
        overwrite the existing session or fire a duplicate DemoStarted event.
        """
        self.current_session = DemoSession(
            team_name=team_name,
            started_at=time.time(),
        )
        self.event_bus.publish(
            DemoStarted(team_name=team_name)
        )

    def on_enter_paused(self, **kwargs) -> None:
        """Publish DemoPaused event when operator pauses the demo."""
        team_name = self.current_session.team_name if self.current_session else "Unknown"
        self.event_bus.publish(
            DemoPaused(team_name=team_name)
        )

    def on_exit_paused(self, **kwargs) -> None:
        """Publish DemoResumed event when leaving paused state (resuming)."""
        # Only publish DemoResumed if transitioning back to capturing (not stopping)
        target = kwargs.get("target", None)
        if target is not None and target.id == "capturing":
            team_name = self.current_session.team_name if self.current_session else "Unknown"
            self.event_bus.publish(
                DemoResumed(team_name=team_name)
            )

    def on_enter_stopped(self, **kwargs) -> None:
        """Finalize the demo session and publish DemoStopped event."""
        if self.current_session is not None:
            self.current_session.stopped_at = time.time()
            duration = self.current_session.stopped_at - (self.current_session.started_at or 0)
            self.event_bus.publish(
                DemoStopped(
                    team_name=self.current_session.team_name,
                    duration=duration,
                )
            )

    def on_enter_idle(self, **kwargs) -> None:
        """Clear session data on reset."""
        self.current_session = None


if __name__ == "__main__":
    import asyncio

    async def main():
        bus = EventBus()
        events_received: list[str] = []

        async def on_started(event: DemoStarted):
            events_received.append(event.event_type)
            print(f"  [callback] Demo started: team={event.team_name}")

        async def on_stopped(event: DemoStopped):
            events_received.append(event.event_type)
            print(f"  [callback] Demo stopped: team={event.team_name}, duration={event.duration:.2f}s")

        bus.subscribe("demo_started", on_started)
        bus.subscribe("demo_stopped", on_stopped)

        machine = DemoMachine(event_bus=bus)
        print(f"Initial state: {machine.current_state}")

        print("\n--- Starting demo for TestTeam ---")
        machine.start_demo(team_name="TestTeam")
        print(f"State: {machine.current_state}")
        assert machine.current_session is not None
        assert machine.current_session.team_name == "TestTeam"

        # Small delay to let async callbacks fire
        await asyncio.sleep(0.1)

        print("\n--- Stopping demo ---")
        machine.stop_demo()
        print(f"State: {machine.current_state}")
        assert machine.current_session is not None
        assert machine.current_session.stopped_at is not None

        await asyncio.sleep(0.1)

        print("\n--- Resetting ---")
        machine.reset()
        print(f"State: {machine.current_state}")
        assert machine.current_session is None

        # Verify events were received
        print(f"\nEvents received: {events_received}")
        assert "demo_started" in events_received, "demo_started event not received"
        assert "demo_stopped" in events_received, "demo_stopped event not received"

        # Verify invalid transitions raise errors
        from statemachine.exceptions import TransitionNotAllowed
        try:
            machine.stop_demo()  # Can't stop from idle
            assert False, "Should have raised TransitionNotAllowed"
        except TransitionNotAllowed:
            print("\nInvalid transition correctly rejected (stop_demo from idle)")

        print("\nAll checks passed!")

    asyncio.run(main())
