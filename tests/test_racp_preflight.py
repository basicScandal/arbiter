"""Preflight tests: does the control plane notice a defective detection policy?

Renewing a lease against a broken policy just reproduces the defect, so
preflight is what stands between "we compiled a policy" and "the policy in
force actually catches attacks". These tests degrade the real detector and
assert that preflight refuses to vouch for it.
"""

from __future__ import annotations

import pytest

from src.defense.injection_detector import INJECTION_PATTERNS, InjectionDetector
from src.racp.preflight import PreflightEvaluator, build_probes


@pytest.fixture
def evaluator() -> PreflightEvaluator:
    return PreflightEvaluator(InjectionDetector())


# ---------------------------------------------------------------------------
# Probe generation
# ---------------------------------------------------------------------------


def test_probes_are_shaped_by_the_current_task():
    probes = build_probes("Team Nebula", "ROGUE::AGENT")
    payloads = " ".join(p.text for p in probes)

    assert "Team Nebula" in payloads
    assert "ROGUE::AGENT" in payloads


def test_probes_cover_every_detection_category():
    probe_ids = {p.probe_id for p in build_probes("T", "X")}

    assert {
        "instruction_override",
        "scoring_override",
        "role_manipulation",
        "context_escape",
        "extraction",
        "semantic_rubric_echo",
        "semantic_self_eval",
    } <= probe_ids


def test_probes_survive_an_empty_team_name():
    probes = build_probes("", "")

    assert probes and all(p.text.strip() for p in probes)


# ---------------------------------------------------------------------------
# Verdicts
# ---------------------------------------------------------------------------


def test_shipped_policy_passes_preflight(evaluator):
    report = evaluator.run("Team Nebula", "ROGUE::AGENT")

    assert report.passed is True
    assert report.probes_missed == []


def test_shipped_policy_is_fully_covered_by_the_probe_suite(evaluator):
    """Every pattern's removal is noticed by at least one probe."""
    report = evaluator.run("Team Nebula", "ROGUE::AGENT")

    assert report.mutation_score == pytest.approx(1.0)


@pytest.mark.parametrize(
    "team",
    ["T", "Team Nebula", "", "A" * 60, "Los Pollos Hermanos"],
)
def test_coverage_does_not_depend_on_team_name(evaluator, team):
    """Task-shaped probes must not make the verdict a function of the team."""
    report = evaluator.run(team, "ROGUE::AGENT")

    assert report.passed is True
    assert report.mutation_score == pytest.approx(1.0)


def test_gutted_policy_fails_preflight():
    """A plugin that strips most patterns must not be silently trusted."""
    gutted = PreflightEvaluator(InjectionDetector(patterns=INJECTION_PATTERNS[:2]))

    report = gutted.run("Team Nebula", "ROGUE::AGENT")

    assert report.passed is False
    assert report.probes_missed


def test_empty_policy_fails_preflight():
    empty = PreflightEvaluator(InjectionDetector(patterns=[]))

    report = empty.run("Team Nebula", "ROGUE::AGENT")

    assert report.passed is False


def test_removing_the_scoring_patterns_is_caught():
    """The single most valuable patterns at a judged event."""
    remaining = [p for p in INJECTION_PATTERNS if p.category != "scoring"]

    report = PreflightEvaluator(InjectionDetector(patterns=remaining)).run("T", "X")

    assert report.passed is False
    assert "scoring_override" in report.probes_missed


def test_preflight_is_fast_enough_to_run_before_every_demo(evaluator):
    report = evaluator.run("Team Nebula", "ROGUE::AGENT")

    # Generous ceiling: the suite runs locally with no model calls.
    assert report.duration_us < 500_000
