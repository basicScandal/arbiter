"""Test suite for rubric definitions.

Validates rubric weight constraints, level descriptor completeness,
and track criteria configuration.
"""

from __future__ import annotations

from src.scoring.rubric import EXTENDED_CRITERIA, GENERAL_CRITERIA, TRACK_CRITERIA

# ---------------------------------------------------------------------------
# General criteria
# ---------------------------------------------------------------------------


class TestGeneralCriteria:
    """Tests for GENERAL_CRITERIA rubric configuration."""

    def test_weights_sum_to_one(self):
        total = sum(c.weight for c in GENERAL_CRITERIA)
        assert abs(total - 1.0) < 0.01

    def test_three_criteria(self):
        assert len(GENERAL_CRITERIA) == 3

    def test_all_have_names(self):
        for c in GENERAL_CRITERIA:
            assert c.name
            assert len(c.name) > 0

    def test_all_have_level_descriptors(self):
        for c in GENERAL_CRITERIA:
            assert len(c.levels) >= 4  # at least 4 score ranges

    def test_expected_criteria_present(self):
        names = {c.name for c in GENERAL_CRITERIA}
        assert "Technical Execution" in names
        assert "Innovation" in names
        assert "Demo Quality" in names

    def test_weights_are_positive(self):
        for c in GENERAL_CRITERIA:
            assert c.weight > 0


# ---------------------------------------------------------------------------
# Extended criteria
# ---------------------------------------------------------------------------


class TestExtendedCriteria:
    """Tests for EXTENDED_CRITERIA rubric configuration."""

    def test_weights_sum_to_one(self):
        total = sum(c.weight for c in EXTENDED_CRITERIA)
        assert abs(total - 1.0) < 0.01

    def test_four_criteria(self):
        assert len(EXTENDED_CRITERIA) == 4

    def test_includes_impact(self):
        names = {c.name for c in EXTENDED_CRITERIA}
        assert "Impact" in names


# ---------------------------------------------------------------------------
# Track criteria
# ---------------------------------------------------------------------------


class TestTrackCriteria:
    """Tests for TRACK_CRITERIA configuration."""

    def test_four_tracks(self):
        assert len(TRACK_CRITERIA) == 4

    def test_expected_tracks(self):
        assert "SHADOW::VECTOR" in TRACK_CRITERIA
        assert "SENTINEL::MESH" in TRACK_CRITERIA
        assert "ZERO::PROOF" in TRACK_CRITERIA
        assert "ROGUE::AGENT" in TRACK_CRITERIA

    def test_all_have_bonus_weight(self):
        for track_id, tc in TRACK_CRITERIA.items():
            assert tc.bonus_weight > 0
            assert tc.bonus_weight <= 0.20  # bonus shouldn't dominate

    def test_all_have_names_and_descriptions(self):
        for track_id, tc in TRACK_CRITERIA.items():
            assert tc.name
            assert tc.description
            assert tc.track_id == track_id
