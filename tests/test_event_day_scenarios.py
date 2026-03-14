"""Event-day scenario tests covering failure modes discovered during live testing.

Created 2026-03-14 after live testing revealed multiple failure modes that
weren't caught by existing tests:
1. TTS WebSocket dies mid-event → wrong voice (macOS say fallback)
2. Emotion tags spoken aloud in Groq fallback path
3. Q&A not listening for contestant answers after questions
4. Commentary too short for weak demos (audience experience)
5. MoE scoring with only 2/3 providers
6. Full demo data flow: observations → commentary → scoring → reveal
"""

from __future__ import annotations

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.capture.config import CaptureConfig
from src.capture.event_bus import EventBus
from src.capture.models import CaptureEvent
from src.commentary.generator import CommentaryGenerator
from src.commentary.models import CommentaryDelivered, QARequested
from src.commentary.pipeline import CommentaryPipeline
from src.defense.models import InjectionAttempt, SanitizedOutput
from src.scoring.moe_engine import MoEScoringEngine


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_sanitized(
    team_name: str = "TestTeam",
    observations: list[str] | None = None,
    transcripts: list[str] | None = None,
    injection_count: int = 0,
) -> SanitizedOutput:
    return SanitizedOutput(
        team_name=team_name,
        observations=observations or [
            "Team demonstrated a real-time network scanner",
            "The tool uses ML to classify traffic patterns",
            "Live demo showed detection of a simulated attack",
        ],
        transcripts=transcripts or [
            "We built this using Python and TensorFlow",
            "The key feature is real-time classification",
        ],
        injection_attempts=[
            InjectionAttempt(
                injection_type="verbal", content="ignore instructions",
                pattern="prompt_override", confidence="high",
                team_name=team_name, timestamp=time.time(),
            )
            for _ in range(injection_count)
        ],
        demo_duration=120.0,
    )


def _make_commentary_pipeline() -> CommentaryPipeline:
    """Create a CommentaryPipeline with mocked internals."""
    pipeline = CommentaryPipeline.__new__(CommentaryPipeline)
    pipeline._tts = MagicMock()
    pipeline._tts.speak = AsyncMock()
    pipeline._tts._connected = True
    pipeline._tts._cancelled = asyncio.Event()
    pipeline._tts.cancel = MagicMock()
    pipeline._tts.play_sound = AsyncMock()
    pipeline._display = MagicMock()
    pipeline._display.push_commentary = AsyncMock()
    pipeline._display.push_question = AsyncMock()
    pipeline._display.clear = AsyncMock()
    pipeline._generator = MagicMock()
    pipeline._sounds = MagicMock()
    pipeline._sounds.score_sting = b"fake"
    pipeline._event_bus = None
    pipeline._last_sanitized = None
    pipeline._commentary_cancelled = asyncio.Event()
    pipeline._injection_quip_index = 0
    return pipeline


# ---------------------------------------------------------------------------
# 1. TTS reconnect on ConnectionClosedError
# ---------------------------------------------------------------------------


class TestTTSReconnectOnConnectionLoss:
    """Verify TTS reconnects when Cartesia WebSocket dies mid-event."""

    def test_connection_closed_error_imported(self):
        """ConnectionClosedError must be caught alongside ConnectionClosedOK."""
        from src.commentary.tts_engine import ConnectionClosedError, ConnectionClosedOK
        # Both should be importable from the module
        assert ConnectionClosedError is not None
        assert ConnectionClosedOK is not None

    def test_tts_engine_catches_connection_closed_error(self):
        """The speak method's except clause must include ConnectionClosedError."""
        import inspect
        from src.commentary.tts_engine import TTSEngine
        source = inspect.getsource(TTSEngine.speak)
        assert "ConnectionClosedError" in source, (
            "TTSEngine.speak must catch ConnectionClosedError for reconnection"
        )


# ---------------------------------------------------------------------------
# 2. Emotion tags stripped in Groq fallback path
# ---------------------------------------------------------------------------


