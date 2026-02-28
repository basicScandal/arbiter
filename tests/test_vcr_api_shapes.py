"""VCR cassette tests for API response shape validation.

Records real API responses from Gemini, Claude, and Groq, then replays
them to validate that response shapes parse into production models
(DemoScorecard, Commentary). Cassettes are recorded once with live API
keys, then replayed in CI without keys.

Recording:
    GEMINI_API_KEY=... ANTHROPIC_API_KEY=... GROQ_API_KEY=... \
      uv run pytest tests/test_vcr_api_shapes.py -v --record-mode=new_episodes

Playback (CI):
    uv run pytest tests/test_vcr_api_shapes.py -v
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from src.commentary.generator import CommentaryGenerator
from src.commentary.models import Commentary
from src.defense.models import SanitizedOutput
from src.scoring.engine import ScoringEngine
from src.scoring.models import DemoScorecard
from src.scoring.rubric import GENERAL_CRITERIA, TRACK_CRITERIA

# Directory where pytest-recording stores cassettes (vcr_config sets this flat)
_CASSETTE_DIR = Path(__file__).parent / "cassettes"

_TRACK = "SHADOW::VECTOR"


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def demo_output() -> SanitizedOutput:
    """Realistic SanitizedOutput mimicking a hackathon demo with 5 observations."""
    return SanitizedOutput(
        team_name="Team Phantom",
        observations=[
            "Presented a custom LLM-based fuzzer that generates context-aware payloads targeting API authentication endpoints",
            "Live demo showed the fuzzer discovering an IDOR vulnerability in a test application within 45 seconds",
            "Tool integrates with Burp Suite via a custom extension for real-time payload generation",
            "Demonstrated a novel technique for chaining prompt injection with SSRF to exfiltrate internal API schemas",
            "Source code is well-structured with comprehensive test coverage shown during the presentation",
        ],
        transcripts=[
            "Our approach combines traditional fuzzing with LLM-guided payload mutation to find vulnerabilities that scanners miss.",
            "The key insight is that LLMs understand API context, so they can generate semantically valid but malicious requests.",
        ],
        injection_attempts=[],
        demo_duration=420.0,
    )


def _cassette_exists(test_name: str) -> bool:
    """Check if a YAML cassette file exists for the given test."""
    return (_CASSETTE_DIR / f"{test_name}.yaml").exists()


def _skip_if_no_key_and_no_cassette(env_var: str, test_name: str) -> None:
    """Skip test when API key is missing AND no recorded cassette exists."""
    if not os.environ.get(env_var) and not _cassette_exists(test_name):
        pytest.skip(
            f"{env_var} not set and no cassette at "
            f"{_CASSETTE_DIR / test_name}.yaml"
        )


# ---------------------------------------------------------------------------
# Scoring shape tests
# ---------------------------------------------------------------------------


@pytest.mark.vcr
@pytest.mark.slow
async def test_gemini_scoring_response_shape(demo_output: SanitizedOutput) -> None:
    """Gemini scoring response parses into a valid DemoScorecard."""
    _skip_if_no_key_and_no_cassette(
        "GEMINI_API_KEY", "test_gemini_scoring_response_shape"
    )

    api_key = os.environ.get("GEMINI_API_KEY", "vcr-placeholder")
    engine = ScoringEngine(api_key=api_key)

    prompt = engine._build_prompt(
        demo_output, _TRACK, GENERAL_CRITERIA, TRACK_CRITERIA
    )
    raw_text = await engine._call_gemini(prompt)
    scorecard = engine._parse_and_validate(
        raw_text, demo_output.team_name, _TRACK, GENERAL_CRITERIA, TRACK_CRITERIA
    )

    assert isinstance(scorecard, DemoScorecard)
    assert scorecard.team_name == "Team Phantom"
    assert scorecard.track == _TRACK
    assert len(scorecard.criteria) >= len(GENERAL_CRITERIA)
    for criterion in scorecard.criteria:
        assert 0.0 <= criterion.score <= 10.0
        assert criterion.justification, f"Empty justification for {criterion.name}"
    assert scorecard.total_score > 0.0


@pytest.mark.vcr
@pytest.mark.slow
async def test_claude_scoring_response_shape(demo_output: SanitizedOutput) -> None:
    """Claude scoring fallback produces a valid DemoScorecard."""
    _skip_if_no_key_and_no_cassette(
        "ANTHROPIC_API_KEY", "test_claude_scoring_response_shape"
    )

    api_key = os.environ.get("ANTHROPIC_API_KEY", "vcr-placeholder")
    engine = ScoringEngine(
        api_key="unused-gemini-key",
        anthropic_api_key=api_key,
    )

    prompt = engine._build_prompt(
        demo_output, _TRACK, GENERAL_CRITERIA, TRACK_CRITERIA
    )
    raw_text = await engine._call_claude(prompt)
    scorecard = engine._parse_and_validate(
        raw_text, demo_output.team_name, _TRACK, GENERAL_CRITERIA, TRACK_CRITERIA
    )

    assert isinstance(scorecard, DemoScorecard)
    assert scorecard.team_name == "Team Phantom"
    assert scorecard.track == _TRACK
    assert len(scorecard.criteria) >= len(GENERAL_CRITERIA)
    for criterion in scorecard.criteria:
        assert 0.0 <= criterion.score <= 10.0
        assert criterion.justification, f"Empty justification for {criterion.name}"
    assert scorecard.total_score > 0.0


# ---------------------------------------------------------------------------
# Commentary shape tests
# ---------------------------------------------------------------------------


@pytest.mark.vcr
@pytest.mark.slow
async def test_groq_commentary_response_shape(demo_output: SanitizedOutput) -> None:
    """Groq commentary fallback parses into a Commentary model."""
    _skip_if_no_key_and_no_cassette(
        "GROQ_API_KEY", "test_groq_commentary_response_shape"
    )

    groq_key = os.environ.get("GROQ_API_KEY", "vcr-placeholder")
    gen = CommentaryGenerator(
        api_key="unused-gemini-key",
        groq_api_key=groq_key,
    )

    # Build the same prompt that generate() would build
    user_prompt = gen._build_user_prompt(demo_output, demo_number=1)
    raw_text = await gen._call_groq(user_prompt)

    # Parse through the same pipeline as generate()
    sentences = gen._split_sentences(raw_text.strip())
    emotion_map = gen._build_emotion_map(sentences)

    commentary = Commentary(
        team_name=demo_output.team_name,
        text=raw_text.strip(),
        sentences=sentences,
        emotion_map=emotion_map,
        generated_at=0.0,
    )

    assert isinstance(commentary, Commentary)
    assert commentary.team_name == "Team Phantom"
    assert len(commentary.text) > 20, "Commentary suspiciously short"
    assert len(commentary.sentences) >= 1
    assert len(commentary.emotion_map) == len(commentary.sentences)


@pytest.mark.vcr
@pytest.mark.slow
async def test_gemini_commentary_response_shape(
    demo_output: SanitizedOutput,
) -> None:
    """Non-streaming Gemini commentary parses into a Commentary model."""
    _skip_if_no_key_and_no_cassette(
        "GEMINI_API_KEY", "test_gemini_commentary_response_shape"
    )

    from google import genai
    from google.genai import types

    from src.commentary.prompts import PERSONA_PROMPT

    api_key = os.environ.get("GEMINI_API_KEY", "vcr-placeholder")
    client = genai.Client(api_key=api_key)

    gen = CommentaryGenerator(api_key=api_key)
    user_prompt = gen._build_user_prompt(demo_output, demo_number=1)
    demo_context = "Early in the event. Set the tone -- sharp, fair, and constructive."
    formatted_prompt = PERSONA_PROMPT.format(demo_context=demo_context)

    response = await client.aio.models.generate_content(
        model="gemini-2.5-flash",
        contents=user_prompt,
        config=types.GenerateContentConfig(
            system_instruction=formatted_prompt,
            max_output_tokens=500,
            temperature=0.8,
            thinking_config=types.ThinkingConfig(thinking_budget=0),
        ),
    )
    raw_text = response.text or ""
    assert raw_text.strip(), "Gemini returned empty commentary"

    sentences = gen._split_sentences(raw_text.strip())
    emotion_map = gen._build_emotion_map(sentences)

    commentary = Commentary(
        team_name=demo_output.team_name,
        text=raw_text.strip(),
        sentences=sentences,
        emotion_map=emotion_map,
        generated_at=0.0,
    )

    assert isinstance(commentary, Commentary)
    assert commentary.team_name == "Team Phantom"
    assert len(commentary.text) > 20, "Commentary suspiciously short"
    assert len(commentary.sentences) >= 1
    assert len(commentary.emotion_map) == len(commentary.sentences)
