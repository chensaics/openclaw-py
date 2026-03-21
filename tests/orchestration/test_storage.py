"""Tests for orchestration manifest persistence."""

import json
from pathlib import Path

import pytest

from pyclaw.agents.orchestration.storage import (
    OrchestrationManifest,
    RoleConfig,
    RoleStatus,
    load_manifest,
    save_manifest,
    update_manifest_status,
)


@pytest.fixture
def temp_manifest_dir(tmp_path):
    """Create a temporary manifest directory for testing."""
    tmp_path.mkdir(parents=True, exist_ok=True)
    yield tmp_path


def test_manifest_save_load():
    """Test save and load manifest roundtrip."""
    manifest = OrchestrationManifest(
        version="1.0",
        task_id="test-001",
        goal="Test goal",
        roles=[
            RoleConfig(
                role_id="researcher",
                name="Researcher",
                responsibility="Gather information from web",
                status=RoleStatus.PLANNED,
            )
        ],
        spawn_policy={"max_parallel": 4, "max_depth": 5, "timeout_seconds": 300},
    )

    # Test save
    save_manifest(manifest, session_id="test-session")

    # Test load
    loaded = load_manifest(session_id="test-session")

    assert loaded is not None
    assert loaded.task_id == "test-001"
    assert loaded.goal == "Test goal"
    assert len(loaded.roles) == 1
    assert loaded.roles[0].role_id == "researcher"


def test_load_nonexistent():
    """Test loading a manifest that doesn't exist."""
    result = load_manifest(session_id="nonexistent")

    assert result is None


def test_update_status(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Test updating role status in manifest file."""
    import pyclaw.agents.orchestration.storage as storage_mod

    monkeypatch.setattr(storage_mod, "MANIFEST_DIR", tmp_path)

    manifest = OrchestrationManifest(
        version="1.0",
        task_id="test-001",
        goal="Test goal",
        roles=[
            RoleConfig(
                role_id="researcher",
                name="Researcher",
                responsibility="Gather information from web",
                status=RoleStatus.PLANNED,
            )
        ],
        spawn_policy={"max_parallel": 4, "max_depth": 5, "timeout_seconds": 300},
    )

    save_manifest(manifest, session_id="update-test")
    ok = update_manifest_status(session_id="update-test", role_id="researcher", status=RoleStatus.RUNNING)
    assert ok is True

    result = load_manifest(session_id="update-test")
    assert result is not None
    # status_update is append-only; load_manifest returns manifest_body state.
    assert result.roles[0].status == RoleStatus.PLANNED

    manifest_file_path = tmp_path / "update-test.manifest.jsonl"
    content = manifest_file_path.read_text(encoding="utf-8")
    lines = content.strip().split("\n")

    assert any("manifest_header" in line for line in lines)
    assert any("manifest_body" in line for line in lines)
    assert any("status_update" in line for line in lines)

    status_update = None
    for line in reversed(lines):
        parsed = json.loads(line)
        if parsed.get("type") == "status_update":
            status_update = parsed
            break

    assert status_update is not None
    assert status_update["status"] == RoleStatus.RUNNING.value
    assert status_update["role_id"] == "researcher"


def test_manifest_file_structure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Test that manifest file has correct JSONL structure."""
    import pyclaw.agents.orchestration.storage as storage_mod

    monkeypatch.setattr(storage_mod, "MANIFEST_DIR", tmp_path)

    manifest = OrchestrationManifest(
        version="1.0",
        task_id="test-001",
        goal="Test goal",
        roles=[
            RoleConfig(
                role_id="researcher",
                name="Researcher",
                responsibility="Gather information from web",
                status=RoleStatus.PLANNED,
            )
        ],
        spawn_policy={"max_parallel": 4, "max_depth": 5, "timeout_seconds": 300},
    )
    save_manifest(manifest, session_id="test-session")

    sample_path = tmp_path / "test-session.manifest.jsonl"
    content = sample_path.read_text(encoding="utf-8")
    lines = content.strip().split("\n")

    assert any("manifest_header" in line for line in lines)
    assert any("manifest_body" in line for line in lines)

    manifest_header = None
    manifest_body = None
    for line in lines:
        parsed = json.loads(line)
        if parsed.get("type") == "manifest_header":
            manifest_header = parsed
        elif parsed.get("type") == "manifest_body":
            manifest_body = parsed

    assert manifest_header is not None
    assert manifest_header["version"] == "1.0"
    assert manifest_body is not None
    assert manifest_body["task_id"] == "test-001"
    assert isinstance(manifest_body["roles"], list)
    assert len(manifest_body["roles"]) == 1
