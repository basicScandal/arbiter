"""Full rehearsal orchestrator exercising the complete Arbiter pipeline.

Wires all sub-pipelines (defense, commentary, scoring, deliberation) with
mock components so the entire event-bus-driven chain runs without real
hardware or API keys. Used for pre-event verification and operator training.
"""

from __future__ import annotations

import asyncio
import logging
from unittest.mock import AsyncMock, MagicMock

from src.capture.event_bus import EventBus
from src.commentary.display_server import DisplayServer
from src.commentary.pipeline import CommentaryPipeline
from src.defense.pipeline import DefensePipeline
from src.memory.pipeline import DeliberationPipeline
from src.rehearsal.replay_provider import ReplayProvider
from src.rehearsal.synthetic_capture import SyntheticCapture
from src.scoring.moe_engine import MoEScoringEngine
from src.scoring.pipeline import ScoringPipeline

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Canned data for mock components
# ---------------------------------------------------------------------------

_CANNED_OBSERVATIONS = [
    "The team built a network reconnaissance tool with graph-based analysis",
    "It correlates CVEs across services to find exploitable chains",
    "Live demo showed real-time graph construction against test environment",
]

_CANNED_COMMENTARY_SENTENCES = [
    ("Well, well -- what do we have here? A team that actually knows what they're doing.", "sarcastic", 0),
    ("The network recon module is impressively clean, though I've seen tidier codebases in my sleep.", "contempt", 1),
    ("Still, I'll give credit where it's due -- that graph-based vuln correlation is a genuinely clever touch.", "content", 2),
]


async def _fake_stream_sentences(sanitized_output):
    """Async generator yielding canned commentary sentences."""
    for sentence, emotion, idx in _CANNED_COMMENTARY_SENTENCES:
        yield (sentence, emotion, idx)


class RehearsalPipeline:
    """Full pipeline orchestrator for rehearsal mode.

    Creates its own EventBus and wires all sub-pipelines with mock
    components (no real Gemini, TTS, or hardware). Exercises the same
    event bus subscriptions as production, catching integration issues early.

    Args:
        display: Optional DisplayServer to use for commentary/scoring output.
            When provided (e.g., from dashboard), rehearsal output appears
            on the live display. When None (CLI mode), a MagicMock is used
            and output goes to logs only.
    """

    def __init__(self, display: DisplayServer | None = None) -> None:
        self._event_bus = EventBus()
        self._synthetic = SyntheticCapture(self._event_bus)
        self._replay = ReplayProvider()
        self._setup_done = False

        # Display: use provided or mock
        if display is not None:
            self._display = display
        else:
            self._display = self._make_mock_display()

        # Defense pipeline with mock GeminiSession
        mock_gemini = self._make_mock_gemini()
        self._defense = DefensePipeline(api_key="rehearsal", gemini_session=mock_gemini)

        # Commentary pipeline with mocked TTS and generator
        self._commentary = CommentaryPipeline(api_key="rehearsal", voice_id="rehearsal")
        self._commentary._tts = MagicMock()
        self._commentary._tts.connect = AsyncMock()
        self._commentary._tts.speak = AsyncMock()
        self._commentary._tts.play_sound = AsyncMock()
        self._commentary._tts._connected = True
        self._commentary._display = self._display
        self._commentary._generator.stream_sentences = _fake_stream_sentences

        # Scoring pipeline with ReplayProvider via MoE engine
        self._scoring = ScoringPipeline(
            api_key="rehearsal",
            display=self._display,
            scores_dir="data/rehearsal/scores",
            moe_engine=MoEScoringEngine([ReplayProvider()]),
        )

        # Deliberation pipeline with mock memory store
        self._deliberation = DeliberationPipeline(
            api_key="rehearsal",
            display=self._display,
            scores_dir="data/rehearsal/scores",
            observations_dir="data/rehearsal/observations",
            deliberation_dir="data/rehearsal/deliberation",
        )
        self._deliberation._memory_store.save = AsyncMock()

    @staticmethod
    def _make_mock_gemini() -> MagicMock:
        """Create a mock GeminiSession returning canned observations."""
        gemini = MagicMock()
        gemini.get_observations.return_value = _CANNED_OBSERVATIONS
        gemini.clear_observations = MagicMock()
        return gemini

    @staticmethod
    def _make_mock_display() -> MagicMock:
        """Create a mock DisplayServer with all async methods stubbed."""
        display = MagicMock(spec=DisplayServer)
        display.start = AsyncMock()
        display.stop = AsyncMock()
        display.push_commentary = AsyncMock()
        display.push_score_intro = AsyncMock()
        display.push_criterion_reveal = AsyncMock()
        display.push_total_score = AsyncMock()
        display.push_deliberation_ranking = AsyncMock()
        display.push_deliberation_narrative = AsyncMock()
        display.clear = AsyncMock()
        return display

    async def setup(self) -> None:
        """Wire all sub-pipelines into the shared event bus.

        Subscribes defense, commentary, scoring, and deliberation pipelines
        to the same event types as production CapturePipeline.run().
        """
        await self._defense.setup(self._event_bus)
        await self._commentary.setup(self._event_bus)
        await self._scoring.setup(self._event_bus)
        await self._deliberation.setup(self._event_bus)
        self._setup_done = True
        logger.info("Rehearsal pipeline fully wired")

    async def run_demo(
        self,
        team_name: str = "RehearsalTeam",
        track: str = "ROGUE::AGENT",
    ) -> None:
        """Run a complete rehearsal demo cycle.

        Sets up the pipeline (if not already done), configures track
        assignments, and drives synthetic events through the full chain:
        defense -> commentary -> scoring -> deliberation.

        Args:
            team_name: Team name for the rehearsal demo.
            track: Challenge track for scoring context.
        """
        if not self._setup_done:
            await self.setup()

        # Set track on scoring and deliberation pipelines
        self._scoring.set_track(team_name, track)
        self._deliberation.set_track(team_name, track)

        logger.info("Rehearsal demo starting for team: %s (track: %s)", team_name, track)

        # Patch asyncio.sleep in scoring pipeline to avoid theatrical delays
        original_sleep = asyncio.sleep

        async def _fast_sleep(duration):
            """Reduced sleep for rehearsal -- keep timing visible but fast."""
            await original_sleep(min(duration, 0.1))

        # Replace scoring pipeline's sleep reference for fast reveals
        import src.scoring.pipeline as scoring_mod
        old_sleep = getattr(scoring_mod.asyncio, "sleep")
        scoring_mod.asyncio.sleep = _fast_sleep

        try:
            # Drive synthetic events through the pipeline
            await self._synthetic.run_demo(team_name=team_name, track=track)

            # Wait for cascading event chain to complete:
            # demo_stopped -> observation_verified -> (commentary + scoring) -> score_revealed
            await asyncio.sleep(3.0)

            logger.info("Rehearsal demo complete for team: %s", team_name)
        finally:
            # Restore original sleep
            scoring_mod.asyncio.sleep = old_sleep
