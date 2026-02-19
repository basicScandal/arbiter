"""Test suite for the deliberation engine, prompt building, and ranking.

Tests the DeliberationEngine including prompt construction, authoritative
Python-side ranking with tiebreakers, the deliberate() entry point, and
Claude fallback when Gemini is unavailable.
"""

from __future__ import annotations

import json
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.memory.deliberation_engine import (
    DELIBERATION_SYSTEM_PROMPT,
    DeliberationEngine,
)
from src.memory.models import DemoMemory, DeliberationResult, TeamRanking
from src.scoring.models import CriterionScore, DemoScorecard


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_memory(
    team_name: str = "CyberFalcons",
    track: str = "ROGUE::AGENT",
    observations: list[str] | None = None,
    transcripts: list[str] | None = None,
    injection_attempts: int = 0,
    demo_duration: float = 180.0,
) -> DemoMemory:
    return DemoMemory(
        team_name=team_name,
        track=track,
        observations=observations or ["Built a packet analysis tool"],
        transcripts=transcripts or ["We built this in 48 hours"],
        injection_attempts=injection_attempts,
        demo_duration=demo_duration,
        stored_at=1000.0,
    )


def _make_scorecard(
    team_name: str = "CyberFalcons",
    track: str = "ROGUE::AGENT",
    total_score: float = 7.1,
    tech_score: float = 8.0,
) -> DemoScorecard:
    return DemoScorecard(
        team_name=team_name,
        track=track,
        criteria=[
            CriterionScore(name="Technical Execution", score=tech_score, weight=0.40, justification="Solid"),
            CriterionScore(name="Innovation", score=7.0, weight=0.30, justification="Novel"),
            CriterionScore(name="Demo Quality", score=6.0, weight=0.30, justification="Good"),
        ],
        track_bonus=None,
        total_score=total_score,
        scored_at=1000.0,
    )


def _make_ranking(
    team_name: str = "CyberFalcons",
    rank: int = 1,
    total_score: float = 7.1,
    track: str = "ROGUE::AGENT",
) -> TeamRanking:
    return TeamRanking(
        rank=rank,
        team_name=team_name,
        track=track,
        total_score=total_score,
        strengths=["Strong technical work"],
        weaknesses=["Limited innovation"],
        cross_references=["Unlike NightOwls, this team focused on depth"],
        reasoning="Solid execution across the board",
    )


def _make_deliberation_result(rankings: list[TeamRanking] | None = None) -> DeliberationResult:
    return DeliberationResult(
        rankings=rankings or [_make_ranking()],
        overall_narrative="An impressive showing from all teams.",
        notable_themes=["Security tooling", "AI integration"],
        deliberated_at=1000.0,
    )


# ---------------------------------------------------------------------------
# Constructor
# ---------------------------------------------------------------------------


class TestConstructor:
    """Tests for DeliberationEngine initialization."""

    def test_creates_separate_client(self):
        engine = DeliberationEngine(api_key="test-key")
        assert engine._client is not None
        assert engine._model == "gemini-2.5-flash"

    def test_custom_model(self):
        engine = DeliberationEngine(api_key="test-key", model="gemini-2.0-flash")
        assert engine._model == "gemini-2.0-flash"

    def test_claude_client_enabled_with_key(self):
        engine = DeliberationEngine(api_key="test-key", anthropic_api_key="sk-ant-test")
        assert engine._claude_client is not None

    def test_claude_client_disabled_without_key(self):
        with patch.dict("os.environ", {}, clear=True):
            engine = DeliberationEngine(api_key="test-key", anthropic_api_key="")
            assert engine._claude_client is None

    def test_claude_client_reads_env_var(self):
        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "sk-ant-env"}):
            engine = DeliberationEngine(api_key="test-key")
            assert engine._claude_client is not None


# ---------------------------------------------------------------------------
# Prompt building
# ---------------------------------------------------------------------------