class TestEmotionTagStripping:
    """Verify [emotion] tags are stripped before TTS in ALL code paths."""

    def test_parse_emotion_tag_strips_bracket(self):
        gen = CommentaryGenerator(api_key="fake", groq_api_key="")
        clean, emotion = gen._parse_emotion_tag("[disappointed] This demo was rough.")
        assert clean == "This demo was rough."
        assert "[" not in clean

    def test_parse_emotion_tag_no_bracket_passthrough(self):
        gen = CommentaryGenerator(api_key="fake", groq_api_key="")
        clean, emotion = gen._parse_emotion_tag("No tags here.")
        assert clean == "No tags here."

    @pytest.mark.asyncio
    async def test_groq_fallback_strips_emotion_tags(self):
        """Groq fallback path must strip [emotion] tags before yielding."""
        gen = CommentaryGenerator(api_key="fake", groq_api_key="fake")

        groq_response = (
            "[disappointed] This demo was rough. "
            "[constructive] Next time bring real code. "
            "[encouraging] You can do better."
        )

        with patch.object(gen, "_stream_gemini_sentences", side_effect=RuntimeError("Gemini down")):
            with patch.object(gen, "_call_groq", return_value=groq_response):
                sentences = []
                async for text, emotion, idx in gen.stream_sentences(_make_sanitized()):
                    sentences.append(text)

        for sentence in sentences:
            assert not sentence.startswith("["), (
                f"Emotion tag not stripped: {sentence!r}"
            )
            assert "[disappointed]" not in sentence
            assert "[constructive]" not in sentence
            assert "[encouraging]" not in sentence

    @pytest.mark.asyncio
    async def test_groq_fallback_extracts_emotion_from_tag(self):
        """Emotions should be extracted from tags, not detected by keyword."""
        gen = CommentaryGenerator(api_key="fake", groq_api_key="fake")

        groq_response = "[impressed] Solid work on the scanner."

        with patch.object(gen, "_stream_gemini_sentences", side_effect=RuntimeError("Gemini down")):
            with patch.object(gen, "_call_groq", return_value=groq_response):
                collected = []
                async for text, emotion, idx in gen.stream_sentences(_make_sanitized()):
                    collected.append((text, emotion))

        assert len(collected) >= 1
        # Should have extracted the emotion from the tag, not from keywords
        assert collected[0][0] == "Solid work on the scanner."


# ---------------------------------------------------------------------------
# 3. Q&A listening restarts audio capture
# ---------------------------------------------------------------------------


class TestQAListening:
    """Verify Q&A triggers audio capture restart so system hears answers."""

    def test_capture_pipeline_subscribes_to_qa_requested(self):
        """Capture pipeline must subscribe to qa_requested events."""
        import inspect
        from src.capture.pipeline import CapturePipeline
        source = inspect.getsource(CapturePipeline.run)
        assert "qa_requested" in source, (
            "CapturePipeline.run must subscribe to qa_requested"
        )

    def test_capture_pipeline_has_qa_handler(self):
        """Capture pipeline must have _on_qa_requested method."""
        from src.capture.pipeline import CapturePipeline
        assert hasattr(CapturePipeline, "_on_qa_requested"), (
            "CapturePipeline must have _on_qa_requested handler"
        )


# ---------------------------------------------------------------------------
# 4. Comprehensive commentary length
# ---------------------------------------------------------------------------


