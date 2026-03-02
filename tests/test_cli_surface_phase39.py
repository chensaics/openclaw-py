"""Phase 39 CLI surface tests (pyclaw root and command bindings)."""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from typer.testing import CliRunner

from pyclaw.cli.app import app


runner = CliRunner()


def test_app_name_is_pyclaw() -> None:
    assert app.info.name == "pyclaw"


def test_root_help_includes_phase39_commands() -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    for command in ("acp", "sessions", "logs", "system", "browser", "health"):
        assert command in result.stdout


def test_agent_help_includes_v2_options() -> None:
    result = runner.invoke(app, ["agent", "--help"])
    assert result.exit_code == 0
    for opt in (
        "--message",
        "--to",
        "--session-id",
        "--thinking",
        "--deliver",
        "--channel",
        "--json",
        "--timeout",
        "--local",
    ):
        assert opt in result.stdout


def test_status_help_includes_usage_flag() -> None:
    result = runner.invoke(app, ["status", "--help"])
    assert result.exit_code == 0
    assert "--usage" in result.stdout


def test_channels_add_and_remove(tmp_path: Path) -> None:
    config_path = tmp_path / "pyclaw.json"
    env = dict(os.environ)
    env["PYCLAW_CONFIG_PATH"] = str(config_path)

    added = runner.invoke(
        app,
        ["channels", "add", "--channel", "telegram", "--account", "test", "--name", "Test TG"],
        env=env,
    )
    assert added.exit_code == 0
    assert "Added channel config" in added.stdout

    removed = runner.invoke(
        app,
        ["channels", "remove", "--channel", "telegram", "--account", "test"],
        env=env,
    )
    assert removed.exit_code == 0
    assert "Removed channel config" in removed.stdout


def test_pyproject_exports_pyclaw_script() -> None:
    project_root = Path(__file__).resolve().parents[1]
    pyproject = project_root / "pyproject.toml"
    content = pyproject.read_text(encoding="utf-8")
    assert "pyclaw = \"pyclaw.main:main\"" in content
    assert "openclaw = \"pyclaw.main:main\"" not in content


def test_sessions_root_flags() -> None:
    result = runner.invoke(app, ["sessions", "--help"])
    assert result.exit_code == 0
    for opt in ("--json", "--verbose", "--store", "--active", "--agent", "--all-agents"):
        assert opt in result.stdout


def test_logs_root_flags() -> None:
    result = runner.invoke(app, ["logs", "--help"])
    assert result.exit_code == 0
    for opt in ("--follow", "--limit", "--json", "--plain", "--local-time"):
        assert opt in result.stdout


def test_system_subcommands_exist() -> None:
    result = runner.invoke(app, ["system", "--help"])
    assert result.exit_code == 0
    for command in ("event", "heartbeat", "presence"):
        assert command in result.stdout


def test_browser_subcommands_exist() -> None:
    result = runner.invoke(app, ["browser", "--help"])
    assert result.exit_code == 0
    for command in (
        "status",
        "start",
        "stop",
        "tabs",
        "open",
        "navigate",
        "click",
        "type",
        "screenshot",
        "snapshot",
        "evaluate",
    ):
        assert command in result.stdout


def test_sessions_json_output(tmp_path: Path) -> None:
    env = dict(os.environ)
    env["PYCLAW_STATE_DIR"] = str(tmp_path)
    sessions_dir = tmp_path / "agents" / "main" / "sessions"
    sessions_dir.mkdir(parents=True, exist_ok=True)
    (sessions_dir / "demo.jsonl").write_text('{"type":"message"}\n', encoding="utf-8")

    result = runner.invoke(app, ["sessions", "--json"], env=env)
    assert result.exit_code == 0
    assert '"count": 1' in result.stdout


def test_browser_start_and_status_json(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    env = dict(os.environ)
    env["PYCLAW_STATE_DIR"] = str(tmp_path)

    def fake_browser_rpc_sync(
        method: str,
        params: dict[str, object],
        *,
        gateway_url: str,
        token: str | None,
        password: str | None,
        timeout_ms: int,
    ) -> dict[str, object]:
        if method == "browser.start":
            return {"started": True, "profile": params.get("profile", "pyclaw")}
        if method == "browser.status":
            return {
                "started": True,
                "profile": params.get("profile", "pyclaw"),
                "tabCount": 0,
                "activeUrl": "",
            }
        return {}

    monkeypatch.setattr("pyclaw.cli.commands.browser_cmd._browser_rpc_sync", fake_browser_rpc_sync)

    started = runner.invoke(app, ["browser", "--json", "start"], env=env)
    assert started.exit_code == 0
    assert '"started": true' in started.stdout

    status = runner.invoke(app, ["browser", "--json", "status"], env=env)
    assert status.exit_code == 0
    assert '"started": true' in status.stdout

