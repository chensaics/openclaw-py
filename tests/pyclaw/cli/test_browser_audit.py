from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from pyclaw.cli.app import app

runner = CliRunner()


def test_browser_audit_lifecycle_json(monkeypatch, tmp_path: Path) -> None:
    state_dir = tmp_path / "state"
    profiles_dir = state_dir / "browser-profiles"
    profiles_dir.mkdir(parents=True, exist_ok=True)
    (profiles_dir / "demo.json").write_text('{"ok":true}', encoding="utf-8")

    monkeypatch.setattr("pyclaw.config.paths.resolve_state_dir", lambda: state_dir)
    result = runner.invoke(app, ["browser", "--json", "audit-lifecycle"])
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["count"] == 1
    assert payload["profiles"][0]["profile"] == "demo"