class TestBuildPrompt:
    """Tests for DeliberationEngine._build_deliberation_prompt."""

    def test_includes_team_count(self):
        memories = [_make_memory(), _make_memory(team_name="NightOwls")]
        scorecards = [_make_scorecard(), _make_scorecard(team_name="NightOwls", total_score=6.5)]
        prompt = DeliberationEngine._build_deliberation_prompt(memories, scorecards)
        assert "2 teams" in prompt

    def test_includes_team_names(self):
        memories = [_make_memory()]
        scorecards = [_make_scorecard()]
        prompt = DeliberationEngine._build_deliberation_prompt(memories, scorecards)
        assert "CyberFalcons" in prompt

    def test_includes_track(self):
        memories = [_make_memory(track="SHADOW::VECTOR")]
        scorecards = [_make_scorecard()]
        prompt = DeliberationEngine._build_deliberation_prompt(memories, scorecards)
        assert "SHADOW::VECTOR" in prompt

    def test_includes_total_score(self):
        memories = [_make_memory()]
        scorecards = [_make_scorecard(total_score=8.5)]
        prompt = DeliberationEngine._build_deliberation_prompt(memories, scorecards)
        assert "8.5" in prompt

    def test_includes_observations(self):
        memories = [_make_memory(observations=["Used Scapy for packet sniffing"])]
        scorecards = [_make_scorecard()]
        prompt = DeliberationEngine._build_deliberation_prompt(memories, scorecards)
        assert "Scapy" in prompt

    def test_includes_transcripts(self):
        memories = [_make_memory(transcripts=["Built in 48 hours"])]
        scorecards = [_make_scorecard()]
        prompt = DeliberationEngine._build_deliberation_prompt(memories, scorecards)
        assert "48 hours" in prompt

    def test_includes_duration(self):
        memories = [_make_memory(demo_duration=300.0)]
        scorecards = [_make_scorecard()]
        prompt = DeliberationEngine._build_deliberation_prompt(memories, scorecards)
        assert "300s" in prompt

    def test_includes_injection_count(self):
        memories = [_make_memory(injection_attempts=3)]
        scorecards = [_make_scorecard()]
        prompt = DeliberationEngine._build_deliberation_prompt(memories, scorecards)
        assert "Injection attempts: 3" in prompt

    def test_caps_observations_at_five(self):
        obs = [f"Observation {i}" for i in range(10)]
        memories = [_make_memory(observations=obs)]
        scorecards = [_make_scorecard()]
        prompt = DeliberationEngine._build_deliberation_prompt(memories, scorecards)
        # Should include obs 0-4 but not 5-9
        assert "Observation 0" in prompt
        assert "Observation 4" in prompt
        assert "Observation 5" not in prompt

    def test_caps_transcripts_at_three(self):
        trans = [f"Transcript {i}" for i in range(6)]
        memories = [_make_memory(transcripts=trans)]
        scorecards = [_make_scorecard()]
        prompt = DeliberationEngine._build_deliberation_prompt(memories, scorecards)
        assert "Transcript 0" in prompt
        assert "Transcript 2" in prompt
        assert "Transcript 3" not in prompt

    def test_missing_scorecard_uses_zero(self):
        memories = [_make_memory(team_name="UnknownTeam")]
        scorecards = []  # no matching scorecard
        prompt = DeliberationEngine._build_deliberation_prompt(memories, scorecards)
        assert "Score: 0.0" in prompt

    def test_multiple_teams_all_present(self):
        memories = [
            _make_memory(team_name="Alpha"),
            _make_memory(team_name="Bravo"),
            _make_memory(team_name="Charlie"),
        ]
        scorecards = [
            _make_scorecard(team_name="Alpha", total_score=8.0),
            _make_scorecard(team_name="Bravo", total_score=7.0),
            _make_scorecard(team_name="Charlie", total_score=6.0),
        ]
        prompt = DeliberationEngine._build_deliberation_prompt(memories, scorecards)
        assert "Alpha" in prompt
        assert "Bravo" in prompt
        assert "Charlie" in prompt

    def test_includes_cross_reference_request(self):
        memories = [_make_memory(), _make_memory(team_name="NightOwls")]
        scorecards = [_make_scorecard(), _make_scorecard(team_name="NightOwls")]
        prompt = DeliberationEngine._build_deliberation_prompt(memories, scorecards)
        assert "cross-references" in prompt.lower()


# ---------------------------------------------------------------------------
# Authoritative ranking
# ---------------------------------------------------------------------------


