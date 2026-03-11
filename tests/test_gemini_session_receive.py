"""Tests for GeminiSession receive loop and configuration.

Validates that the receive loop correctly extracts observations from all
Gemini Live API response types (model_turn text, output_transcription,
input_transcription) and that the session config uses correct modalities.

These tests exist because a production bug went undetected: the receive loop
only captured output_transcription (audio-to-text) but missed model_turn text
parts. All other tests mocked GeminiSession entirely, so the real parsing
logic was never exercised. These tests mock the Gemini API *responses* while
testing the real receive loop code.
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from src.capture.config import CaptureConfig
from src.capture.event_bus import EventBus
from src.capture.gemini_session import GeminiSession
from src.capture.models import MediaChunk


def _make_session(api_key: str = "test-key") -> GeminiSession:
    """Create a GeminiSession with minimal config for testing."""
    config = CaptureConfig(gemini_api_key=api_key)
    event_bus = EventBus()
    queue: asyncio.Queue[MediaChunk] = asyncio.Queue()
    with patch("src.capture.gemini_session.genai"):
        session = GeminiSession(config, event_bus, queue)
    return session


class _FakeAsyncTurn:
    """Fake async iterable that yields responses, then raises to exit the loop."""

    def __init__(self, responses: list) -> None:
        self._responses = responses

    def __aiter__(self):
        return self

    async def __anext__(self):
        if not self._responses:
            # Raise an exception to break out of the receive loop's
            # inner `async for` and trigger the except clause which
            # checks stop_event
            raise ConnectionError("fake turn exhausted")
        return self._responses.pop(0)


class _FakeSession:
    """Fake Gemini session whose receive() returns a _FakeAsyncTurn."""

    def __init__(self, responses: list) -> None:
        self._responses = responses

    def receive(self):
        return _FakeAsyncTurn(list(self._responses))


def _make_response(
    model_turn_texts: list[str] | None = None,
    output_transcription_text: str | None = None,
    input_transcription_text: str | None = None,
    turn_complete: bool = False,
    resumption_handle: str | None = None,
) -> SimpleNamespace:
    """Build a fake Gemini Live API response object."""
    server_content = SimpleNamespace()

    # model_turn with text parts
    if model_turn_texts is not None:
        parts = [SimpleNamespace(text=t) for t in model_turn_texts]
        server_content.model_turn = SimpleNamespace(parts=parts)
    else:
        server_content.model_turn = None

    # output_transcription (Gemini audio-to-text)
    if output_transcription_text is not None:
        server_content.output_transcription = SimpleNamespace(text=output_transcription_text)
    else:
        server_content.output_transcription = None

    # input_transcription (presenter speech-to-text)
    if input_transcription_text is not None:
        server_content.input_transcription = SimpleNamespace(text=input_transcription_text)
    else:
        server_content.input_transcription = None

    server_content.turn_complete = turn_complete

    # session_resumption_update
    if resumption_handle:
        resumption = SimpleNamespace(resumable=True, new_handle=resumption_handle)
    else:
        resumption = None

    return SimpleNamespace(
        server_content=server_content,
        session_resumption_update=resumption,
    )


async def _run_receive_loop(session: GeminiSession, responses: list) -> None:
    """Run the receive loop with fake responses and auto-stop.

    Sets up a FakeSession, runs the receive loop with a timeout to prevent
    hangs, then stops. The FakeAsyncTurn raises ConnectionError when
    exhausted, which the receive loop catches and retries -- we use the
    stop event + timeout to cleanly exit.
    """
    session._session = _FakeSession(responses)
    session._stop_event.clear()

    async def _stop_soon():
        await asyncio.sleep(0.3)
        session._stop_event.set()

    # Timeout as safety net -- tests should complete in <1s
    try:
        await asyncio.wait_for(
            asyncio.gather(session._receive_loop(), _stop_soon()),
            timeout=3.0,
        )
    except TimeoutError:
        session._stop_event.set()


class TestBuildConfig:
    """Verify session configuration is correct."""

    def test_response_modality_is_text(self):
        """Response modality must be TEXT so observations arrive as text parts.

        This was the root cause of empty observations in production: the native
        audio model with AUDIO modality generated audio responses that were never
        consumed, so output_transcription never fired.
        """
        session = _make_session()
        config = session._build_config()
        assert "TEXT" in config.response_modalities
        assert "AUDIO" not in config.response_modalities

    def test_input_audio_transcription_enabled(self):
        """Input audio transcription must be enabled to capture presenter speech."""
        session = _make_session()
        config = session._build_config()
        assert config.input_audio_transcription is not None

    def test_system_instruction_present(self):
        """System instruction must be set to guide observation generation."""
        session = _make_session()
        config = session._build_config()
        assert config.system_instruction is not None
        assert "hackathon" in config.system_instruction.lower()

    def test_context_window_compression_enabled(self):
        """Compression must be enabled for long-running sessions."""
        session = _make_session()
        config = session._build_config()
        assert config.context_window_compression is not None

    def test_session_resumption_enabled(self):
        """Session resumption must be configured for reconnection resilience."""
        session = _make_session()
        config = session._build_config()
        assert config.session_resumption is not None


class TestReceiveLoopObservations:
    """Verify the receive loop extracts observations from all response types.

    These tests run the real _receive_loop code against mock API responses.
    They would have caught the production bug where model_turn text was ignored.
    """

    @pytest.mark.asyncio
    async def test_model_turn_text_captured_as_observation(self):
        """model_turn.parts[].text must be captured as observations.

        This is the PRIMARY observation channel — Gemini sends structured text
        observations here when response_modalities includes TEXT.
        """
        session = _make_session()
        await _run_receive_loop(session, [
            _make_response(model_turn_texts=["The team demonstrated a network scanner"]),
            _make_response(model_turn_texts=["It detected 3 open ports"]),
        ])

        assert len(session._observations) == 2
        assert "network scanner" in session._observations[0]
        assert "3 open ports" in session._observations[1]

    @pytest.mark.asyncio
    async def test_output_transcription_captured_as_observation(self):
        """output_transcription.text must be captured as observations.

        This is the SECONDARY channel — audio-to-text transcription of Gemini's
        spoken responses (only fires when AUDIO modality is used).
        """
        session = _make_session()
        await _run_receive_loop(session, [
            _make_response(output_transcription_text="The presenter showed a login page"),
        ])

        assert len(session._observations) == 1
        assert "login page" in session._observations[0]

    @pytest.mark.asyncio
    async def test_input_transcription_publishes_transcript_event(self):
        """input_transcription.text must publish TranscriptReceived events.

        This captures presenter speech for injection detection and is the
        source of the transcripts list in SanitizedOutput.
        """
        session = _make_session()
        published_events = []
        session._event_bus.subscribe(
            "transcript_received",
            lambda e: published_events.append(e),
        )

        await _run_receive_loop(session, [
            _make_response(input_transcription_text="Hello everyone, let me show you our project"),
        ])
        await session._event_bus.drain()

        assert len(published_events) == 1
        assert "our project" in published_events[0].segment.text

    @pytest.mark.asyncio
    async def test_both_model_turn_and_transcription_captured(self):
        """A single response can contain both model_turn and input_transcription."""
        session = _make_session()
        published_events = []
        session._event_bus.subscribe(
            "transcript_received",
            lambda e: published_events.append(e),
        )

        await _run_receive_loop(session, [
            _make_response(
                model_turn_texts=["Screen shows a terminal with nmap output"],
                input_transcription_text="So we ran nmap against the target",
            ),
        ])
        await session._event_bus.drain()

        assert len(session._observations) == 1
        assert "nmap" in session._observations[0]
        assert len(published_events) == 1
        assert "nmap" in published_events[0].segment.text

    @pytest.mark.asyncio
    async def test_multi_part_model_turn(self):
        """model_turn with multiple text parts captures all of them."""
        session = _make_session()
        await _run_receive_loop(session, [
            _make_response(model_turn_texts=[
                "The screen shows a React dashboard.",
                "There are 4 API endpoints listed.",
            ]),
        ])

        assert len(session._observations) == 2
        assert "React dashboard" in session._observations[0]
        assert "API endpoints" in session._observations[1]

    @pytest.mark.asyncio
    async def test_empty_text_ignored(self):
        """Empty or None text parts should not create observations."""
        session = _make_session()
        await _run_receive_loop(session, [
            _make_response(model_turn_texts=["", "  Valid observation  "]),
            _make_response(output_transcription_text=""),
            _make_response(output_transcription_text="Valid audio observation"),
        ])

        # Only non-empty text should be captured
        assert len(session._observations) == 2

    @pytest.mark.asyncio
    async def test_resumption_handle_updated(self):
        """Session resumption handles are stored for reconnection."""
        session = _make_session()
        await _run_receive_loop(session, [
            _make_response(resumption_handle="handle-abc123-long-enough-for-slice"),
        ])

        assert session._resumption_handle == "handle-abc123-long-enough-for-slice"


class TestObservationLifecycle:
    """Verify get/clear observation lifecycle."""

    def test_get_observations_returns_copy(self):
        """get_observations returns a copy, not a reference to internal list."""
        session = _make_session()
        session._observations.append("test obs")
        result = session.get_observations()
        result.append("should not appear in session")
        assert len(session._observations) == 1

    def test_clear_observations_empties_list(self):
        """clear_observations resets the internal observation buffer."""
        session = _make_session()
        session._observations.extend(["obs1", "obs2", "obs3"])
        session.clear_observations()
        assert session.get_observations() == []


class TestDefensePipelineIntegration:
    """Verify the defense pipeline correctly processes real observations.

    These tests ensure the full chain works: GeminiSession observations ->
    DefensePipeline._process_demo_stopped -> ObservationVerified event.
    Unlike other tests that mock get_observations(), these use a real
    GeminiSession with pre-populated observations.
    """

    @pytest.mark.asyncio
    async def test_observations_flow_to_sanitized_output(self):
        """Observations from GeminiSession must appear in ObservationVerified."""
        from src.capture.models import DemoStopped
        from src.defense.pipeline import DefensePipeline

        session = _make_session()
        # Simulate Gemini having produced observations during a demo
        session._observations.extend([
            "The team built a network scanner.",
            "It detected 3 open ports on the target.",
        ])

        event_bus = EventBus()
        defense = DefensePipeline(api_key="test", gemini_session=session)
        await defense.setup(event_bus)

        verified_events = []
        event_bus.subscribe(
            "observation_verified",
            lambda e: verified_events.append(e),
        )

        # Trigger demo stop
        defense._current_team = "TestTeam"
        event = DemoStopped(team_name="TestTeam", duration=30.0)
        await defense._on_demo_stopped(event)
        await event_bus.drain()

        assert len(verified_events) == 1
        output = verified_events[0].output
        assert output.team_name == "TestTeam"
        # Observations must be present when Gemini provided them
        assert len(output.observations) > 0

    @pytest.mark.asyncio
    async def test_empty_observations_still_publishes_event(self):
        """Even with zero observations, ObservationVerified must be published.

        Downstream pipelines (scoring, commentary) depend on this event.
        If it's never published, scores hang forever.
        """
        from src.capture.models import DemoStopped
        from src.defense.pipeline import DefensePipeline

        session = _make_session()
        # No observations — simulates the bug where Gemini produces nothing

        event_bus = EventBus()
        defense = DefensePipeline(api_key="test", gemini_session=session)
        await defense.setup(event_bus)

        verified_events = []
        event_bus.subscribe(
            "observation_verified",
            lambda e: verified_events.append(e),
        )

        defense._current_team = "EmptyTeam"
        event = DemoStopped(team_name="EmptyTeam", duration=5.0)
        await defense._on_demo_stopped(event)
        await event_bus.drain()

        # Event MUST be published even with empty observations
        assert len(verified_events) == 1
        assert verified_events[0].output.team_name == "EmptyTeam"
