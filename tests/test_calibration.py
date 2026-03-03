"""Calibration validation tests — Phase 2 Red Team + Scoring Gauntlet.

Validates DEFAULT_CALIBRATION values, Groq's neutral defaults,
provider convergence after calibration, score clamping at extremes,
and empirical convergence from VCR cassette data.
"""

from __future__ import annotations

from src.scoring.aggregator import DEFAULT_CALIBRATION, ScoreAggregator

# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_default_calibration_values_documented():
    """Assert DEFAULT_CALIBRATION has the expected provider keys and sane ranges.

    Documents the calibration contract:
    - Providers: gemini, claude, openai, groq
    - Temperature: (0.5, 3.0) — must be positive, reasonable scaling factor
    - Bias: (-2.0, 2.0) — additive correction, kept small
    """
    expected_keys = {"gemini", "claude", "openai", "groq"}
    assert set(DEFAULT_CALIBRATION.keys()) == expected_keys, (
        f"Expected providers {expected_keys}, got {set(DEFAULT_CALIBRATION.keys())}"
    )

    for provider, cal in DEFAULT_CALIBRATION.items():
        assert "temperature" in cal, f"{provider}: missing temperature"
        assert "bias" in cal, f"{provider}: missing bias"

        t = cal["temperature"]
        assert 0.5 < t < 3.0, (
            f"{provider}: temperature {t} outside sane range (0.5, 3.0)"
        )

        b = cal["bias"]
        assert -2.0 < b < 2.0, (
            f"{provider}: bias {b} outside sane range (-2.0, 2.0)"
        )


def test_groq_neutral_defaults():
    """Assert Groq has temperature=1.0 and bias=0.0 (neutral/passthrough).

    Groq's calibration is intentionally neutral because empirical data
    from live hackathon scoring hasn't been collected yet. This test
    documents that assumption.
    """
    groq_cal = DEFAULT_CALIBRATION["groq"]
    assert groq_cal["temperature"] == 1.0, (
        f"Groq temperature {groq_cal['temperature']} != 1.0 (expected neutral)"
    )
    assert groq_cal["bias"] == 0.0, (
        f"Groq bias {groq_cal['bias']} != 0.0 (expected neutral)"
    )


def test_calibration_converges_providers():
    """All 4 providers given raw score 7.0; calibrated scores within 1.5.

    calibrate_score() applies temperature scaling and bias correction.
    With the same raw input, all providers should converge to approximately
    the same calibrated score.
    """
    aggregator = ScoreAggregator()
    raw_score = 7.0

    calibrated = {
        provider: aggregator.calibrate_score(raw_score, provider)
        for provider in DEFAULT_CALIBRATION
    }

    values = list(calibrated.values())
    spread = max(values) - min(values)
    assert spread < 1.5, (
        f"Calibrated spread {spread:.3f} >= 1.5 — providers diverge too much. "
        f"Calibrated: {calibrated}"
    )


def test_extreme_scores_clamped():
    """calibrate_score() clamps results to [0.0, 10.0] despite temperature and bias.

    OpenAI has temperature=1.5 and bias=0.3 — the most aggressive calibration.
    Even with extreme raw inputs (0.0 and 10.0), the output must stay in bounds.
    """
    aggregator = ScoreAggregator()

    low = aggregator.calibrate_score(0.0, "openai")
    assert low >= 0.0, f"calibrate_score(0.0, 'openai') = {low} < 0.0"

    high = aggregator.calibrate_score(10.0, "openai")
    assert high <= 10.0, f"calibrate_score(10.0, 'openai') = {high} > 10.0"

    # Verify clamping works for all providers at extremes
    for provider in DEFAULT_CALIBRATION:
        assert aggregator.calibrate_score(0.0, provider) >= 0.0
        assert aggregator.calibrate_score(10.0, provider) <= 10.0


def test_cassette_empirical_convergence():
    """Cassette-derived raw scores converge after calibration (delta < 0.5).

    VCR cassettes captured Gemini and Claude scoring the identical demo
    (Team Phantom, SHADOW::VECTOR). Raw scores:
        Gemini: Tech=9, Innovation=9, Demo=8, Track=9 → mean 8.75
        Claude: Tech=8, Innovation=8, Demo=8, Track=8 → mean 8.0
        Raw delta: 0.75

    After calibration, the per-criterion means should be within 0.5.
    """
    aggregator = ScoreAggregator()

    # Raw per-criterion scores from cassettes
    gemini_raw = {"Technical Execution": 9, "Innovation": 9, "Demo Quality": 8, "Track Bonus": 9}
    claude_raw = {"Technical Execution": 8, "Innovation": 8, "Demo Quality": 8, "Track Bonus": 8}

    gemini_calibrated = [aggregator.calibrate_score(s, "gemini") for s in gemini_raw.values()]
    claude_calibrated = [aggregator.calibrate_score(s, "claude") for s in claude_raw.values()]

    gemini_mean = sum(gemini_calibrated) / len(gemini_calibrated)
    claude_mean = sum(claude_calibrated) / len(claude_calibrated)

    delta = abs(gemini_mean - claude_mean)
    assert delta < 0.5, (
        f"Cassette calibration delta {delta:.2f} >= 0.5 — "
        f"Gemini mean={gemini_mean:.2f}, Claude mean={claude_mean:.2f}"
    )