class TestAuthoritativeRanking:
    """Tests for DeliberationEngine._apply_authoritative_ranking."""

    def test_sorts_by_total_score_descending(self):
        rankings = [
            _make_ranking(team_name="Low", rank=1, total_score=5.0),
            _make_ranking(team_name="High", rank=2, total_score=9.0),
            _make_ranking(team_name="Mid", rank=3, total_score=7.0),
        ]
        result = _make_deliberation_result(rankings=rankings)
        scorecards = [
            _make_scorecard(team_name="Low", total_score=5.0),
            _make_scorecard(team_name="High", total_score=9.0),
            _make_scorecard(team_name="Mid", total_score=7.0),
        ]
        memories = [
            _make_memory(team_name="Low"),
            _make_memory(team_name="High"),
            _make_memory(team_name="Mid"),
        ]

        result = DeliberationEngine._apply_authoritative_ranking(result, scorecards, memories)

        assert result.rankings[0].team_name == "High"
        assert result.rankings[1].team_name == "Mid"
        assert result.rankings[2].team_name == "Low"

    def test_assigns_rank_numbers(self):
        rankings = [
            _make_ranking(team_name="B", rank=99),
            _make_ranking(team_name="A", rank=99),
        ]
        result = _make_deliberation_result(rankings=rankings)
        scorecards = [
            _make_scorecard(team_name="A", total_score=9.0),
            _make_scorecard(team_name="B", total_score=5.0),
        ]
        memories = [_make_memory(team_name="A"), _make_memory(team_name="B")]

        result = DeliberationEngine._apply_authoritative_ranking(result, scorecards, memories)

        assert result.rankings[0].rank == 1
        assert result.rankings[1].rank == 2

    def test_tiebreaker_technical_execution(self):
        """When total scores tie, higher Technical Execution wins."""
        rankings = [
            _make_ranking(team_name="LowTech", total_score=7.0),
            _make_ranking(team_name="HighTech", total_score=7.0),
        ]
        result = _make_deliberation_result(rankings=rankings)
        scorecards = [
            _make_scorecard(team_name="LowTech", total_score=7.0, tech_score=6.0),
            _make_scorecard(team_name="HighTech", total_score=7.0, tech_score=9.0),
        ]
        memories = [
            _make_memory(team_name="LowTech", demo_duration=180.0),
            _make_memory(team_name="HighTech", demo_duration=180.0),
        ]

        result = DeliberationEngine._apply_authoritative_ranking(result, scorecards, memories)

        assert result.rankings[0].team_name == "HighTech"
        assert result.rankings[1].team_name == "LowTech"

    def test_tiebreaker_demo_duration(self):
        """When total and tech scores tie, longer demo duration wins."""
        rankings = [
            _make_ranking(team_name="Short", total_score=7.0),
            _make_ranking(team_name="Long", total_score=7.0),
        ]
        result = _make_deliberation_result(rankings=rankings)
        scorecards = [
            _make_scorecard(team_name="Short", total_score=7.0, tech_score=8.0),
            _make_scorecard(team_name="Long", total_score=7.0, tech_score=8.0),
        ]
        memories = [
            _make_memory(team_name="Short", demo_duration=120.0),
            _make_memory(team_name="Long", demo_duration=300.0),
        ]

        result = DeliberationEngine._apply_authoritative_ranking(result, scorecards, memories)

        assert result.rankings[0].team_name == "Long"
        assert result.rankings[1].team_name == "Short"

    def test_overwrites_llm_total_score(self):
        """Rankings should use ScoreStore total_score, not whatever the LLM provided."""
        rankings = [_make_ranking(team_name="Team", total_score=999.0)]
        result = _make_deliberation_result(rankings=rankings)
        scorecards = [_make_scorecard(team_name="Team", total_score=7.1)]
        memories = [_make_memory(team_name="Team")]

        result = DeliberationEngine._apply_authoritative_ranking(result, scorecards, memories)

        assert result.rankings[0].total_score == 7.1

    def test_missing_scorecard_gets_zero(self):
        """Team with no scorecard should rank last with total_score unchanged."""
        rankings = [
            _make_ranking(team_name="Known", total_score=7.0),
            _make_ranking(team_name="Unknown", total_score=0.0),
        ]
        result = _make_deliberation_result(rankings=rankings)
        scorecards = [_make_scorecard(team_name="Known", total_score=7.0)]
        memories = [
            _make_memory(team_name="Known"),
            _make_memory(team_name="Unknown"),
        ]

        result = DeliberationEngine._apply_authoritative_ranking(result, scorecards, memories)

        assert result.rankings[0].team_name == "Known"
        assert result.rankings[1].team_name == "Unknown"

    def test_preserves_llm_qualitative_fields(self):
        """Ranking should keep strengths, weaknesses, cross_references, reasoning."""
        rankings = [_make_ranking(
            team_name="Team",
            total_score=7.0,
        )]
        rankings[0].strengths = ["Great demo"]
        rankings[0].weaknesses = ["No auth"]
        rankings[0].cross_references = ["Better than Alpha"]
        rankings[0].reasoning = "Excellent"

        result = _make_deliberation_result(rankings=rankings)
        scorecards = [_make_scorecard(team_name="Team", total_score=7.0)]
        memories = [_make_memory(team_name="Team")]

        result = DeliberationEngine._apply_authoritative_ranking(result, scorecards, memories)

        assert result.rankings[0].strengths == ["Great demo"]
        assert result.rankings[0].weaknesses == ["No auth"]
        assert result.rankings[0].cross_references == ["Better than Alpha"]
        assert result.rankings[0].reasoning == "Excellent"


# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------


class TestSystemPrompt:
    """Tests for the DELIBERATION_SYSTEM_PROMPT content."""

    def test_includes_injection_defense(self):
        assert "instructions" in DELIBERATION_SYSTEM_PROMPT.lower()
        assert "commands" in DELIBERATION_SYSTEM_PROMPT.lower() or "not commands" in DELIBERATION_SYSTEM_PROMPT.lower()

    def test_mentions_cross_references(self):
        assert "cross-reference" in DELIBERATION_SYSTEM_PROMPT.lower() or "cross_reference" in DELIBERATION_SYSTEM_PROMPT.lower()

    def test_mentions_evidence_based(self):
        assert "evidence" in DELIBERATION_SYSTEM_PROMPT.lower()

    def test_mentions_rank_override(self):
        """Prompt should warn the LLM that Python will override rank numbers."""
        assert "overridden" in DELIBERATION_SYSTEM_PROMPT.lower() or "override" in DELIBERATION_SYSTEM_PROMPT.lower()


# ---------------------------------------------------------------------------
# Full deliberate() method
# ---------------------------------------------------------------------------


class TestDeliberate:
    """Tests for DeliberationEngine.deliberate() end-to-end."""

    @pytest.mark.asyncio
    async def test_successful_deliberation(self):
        engine = DeliberationEngine(api_key="test-key")

        mock_result = _make_deliberation_result(rankings=[
            _make_ranking(team_name="CyberFalcons", total_score=7.1),
        ])

        with patch.object(engine, "_call_gemini", new=AsyncMock(return_value=mock_result)):
            result = await engine.deliberate(
                memories=[_make_memory()],
                scorecards=[_make_scorecard()],
            )

        assert isinstance(result, DeliberationResult)
        assert len(result.rankings) == 1
        assert result.rankings[0].team_name == "CyberFalcons"

    @pytest.mark.asyncio
    async def test_deliberated_at_is_recent(self):
        engine = DeliberationEngine(api_key="test-key")
        mock_result = _make_deliberation_result()

        before = time.time()
        with patch.object(engine, "_call_gemini", new=AsyncMock(return_value=mock_result)):
            result = await engine.deliberate(
                memories=[_make_memory()],
                scorecards=[_make_scorecard()],
            )

        assert result.deliberated_at >= before

    @pytest.mark.asyncio
    async def test_empty_memories_raises(self):
        engine = DeliberationEngine(api_key="test-key")

        with pytest.raises(ValueError, match="No demo observations"):
            await engine.deliberate(memories=[], scorecards=[])

    @pytest.mark.asyncio
    async def test_gemini_failure_without_claude_raises_runtime_error(self):
        """When Gemini fails and no Claude client is available, RuntimeError is raised."""
        engine = DeliberationEngine(api_key="test-key", anthropic_api_key="")
        engine._claude_client = None  # explicitly disable

        with patch.object(engine, "_call_gemini", new=AsyncMock(side_effect=Exception("API down"))):
            with pytest.raises(RuntimeError, match="All deliberation providers failed"):
                await engine.deliberate(
                    memories=[_make_memory()],
                    scorecards=[_make_scorecard()],
                )

    @pytest.mark.asyncio
    async def test_applies_authoritative_ranking(self):
        """Python should re-sort rankings regardless of LLM ordering."""
        engine = DeliberationEngine(api_key="test-key")

        # LLM returns wrong order
        mock_result = _make_deliberation_result(rankings=[
            _make_ranking(team_name="Low", rank=1, total_score=5.0),
            _make_ranking(team_name="High", rank=2, total_score=9.0),
        ])

        scorecards = [
            _make_scorecard(team_name="Low", total_score=5.0),
            _make_scorecard(team_name="High", total_score=9.0),
        ]

        with patch.object(engine, "_call_gemini", new=AsyncMock(return_value=mock_result)):
            result = await engine.deliberate(
                memories=[_make_memory(team_name="Low"), _make_memory(team_name="High")],
                scorecards=scorecards,
            )

        # Python should have re-sorted: High first
        assert result.rankings[0].team_name == "High"
        assert result.rankings[0].rank == 1
        assert result.rankings[1].team_name == "Low"
        assert result.rankings[1].rank == 2