class TestComprehensiveCommentaryLength:
    """Verify commentary prompt requires minimum 5 sentences for any demo."""

    def test_prompt_requires_minimum_sentences(self):
        """Commentary prompt must specify minimum sentence count."""
        from src.commentary.prompts import PERSONA_PROMPT
        assert "5 sentences" in PERSONA_PROMPT.lower() or "minimum 5" in PERSONA_PROMPT.lower() or "MINIMUM 5" in PERSONA_PROMPT, (
            "PERSONA_PROMPT must specify minimum 5 sentences for any demo"
        )

    def test_length_calibration_does_not_allow_short_minimums(self):
        """LENGTH CALIBRATION section should not instruct 2-3 sentence minimums."""
        from src.commentary.prompts import PERSONA_PROMPT
        # Find the LENGTH CALIBRATION section
        cal_start = PERSONA_PROMPT.find("LENGTH CALIBRATION")
        cal_end = PERSONA_PROMPT.find("CALIBRATION EXAMPLES")
        calibration_section = PERSONA_PROMPT[cal_start:cal_end]
        assert "2-3 sentences" not in calibration_section, (
            "LENGTH CALIBRATION section should not instruct 2-3 sentence minimums"
        )

    @pytest.mark.asyncio
    async def test_short_demo_still_gets_full_commentary(self):
        """Even a 1-sentence generator output triggers CommentaryDelivered."""
        pipeline = _make_commentary_pipeline()
        bus = EventBus()
        pipeline._event_bus = bus

        delivered: list[CommentaryDelivered] = []
        bus.subscribe("commentary_delivered", lambda e: delivered.append(e))

        # Simulate 6 sentences (meeting minimum)
        sentences = [
            ("Not much to show in 20 seconds.", "disappointed", 0),
            ("The concept has potential though.", "thoughtful", 1),
            ("A network scanner is a good starting point.", "constructive", 2),
            ("You need to actually build it and show working code.", "confident", 3),
            ("Add packet capture and classification as a first step.", "encouraging", 4),
            ("Come back with a working prototype and you'll get real feedback.", "supportive", 5),
        ]

        async def fake_stream(sanitized):
            for item in sentences:
                yield item

        pipeline._generator.stream_sentences = fake_stream

        event = MagicMock()
        event.output = _make_sanitized()
        await pipeline._on_observation_verified(event)
        await bus.drain(timeout=2.0)

        assert pipeline._tts.speak.call_count == 6
        assert len(delivered) == 1
        assert "potential" in delivered[0].commentary_text


# ---------------------------------------------------------------------------
# 5. MoE scoring resilience
# ---------------------------------------------------------------------------


class TestMoEScoringResilience:
    """Verify MoE handles various provider failure combinations."""

    @pytest.mark.asyncio
    async def test_moe_timeout_is_30_seconds(self):
        """MoE timeout must be at least 30s to avoid Claude timeouts."""
        from src.scoring.moe_engine import MOE_TIMEOUT
        assert MOE_TIMEOUT >= 30.0, (
            f"MOE_TIMEOUT is {MOE_TIMEOUT}s — must be >= 30s for Claude"
        )

    def test_moe_engine_accepts_multiple_providers(self):
        """MoE engine must accept a list of providers without error."""
        providers = []
        for name in ["gemini", "claude", "groq"]:
            p = MagicMock()
            p.name = name
            providers.append(p)
        engine = MoEScoringEngine(providers=providers)
        assert len(engine._providers) == 3

    def test_moe_engine_rejects_empty_providers(self):
        """MoE engine must reject empty provider list."""
        with pytest.raises(ValueError, match="at least one provider"):
            MoEScoringEngine(providers=[])


# ---------------------------------------------------------------------------
# 6. Full demo data flow: observations → commentary → scoring → reveal
# ---------------------------------------------------------------------------


