from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from pyclaw.agents.skills.runner import parse_payload, run_skill
from pyclaw.cli.app import app

runner = CliRunner()


def test_parse_payload_rejects_non_object() -> None:
    try:
        parse_payload('["bad"]')
    except ValueError as exc:
        assert "JSON object" in str(exc)
    else:
        raise AssertionError("Expected ValueError for non-object payload")


def test_run_release_helper_returns_structured_result(monkeypatch) -> None:
    monkeypatch.setattr(
        "pyclaw.agents.skills.runner._run_git",
        lambda _workspace, args: "master" if "--abbrev-ref" in args else "",
    )
    result = run_skill(
        "release-helper",
        payload={
            "tag": "v0.1.5",
            "release_notes": "test notes",
            "rollback_notes": "rollback steps",
        },
    )
    assert result["skill"] == "release-helper"
    assert "clean_worktree" in result
    assert result["requested_tag"] == "v0.1.5"
    assert result["status"] == "ok"


def test_run_release_helper_reports_blockers(monkeypatch) -> None:
    def fake_run_git(_workspace, args):
        if "--abbrev-ref" in args:
            return "master"
        if args == ["status", "--porcelain"]:
            return " M src/pyclaw/gateway/methods/extended.py"
        return ""

    monkeypatch.setattr("pyclaw.agents.skills.runner._run_git", fake_run_git)
    result = run_skill("release-helper", payload={"tag": "v0.1.5"})
    assert result["status"] == "needs_attention"
    assert "working_tree_clean" in result["blocking_items"]
    assert "release_notes_present" in result["blocking_items"]
    assert "rollback_notes_present" in result["blocking_items"]


def test_run_docs_sync_reports_drift_summary() -> None:
    workspace = Path(__file__).resolve().parents[3]
    result = run_skill(
        "docs-sync",
        workspace_dir=workspace,
        payload={"workspace_dir": str(workspace), "scope": "docs/configuration.md"},
    )
    assert result["skill"] == "docs-sync"
    assert "drift_summary" in result
    assert "drifts" in result


def test_run_docs_sync_missing_scope_returns_blocker(tmp_path: Path) -> None:
    result = run_skill(
        "docs-sync",
        workspace_dir=tmp_path,
        payload={"workspace_dir": str(tmp_path), "scope": "docs/not-exists.md"},
    )
    assert result["status"] == "needs_attention"
    assert result["blocking_items"]


def test_run_node_toolchain_reports_missing_node(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr("pyclaw.agents.skills.runner._run_command", lambda *_args, **_kwargs: (False, ""))
    result = run_skill("node-toolchain", workspace_dir=tmp_path, payload={"workspace_dir": str(tmp_path)})
    assert result["status"] == "needs_attention"
    assert "node_missing" in result["blocking_items"]


def test_run_node_toolchain_inherits_workspace_dir(monkeypatch, tmp_path: Path) -> None:
    (tmp_path / "package-lock.json").write_text("", encoding="utf-8")
    monkeypatch.setattr("pyclaw.agents.skills.runner._run_command", lambda *_args, **_kwargs: (True, "ok"))
    result = run_skill("node-toolchain", workspace_dir=tmp_path, payload={})
    assert result["workspace"] == str(tmp_path)
    assert "package-lock.json" in result["package_manager"]["lockfiles"]


def test_run_mcp_admin_detects_invalid_server() -> None:
    config = {
        "tools": {
            "mcpServers": {
                "bad-http": {"url": "ftp://bad.example.com/mcp"},
                "bad-stdio": {"command": "not-a-real-command"},
            }
        }
    }
    result = run_skill("mcp-admin", config=config)
    assert result["status"] == "needs_attention"
    assert set(result["failed_servers"]) == {"bad-http", "bad-stdio"}


def test_run_mcp_admin_empty_config_is_ok() -> None:
    result = run_skill("mcp-admin", config={})
    assert result["status"] == "ok"
    assert result["configured_servers"] == []


def test_cli_skills_run_json_output() -> None:
    result = runner.invoke(
        app,
        ["skills", "run", "repo-review", "--payload", '{"findings":[{"severity":"high"}]}', "--json"],
    )
    assert result.exit_code == 0
    body = json.loads(result.stdout)
    assert body["skill"] == "repo-review"
    assert isinstance(body["findings"], list)


def test_cli_skills_run_invalid_payload() -> None:
    result = runner.invoke(app, ["skills", "run", "repo-review", "--payload", "[]", "--json"])
    assert result.exit_code == 1


def test_run_skill_blocks_missing_runtime_deps(tmp_path: Path, monkeypatch) -> None:
    skill_dir = tmp_path / ".skills" / "guarded"
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "SKILL.md").write_text(
        "---\nskill_key: guarded\nruntime: node-wrapper\ndeps: cmd:__missing_bin__\n---\nblocked\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "pyclaw.agents.skills.loader.shutil.which",
        lambda cmd: None if cmd == "__missing_bin__" else "/usr/bin/ok",
    )

    result = run_skill("guarded", workspace_dir=tmp_path)
    assert result["status"] == "needs_attention"
    assert "missing_dep:cmd:__missing_bin__" in result["blocking_items"]


