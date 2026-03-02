"""Extended RPC methods — browser, push, talk, tts, wizard, usage, system, etc.

Ported from ``src/gateway/method-handlers/*.ts`` (missing methods).

Provides additional Gateway RPC handlers beyond the core set.
"""

from __future__ import annotations

import logging
import time
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from pyclaw.gateway.server import GatewayConnection, MethodHandler

logger = logging.getLogger(__name__)


def create_extended_handlers() -> dict[str, "MethodHandler"]:
    """Create handlers for extended RPC methods."""

    async def handle_tts_speak(
        params: dict[str, Any] | None, conn: "GatewayConnection"
    ) -> None:
        text = (params or {}).get("text", "")
        voice = (params or {}).get("voice", "default")
        if not text:
            await conn.send_error("tts.speak", "invalid_params", "Missing 'text'")
            return
        await conn.send_ok("tts.speak", {
            "text": text[:200],
            "voice": voice,
            "status": "queued",
        })

    async def handle_tts_voices(
        params: dict[str, Any] | None, conn: "GatewayConnection"
    ) -> None:
        await conn.send_ok("tts.voices", {
            "voices": ["default", "alloy", "echo", "fable", "onyx", "nova", "shimmer"],
        })

    async def handle_usage_get(
        params: dict[str, Any] | None, conn: "GatewayConnection"
    ) -> None:
        from pyclaw.infra.session_cost import aggregate_usage

        days = int((params or {}).get("days", 7) or 7)
        usage = aggregate_usage(days=max(days, 1))
        await conn.send_ok(
            "usage.get",
            {
                "windowDays": usage["window_days"],
                "sessions": usage["sessions"],
                "calls": usage["calls"],
                "totalTokens": usage["total_tokens"],
                "inputTokens": usage["total_input_tokens"],
                "outputTokens": usage["total_output_tokens"],
                "estimatedCost": usage["estimated_cost"],
                "estimatedCostValue": usage["estimated_cost_value"],
                "byProvider": usage["by_provider"],
                "byModel": usage["by_model"],
            },
        )

    async def handle_system_info(
        params: dict[str, Any] | None, conn: "GatewayConnection"
    ) -> None:
        import platform
        import sys
        await conn.send_ok("system.info", {
            "platform": platform.system(),
            "python": sys.version,
            "uptime": time.time(),
        })

    async def handle_system_logs(
        params: dict[str, Any] | None, conn: "GatewayConnection"
    ) -> None:
        """Read log lines from the gateway log file."""
        from pyclaw.config.paths import resolve_state_dir

        p = params or {}
        max_lines = min(int(p.get("lines", 50)), 500)
        level_filter = (p.get("level", "") or "").lower()

        log_path = resolve_state_dir() / "logs" / "pyclaw.log"
        entries: list[str] = []
        if log_path.exists():
            try:
                raw = log_path.read_text(encoding="utf-8", errors="replace").splitlines()
                tail = raw[-max_lines:] if len(raw) > max_lines else raw
                if level_filter and level_filter != "all":
                    entries = [ln for ln in tail if level_filter.upper() in ln]
                else:
                    entries = tail
            except Exception as exc:
                logger.warning("system.logs read error: %s", exc)

        await conn.send_ok("system.logs", {
            "logs": entries,
            "count": len(entries),
            "level": level_filter or "all",
            "maxLines": max_lines,
        })

    async def handle_doctor_run(
        params: dict[str, Any] | None, conn: "GatewayConnection"
    ) -> None:
        """Run real diagnostic checks and return results."""
        from pyclaw.cli.commands.doctor_flows import run_doctor

        report = run_doctor()
        checks = []
        passed = 0
        failed = 0
        warns = 0
        for r in report.results:
            entry = {
                "name": r.check_name,
                "category": r.category,
                "severity": r.severity.value,
                "message": r.message,
            }
            if r.fix_hint:
                entry["fixHint"] = r.fix_hint
            checks.append(entry)

            if r.severity.value == "ok":
                passed += 1
            elif r.severity.value in ("error", "critical"):
                failed += 1
            elif r.severity.value == "warning":
                warns += 1

        await conn.send_ok("doctor.run", {
            "checks": checks,
            "summary": {"passed": passed, "failed": failed, "warnings": warns},
            "platform": report.platform,
            "pythonVersion": report.python_version,
        })

    async def handle_skills_list(
        params: dict[str, Any] | None, conn: "GatewayConnection"
    ) -> None:
        """Return discoverable skills with metadata."""
        skills: list[dict[str, Any]] = []
        try:
            from pathlib import Path
            from pyclaw.agents.skills import load_skill_entries, load_workspace_skill_entries
            from pyclaw.config.paths import resolve_state_dir

            # Load from workspace cwd and state dir skills
            for source_dir, source_label in [
                (Path.cwd(), "workspace"),
                (resolve_state_dir() / "skills", "global"),
            ]:
                if source_dir.is_dir():
                    for sk in load_skill_entries(source_dir, source=source_label):
                        skills.append({
                            "name": getattr(sk, "name", ""),
                            "source": source_label,
                            "description": getattr(sk, "description", ""),
                            "enabled": True,
                        })
        except ImportError:
            pass
        except Exception as exc:
            logger.warning("skills.list discovery error: %s", exc)

        await conn.send_ok("skills.list", {"skills": skills, "count": len(skills)})

    async def handle_wizard_start(
        params: dict[str, Any] | None, conn: "GatewayConnection"
    ) -> None:
        wizard_type = (params or {}).get("type", "setup")
        await conn.send_ok("wizard.start", {
            "type": wizard_type,
            "sessionId": f"wizard-{int(time.time())}",
            "steps": [],
        })

    async def handle_wizard_step(
        params: dict[str, Any] | None, conn: "GatewayConnection"
    ) -> None:
        session_id = (params or {}).get("sessionId", "")
        step_id = (params or {}).get("stepId", "")
        if not session_id or not step_id:
            await conn.send_error("wizard.step", "invalid_params", "Missing sessionId or stepId")
            return
        await conn.send_ok("wizard.step", {
            "sessionId": session_id,
            "stepId": step_id,
            "status": "completed",
        })

    async def handle_push_send(
        params: dict[str, Any] | None, conn: "GatewayConnection"
    ) -> None:
        message = (params or {}).get("message", "")
        target = (params or {}).get("target", "")
        await conn.send_ok("push.send", {
            "sent": bool(message),
            "target": target,
        })

    async def handle_voicewake_status(
        params: dict[str, Any] | None, conn: "GatewayConnection"
    ) -> None:
        await conn.send_ok("voicewake.status", {
            "enabled": False,
            "listening": False,
            "wakeWord": "hey pyclaw",
        })

    async def handle_update_check(
        params: dict[str, Any] | None, conn: "GatewayConnection"
    ) -> None:
        await conn.send_ok("update.check", {
            "currentVersion": "0.0.0",
            "latestVersion": "0.0.0",
            "updateAvailable": False,
        })

    async def handle_web_status(
        params: dict[str, Any] | None, conn: "GatewayConnection"
    ) -> None:
        await conn.send_ok("web.status", {
            "connected": False,
            "provider": "none",
        })

    return {
        "tts.speak": handle_tts_speak,
        "tts.voices": handle_tts_voices,
        "usage.get": handle_usage_get,
        "system.info": handle_system_info,
        "system.logs": handle_system_logs,
        "doctor.run": handle_doctor_run,
        "skills.list": handle_skills_list,
        "wizard.start": handle_wizard_start,
        "wizard.step": handle_wizard_step,
        "push.send": handle_push_send,
        "voicewake.status": handle_voicewake_status,
        "update.check": handle_update_check,
        "web.status": handle_web_status,
    }
