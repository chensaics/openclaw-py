"""Extended RPC methods — system, usage, tts, wizard, push, doctor, skills, etc.

Phase 56: Added system.event, system.heartbeat.last, system.presence real RPC handlers.
Phase 57: Replaced placeholder-success returns with real implementations or NOT_IMPLEMENTED.
"""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING, Any

from pyclaw.infra.system_events import (
    EventBus,
    EventType,
    PresenceManager,
    SystemEvent,
)

if TYPE_CHECKING:
    from pyclaw.gateway.server import GatewayConnection, MethodHandler

logger = logging.getLogger(__name__)

_bus = EventBus()
_presence = PresenceManager(idle_timeout_s=300.0)
_heartbeat_enabled = True
_last_heartbeat_at = 0.0
_started_at = time.time()


def create_extended_handlers() -> dict[str, MethodHandler]:
    """Create handlers for extended RPC methods."""

    # ------------------------------------------------------------------
    # TTS
    # ------------------------------------------------------------------

    async def handle_tts_speak(params: dict[str, Any] | None, conn: GatewayConnection) -> None:
        """Placeholder: TTS synthesis not yet implemented. Returns not_implemented error."""
        text = (params or {}).get("text", "")
        if not text:
            await conn.send_error("tts.speak", "invalid_params", "Missing 'text'")
            return
        await conn.send_error(
            "tts.speak",
            "not_implemented",
            "TTS synthesis is not yet implemented. Configure an external TTS provider to use this feature.",
        )

    async def handle_tts_voices(params: dict[str, Any] | None, conn: GatewayConnection) -> None:
        await conn.send_ok(
            "tts.voices",
            {
                "voices": ["default", "alloy", "echo", "fable", "onyx", "nova", "shimmer"],
                "note": "Static list — no TTS provider configured yet.",
            },
        )

    # ------------------------------------------------------------------
    # Usage
    # ------------------------------------------------------------------

    async def handle_usage_get(params: dict[str, Any] | None, conn: GatewayConnection) -> None:
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

    # ------------------------------------------------------------------
    # System (Phase 56 — real RPC implementations)
    # ------------------------------------------------------------------

    async def handle_system_info(params: dict[str, Any] | None, conn: GatewayConnection) -> None:
        import platform
        import sys

        await conn.send_ok(
            "system.info",
            {
                "platform": platform.system(),
                "python": sys.version,
                "uptime": time.time() - _started_at,
                "startedAt": _started_at,
            },
        )

    async def handle_system_logs(params: dict[str, Any] | None, conn: GatewayConnection) -> None:
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

        await conn.send_ok(
            "system.logs",
            {
                "logs": entries,
                "count": len(entries),
                "level": level_filter or "all",
                "maxLines": max_lines,
            },
        )

    async def handle_system_event(params: dict[str, Any] | None, conn: GatewayConnection) -> None:
        global _last_heartbeat_at
        p = params or {}
        text = str(p.get("text", ""))
        mode = str(p.get("mode", "next-heartbeat"))

        event = SystemEvent(
            event_type=EventType.HEALTH_CHECK,
            source="gateway-rpc",
            data={"text": text, "mode": mode},
        )
        _bus.emit(event)
        _presence.heartbeat("system")
        if mode == "now" and _heartbeat_enabled:
            _last_heartbeat_at = time.time()

        await conn.send_ok(
            "system.event",
            {
                "ok": True,
                "eventType": event.event_type.value,
                "mode": mode,
                "heartbeatTriggered": bool(mode == "now" and _heartbeat_enabled),
                "source": "gateway",
            },
        )

    async def handle_system_heartbeat_last(params: dict[str, Any] | None, conn: GatewayConnection) -> None:
        await conn.send_ok(
            "system.heartbeat.last",
            {
                "enabled": _heartbeat_enabled,
                "lastHeartbeatAt": _last_heartbeat_at or None,
            },
        )

    async def handle_system_presence(params: dict[str, Any] | None, conn: GatewayConnection) -> None:
        _presence.check_idle()
        entries = [
            {
                "componentId": cid,
                "state": info.state.value,
                "lastSeenAt": info.last_seen_at,
            }
            for cid, info in _presence._entries.items()
        ]
        await conn.send_ok("system.presence", {"entries": entries})

    # ------------------------------------------------------------------
    # Doctor
    # ------------------------------------------------------------------

    async def handle_doctor_run(params: dict[str, Any] | None, conn: GatewayConnection) -> None:
        from pyclaw.cli.commands.doctor_flows import run_doctor

        report = run_doctor()
        checks = []
        passed = 0
        failed = 0
        warns = 0
        for r in report.results:
            entry: dict[str, Any] = {
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

        await conn.send_ok(
            "doctor.run",
            {
                "checks": checks,
                "summary": {"passed": passed, "failed": failed, "warnings": warns},
                "platform": report.platform,
                "pythonVersion": report.python_version,
            },
        )

    # ------------------------------------------------------------------
    # Skills
    # ------------------------------------------------------------------

    async def handle_skills_list(params: dict[str, Any] | None, conn: GatewayConnection) -> None:
        skills: list[dict[str, Any]] = []
        try:
            from pathlib import Path

            from pyclaw.agents.skills import load_skill_entries
            from pyclaw.config.paths import resolve_state_dir

            for source_dir, source_label in [
                (Path.cwd(), "workspace"),
                (resolve_state_dir() / "skills", "global"),
            ]:
                if source_dir.is_dir():
                    for sk in load_skill_entries(source_dir, source=source_label):
                        skills.append(
                            {
                                "name": getattr(sk, "name", ""),
                                "source": source_label,
                                "description": getattr(sk, "description", ""),
                                "enabled": True,
                            }
                        )
        except ImportError:
            pass
        except Exception as exc:
            logger.warning("skills.list discovery error: %s", exc)

        await conn.send_ok("skills.list", {"skills": skills, "count": len(skills)})

    # ------------------------------------------------------------------
    # Wizard — NOT_IMPLEMENTED (Phase 57)
    # ------------------------------------------------------------------

    async def handle_wizard_start(params: dict[str, Any] | None, conn: GatewayConnection) -> None:
        """Placeholder: Setup wizard not yet implemented. Returns not_implemented error."""
        await conn.send_error(
            "wizard.start",
            "not_implemented",
            "Setup wizard is not yet implemented. Use `pyclaw setup` CLI instead.",
        )

    async def handle_wizard_step(params: dict[str, Any] | None, conn: GatewayConnection) -> None:
        """Placeholder: Setup wizard not yet implemented. Returns not_implemented error."""
        await conn.send_error(
            "wizard.step",
            "not_implemented",
            "Setup wizard is not yet implemented. Use `pyclaw setup` CLI instead.",
        )

    # ------------------------------------------------------------------
    # Push — NOT_IMPLEMENTED (Phase 57)
    # ------------------------------------------------------------------

    async def handle_push_send(params: dict[str, Any] | None, conn: GatewayConnection) -> None:
        """Placeholder: Push notification delivery not yet implemented. Returns not_implemented error."""
        await conn.send_error(
            "push.send",
            "not_implemented",
            "Push notification delivery is not yet implemented. Configure a push provider (FCM/APNs) to enable this.",
        )

    # ------------------------------------------------------------------
    # Voice Wake — NOT_IMPLEMENTED (Phase 57)
    # ------------------------------------------------------------------

    async def handle_voicewake_status(params: dict[str, Any] | None, conn: GatewayConnection) -> None:
        """Placeholder: Voice wake-word detection not yet available. Returns not_implemented error."""
        await conn.send_error(
            "voicewake.status",
            "not_implemented",
            "Voice wake-word detection is not yet available in the Python runtime.",
        )

    # ------------------------------------------------------------------
    # Update Check — real version read (Phase 57)
    # ------------------------------------------------------------------

    async def handle_update_check(params: dict[str, Any] | None, conn: GatewayConnection) -> None:
        current_version = _get_current_version()
        await conn.send_ok(
            "update.check",
            {
                "currentVersion": current_version,
                "latestVersion": current_version,
                "updateAvailable": False,
                "note": "Automatic update checking from PyPI is not yet implemented.",
            },
        )

    # ------------------------------------------------------------------
    # Web Status — real Gateway state (Phase 57)
    # ------------------------------------------------------------------

    async def handle_web_status(params: dict[str, Any] | None, conn: GatewayConnection) -> None:
        await conn.send_ok(
            "web.status",
            {
                "connected": True,
                "provider": "gateway-websocket",
                "uptime": time.time() - _started_at,
                "note": "Web UI tunnel is not yet implemented; Gateway WebSocket is active.",
            },
        )

    return {
        "tts.speak": handle_tts_speak,
        "tts.voices": handle_tts_voices,
        "usage.get": handle_usage_get,
        "system.info": handle_system_info,
        "system.logs": handle_system_logs,
        "system.event": handle_system_event,
        "system.heartbeat.last": handle_system_heartbeat_last,
        "system.presence": handle_system_presence,
        "doctor.run": handle_doctor_run,
        "skills.list": handle_skills_list,
        "wizard.start": handle_wizard_start,
        "wizard.step": handle_wizard_step,
        "push.send": handle_push_send,
        "voicewake.status": handle_voicewake_status,
        "update.check": handle_update_check,
        "web.status": handle_web_status,
    }


def _get_current_version() -> str:
    try:
        from importlib.metadata import version

        return version("pyclaw")
    except Exception:
        return "0.0.0-dev"
