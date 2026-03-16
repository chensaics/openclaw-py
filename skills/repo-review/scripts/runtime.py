from __future__ import annotations

from typing import Any


def run(payload: dict[str, Any] | None = None, *, skill_key: str = "repo-review") -> dict[str, Any]:
    payload = payload or {}
    return {
        "skill": skill_key,
        "status": "ok",
        "summary": "Repo review script runtime ready.",
        "focus_order": [
            "behavioral_regressions",
            "security_data_safety",
            "concurrency_performance",
            "error_handling_fallbacks",
            "missing_tests_observability",
        ],
        "findings": payload.get("findings", []),
    }
