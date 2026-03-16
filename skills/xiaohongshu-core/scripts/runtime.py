from __future__ import annotations

from typing import Any


def run(
    payload: dict[str, Any] | None = None,
    *,
    workspace_dir: str = "",
    skill_key: str = "claw-redbook-auto",
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload = payload or {}
    intent = str(payload.get("intent", "full-stack-ops")).strip() or "full-stack-ops"
    account = str(payload.get("account", "default")).strip() or "default"
    mode = str(payload.get("mode", "headless")).strip() or "headless"
    return {
        "skill": skill_key,
        "status": "ok",
        "summary": "Xiaohongshu core script runtime ready.",
        "workspace": workspace_dir,
        "intent": intent,
        "account": account,
        "mode": mode,
        "capability_groups": ["auth", "publish", "explore", "interact", "analytics", "content-ops"],
        "config_keys": sorted((config or {}).keys())[:20],
    }
