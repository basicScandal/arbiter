"""Regression guard for the controller comparison in scripts/racp_experiment.py.

The experiment is the evidence behind the claim that renewal and preflight each
prevent effects a startup-only policy lets through. If that ordering ever
inverts, the claim is wrong and this fails.
"""

from __future__ import annotations

import random

import pytest

from scripts.racp_experiment import CONTROLLERS, build_scenarios, run_controller

SCENARIOS = 120
SEED = 20260906


@pytest.fixture(scope="module")
def results() -> dict[str, dict]:
    scenarios = build_scenarios(SCENARIOS, random.Random(SEED))
    return {name: run_controller(name, scenarios) for name in CONTROLLERS}


def test_ungoverned_execution_prevents_nothing(results):
    assert results["no_control"]["vpr"] == 0.0


def test_renewal_beats_a_policy_compiled_only_at_startup(results):
    assert results["dynamic_lease"]["vpr"] > results["static_startup_policy"]["vpr"]


def test_preflight_adds_prevention_on_top_of_renewal(results):
    """Preflight catches the defective-policy family that renewal reproduces."""
    assert (
        results["dynamic_lease_preflight"]["vpr"] > results["dynamic_lease"]["vpr"]
    )


def test_full_control_plane_catches_every_observable_harm(results):
    scenarios = build_scenarios(SCENARIOS, random.Random(SEED))
    unsafe = [s for s in scenarios if s.unsafe]
    unobservable = [s for s in unsafe if s.family == "unobservable_harm"]
    ceiling = (len(unsafe) - len(unobservable)) / len(unsafe)

    assert results["dynamic_lease_preflight"]["vpr"] == pytest.approx(ceiling)


def test_no_controller_blocks_a_benign_demo(results):
    """A judge that refuses to judge is not a defense."""
    for name, result in results.items():
        assert result["false_block_rate"] == 0.0, name


def test_decisions_stay_inside_the_live_latency_budget(results):
    for name, result in results.items():
        assert result["p95_latency_us"] < 50_000, name
