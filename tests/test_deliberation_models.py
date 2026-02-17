"""Test suite for deliberation models.

Validates DemoMemory, TeamRanking, DeliberationResult, and deliberation
event types.
"""

from __future__ import annotations

import pytest

from src.memory.models import (
    DeliberationComplete,
    DeliberationRequested,
    DeliberationResult,
    DemoMemory,
    TeamRanking,
)


# ---------------------------------------------------------------------------
# DemoMemory
# ---------------------------------------------------------------------------


class TestDemoMemory:
    """Tests for DemoMemory model validation."""

    def test_basic_construction(self):
        mem = DemoMemory(
            team_name="CyberFalcons",
            track="ROGUE::AGENT",
            observations=["Built a tool"],
            transcripts=["We built this"],
            injection_attempts=0,
            demo_duration=180.0,
            stored_at=1000.0,
        )
        assert mem.team_name == "CyberFalcons"
        assert mem.injection_attempts == 0

    def test_empty_observations_allowed(self):
        mem = DemoMemory(
            team_name="Team",
            track="ROGUE::AGENT",
            observations=[],
            transcripts=[],
            injection_attempts=0,
            demo_duration=60.0,
            stored_at=1000.0,
        )
        assert len(mem.observations) == 0

    def test_serialization_round_trip(self):
        mem = DemoMemory(
            team_name="CyberFalcons",
            track="SHADOW::VECTOR",
            observations=["obs1", "obs2"],
            transcripts=["trans1"],
            injection_attempts=2,
            demo_duration=200.0,
            stored_at=1500.0,
        )
        json_str = mem.model_dump_json()
        restored = DemoMemory.model_validate_json(json_str)
        assert restored.team_name == mem.team_name
        assert restored.injection_attempts == 2
        assert restored.observations == ["obs1", "obs2"]

    def test_stores_count_not_content(self):
        """DemoMemory stores injection count, not payload content (security)."""
        mem = DemoMemory(
            team_name="Team",
            track="ROGUE::AGENT",
            observations=[],
            transcripts=[],
            injection_attempts=5,
            demo_duration=180.0,
            stored_at=1000.0,
        )
        # The model only has an int field, not a list of injection payloads
        assert isinstance(mem.injection_attempts, int)
        assert not hasattr(mem, "injection_content")


# ---------------------------------------------------------------------------
# TeamRanking
# ---------------------------------------------------------------------------


class TestTeamRanking:
    """Tests for TeamRanking model."""

    def test_basic_construction(self):
        ranking = TeamRanking(
            rank=1,
            team_name="CyberFalcons",
            track="ROGUE::AGENT",
            total_score=7.1,
            strengths=["Strong tech"],
            weaknesses=["Limited scope"],
            cross_references=["Unlike NightOwls"],
            reasoning="Top execution",
        )
        assert ranking.rank == 1
        assert ranking.total_score == 7.1

    def test_allows_empty_cross_references(self):
        ranking = TeamRanking(
            rank=1,
            team_name="Solo",
            track="ROGUE::AGENT",
            total_score=7.0,
            strengths=["Good"],
            weaknesses=[],
            cross_references=[],
            reasoning="Only team",
        )
        assert len(ranking.cross_references) == 0

    def test_serialization(self):
        ranking = TeamRanking(
            rank=2,
            team_name="NightOwls",
            track="SHADOW::VECTOR",
            total_score=6.5,
            strengths=["Creative approach"],
            weaknesses=["Rough demo"],
            cross_references=["More creative than CyberFalcons"],
            reasoning="Novel but unpolished",
        )
        data = ranking.model_dump()
        assert data["rank"] == 2
        assert data["team_name"] == "NightOwls"
        assert len(data["strengths"]) == 1


# ---------------------------------------------------------------------------
# DeliberationResult
# ---------------------------------------------------------------------------


class TestDeliberationResult:
    """Tests for DeliberationResult model."""

    def test_basic_construction(self):
        result = DeliberationResult(
            rankings=[
                TeamRanking(
                    rank=1, team_name="Team", track="ROGUE::AGENT",
                    total_score=7.0, strengths=["Good"], weaknesses=[],
                    cross_references=[], reasoning="Top",
                ),
            ],
            overall_narrative="Great event.",
            notable_themes=["AI security"],
            deliberated_at=1000.0,
        )
        assert len(result.rankings) == 1
        assert result.overall_narrative == "Great event."

    def test_multiple_rankings(self):
        rankings = [
            TeamRanking(
                rank=i, team_name=f"Team{i}", track="ROGUE::AGENT",
                total_score=10.0 - i, strengths=[], weaknesses=[],
                cross_references=[], reasoning=f"Rank {i}",
            )
            for i in range(1, 5)
        ]
        result = DeliberationResult(
            rankings=rankings,
            overall_narrative="Event narrative.",
            notable_themes=["Theme A", "Theme B"],
            deliberated_at=1000.0,
        )
        assert len(result.rankings) == 4
        assert len(result.notable_themes) == 2

    def test_serialization_round_trip(self):
        result = DeliberationResult(
            rankings=[
                TeamRanking(
                    rank=1, team_name="Alpha", track="SHADOW::VECTOR",
                    total_score=8.5, strengths=["Strong"], weaknesses=["Weak"],
                    cross_references=["vs Bravo"], reasoning="Top team",
                ),
            ],
            overall_narrative="Impressive hackathon.",
            notable_themes=["Security", "AI"],
            deliberated_at=2000.0,
        )
        json_str = result.model_dump_json()
        restored = DeliberationResult.model_validate_json(json_str)
        assert restored.rankings[0].team_name == "Alpha"
        assert restored.deliberated_at == 2000.0


# ---------------------------------------------------------------------------
# Event types
# ---------------------------------------------------------------------------


class TestEvents:
    """Tests for deliberation event types."""

    def test_deliberation_requested_event_type(self):
        event = DeliberationRequested()
        assert event.event_type == "deliberation_requested"

    def test_deliberation_complete_carries_result(self):
        result = DeliberationResult(
            rankings=[],
            overall_narrative="Done.",
            notable_themes=[],
            deliberated_at=1000.0,
        )
        event = DeliberationComplete(result=result)
        assert event.event_type == "deliberation_complete"
        assert event.result.overall_narrative == "Done."
