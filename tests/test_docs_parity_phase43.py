"""Phase 43 tests — docs parity contract for CLI surface."""

from __future__ import annotations

import re
from pathlib import Path

from typer.testing import CliRunner

from pyclaw.cli.app import app

runner = CliRunner()
PROJECT_ROOT = Path(__file__).resolve().parents[1]
REFERENCE_DIR = PROJECT_ROOT / "reference"


def _read_doc(name: str) -> str:
    return (REFERENCE_DIR / name).read_text(encoding="utf-8")


def test_docs_mark_phase39_to_phase42_completed() -> None:
    progress = _read_doc("PROGRESS.md")
    for phase in ("39", "40", "41", "42"):
        assert re.search(rf"\| Phase {phase}: .+\| \*\*已完成\*\* \|", progress)


def test_docs_keep_pyclaw_as_only_cli_name() -> None:
    pyproject = (PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert 'pyclaw = "pyclaw.main:main"' in pyproject
    assert 'openclaw = "pyclaw.main:main"' not in pyproject

    progress = _read_doc("PROGRESS.md")
    assert "pyclaw" in progress and "CLI 主命令" in progress


def test_documented_cli_commands_exist() -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    for command in ("agent", "acp", "sessions", "logs", "system", "browser", "health", "status", "models", "channels"):
        assert command in result.stdout


def test_documented_cli_options_exist() -> None:
    acp_help = runner.invoke(app, ["acp", "--help"])
    assert acp_help.exit_code == 0
    for opt in ("--url", "--token-file", "--password-file", "--session-label", "--require-existing", "--reset-session"):
        assert opt in acp_help.stdout

    browser_help = runner.invoke(app, ["browser", "--help"])
    assert browser_help.exit_code == 0
    for opt in ("--url", "--token", "--password", "--timeout", "--browser-profile", "--json"):
        assert opt in browser_help.stdout

    status_help = runner.invoke(app, ["status", "--help"])
    assert status_help.exit_code == 0
    assert "--usage" in status_help.stdout
