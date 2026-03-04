"""Tests for skills marketplace — search, install, remove."""

from __future__ import annotations

from pathlib import Path

import pytest

from pyclaw.agents.skills.marketplace import (
    MarketplaceSkill,
    install_skill,
    list_installed_skills,
    remove_skill,
)


class TestInstallSkill:
    def test_install_creates_file(self, tmp_path: Path) -> None:
        ws = tmp_path / "workspace"
        ws.mkdir()
        path = install_skill("weather", "# Weather Skill\nFetch weather.", workspace_dir=ws)
        assert path.exists()
        assert path.name == "SKILL.md"
        assert "Weather Skill" in path.read_text()

    def test_install_force_overwrites(self, tmp_path: Path) -> None:
        ws = tmp_path / "workspace"
        ws.mkdir()
        install_skill("weather", "v1", workspace_dir=ws)
        install_skill("weather", "v2", workspace_dir=ws, force=True)
        content = (ws / ".skills" / "weather" / "SKILL.md").read_text()
        assert content == "v2"

    def test_install_refuses_overwrite(self, tmp_path: Path) -> None:
        ws = tmp_path / "workspace"
        ws.mkdir()
        install_skill("weather", "v1", workspace_dir=ws)
        with pytest.raises(FileExistsError):
            install_skill("weather", "v2", workspace_dir=ws)


class TestRemoveSkill:
    def test_remove_existing(self, tmp_path: Path) -> None:
        ws = tmp_path / "workspace"
        ws.mkdir()
        install_skill("weather", "# test", workspace_dir=ws)
        assert remove_skill("weather", workspace_dir=ws)
        assert not (ws / ".skills" / "weather").exists()

    def test_remove_nonexistent(self, tmp_path: Path) -> None:
        ws = tmp_path / "workspace"
        ws.mkdir()
        assert not remove_skill("ghost", workspace_dir=ws)


class TestListInstalledSkills:
    def test_empty(self, tmp_path: Path) -> None:
        ws = tmp_path / "workspace"
        ws.mkdir()
        assert list_installed_skills(workspace_dir=ws) == []

    def test_lists_installed(self, tmp_path: Path) -> None:
        ws = tmp_path / "workspace"
        ws.mkdir()
        install_skill("weather", "# w", workspace_dir=ws)
        install_skill("github", "# g", workspace_dir=ws)
        skills = list_installed_skills(workspace_dir=ws)
        names = [s["name"] for s in skills]
        assert "weather" in names
        assert "github" in names

    def test_source_label(self, tmp_path: Path) -> None:
        ws = tmp_path / "workspace"
        ws.mkdir()
        install_skill("test", "# t", workspace_dir=ws)
        skills = list_installed_skills(workspace_dir=ws)
        assert skills[0]["source"] == "workspace"


class TestMarketplaceSkill:
    def test_fields(self) -> None:
        s = MarketplaceSkill(name="weather", description="Fetch weather", url="https://...")
        assert s.name == "weather"
        assert s.description == "Fetch weather"
        assert s.tags == []