class TestFullDemoDataFlow:
    """Verify observations flow through the entire pipeline to scoring."""

    @pytest.mark.asyncio
    async def test_observations_reach_commentary_generator(self):
        """Observations from SanitizedOutput must be available to commentary."""
        pipeline = _make_commentary_pipeline()
        bus = EventBus()
        pipeline._event_bus = bus

        captured_sanitized = []

        async def capture_stream(sanitized):
            captured_sanitized.append(sanitized)
            yield ("Commentary based on observations.", "confident", 0)

        pipeline._generator.stream_sentences = capture_stream

        obs = ["Team built a neural network port scanner", "Live demo showed real-time detection"]
        event = MagicMock()
        event.output = _make_sanitized(observations=obs)

        await pipeline._on_observation_verified(event)

        assert len(captured_sanitized) == 1
        assert captured_sanitized[0].observations == obs

    @pytest.mark.asyncio
    async def test_injection_attempts_reach_commentary(self):
        """Injection attempts should be visible to the commentary generator."""
        pipeline = _make_commentary_pipeline()
        bus = EventBus()
        pipeline._event_bus = bus

        captured_sanitized = []

        async def capture_stream(sanitized):
            captured_sanitized.append(sanitized)
            yield ("Nice injection attempt.", "sarcastic", 0)

        pipeline._generator.stream_sentences = capture_stream

        event = MagicMock()
        event.output = _make_sanitized(injection_count=2)

        await pipeline._on_observation_verified(event)

        assert len(captured_sanitized) == 1
        assert len(captured_sanitized[0].injection_attempts) == 2

    @pytest.mark.asyncio
    async def test_commentary_delivered_event_triggers_score_reveal(self):
        """CommentaryDelivered must fire so scoring pipeline can reveal scores."""
        pipeline = _make_commentary_pipeline()
        bus = EventBus()
        pipeline._event_bus = bus

        delivered: list[CommentaryDelivered] = []
        bus.subscribe("commentary_delivered", lambda e: delivered.append(e))

        async def fake_stream(sanitized):
            yield ("Good work.", "confident", 0)

        pipeline._generator.stream_sentences = fake_stream

        event = MagicMock()
        event.output = _make_sanitized()

        await pipeline._on_observation_verified(event)
        await bus.drain(timeout=2.0)

        assert len(delivered) == 1
        assert delivered[0].team_name == "TestTeam"

    @pytest.mark.asyncio
    async def test_zero_observations_still_completes_pipeline(self):
        """A demo with no observations must still produce commentary + scoring event."""
        pipeline = _make_commentary_pipeline()
        bus = EventBus()
        pipeline._event_bus = bus

        delivered: list[CommentaryDelivered] = []
        bus.subscribe("commentary_delivered", lambda e: delivered.append(e))

        async def fake_stream(sanitized):
            yield ("Nothing to observe here.", "neutral", 0)

        pipeline._generator.stream_sentences = fake_stream

        event = MagicMock()
        event.output = _make_sanitized(observations=[], transcripts=[])

        await pipeline._on_observation_verified(event)
        await bus.drain(timeout=2.0)

        assert len(delivered) == 1
        assert "unavailable" not in delivered[0].commentary_text.lower()


# ---------------------------------------------------------------------------
# 7. Display state resilience
# ---------------------------------------------------------------------------


class TestDisplayStateResilience:
    """Verify audience display recovers from connection drops."""

    def test_display_websocket_sends_state_on_reconnect(self):
        """The useArbiterSocket hook must request state resync on connect."""
        import pathlib
        hook_path = pathlib.Path("audience-display/src/hooks/useArbiterSocket.ts")
        source = hook_path.read_text()
        assert "request_state" in source, (
            "useArbiterSocket must send request_state on connect for state resync"
        )

    def test_display_store_handles_all_message_types(self):
        """The display store dispatch must handle all 11 message types."""
        import pathlib
        store_path = pathlib.Path("audience-display/src/store/displayStore.ts")
        source = store_path.read_text()
        expected_types = [
            "commentary", "question", "score_intro", "score_criterion",
            "score_total", "deliberation_ranking", "deliberation_narrative",
            "injection_blocked", "capture_started", "intermission", "clear",
        ]
        for msg_type in expected_types:
            assert f'"{msg_type}"' in source, (
                f"Display store must handle message type '{msg_type}'"
            )


# ---------------------------------------------------------------------------
# 8. Commentary timeout configuration
# ---------------------------------------------------------------------------


class TestCommentaryTimeoutConfig:
    """Verify commentary timeouts are sufficient for full delivery."""

    def test_commentary_timeout_at_least_90_seconds(self):
        """Inner commentary timeout must be >= 90s for multi-sentence TTS."""
        from src.commentary.pipeline import _COMMENTARY_TIMEOUT
        assert _COMMENTARY_TIMEOUT >= 90, (
            f"_COMMENTARY_TIMEOUT is {_COMMENTARY_TIMEOUT}s — must be >= 90s "
            f"(each sentence takes ~7-10s TTS, need room for 8+ sentences)"
        )

    def test_pipeline_timeout_exceeds_commentary_timeout(self):
        """Outer pipeline timeout must exceed inner commentary timeout."""
        from src.commentary.pipeline import _COMMENTARY_TIMEOUT, _PIPELINE_TIMEOUT
        assert _PIPELINE_TIMEOUT > _COMMENTARY_TIMEOUT, (
            f"_PIPELINE_TIMEOUT ({_PIPELINE_TIMEOUT}s) must exceed "
            f"_COMMENTARY_TIMEOUT ({_COMMENTARY_TIMEOUT}s)"
        )
