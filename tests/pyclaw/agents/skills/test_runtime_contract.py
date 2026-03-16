from __future__ import annotations

from pathlib import Path

from pyclaw.agents.skills.loader import load_workspace_skill_entries
from pyclaw.agents.skills.prompt import build_workspace_skills_prompt


def _write_skill(workspace: Path, name: str, frontmatter: str, body: str = "skill body") -> None:
    skill_dir = workspace / ".skills" / name
    skill_dir.mkdir(parents=True, exist_ok=True)
    content = f"---\n{frontmatter}\n---\n{body}\n"
    (skill_dir / "SKILL.md").write_text(content, encoding="utf-8")


def test_loader_parses_runtime_contract_and_missing_deps(tmp_path: Path, monkeypatch) -> None:
    _write_skill(
        tmp_path,
        "node-skill",
        "runtime: node-wrapper\ndeps: cmd:node, env:OPENAI_API_KEY\nsecurity-level: elevated",
    )

    monkeypatch.setattr("pyclaw.agents.skills.loader.shutil.which", lambda _: None)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    entries = load_workspace_skill_entries(tmp_path)
    entry = next(e for e in entries if e.name == "node-skill")
    contract = entry.runtime_contract
    assert contract.runtime == "node-wrapper"
    assert contract.security_level == "elevated"
    assert "cmd:node" in contract.deps
    assert "cmd:node" in contract.missing_deps
    assert "env:OPENAI_API_KEY" in contract.missing_deps
    assert contract.is_compatible is False


def test_loader_resolves_mcp_dependency_from_config(tmp_path: Path) -> None:
    _write_skill(
        tmp_path,
        "mcp-skill",
        "runtime: mcp-bridge\ndeps: mcp:github",
    )

    config = {"tools": {"mcpServers": {"github": {"url": "https://example.com/mcp"}}}}
    entries = load_workspace_skill_entries(tmp_path, config=config)
    entry = next(e for e in entries if e.name == "mcp-skill")
    contract = entry.runtime_contract
    assert contract.runtime == "mcp-bridge"
    assert contract.missing_deps == []
    assert contract.is_compatible is True


def test_prompt_skips_incompatible_runtime_skills(tmp_path: Path, monkeypatch) -> None:
    _write_skill(
        tmp_path,
        "bad-skill",
        "runtime: node-wrapper\ndeps: cmd:__missing_binary__",
        body="should be skipped",
    )
    _write_skill(
        tmp_path,
        "good-skill",
        "runtime: python-native",
        body="should be included",
    )

    monkeypatch.setattr(
        "pyclaw.agents.skills.loader.shutil.which",
        lambda cmd: None if cmd == "__missing_binary__" else "/usr/bin/ok",
    )

    snapshot = build_workspace_skills_prompt(str(tmp_path))
    assert "good-skill" in snapshot.resolved_skills
    assert "bad-skill" not in snapshot.resolved_skills
    assert "should be included" in snapshot.prompt
    assert "should be skipped" not in snapshot.prompt
