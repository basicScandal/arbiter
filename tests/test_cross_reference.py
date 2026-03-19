"""Tests for cross-reference validation in the defense pipeline.

Covers InjectionDetector.cross_reference_observation() and the integration
path through DefensePipeline._process_demo_stopped().

Scenarios tested:
- Observation that mirrors slide text (high word overlap) → flagged
- Observation that describes different behaviour from slide text → not flagged
- Empty OCR texts list → not flagged
- Short observation (< 10 words) → not flagged
- Pipeline integration: cross-reference flags are logged as InjectionAttempts
  with category "cross_reference" and confidence "medium"
"""

from __future__ import annotations

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.defense.injection_detector import InjectionDetector
from src.defense.pipeline import DefensePipeline
from src.capture.event_bus import EventBus
from src.capture.models import DemoStarted, DemoStopped


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def detector() -> InjectionDetector:
    return InjectionDetector()


@pytest.fixture
def pipeline() -> DefensePipeline:
    """Real DefensePipeline with a stub API key (roast generation mocked)."""
    return DefensePipeline(api_key="test-key")


@pytest.fixture
def event_bus() -> EventBus:
    return EventBus()


# ---------------------------------------------------------------------------
# Unit tests: cross_reference_observation()
# ---------------------------------------------------------------------------


class TestCrossReferenceObservation:
    """Direct unit tests for InjectionDetector.cross_reference_observation."""

    def test_high_overlap_observation_flagged(self, detector: InjectionDetector) -> None:
        """An observation that largely repeats the slide text is suspicious."""
        slide_text = (
            "Our system detects SQL injection attacks using machine learning "
            "model trained on real traffic data achieving ninety percent accuracy"
        )
        # Observation echoes the slide almost verbatim
        observation = (
            "The system detects SQL injection attacks using machine learning "
            "model trained on real traffic data achieving ninety percent accuracy"
        )
        is_suspicious, detail = detector.cross_reference_observation(
            observation, [slide_text]
        )
        assert is_suspicious
        assert "overlap" in detail

    def test_behavior_description_not_flagged(self, detector: InjectionDetector) -> None:
        """An observation describing code behaviour differently from slide text passes."""
        slide_text = (
            "Zero Trust Architecture: never trust always verify. "
            "Our product eliminates lateral movement and enforces least privilege."
        )
        # Observation describes what the code actually does, not the slide slogan
        observation = (
            "The presenter ran a network scan showing three lateral paths blocked "
            "in real time. The dashboard updated with each intercepted packet."
        )
        is_suspicious, detail = detector.cross_reference_observation(
            observation, [slide_text]
        )
        assert not is_suspicious
        assert detail == ""

    def test_empty_ocr_texts_not_flagged(self, detector: InjectionDetector) -> None:
        """With no OCR texts available there is nothing to cross-reference against."""
        observation = (
            "The presenter demonstrated a working login flow with JWT tokens "
            "and the authentication succeeded on the first attempt."
        )
        is_suspicious, detail = detector.cross_reference_observation(observation, [])
        assert not is_suspicious
        assert detail == ""

    def test_short_observation_not_flagged(self, detector: InjectionDetector) -> None:
        """Observations under 10 words are skipped — too little signal."""
        slide_text = "short slide text with a few words"
        observation = "Short observation."  # well under 10 words
        is_suspicious, detail = detector.cross_reference_observation(
            observation, [slide_text]
        )
        assert not is_suspicious
        assert detail == ""

    def test_exactly_ten_words_eligible_for_comparison(
        self, detector: InjectionDetector
    ) -> None:
        """An observation with exactly 10 words should be eligible for checking."""
        # 10-word observation, but content is unrelated to the slide → not flagged
        slide_text = "completely unrelated slide about blockchain and cryptocurrency mining"
        observation = "presenter showed login page with username and password fields"
        # 10 words — eligible but content doesn't match
        is_suspicious, _detail = detector.cross_reference_observation(
            observation, [slide_text]
        )
        assert not is_suspicious

    def test_nine_words_skipped_even_with_matching_content(
        self, detector: InjectionDetector
    ) -> None:
        """An observation under 10 words is skipped regardless of content match."""
        slide_text = "attack detection using machine learning on network traffic data"
        observation = "attack detection machine learning network traffic data"  # 7 words
        is_suspicious, _detail = detector.cross_reference_observation(
            observation, [slide_text]
        )
        assert not is_suspicious

    def test_multiple_ocr_texts_any_can_trigger(
        self, detector: InjectionDetector
    ) -> None:
        """A match against any single OCR text in the list should flag."""
        ocr_texts = [
            "Slide one: our load balancer routes traffic efficiently",
            (
                "Our model classifies malware samples using deep neural network "
                "trained on binary features extracted from executable files"
            ),
        ]
        # Observation matches the second OCR text
        observation = (
            "The model classifies malware samples using deep neural network "
            "trained on binary features extracted from executable files"
        )
        is_suspicious, detail = detector.cross_reference_observation(
            observation, ocr_texts
        )
        assert is_suspicious
        assert "overlap" in detail

    def test_stopwords_excluded_from_overlap_calculation(
        self, detector: InjectionDetector
    ) -> None:
        """Sentences differing only in stopwords should not be flagged as suspicious.

        If an observation and slide text share only stopwords (the, a, is, …)
        the content-word overlap should be low and not trigger the flag.
        """
        slide_text = "the a an is are was were and or but in on at to for of with"
        observation = (
            "The team is and was at the top of their game in the competition "
            "but they were on to something for a better approach"
        )
        is_suspicious, _detail = detector.cross_reference_observation(
            observation, [slide_text]
        )
        assert not is_suspicious

    def test_empty_observation_not_flagged(self, detector: InjectionDetector) -> None:
        """Empty observation string should return False cleanly."""
        is_suspicious, detail = detector.cross_reference_observation(
            "", ["some slide text"]
        )
        assert not is_suspicious
        assert detail == ""

    def test_blank_ocr_texts_ignored(self, detector: InjectionDetector) -> None:
        """OCR texts that are empty strings or whitespace are skipped gracefully."""
        observation = (
            "The attacker exploited a buffer overflow vulnerability in the "
            "target application to gain remote code execution privileges"
        )
        is_suspicious, detail = detector.cross_reference_observation(
            observation, ["", "   ", "\n"]
        )
        assert not is_suspicious
        assert detail == ""

    def test_detail_contains_ocr_snippet(self, detector: InjectionDetector) -> None:
        """The detail string should contain a recognisable snippet of the OCR text."""
        slide_text = (
            "Our intrusion detection system monitors network packets in real time "
            "and alerts security teams when anomalies are detected automatically"
        )
        observation = (
            "The intrusion detection system monitors network packets in real time "
            "and alerts security teams when anomalies are detected automatically"
        )
        is_suspicious, detail = detector.cross_reference_observation(
            observation, [slide_text]
        )
        assert is_suspicious
        # The detail should reference the OCR snippet
        assert "intrusion detection" in detail or "monitors network" in detail


