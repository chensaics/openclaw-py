from __future__ import annotations

from typing import Any


def run(
    payload: dict[str, Any] | None = None,
    *,
    workspace_dir: str = "",
    skill_key: str = "docs-sync",
) -> dict[str, Any]:
    payload = payload or {}
    return {
        "skill": skill_key,
        "status": "ok",
        "summary": "Docs sync script runtime ready.",
        "workspace": workspace_dir,
        "requested_scope": payload.get("scope", "docs/configuration.md"),
        "checks": [
            "config_keys_alignment",
            "env_vars_alignment",
            "cli_examples_alignment",
            "broken_or_stale_paths",
        ],
    }