# ---------------------------------------------------------------------------
# Claude fallback
# ---------------------------------------------------------------------------


def _make_claude_response_json(
    team_name: str = "CyberFalcons",
    track: str = "ROGUE::AGENT",
    total_score: float = 7.1,
) -> str:
    """Build a valid DeliberationResult JSON string as Claude would return."""
    return json.dumps({
        "rankings": [{
            "rank": 1,
            "team_name": team_name,
            "track": track,
            "total_score": total_score,
            "strengths": ["Strong execution"],
            "weaknesses": ["Limited scope"],
            "cross_references": ["Better than other teams"],
            "reasoning": "Solid work overall",
        }],
        "overall_narrative": "An impressive competition.",
        "notable_themes": ["AI tooling"],
        "deliberated_at": 0.0,
    })


def _mock_claude_message(text: str) -> MagicMock:
    """Create a mock Anthropic message response."""
    content_block = MagicMock()
    content_block.text = text
    message = MagicMock()
    message.content = [content_block]
    return message


class TestClaudeFallback:
    """Tests for Claude fallback in deliberation."""

    @pytest.mark.asyncio
    async def test_gemini_fail_claude_succeeds(self):
        """When Gemini fails, Claude fallback produces a valid result."""
        engine = DeliberationEngine(api_key="test-key", anthropic_api_key="sk-ant-test")

        mock_result = _make_deliberation_result(rankings=[
            _make_ranking(team_name="CyberFalcons", total_score=7.1),
        ])

        with (
            patch.object(engine, "_call_gemini", new=AsyncMock(side_effect=Exception("quota"))),
            patch.object(engine, "_call_claude", new=AsyncMock(return_value=mock_result)),
        ):
            result = await engine.deliberate(
                memories=[_make_memory()],
                scorecards=[_make_scorecard()],
            )

        assert isinstance(result, DeliberationResult)
        assert result.rankings[0].team_name == "CyberFalcons"

    @pytest.mark.asyncio
    async def test_both_providers_fail_raises_runtime_error(self):
        """When both Gemini and Claude fail, RuntimeError is raised."""
        engine = DeliberationEngine(api_key="test-key", anthropic_api_key="sk-ant-test")

        with (
            patch.object(engine, "_call_gemini", new=AsyncMock(side_effect=Exception("quota"))),
            patch.object(engine, "_call_claude", new=AsyncMock(side_effect=Exception("Claude down"))),
        ):
            with pytest.raises(RuntimeError, match="All deliberation providers failed"):
                await engine.deliberate(
                    memories=[_make_memory()],
                    scorecards=[_make_scorecard()],
                )

    @pytest.mark.asyncio
    async def test_gemini_success_skips_claude(self):
        """When Gemini succeeds, Claude is never called."""
        engine = DeliberationEngine(api_key="test-key", anthropic_api_key="sk-ant-test")
        mock_result = _make_deliberation_result()

        claude_mock = AsyncMock()
        with (
            patch.object(engine, "_call_gemini", new=AsyncMock(return_value=mock_result)),
            patch.object(engine, "_call_claude", new=claude_mock),
        ):
            await engine.deliberate(
                memories=[_make_memory()],
                scorecards=[_make_scorecard()],
            )

        claude_mock.assert_not_called()

    @pytest.mark.asyncio
    async def test_claude_applies_authoritative_ranking(self):
        """Rankings from Claude fallback still get Python-sorted."""
        engine = DeliberationEngine(api_key="test-key", anthropic_api_key="sk-ant-test")

        # Claude returns wrong order
        mock_result = _make_deliberation_result(rankings=[
            _make_ranking(team_name="Low", rank=1, total_score=5.0),
            _make_ranking(team_name="High", rank=2, total_score=9.0),
        ])

        scorecards = [
            _make_scorecard(team_name="Low", total_score=5.0),
            _make_scorecard(team_name="High", total_score=9.0),
        ]

        with (
            patch.object(engine, "_call_gemini", new=AsyncMock(side_effect=Exception("quota"))),
            patch.object(engine, "_call_claude", new=AsyncMock(return_value=mock_result)),
        ):
            result = await engine.deliberate(
                memories=[_make_memory(team_name="Low"), _make_memory(team_name="High")],
                scorecards=scorecards,
            )

        assert result.rankings[0].team_name == "High"
        assert result.rankings[0].rank == 1

    @pytest.mark.asyncio
    async def test_call_claude_parses_valid_json(self):
        """_call_claude should parse valid JSON into a DeliberationResult."""
        engine = DeliberationEngine(api_key="test-key", anthropic_api_key="sk-ant-test")

        response_json = _make_claude_response_json()
        mock_message = _mock_claude_message(response_json)

        with patch.object(engine._claude_client.messages, "create", new=AsyncMock(return_value=mock_message)):
            result = await engine._call_claude("test prompt")

        assert isinstance(result, DeliberationResult)
        assert result.rankings[0].team_name == "CyberFalcons"

    @pytest.mark.asyncio
    async def test_call_claude_strips_markdown_fences(self):
        """_call_claude should strip ```json fences before parsing."""
        engine = DeliberationEngine(api_key="test-key", anthropic_api_key="sk-ant-test")

        response_json = _make_claude_response_json()
        fenced = f"```json\n{response_json}\n```"
        mock_message = _mock_claude_message(fenced)

        with patch.object(engine._claude_client.messages, "create", new=AsyncMock(return_value=mock_message)):
            result = await engine._call_claude("test prompt")

        assert isinstance(result, DeliberationResult)
        assert result.rankings[0].team_name == "CyberFalcons"

    @pytest.mark.asyncio
    async def test_call_claude_includes_json_schema_in_prompt(self):
        """_call_claude should append the JSON schema to the prompt."""
        engine = DeliberationEngine(api_key="test-key", anthropic_api_key="sk-ant-test")

        response_json = _make_claude_response_json()
        mock_message = _mock_claude_message(response_json)

        create_mock = AsyncMock(return_value=mock_message)
        with patch.object(engine._claude_client.messages, "create", new=create_mock):
            await engine._call_claude("my deliberation prompt")

        # Verify the prompt sent to Claude includes the JSON schema
        call_kwargs = create_mock.call_args[1]
        user_content = call_kwargs["messages"][0]["content"]
        assert "my deliberation prompt" in user_content
        assert "rankings" in user_content  # from _DELIBERATION_JSON_SCHEMA

    @pytest.mark.asyncio
    async def test_call_claude_uses_system_prompt(self):
        """_call_claude should use DELIBERATION_SYSTEM_PROMPT as the system message."""
        engine = DeliberationEngine(api_key="test-key", anthropic_api_key="sk-ant-test")

        response_json = _make_claude_response_json()
        mock_message = _mock_claude_message(response_json)

        create_mock = AsyncMock(return_value=mock_message)
        with patch.object(engine._claude_client.messages, "create", new=create_mock):
            await engine._call_claude("test prompt")

        call_kwargs = create_mock.call_args[1]
        assert call_kwargs["system"] == DELIBERATION_SYSTEM_PROMPT
