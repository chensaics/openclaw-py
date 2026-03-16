from __future__ import annotations

from typing import Any


def run(payload: dict[str, Any] | None = None, *, skill_key: str = "pptx") -> dict[str, Any]:
    payload = payload or {}
    return {
        "skill": skill_key,
        "status": "ok",
        "summary": "PPTX reader script runtime ready.",
        "path": str(payload.get("path", "")).strip(),
    }
