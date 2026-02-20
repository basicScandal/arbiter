"""Tests for the unified track configuration in shared/tracks.json."""
from __future__ import annotations

import json
from pathlib import Path


_SHARED_TRACKS_PATH = Path(__file__).parent / "../shared/tracks.json"


def test_shared_tracks_json_exists() -> None:
    """shared/tracks.json must exist at the project root."""
    assert _SHARED_TRACKS_PATH.exists(), f"Expected {_SHARED_TRACKS_PATH} to exist"


def test_shared_tracks_json_is_valid_json() -> None:
    """shared/tracks.json must be parseable as valid JSON."""
    data = json.loads(_SHARED_TRACKS_PATH.read_text())
    assert isinstance(data, dict)


def test_tracks_has_exactly_four_entries() -> None:
    """The 'tracks' list must contain exactly 4 entries."""
    from src.config.tracks import TRACKS

    assert len(TRACKS) == 4, f"Expected 4 tracks, got {len(TRACKS)}: {TRACKS}"


def test_tracks_is_list_of_strings() -> None:
    """Every entry in TRACKS must be a non-empty string."""
    from src.config.tracks import TRACKS

    for track in TRACKS:
        assert isinstance(track, str) and track, f"Invalid track entry: {track!r}"


def test_valid_tracks_is_set_matching_list() -> None:
    """VALID_TRACKS must be a set containing the same elements as TRACKS."""
    from src.config.tracks import TRACKS, VALID_TRACKS

    assert isinstance(VALID_TRACKS, set)
    assert VALID_TRACKS == set(TRACKS)


def test_default_track_is_in_valid_tracks() -> None:
    """DEFAULT_TRACK must be one of the canonical tracks."""
    from src.config.tracks import DEFAULT_TRACK, VALID_TRACKS

    assert DEFAULT_TRACK in VALID_TRACKS, (
        f"DEFAULT_TRACK {DEFAULT_TRACK!r} is not in VALID_TRACKS {VALID_TRACKS}"
    )


def test_expected_track_names_present() -> None:
    """The four canonical NEBULA:FOG track names must all be present."""
    from src.config.tracks import VALID_TRACKS

    expected = {"SHADOW::VECTOR", "SENTINEL::MESH", "ZERO::PROOF", "ROGUE::AGENT"}
    assert expected == VALID_TRACKS, (
        f"Track mismatch. Expected {expected}, got {VALID_TRACKS}"
    )


def test_default_track_is_rogue_agent() -> None:
    """DEFAULT_TRACK must be ROGUE::AGENT per current config."""
    from src.config.tracks import DEFAULT_TRACK

    assert DEFAULT_TRACK == "ROGUE::AGENT"
