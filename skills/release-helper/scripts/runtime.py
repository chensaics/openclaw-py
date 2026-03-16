from __future__ import annotations

from typing import Any


def run(payload: dict[str, Any] | None = None, *, skill_key: str = "release-helper") -> dict[str, Any]:
    payload = payload or {}
    return {
        "skill": skill_key,
        "status": "ok",
        "summary": "Release helper script runtime ready.",
        "requested_tag": str(payload.get("tag", "")).strip(),
        "checks": [
            "working_tree_clean",
            "critical_changes_test_plan",
            "release_notes_present",
            "breaking_change_notes",
            "rollback_notes_present",
        ],
    }
