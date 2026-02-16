"""Demo lifecycle state machine for managing hackathon demo sessions.

Transitions: idle -> capturing -> stopped -> idle
Each transition publishes events to the event bus so downstream components
(camera capture, audio capture, Gemini session) can react to lifecycle changes.
"""

from __future__ import annotations

import time

from statemachine import State, StateMachine

from src.capture.event_bus import EventBus, default_bus
from src.capture.models import DemoSession, DemoStarted, DemoStopped


class DemoMachine(StateMachine):
    """State machine controlling the demo capture lifecycle.

    States:
        idle: No demo running. Ready to start a new demo.
        capturing: Demo in progress, capture active.
        stopped: Demo ended, captured data available.

    Transitions:
        start_demo: idle -> capturing (requires team_name)
        stop_demo: capturing -> stopped
        reset: stopped -> idle (clears session data)
    """

    # States
    idle = State(initial=True)
    capturing = State()
    stopped = State()

    # Transitions
    start_demo = idle.to(capturing)
    stop_demo = capturing.to(stopped)
    reset = stopped.to(idle)

    def __init__(self, event_bus: EventBus | None = None, **kwargs) -> None:
        self.event_bus = event_bus or default_bus
        self.current_session: DemoSession | None = None
        super().__init__(**kwargs)

    def on_enter_capturing(self, team_name: str = "Unknown", **kwargs) -> None:
        """Create a new demo session and publish DemoStarted event."""
        self.current_session = DemoSession(
            team_name=team_name,
            started_at=time.time(),
        )
        self.event_bus.publish(
            DemoStarted(team_name=team_name)
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
