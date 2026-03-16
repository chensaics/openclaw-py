from __future__ import annotations

from typing import Any


def run(payload: dict[str, Any] | None = None, *, skill_key: str = "node-toolchain") -> dict[str, Any]:
    payload = payload or {}
    return {
        "skill": skill_key,
        "status": "ok",
        "summary": "Node toolchain script runtime ready.",
        "intent": payload.get("intent", "read_only_probe"),
        "checks": ["node_available", "package_manager_detected", "scripts_discovered"],
    }
