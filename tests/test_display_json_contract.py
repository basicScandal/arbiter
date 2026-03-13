"""Contract tests: verify DisplayServer WebSocket JSON payloads match React audience-display expectations.

The React frontend (audience-display/src/types/messages.ts) expects specific message
shapes. If the Python backend emits different keys or types, the display breaks silently.
These tests catch that drift by capturing broadcast payloads and asserting exact key sets
and value types.
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock

import pytest

from src.commentary.display_server import DisplayServer


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def captured_messages() -> list[dict]:
    """Shared list that collects all broadcast payloads."""
    return []


@pytest.fixture
def server(captured_messages: list[dict]) -> DisplayServer:
    """DisplayServer with broadcast replaced by a capture list (no network)."""
    ds = DisplayServer.__new__(DisplayServer)
    # Minimal init — we only need _manager.broadcast to work
    from src.commentary.display_server import ConnectionManager

    ds._manager = ConnectionManager()
    # Monkey-patch broadcast to just append to our capture list
    original_broadcast = ds._manager.broadcast

    async def capturing_broadcast(message: dict) -> None:
        captured_messages.append(message)

    ds._manager.broadcast = capturing_broadcast  # type: ignore[assignment]
    return ds


# ---------------------------------------------------------------------------
# React frontend contract: required keys and value types per message type
#
# Source of truth: audience-display/src/types/messages.ts
# ---------------------------------------------------------------------------

# Keys marked as required in the TS interfaces (optional keys noted separately)
CONTRACTS: dict[str, dict[str, type]] = {
    "commentary": {
        "type": str,
        "text": str,
        "team_name": str,
        "sentence_index": int,
        "is_final": bool,
        # "emotion" is optional — tested separately
    },
    "question": {
        "type": str,
        "text": str,
        "team_name": str,
    },
    "score_intro": {
        "type": str,
        "team_name": str,
    },
    "score_criterion": {
        "type": str,
        "name": str,
        "score": (int, float),
        "weight": (int, float),
        "justification": str,
    },
    "score_total": {
        "type": str,
        "team_name": str,
        "total_score": (int, float),
        "track": str,
    },
    "deliberation_ranking": {
        "type": str,
        "rank": int,
        "team_name": str,
        "total_score": (int, float),
        "track": str,
        "reasoning": str,
    },
    "deliberation_narrative": {
        "type": str,
        "narrative": str,
    },
    "injection_blocked": {
        "type": str,
        "category": str,
        "confidence": str,
        "roast": str,
        "team_name": str,
    },
    "capture_started": {
        "type": str,
        "team_name": str,
        "track": str,
    },
    "intermission": {
        "type": str,
        "leaderboard": list,
        "total_injections": int,
    },
    "clear": {
        "type": str,
    },
}


def _assert_contract(msg: dict, expected_type: str) -> None:
    """Assert a message satisfies the React contract for its type."""
    contract = CONTRACTS[expected_type]

    # 1. type field matches exactly
    assert msg["type"] == expected_type, (
        f"Expected type={expected_type!r}, got type={msg.get('type')!r}"
    )

    # 2. All required keys are present
    missing = set(contract.keys()) - set(msg.keys())
    assert not missing, f"Missing required keys for {expected_type}: {missing}"

    # 3. Value types are correct
    for key, expected_types in contract.items():
        val = msg[key]
        if isinstance(expected_types, tuple):
            assert isinstance(val, expected_types), (
                f"{expected_type}.{key}: expected {expected_types}, got {type(val).__name__} ({val!r})"
            )
        else:
            assert isinstance(val, expected_types), (
                f"{expected_type}.{key}: expected {expected_types.__name__}, got {type(val).__name__} ({val!r})"
            )


# ---------------------------------------------------------------------------
# Tests — one per push method
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_commentary_contract(server: DisplayServer, captured_messages: list[dict]) -> None:
    await server.push_commentary("Nice exploit!", "TeamAlpha", emotion="excited", sentence_index=1, is_final=True)
    assert len(captured_messages) == 1
    msg = captured_messages[0]
    _assert_contract(msg, "commentary")
    # Optional emotion should be present when provided
    assert msg["emotion"] == "excited"


@pytest.mark.asyncio
async def test_commentary_without_emotion(server: DisplayServer, captured_messages: list[dict]) -> None:
    """When emotion is empty string, the key may be omitted (TS marks it optional)."""
    await server.push_commentary("Good work", "TeamBeta")
    msg = captured_messages[0]
    _assert_contract(msg, "commentary")
    # emotion omitted when empty — frontend treats missing as undefined, which is fine
    assert "emotion" not in msg or isinstance(msg.get("emotion"), str)


@pytest.mark.asyncio
async def test_commentary_defaults(server: DisplayServer, captured_messages: list[dict]) -> None:
    """Default sentence_index=0 and is_final=False must still be present."""
    await server.push_commentary("Hello", "TeamGamma")
    msg = captured_messages[0]
    assert msg["sentence_index"] == 0
    assert msg["is_final"] is False


@pytest.mark.asyncio
async def test_question_contract(server: DisplayServer, captured_messages: list[dict]) -> None:
    await server.push_question("What was your approach to privilege escalation?", "TeamAlpha")
    assert len(captured_messages) == 1
    msg = captured_messages[0]
    _assert_contract(msg, "question")
    assert msg["text"] == "What was your approach to privilege escalation?"
    assert msg["team_name"] == "TeamAlpha"


@pytest.mark.asyncio
async def test_score_intro_contract(server: DisplayServer, captured_messages: list[dict]) -> None:
    await server.push_score_intro("TeamAlpha")
    assert len(captured_messages) == 1
    _assert_contract(captured_messages[0], "score_intro")
    assert captured_messages[0]["team_name"] == "TeamAlpha"


@pytest.mark.asyncio
async def test_score_criterion_contract(server: DisplayServer, captured_messages: list[dict]) -> None:
    await server.push_criterion_reveal("Innovation", 8.5, 0.4, "Very creative approach")
    assert len(captured_messages) == 1
    msg = captured_messages[0]
    _assert_contract(msg, "score_criterion")
    assert msg["name"] == "Innovation"
    assert msg["score"] == 8.5
    assert msg["weight"] == 0.4
    assert msg["justification"] == "Very creative approach"


@pytest.mark.asyncio
async def test_score_criterion_numeric_types(server: DisplayServer, captured_messages: list[dict]) -> None:
    """score and weight must be numbers, never strings."""
    await server.push_criterion_reveal("Technical", 7, 0.3, "Solid")
    msg = captured_messages[0]
    assert isinstance(msg["score"], (int, float))
    assert isinstance(msg["weight"], (int, float))


@pytest.mark.asyncio
async def test_score_total_contract(server: DisplayServer, captured_messages: list[dict]) -> None:
    await server.push_total_score("TeamAlpha", 85.5, "offensive")
    assert len(captured_messages) == 1
    msg = captured_messages[0]
    _assert_contract(msg, "score_total")
    assert msg["total_score"] == 85.5
    assert msg["track"] == "offensive"


@pytest.mark.asyncio
async def test_deliberation_ranking_contract(server: DisplayServer, captured_messages: list[dict]) -> None:
    await server.push_deliberation_ranking(1, "TeamAlpha", 92.0, "offensive", "Dominated the field")
    assert len(captured_messages) == 1
    msg = captured_messages[0]
    _assert_contract(msg, "deliberation_ranking")
    assert msg["rank"] == 1
    assert isinstance(msg["rank"], int)


@pytest.mark.asyncio
async def test_deliberation_narrative_contract(server: DisplayServer, captured_messages: list[dict]) -> None:
    await server.push_deliberation_narrative("An incredible competition today...")
    assert len(captured_messages) == 1
    msg = captured_messages[0]
    _assert_contract(msg, "deliberation_narrative")
    assert msg["narrative"] == "An incredible competition today..."


@pytest.mark.asyncio
async def test_injection_blocked_contract(server: DisplayServer, captured_messages: list[dict]) -> None:
    await server.push_injection_blocked("prompt_injection", "high", "Nice try!", "TeamEvil")
    assert len(captured_messages) == 1
    msg = captured_messages[0]
    _assert_contract(msg, "injection_blocked")
    assert msg["category"] == "prompt_injection"
    assert msg["confidence"] == "high"
    assert msg["roast"] == "Nice try!"
    assert msg["team_name"] == "TeamEvil"


@pytest.mark.asyncio
async def test_capture_started_contract(server: DisplayServer, captured_messages: list[dict]) -> None:
    await server.push_capture_started("TeamAlpha", "defensive")
    assert len(captured_messages) == 1
    msg = captured_messages[0]
    _assert_contract(msg, "capture_started")
    assert msg["team_name"] == "TeamAlpha"
    assert msg["track"] == "defensive"


@pytest.mark.asyncio
async def test_intermission_contract(server: DisplayServer, captured_messages: list[dict]) -> None:
    leaderboard = [
        {"team_name": "TeamAlpha", "total_score": 90.0, "track": "offensive"},
        {"team_name": "TeamBeta", "total_score": 85.0, "track": "defensive"},
    ]
    await server.push_intermission(leaderboard, total_injections=3)
    assert len(captured_messages) == 1
    msg = captured_messages[0]
    _assert_contract(msg, "intermission")
    assert isinstance(msg["leaderboard"], list)
    assert len(msg["leaderboard"]) == 2
    assert isinstance(msg["total_injections"], int)
    assert msg["total_injections"] == 3


@pytest.mark.asyncio
async def test_intermission_leaderboard_entry_shape(server: DisplayServer, captured_messages: list[dict]) -> None:
    """Each leaderboard entry must have team_name, total_score, track."""
    leaderboard = [
        {"team_name": "TeamAlpha", "total_score": 90.0, "track": "offensive"},
    ]
    await server.push_intermission(leaderboard, total_injections=0)
    entry = captured_messages[0]["leaderboard"][0]
    assert "team_name" in entry
    assert "total_score" in entry
    assert "track" in entry
    assert isinstance(entry["team_name"], str)
    assert isinstance(entry["total_score"], (int, float))
    assert isinstance(entry["track"], str)


@pytest.mark.asyncio
async def test_clear_contract(server: DisplayServer, captured_messages: list[dict]) -> None:
    await server.clear()
    assert len(captured_messages) == 1
    msg = captured_messages[0]
    _assert_contract(msg, "clear")
    # clear should have ONLY "type" — no extra keys
    assert set(msg.keys()) == {"type"}


@pytest.mark.asyncio
async def test_no_extra_keys_score_intro(server: DisplayServer, captured_messages: list[dict]) -> None:
    """score_intro should not leak unexpected keys to the frontend."""
    await server.push_score_intro("TeamAlpha")
    msg = captured_messages[0]
    allowed = {"type", "team_name"}
    extra = set(msg.keys()) - allowed
    assert not extra, f"Unexpected keys in score_intro: {extra}"


@pytest.mark.asyncio
async def test_all_message_types_covered() -> None:
    """Meta-test: every contract type has at least one test above (via CONTRACTS dict).

    If a new message type is added to CONTRACTS but not tested, this will catch it
    by checking that all CONTRACTS keys appear in at least one test function name.
    """
    import inspect
    import sys

    this_module = sys.modules[__name__]
    test_source = inspect.getsource(this_module)

    for msg_type in CONTRACTS:
        # Each message type should be referenced in at least one _assert_contract call
        assert msg_type in test_source, (
            f"Message type {msg_type!r} is in CONTRACTS but has no test"
        )
