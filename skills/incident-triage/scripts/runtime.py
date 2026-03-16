from __future__ import annotations

from typing import Any


def run(payload: dict[str, Any] | None = None, *, skill_key: str = "incident-triage") -> dict[str, Any]:
    payload = payload or {}
    severity = str(payload.get("severity", "medium")).strip().lower() or "medium"
    return {
        "skill": skill_key,
        "status": "ok",
        "summary": "Incident triage script runtime ready.",
        "severity": severity,
        "next_actions": payload.get(
            "next_actions",
            ["classify_blast_radius", "collect_logs_metrics", "prepare_safe_mitigation", "verify_signals"],
        ),
    }
