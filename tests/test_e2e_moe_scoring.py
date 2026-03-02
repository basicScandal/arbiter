"""E2E tests for MoE multi-provider scoring through ScoringPipeline event path.

Tests the MoE scoring path THROUGH the ScoringPipeline event bus wiring
(not just calling MoEScoringEngine.score() directly like existing unit tests).
This validates the complete integration: EventBus publish -> ScoringPipeline
handler -> MoEScoringEngine -> ScoreAggregator -> ScoringComplete event.

Coverage: E2E-02 (MoE integration through pipeline event path)
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, PropertyMock

import pytest

from src.capture.event_bus import EventBus
from src.commentary.display_server import DisplayServer
from src.defense.models import ObservationVerified, SanitizedOutput
from src.scoring.models import ScoringComplete
from src.scoring.moe_engine import MoEScoringEngine
from src.scoring.pipeline import ScoringPipeline
from tests.helpers.event_collector import EventCollector

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_provider(name: str, scores: dict[str, float]) -> MagicMock:
    """Create a mock LLMProvider returning JSON with specific criterion scores."""
    provider = MagicMock()
    type(provider).name = PropertyMock(return_value=name)
    criteria = [
        {"name": n, "score": s, "justification": f"Evidence for {n}"}
        for n, s in scores.items()
    ]
    provider.generate = AsyncMock(return_value=json.dumps({"criteria": criteria}))
    return provider


def _make_failing_provider(name: str) -> MagicMock:
    """Create a mock LLMProvider that raises an exception on generate."""
    provider = MagicMock()
    type(provider).name = PropertyMock(return_value=name)
    provider.generate = AsyncMock(side_effect=Exception(f"{name} API error"))
    return provider


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def sanitized() -> SanitizedOutput:
    return SanitizedOutput(
        team_name="TestTeam",
        observations=["Built a solid tool"],
        transcripts=[],
        injection_attempts=[],
        demo_duration=180.0,
    )


@pytest.fixture
def mock_display() -> MagicMock:
    display = MagicMock(spec=DisplayServer)
    display.push_score_intro = AsyncMock()
    display.push_criterion_reveal = AsyncMock()
    display.push_total_score = AsyncMock()
    return display


# ---------------------------------------------------------------------------
# Tests: MoE through pipeline event bus
# ---------------------------------------------------------------------------


@pytest.mark.timeout(15)
async def test_moe_three_providers_through_pipeline(
    event_bus: EventBus,
    event_collector: EventCollector,
    sanitized: SanitizedOutput,
    mock_display: MagicMock,
):
    """Three mock providers produce different scores; ScoringPipeline event path
    aggregates them into a weighted scorecard published via ScoringComplete."""
    gemini = _make_provider("gemini", {
        "Technical Execution": 8.0, "Innovation": 7.0, "Demo Quality": 6.0,
    })
    claude = _make_provider("claude", {
        "Technical Execution": 7.0, "Innovation": 8.0, "Demo Quality": 7.0,
    })
    openai = _make_provider("openai", {
        "Technical Execution": 9.0, "Innovation": 6.0, "Demo Quality": 5.0,
    })

    moe = MoEScoringEngine(providers=[gemini, claude, openai])
    scoring = ScoringPipeline(api_key="test", display=mock_display, moe_engine=moe)
    scoring._store.save = AsyncMock()

    await scoring.setup(event_bus)

    # Publish the trigger event
    event_bus.publish(ObservationVerified(output=sanitized))

    # Wait for the scoring_complete event
    event = await event_collector.wait_for("scoring_complete", timeout=5.0)
    assert isinstance(event, ScoringComplete)

    scorecard = event.scorecard
    assert scorecard.team_name == "TestTeam"
    assert scorecard.total_score > 0
    assert len(scorecard.criteria) == 3

    # Each criterion score must be in valid range
    for criterion in scorecard.criteria:
        assert 0.0 <= criterion.score <= 10.0

    # All three providers must have been called exactly once
    gemini.generate.assert_called_once()
    claude.generate.assert_called_once()
    openai.generate.assert_called_once()

    # Store must have been called with the aggregated scorecard
    scoring._store.save.assert_called_once_with(scorecard)


@pytest.mark.timeout(15)
async def test_moe_aggregated_score_between_extremes(
    event_bus: EventBus,
    event_collector: EventCollector,
    sanitized: SanitizedOutput,
    mock_display: MagicMock,
):
    """Aggregated per-criterion scores fall in a reasonable range after calibration."""
    gemini = _make_provider("gemini", {
        "Technical Execution": 8.0, "Innovation": 7.0, "Demo Quality": 6.0,
    })
    claude = _make_provider("claude", {
        "Technical Execution": 7.0, "Innovation": 8.0, "Demo Quality": 7.0,
    })
    openai = _make_provider("openai", {
        "Technical Execution": 9.0, "Innovation": 6.0, "Demo Quality": 5.0,
    })

    moe = MoEScoringEngine(providers=[gemini, claude, openai])
    scoring = ScoringPipeline(api_key="test", display=mock_display, moe_engine=moe)
    scoring._store.save = AsyncMock()

    await scoring.setup(event_bus)
    event_bus.publish(ObservationVerified(output=sanitized))

    event = await event_collector.wait_for("scoring_complete", timeout=5.0)
    scorecard = event.scorecard

    scores = {c.name: c.score for c in scorecard.criteria}

    # Technical Execution raw scores: 8.0, 7.0, 9.0 -> after calibration, should
    # be in a reasonable range (calibration flattens toward center)
    assert 5.5 <= scores["Technical Execution"] <= 9.0

    # Innovation raw scores: 7.0, 8.0, 6.0 -> reasonable range
    assert 4.0 <= scores["Innovation"] <= 9.0

    # Total should be a reasonable weighted sum, NOT the fallback value (5.0 * sum(weights))
    # Fallback total = 5.0 * (0.4 + 0.3 + 0.3) = 5.0
    assert scorecard.total_score != 5.0
    assert scorecard.total_score > 0


@pytest.mark.timeout(15)
async def test_moe_one_provider_fails_uses_remaining(
    event_bus: EventBus,
    event_collector: EventCollector,
    sanitized: SanitizedOutput,
    mock_display: MagicMock,
):
    """One failing provider does not prevent scoring; remaining providers produce valid scores."""
    good1 = _make_provider("gemini", {
        "Technical Execution": 8.0, "Innovation": 7.0, "Demo Quality": 6.0,
    })
    good2 = _make_provider("claude", {
        "Technical Execution": 7.0, "Innovation": 8.0, "Demo Quality": 7.0,
    })
    bad = _make_failing_provider("openai")

    moe = MoEScoringEngine(providers=[good1, good2, bad])
    scoring = ScoringPipeline(api_key="test", display=mock_display, moe_engine=moe)
    scoring._store.save = AsyncMock()

    await scoring.setup(event_bus)
    event_bus.publish(ObservationVerified(output=sanitized))

    event = await event_collector.wait_for("scoring_complete", timeout=5.0)
    scorecard = event.scorecard

    # Should NOT be the fallback scorecard
    assert scorecard.total_score != 5.0
    assert scorecard.team_name == "TestTeam"
    assert len(scorecard.criteria) == 3


@pytest.mark.timeout(15)
async def test_moe_all_providers_fail_produces_fallback(
    event_bus: EventBus,
    event_collector: EventCollector,
    sanitized: SanitizedOutput,
    mock_display: MagicMock,
):
    """When all providers fail, MoE engine returns fallback scorecard (total_score == 5.0),
    which is still published through the pipeline as a ScoringComplete event."""
    bad1 = _make_failing_provider("gemini")
    bad2 = _make_failing_provider("claude")
    bad3 = _make_failing_provider("openai")

    moe = MoEScoringEngine(providers=[bad1, bad2, bad3])
    scoring = ScoringPipeline(api_key="test", display=mock_display, moe_engine=moe)
    scoring._store.save = AsyncMock()

    await scoring.setup(event_bus)
    event_bus.publish(ObservationVerified(output=sanitized))

    # The MoE engine catches all exceptions internally and returns a fallback
    # scorecard, so the pipeline should still publish scoring_complete.
    event = await event_collector.wait_for("scoring_complete", timeout=5.0)
    scorecard = event.scorecard

    assert scorecard.total_score == 5.0  # fallback scorecard
    assert scorecard.team_name == "TestTeam"