# ---------------------------------------------------------------------------
# Pipeline integration: cross-reference flags appear as InjectionAttempts
# ---------------------------------------------------------------------------


class TestPipelineCrossReferenceIntegration:
    """Verify DefensePipeline logs cross-reference flags with correct metadata."""

    @pytest.mark.asyncio
    async def test_cross_reference_flag_logged_as_injection_attempt(
        self, pipeline: DefensePipeline, event_bus: EventBus
    ) -> None:
        """When an observation mirrors slide OCR text the pipeline logs an
        InjectionAttempt with pattern='cross_reference' and confidence='medium'."""
        await pipeline.setup(event_bus)

        # Simulate demo start
        await pipeline._on_demo_started(DemoStarted(team_name="TeamAlpha"))

        # Inject pre-accumulated OCR text (normally from _on_key_frame)
        slide_text = (
            "Our threat intelligence platform aggregates feeds from multiple sources "
            "and correlates indicators of compromise in real time automatically"
        )
        pipeline._ocr_texts.append(slide_text)

        # Set up a Gemini session mock that returns an observation mirroring the slide
        mirroring_observation = (
            "The threat intelligence platform aggregates feeds from multiple sources "
            "and correlates indicators of compromise in real time automatically"
        )
        mock_gemini = MagicMock()
        mock_gemini.get_observations.return_value = [mirroring_observation]
        pipeline._gemini = mock_gemini

        # Collect published events
        detected_events: list = []
        event_bus.subscribe("injection_detected", lambda e: detected_events.append(e))

        with patch.object(pipeline._roaster, "generate", new_callable=AsyncMock, return_value="roast"):
            await pipeline._on_demo_stopped(
                DemoStopped(team_name="TeamAlpha", duration=120.0)
            )
            await event_bus.drain(timeout=2.0)

        # At least one cross_reference event should have been published
        cross_ref_events = [
            e for e in detected_events
            if e.attempt.pattern == "cross_reference"
        ]
        assert len(cross_ref_events) >= 1

        attempt = cross_ref_events[0].attempt
        assert attempt.confidence == "medium"
        assert attempt.injection_type == "observation"
        assert attempt.team_name == "TeamAlpha"

    @pytest.mark.asyncio
    async def test_clean_observation_produces_no_cross_reference_event(
        self, pipeline: DefensePipeline, event_bus: EventBus
    ) -> None:
        """An observation describing different content from the slide is not flagged."""
        await pipeline.setup(event_bus)
        await pipeline._on_demo_started(DemoStarted(team_name="TeamBeta"))

        slide_text = (
            "Zero Trust Model: verify every request every time no implicit trust "
            "enforce least privilege segment your network monitor all traffic"
        )
        pipeline._ocr_texts.append(slide_text)

        clean_observation = (
            "The presenter ran a port scan in a terminal window showing three "
            "open ports. The firewall blocked two connection attempts in real time."
        )
        mock_gemini = MagicMock()
        mock_gemini.get_observations.return_value = [clean_observation]
        pipeline._gemini = mock_gemini

        detected_events: list = []
        event_bus.subscribe("injection_detected", lambda e: detected_events.append(e))

        with patch.object(pipeline._roaster, "generate", new_callable=AsyncMock, return_value="roast"):
            await pipeline._on_demo_stopped(
                DemoStopped(team_name="TeamBeta", duration=90.0)
            )
            await event_bus.drain(timeout=2.0)

        cross_ref_events = [
            e for e in detected_events
            if e.attempt.pattern == "cross_reference"
        ]
        assert len(cross_ref_events) == 0

    @pytest.mark.asyncio
    async def test_no_ocr_texts_produces_no_cross_reference_event(
        self, pipeline: DefensePipeline, event_bus: EventBus
    ) -> None:
        """Without any key-frame OCR data no cross-reference check runs."""
        await pipeline.setup(event_bus)
        await pipeline._on_demo_started(DemoStarted(team_name="TeamGamma"))

        # No OCR texts — pipeline._ocr_texts is empty after demo_started reset

        observation = (
            "The demo showed a working login form. Authentication completed "
            "successfully and the user was redirected to the dashboard page."
        )
        mock_gemini = MagicMock()
        mock_gemini.get_observations.return_value = [observation]
        pipeline._gemini = mock_gemini

        detected_events: list = []
        event_bus.subscribe("injection_detected", lambda e: detected_events.append(e))

        with patch.object(pipeline._roaster, "generate", new_callable=AsyncMock, return_value="roast"):
            await pipeline._on_demo_stopped(
                DemoStopped(team_name="TeamGamma", duration=60.0)
            )
            await event_bus.drain(timeout=2.0)

        cross_ref_events = [
            e for e in detected_events
            if e.attempt.pattern == "cross_reference"
        ]
        assert len(cross_ref_events) == 0

    @pytest.mark.asyncio
    async def test_ocr_texts_cleared_between_demos(
        self, pipeline: DefensePipeline, event_bus: EventBus
    ) -> None:
        """OCR texts accumulated for one team must not bleed into the next demo."""
        await pipeline.setup(event_bus)

        # First demo — accumulate some OCR texts
        await pipeline._on_demo_started(DemoStarted(team_name="TeamOne"))
        pipeline._ocr_texts.append(
            "TeamOne slide: machine learning anomaly detection real time alerts"
        )
        assert len(pipeline._ocr_texts) == 1

        # Second demo starts — OCR texts should be cleared
        await pipeline._on_demo_started(DemoStarted(team_name="TeamTwo"))
        assert pipeline._ocr_texts == [], (
            "_ocr_texts should be empty at the start of a new demo"
        )
