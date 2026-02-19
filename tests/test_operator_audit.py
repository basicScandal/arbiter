"""Tests for the operator command audit log."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

from src.operator.audit import log_command


class TestLogCommand:
    def test_creates_audit_file(self, tmp_path: Path):
        audit_path = tmp_path / "audit.jsonl"
        with patch("src.operator.audit._AUDIT_PATH", audit_path):
            log_command("start", success=True, team_name="TeamA")

        assert audit_path.exists()

    def test_writes_valid_jsonl(self, tmp_path: Path):
        audit_path = tmp_path / "audit.jsonl"
        with patch("src.operator.audit._AUDIT_PATH", audit_path):
            log_command("start", success=True, team_name="TeamA")

        line = audit_path.read_text().strip()
        entry = json.loads(line)
        assert entry["action"] == "start"
        assert entry["success"] is True
        assert entry["team_name"] == "TeamA"

    def test_includes_timestamp(self, tmp_path: Path):
        audit_path = tmp_path / "audit.jsonl"
        with patch("src.operator.audit._AUDIT_PATH", audit_path):
            log_command("stop", success=True)

        entry = json.loads(audit_path.read_text().strip())
        assert "timestamp" in entry
        assert isinstance(entry["timestamp"], float)

    def test_includes_state_transitions(self, tmp_path: Path):
        audit_path = tmp_path / "audit.jsonl"
        with patch("src.operator.audit._AUDIT_PATH", audit_path):
            log_command(
                "start", success=True, team_name="T",
                state_before="idle", state_after="running",
            )

        entry = json.loads(audit_path.read_text().strip())
        assert entry["state_before"] == "idle"
        assert entry["state_after"] == "running"

    def test_includes_track(self, tmp_path: Path):
        audit_path = tmp_path / "audit.jsonl"
        with patch("src.operator.audit._AUDIT_PATH", audit_path):
            log_command("start", success=True, team_name="T", track="ROGUE::AGENT")

        entry = json.loads(audit_path.read_text().strip())
        assert entry["track"] == "ROGUE::AGENT"

    def test_includes_detail_when_provided(self, tmp_path: Path):
        audit_path = tmp_path / "audit.jsonl"
        with patch("src.operator.audit._AUDIT_PATH", audit_path):
            log_command("stop", success=True, detail="duration=120.5s")

        entry = json.loads(audit_path.read_text().strip())
        assert entry["detail"] == "duration=120.5s"

    def test_omits_detail_when_empty(self, tmp_path: Path):
        audit_path = tmp_path / "audit.jsonl"
        with patch("src.operator.audit._AUDIT_PATH", audit_path):
            log_command("reset", success=True)

        entry = json.loads(audit_path.read_text().strip())
        assert "detail" not in entry

    def test_appends_multiple_entries(self, tmp_path: Path):
        audit_path = tmp_path / "audit.jsonl"
        with patch("src.operator.audit._AUDIT_PATH", audit_path):
            log_command("start", success=True, team_name="A")
            log_command("stop", success=True, team_name="A")
            log_command("reset", success=True)

        lines = audit_path.read_text().strip().split("\n")
        assert len(lines) == 3
        assert json.loads(lines[0])["action"] == "start"
        assert json.loads(lines[1])["action"] == "stop"
        assert json.loads(lines[2])["action"] == "reset"

    def test_logs_failed_command(self, tmp_path: Path):
        audit_path = tmp_path / "audit.jsonl"
        with patch("src.operator.audit._AUDIT_PATH", audit_path):
            log_command("start", success=False, detail="transition not allowed")

        entry = json.loads(audit_path.read_text().strip())
        assert entry["success"] is False
        assert entry["detail"] == "transition not allowed"

    def test_creates_parent_directory(self, tmp_path: Path):
        audit_path = tmp_path / "nested" / "dir" / "audit.jsonl"
        with patch("src.operator.audit._AUDIT_PATH", audit_path):
            log_command("test", success=True)

        assert audit_path.exists()

    def test_handles_write_error_gracefully(self, tmp_path: Path):
        """If the log file can't be written, log_command should not raise."""
        audit_path = tmp_path / "readonly" / "audit.jsonl"
        (tmp_path / "readonly").mkdir()
        (tmp_path / "readonly").chmod(0o444)

        try:
            with patch("src.operator.audit._AUDIT_PATH", audit_path):
                # Should not raise
                log_command("test", success=True)
        finally:
            (tmp_path / "readonly").chmod(0o755)
