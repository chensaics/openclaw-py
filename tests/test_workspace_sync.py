"""Tests for workspace template sync."""

from __future__ import annotations

from pathlib import Path

import pytest

from pyclaw.agents.workspace_sync import diff_templates, sync_templates


class TestSyncTemplates:
    def test_creates_missing(self, tmp_path: Path) -> None:
        ws = tmp_path / "workspace"
        ws.mkdir()
        result = sync_templates(workspace=ws)
        assert len(result["created"]) > 0
        assert (ws / "AGENTS.md").exists()
        assert (ws / "HEARTBEAT.md").exists()

    def test_skips_modified(self, tmp_path: Path) -> None:
        ws = tmp_path / "workspace"
        ws.mkdir()
        sync_templates(workspace=ws)
        (ws / "AGENTS.md").write_text("custom content")
        result = sync_templates(workspace=ws)
        assert "AGENTS.md" in result["skipped"]
        assert (ws / "AGENTS.md").read_text() == "custom content"

    def test_force_overwrites(self, tmp_path: Path) -> None:
        ws = tmp_path / "workspace"
        ws.mkdir()
        sync_templates(workspace=ws)
        (ws / "AGENTS.md").write_text("custom content")
        result = sync_templates(workspace=ws, force=True)
        assert "AGENTS.md" in result["updated"]
        assert (ws / "AGENTS.md").read_text() != "custom content"

    def test_idempotent(self, tmp_path: Path) -> None:
        ws = tmp_path / "workspace"
        ws.mkdir()
        sync_templates(workspace=ws)
        result = sync_templates(workspace=ws)
        assert result["created"] == []
        assert result["updated"] == []
        assert result["skipped"] == []


class TestDiffTemplates:
    def test_missing_files(self, tmp_path: Path) -> None:
        ws = tmp_path / "workspace"
        ws.mkdir()
        diffs = diff_templates(workspace=ws)
        assert len(diffs) > 0
        assert all(d["status"] == "missing" for d in diffs)

    def test_no_diff_after_sync(self, tmp_path: Path) -> None:
        ws = tmp_path / "workspace"
        ws.mkdir()
        sync_templates(workspace=ws)
        diffs = diff_templates(workspace=ws)
        assert diffs == []

    def test_modified_detected(self, tmp_path: Path) -> None:
        ws = tmp_path / "workspace"
        ws.mkdir()
        sync_templates(workspace=ws)
        (ws / "HEARTBEAT.md").write_text("changed")
        diffs = diff_templates(workspace=ws)
        names = [d["name"] for d in diffs]
        assert "HEARTBEAT.md" in names
