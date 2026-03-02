"""Tests for replay pipeline result caching."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch


class TestHasCachedResults:
    """Tests for ReplayPipeline._has_cached_results."""

    def test_returns_true_when_both_files_exist(self, tmp_path: Path):
        """Should return True when score and memory files both exist."""
        from src.replay.pipeline import ReplayPipeline

        scores_dir = tmp_path / "scores"
        obs_dir = tmp_path / "observations"
        scores_dir.mkdir()
        obs_dir.mkdir()

        # Create files matching sanitized team name
        (scores_dir / "cyber_falcons.json").write_text("{}")
        (obs_dir / "cyber_falcons.json").write_text("{}")

        with (
            patch("src.replay.pipeline.SCORES_DIR", scores_dir),
            patch("src.replay.pipeline.OBSERVATIONS_DIR", obs_dir),
            patch("src.replay.pipeline.load_dotenv"),
            patch("src.replay.pipeline.VideoAnalyzer"),
            patch.dict("os.environ", {"GEMINI_API_KEY": "test-key", "ANTHROPIC_API_KEY": "test-key"}),
        ):
            pipeline = ReplayPipeline()
            assert pipeline._has_cached_results("Cyber Falcons") is True

    def test_returns_false_when_score_missing(self, tmp_path: Path):
        """Should return False when score file is missing."""
        from src.replay.pipeline import ReplayPipeline

        scores_dir = tmp_path / "scores"
        obs_dir = tmp_path / "observations"
        scores_dir.mkdir()
        obs_dir.mkdir()

        # Only memory file exists
        (obs_dir / "cyber_falcons.json").write_text("{}")

        with (
            patch("src.replay.pipeline.SCORES_DIR", scores_dir),
            patch("src.replay.pipeline.OBSERVATIONS_DIR", obs_dir),
            patch("src.replay.pipeline.load_dotenv"),
            patch("src.replay.pipeline.VideoAnalyzer"),
            patch.dict("os.environ", {"GEMINI_API_KEY": "test-key", "ANTHROPIC_API_KEY": "test-key"}),
        ):
            pipeline = ReplayPipeline()
            assert pipeline._has_cached_results("Cyber Falcons") is False

    def test_returns_false_when_memory_missing(self, tmp_path: Path):
        """Should return False when memory file is missing."""
        from src.replay.pipeline import ReplayPipeline

        scores_dir = tmp_path / "scores"
        obs_dir = tmp_path / "observations"
        scores_dir.mkdir()
        obs_dir.mkdir()

        # Only score file exists
        (scores_dir / "cyber_falcons.json").write_text("{}")

        with (
            patch("src.replay.pipeline.SCORES_DIR", scores_dir),
            patch("src.replay.pipeline.OBSERVATIONS_DIR", obs_dir),
            patch("src.replay.pipeline.load_dotenv"),
            patch("src.replay.pipeline.VideoAnalyzer"),
            patch.dict("os.environ", {"GEMINI_API_KEY": "test-key", "ANTHROPIC_API_KEY": "test-key"}),
        ):
            pipeline = ReplayPipeline()
            assert pipeline._has_cached_results("Cyber Falcons") is False

    def test_returns_false_when_neither_exists(self, tmp_path: Path):
        """Should return False when no files exist."""
        from src.replay.pipeline import ReplayPipeline

        scores_dir = tmp_path / "scores"
        obs_dir = tmp_path / "observations"
        scores_dir.mkdir()
        obs_dir.mkdir()

        with (
            patch("src.replay.pipeline.SCORES_DIR", scores_dir),
            patch("src.replay.pipeline.OBSERVATIONS_DIR", obs_dir),
            patch("src.replay.pipeline.load_dotenv"),
            patch("src.replay.pipeline.VideoAnalyzer"),
            patch.dict("os.environ", {"GEMINI_API_KEY": "test-key", "ANTHROPIC_API_KEY": "test-key"}),
        ):
            pipeline = ReplayPipeline()
            assert pipeline._has_cached_results("Cyber Falcons") is False

    def test_sanitizes_team_name_correctly(self, tmp_path: Path):
        """Should sanitize team names the same way as ScoreStore."""
        from src.replay.pipeline import ReplayPipeline

        scores_dir = tmp_path / "scores"
        obs_dir = tmp_path / "observations"
        scores_dir.mkdir()
        obs_dir.mkdir()

        # Team name with special characters
        (scores_dir / "team_alpha_2.json").write_text("{}")
        (obs_dir / "team_alpha_2.json").write_text("{}")

        with (
            patch("src.replay.pipeline.SCORES_DIR", scores_dir),
            patch("src.replay.pipeline.OBSERVATIONS_DIR", obs_dir),
            patch("src.replay.pipeline.load_dotenv"),
            patch("src.replay.pipeline.VideoAnalyzer"),
            patch.dict("os.environ", {"GEMINI_API_KEY": "test-key", "ANTHROPIC_API_KEY": "test-key"}),
        ):
            pipeline = ReplayPipeline()
            assert pipeline._has_cached_results("Team Alpha #2") is True
