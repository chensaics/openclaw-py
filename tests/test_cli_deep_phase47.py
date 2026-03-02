"""Phase 47 tests — sessions cleanup, security audit, system RPC alignment."""

from __future__ import annotations

import json
import os
from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from pyclaw.cli.app import app

runner = CliRunner()


# ---------------------------------------------------------------------------
# 47a: sessions cleanup
# ---------------------------------------------------------------------------

class TestSessionsCleanup:
    """Verify sessions cleanup command surface and behavior."""

    def test_cleanup_help(self) -> None:
        result = runner.invoke(app, ["sessions", "cleanup", "--help"])
        assert result.exit_code == 0
        for flag in ("--dry-run", "--enforce", "--active-key", "--json"):
            assert flag in result.stdout

    def test_cleanup_dry_run_no_stale(self, tmp_path: Path) -> None:
        agents_dir = tmp_path / "agents" / "main" / "sessions"
        agents_dir.mkdir(parents=True)
        # Create a valid session
        (agents_dir / "good.jsonl").write_text('{"msg": "hello"}\n')

        with patch("pyclaw.cli.commands.sessions_cmd.resolve_agents_dir", return_value=tmp_path / "agents"):
            result = runner.invoke(app, ["sessions", "cleanup", "--dry-run", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["staleLocks"] == 0
        assert data["emptyFiles"] == 0

    def test_cleanup_removes_locks(self, tmp_path: Path) -> None:
        agents_dir = tmp_path / "agents" / "main" / "sessions"
        agents_dir.mkdir(parents=True)
        (agents_dir / "stale.jsonl.lock").write_text("")
        (agents_dir / "empty.jsonl").write_text("")

        with patch("pyclaw.cli.commands.sessions_cmd.resolve_agents_dir", return_value=tmp_path / "agents"):
            result = runner.invoke(app, ["sessions", "cleanup", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["removed"] == 2

    def test_cleanup_enforce_removes_old(self, tmp_path: Path) -> None:
        agents_dir = tmp_path / "agents" / "main" / "sessions"
        agents_dir.mkdir(parents=True)
        old_file = agents_dir / "old.jsonl"
        old_file.write_text('{"msg": "old"}\n')
        # Make it very old
        import time
        old_time = time.time() - (31 * 86400)
        os.utime(old_file, (old_time, old_time))

        with patch("pyclaw.cli.commands.sessions_cmd.resolve_agents_dir", return_value=tmp_path / "agents"):
            result = runner.invoke(app, ["sessions", "cleanup", "--enforce", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["oldSessions"] == 1


# ---------------------------------------------------------------------------
# 47b: security audit
# ---------------------------------------------------------------------------

class TestSecurityAudit:
    """Verify security audit command surface and behavior."""

    def test_audit_help(self) -> None:
        result = runner.invoke(app, ["security", "audit", "--help"])
        assert result.exit_code == 0
        for flag in ("--deep", "--fix", "--json"):
            assert flag in result.stdout

    def test_audit_no_config_json(self, tmp_path: Path) -> None:
        with patch("pyclaw.cli.commands.security_cmd.resolve_config_path", return_value=tmp_path / "nope.json"):
            result = runner.invoke(app, ["security", "audit", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert "findings" in data
        assert data["errors"] == 0

    def test_audit_detects_bind_all(self, tmp_path: Path) -> None:
        config_file = tmp_path / "pyclaw.json"
        config_file.write_text(json.dumps({
            "gateway": {"bind": "0.0.0.0", "port": 18789},
        }))
        with patch("pyclaw.cli.commands.security_cmd.resolve_config_path", return_value=config_file):
            result = runner.invoke(app, ["security", "audit", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["warnings"] >= 1
        messages = [f["message"] for f in data["findings"]]
        assert any("0.0.0.0" in m for m in messages)


# ---------------------------------------------------------------------------
# 47c: system CLI RPC fallback
# ---------------------------------------------------------------------------

class TestSystemRPC:
    """Verify system commands try RPC first and fall back gracefully."""

    def test_system_event_help(self) -> None:
        result = runner.invoke(app, ["system", "event", "--help"])
        assert result.exit_code == 0
        assert "--text" in result.stdout
        assert "--mode" in result.stdout

    def test_system_event_local_fallback(self) -> None:
        with patch("pyclaw.cli.commands.system_cmd._try_rpc", return_value=None):
            result = runner.invoke(app, ["system", "event", "--text", "test", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["ok"] is True
        assert data["source"] == "local"

    def test_system_presence_local_fallback(self) -> None:
        with patch("pyclaw.cli.commands.system_cmd._try_rpc", return_value=None):
            result = runner.invoke(app, ["system", "presence", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert "entries" in data

    def test_heartbeat_enable_disable(self) -> None:
        result = runner.invoke(app, ["system", "heartbeat", "enable", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["enabled"] is True

        result = runner.invoke(app, ["system", "heartbeat", "disable", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["enabled"] is False


# ---------------------------------------------------------------------------
# 47d: root help regression
# ---------------------------------------------------------------------------

class TestRootHelpRegression:
    """Verify new commands show in root help."""

    def test_root_help_includes_security(self) -> None:
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "security" in result.stdout

    def test_sessions_help_includes_cleanup(self) -> None:
        result = runner.invoke(app, ["sessions", "--help"])
        assert result.exit_code == 0
        assert "cleanup" in result.stdout
