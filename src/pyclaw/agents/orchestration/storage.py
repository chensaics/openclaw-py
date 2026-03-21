"""Orchestration manifest persistence layer using JSONL format."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Optional

from pyclaw.agents.orchestration.manifest import OrchestrationManifest, RoleConfig, RoleStatus, SpawnPolicy, ToolPolicy


MANIFEST_DIR = Path.home() / ".pyclaw" / "orchestration"
MANIFEST_DIR.mkdir(parents=True, exist_ok=True)


def save_manifest(manifest: OrchestrationManifest, session_id: str) -> None:
    """Save manifest to JSONL format with version suffix.

    Each manifest file consists of multiple JSON objects written sequentially.
    """
    path = MANIFEST_DIR / f"{session_id}.manifest.jsonl"

    # Convert to dict and add metadata header
    lines = []
    lines.append(json.dumps({"type": "manifest_header", "version": manifest.version}))
    lines.append(json.dumps({
        "type": "manifest_body",
        "task_id": manifest.task_id,
        "goal": manifest.goal,
        "roles": [r.model_dump() for r in manifest.roles],
        "spawn_policy": manifest.spawn_policy.model_dump(),
        "tool_policy": manifest.tool_policy.model_dump() if manifest.tool_policy else None,
        "metadata": manifest.metadata,
    }, ensure_ascii=False))

    path.write_text("\n".join(lines), encoding="utf-8")


def load_manifest(session_id: str) -> Optional[OrchestrationManifest]:
    """Load manifest from JSONL file."""
    path = MANIFEST_DIR / f"{session_id}.manifest.jsonl"

    if not path.exists():
        return None

    lines = path.read_text(encoding="utf-8").strip().split("\n")

    # Find the manifest body (last line should be manifest_body type)
    manifest_body = None
    for line in reversed(lines):
        try:
            parsed = json.loads(line)
            if parsed.get("type") == "manifest_body":
                manifest_body = parsed
                break
        except json.JSONDecodeError:
            continue

    if not manifest_body:
        return None

    # Reconstruct Pydantic models
    roles = [RoleConfig(**r) for r in manifest_body.get("roles", [])]

    return OrchestrationManifest(
        version=manifest_body.get("version", "1.0"),
        task_id=manifest_body.get("task_id", ""),
        goal=manifest_body.get("goal", ""),
        roles=roles,
        spawn_policy=SpawnPolicy(**manifest_body.get("spawn_policy", {})),
        tool_policy=ToolPolicy(**manifest_body.get("tool_policy", {})) if manifest_body.get("tool_policy") else None,
        metadata=manifest_body.get("metadata", {}),
    )


def update_manifest_status(session_id: str, role_id: str, status: RoleStatus) -> bool:
    """Update role status in manifest file (append-only)."""
    path = MANIFEST_DIR / f"{session_id}.manifest.jsonl"

    if not path.exists():
        return False

    # Create status update record
    update = json.dumps({
        "type": "status_update",
        "role_id": role_id,
        "status": status.value,
        "timestamp": datetime.now().isoformat(),
    }, ensure_ascii=False)

    with path.open("a", encoding="utf-8") as f:
        f.write("\n" + update)

    return True
