from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from pyclaw.cli.app import app

runner = CliRunner()


def test_ops_release_gate_generates_sha_report(tmp_path: Path, monkeypatch) -> None:
    dist = tmp_path / "dist"
    dist.mkdir(parents=True, exist_ok=True)
    (dist / "linux-1.2.3-build42.tar.gz").write_text("artifact-linux", encoding="utf-8")
    (dist / "web-1.2.3-build42.zip").write_text("artifact-web", encoding="utf-8")

    monkeypatch.setattr("pyclaw.cli.commands.ops_cmd._is_worktree_clean", lambda _ws: (True, "clean"))
    monkeypatch.setattr("pyclaw.cli.commands.ops_cmd._read_project_version", lambda _path: "1.2.3")

    report_path = tmp_path / "gate-report.json"
    result = runner.invoke(
        app,
        [
            "ops",
            "release-gate",
            "--artifacts-dir",
            str(dist),
            "--version",
            "1.2.3",
            "--release-notes",
            "notes",
            "--rollback-notes",
            "rollback",
            "--write-report",
            str(report_path),
            "--json",
        ],
    )
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["milestone"] == "M3"
    assert payload["decision"] == "go"
    assert (dist / "SHA256SUMS.txt").exists()
    assert report_path.exists()


def test_ops_m2_baseline_outputs_structured_json(monkeypatch) -> None:
    class _Status:
        gateway_running = True

    monkeypatch.setattr("pyclaw.cli.commands.ops_cmd.scan_status", lambda **_kwargs: _Status())

    def _fake_run_skill(name: str, **_kwargs):
        if name == "repo-review":
            return {"skill": "repo-review", "status": "ok", "findings": []}
        return {"skill": "docs-sync", "status": "needs_attention", "blocking_items": ["x"]}

    monkeypatch.setattr("pyclaw.cli.commands.ops_cmd.run_skill", _fake_run_skill)

    result = runner.invoke(app, ["ops", "m2-baseline", "--json"])
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["milestone"] == "M2"
    assert payload["decision"] == "pass"
    assert payload["failed_required"] == []


def test_ops_m2_baseline_handles_skill_exceptions(monkeypatch) -> None:
    class _Status:
        gateway_running = True

    monkeypatch.setattr("pyclaw.cli.commands.ops_cmd.scan_status", lambda **_kwargs: _Status())
    monkeypatch.setattr(
        "pyclaw.cli.commands.ops_cmd.run_skill", lambda *_args, **_kwargs: (_ for _ in ()).throw(KeyError("missing"))
    )

    result = runner.invoke(app, ["ops", "m2-baseline", "--json"])
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["decision"] == "fail"
    assert "skills_run_structured_result" in payload["failed_required"]


def test_ops_m4_snapshot_appends_tracker(tmp_path: Path) -> None:
    tracker = tmp_path / "M4.md"
    tracker.write_text("# tracker\n", encoding="utf-8")
    result = runner.invoke(
        app,
        [
            "ops",
            "m4-snapshot",
            "--window-start",
            "2026-03-08",
            "--window-end",
            "2026-03-15",
            "--summary",
            "无新增P0差距",
            "--tracker-path",
            str(tracker),
            "--json",
        ],
    )
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["status"] == "recorded"
    text = tracker.read_text(encoding="utf-8")
    assert "Snapshot" in text
    assert "无新增P0差距" in text


def test_ops_release_gate_enforces_full_artifact_name(tmp_path: Path, monkeypatch) -> None:
    dist = tmp_path / "dist"
    dist.mkdir(parents=True, exist_ok=True)
    (dist / "linuxx-1.2.3-build42.tar.gz").write_text("bad-artifact", encoding="utf-8")
    monkeypatch.setattr("pyclaw.cli.commands.ops_cmd._is_worktree_clean", lambda _ws: (True, "clean"))
    monkeypatch.setattr("pyclaw.cli.commands.ops_cmd._read_project_version", lambda _path: "1.2.3")
    result = runner.invoke(
        app,
        [
            "ops",
            "release-gate",
            "--artifacts-dir",
            str(dist),
            "--version",
            "1.2.3",
            "--release-notes",
            "notes",
            "--rollback-notes",
            "rollback",
            "--json",
        ],
    )
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["decision"] == "hold"
    assert "artifact_naming_rule" in payload["failed_required"]


def test_ops_m4_snapshot_rejects_invalid_window(tmp_path: Path) -> None:
    tracker = tmp_path / "M4.md"
    tracker.write_text("# tracker\n", encoding="utf-8")
    result = runner.invoke(
        app,
        [
            "ops",
            "m4-snapshot",
            "--window-start",
            "2026-03-20",
            "--window-end",
            "2026-03-15",
            "--summary",
            "bad window",
            "--tracker-path",
            str(tracker),
        ],
    )
    assert result.exit_code != 0