def test_run_skill_can_bypass_contract_for_diagnostics(tmp_path: Path, monkeypatch) -> None:
    skill_dir = tmp_path / ".skills" / "guarded"
    runtime_dir = skill_dir / "scripts"
    runtime_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "SKILL.md").write_text(
        "---\nskill_key: guarded\nruntime: node-wrapper\ndeps: cmd:__missing_bin__\n---\nbypass\n",
        encoding="utf-8",
    )
    (runtime_dir / "runtime.py").write_text(
        "from __future__ import annotations\n"
        "from typing import Any\n"
        "\n"
        "def run(payload: dict[str, Any] | None = None, *, skill_key: str = 'guarded') -> dict[str, Any]:\n"
        "    return {'skill': skill_key, 'status': 'ok', 'summary': 'ran'}\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "pyclaw.agents.skills.loader.shutil.which",
        lambda cmd: None if cmd == "__missing_bin__" else "/usr/bin/ok",
    )

    result = run_skill("guarded", workspace_dir=tmp_path, payload={"ignore_runtime_contract": True})
    assert result["status"] == "ok"
    assert result["skill"] == "guarded"


def test_run_skill_string_false_does_not_bypass_contract(tmp_path: Path, monkeypatch) -> None:
    skill_dir = tmp_path / ".skills" / "guarded"
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "SKILL.md").write_text(
        "---\nskill_key: guarded\nruntime: node-wrapper\ndeps: cmd:__missing_bin__\n---\nblocked\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "pyclaw.agents.skills.loader.shutil.which",
        lambda cmd: None if cmd == "__missing_bin__" else "/usr/bin/ok",
    )

    result = run_skill("guarded", workspace_dir=tmp_path, payload={"ignore_runtime_contract": "false"})
    assert result["status"] == "needs_attention"
    assert "missing_dep:cmd:__missing_bin__" in result["blocking_items"]


def test_run_skill_blocks_non_user_invocable_skill(tmp_path: Path) -> None:
    skill_dir = tmp_path / ".skills" / "internal-only"
    runtime_dir = skill_dir / "scripts"
    runtime_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "SKILL.md").write_text(
        "---\nskill_key: internal-only\nruntime: python-native\nuserInvocable: false\n---\ninternal\n",
        encoding="utf-8",
    )
    (runtime_dir / "runtime.py").write_text(
        "from __future__ import annotations\n"
        "def run(**_kwargs):\n"
        "    return {'skill': 'internal-only', 'status': 'ok'}\n",
        encoding="utf-8",
    )

    result = run_skill("internal-only", workspace_dir=tmp_path)
    assert result["status"] == "invalid"
    assert "skill_not_user_invocable" in result["blocking_items"]


def test_probe_skill_still_honors_user_invocable_policy(tmp_path: Path) -> None:
    skill_dir = tmp_path / ".skills" / "mcp-admin"
    runtime_dir = skill_dir / "scripts"
    runtime_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "SKILL.md").write_text(
        "---\n"
        "skill_key: mcp-admin\n"
        "runtime: mcp-bridge\n"
        "deps: mcp:filesystem\n"
        "userInvocable: false\n"
        "---\n"
        "internal mcp admin\n",
        encoding="utf-8",
    )
    (runtime_dir / "runtime.py").write_text(
        "from __future__ import annotations\ndef run(**_kwargs):\n    return {'skill': 'mcp-admin', 'status': 'ok'}\n",
        encoding="utf-8",
    )

    result = run_skill("mcp-admin", workspace_dir=tmp_path)
    assert result["status"] == "invalid"
    assert "skill_not_user_invocable" in result["blocking_items"]


def test_run_claw_wechat_article_probe_returns_plan(tmp_path: Path, monkeypatch) -> None:
    article = tmp_path / "article.md"
    article.write_text(
        "---\ntitle: demo\ncover: /tmp/cover.jpg\n---\n\nhello world\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("WECHAT_APP_ID", "wx_demo")
    monkeypatch.setenv("WECHAT_APP_SECRET", "secret_demo")
    monkeypatch.setattr(
        "shutil.which",
        lambda name: f"/usr/bin/{name}" if name in {"python", "wenyan", "node", "mcporter"} else None,
    )
    result = run_skill(
        "claw-wechat-article",
        workspace_dir=tmp_path,
        payload={"action": "probe", "article_path": str(article)},
    )
    assert result["skill"] == "claw-wechat-article"
    assert result["status"] == "ok"
    assert result["plan"]["mode"] in {"local-basic", "local-video", "remote"}
