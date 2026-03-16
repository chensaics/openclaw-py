from __future__ import annotations

from typing import Any


def run(payload: dict[str, Any] | None = None, *, skill_key: str = "social") -> dict[str, Any]:
    payload = payload or {}
    return {
        "skill": skill_key,
        "status": "ok",
        "summary": "Social skill script runtime ready.",
        "requested_action": payload.get("action", "status"),
        "supported_actions": ["social_join", "social_status"],
    }
