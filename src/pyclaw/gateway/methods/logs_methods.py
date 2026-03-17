"""Gateway RPC: logs.tail — read and stream log lines."""

from __future__ import annotations

import logging
from datetime import timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any

from pyclaw.config.paths import resolve_state_dir

if TYPE_CHECKING:
    from pyclaw.gateway.server import GatewayConnection, MethodHandler

logger = logging.getLogger(__name__)

LOG_FILENAME = "pyclaw.log"
MAX_LINES = 2000


def create_logs_handlers() -> dict[str, MethodHandler]:
    """Create handlers for logs RPC methods."""

    async def handle_logs_tail(params: dict[str, Any] | None, conn: GatewayConnection) -> None:
        """Return recent log lines from the gateway log file."""
        p = params or {}
        limit = min(int(p.get("limit", 200)), MAX_LINES)
        output_json = bool(p.get("json", False))
        local_time = bool(p.get("localTime", False))

        log_path = _resolve_log_path()
        if not log_path.exists():
            await conn.send_ok("logs.tail", {"lines": [], "count": 0, "path": str(log_path)})
            return

        try:
            raw_lines = log_path.read_text(encoding="utf-8", errors="replace").splitlines()
            tail = raw_lines[-limit:] if len(raw_lines) > limit else raw_lines

            if output_json:
                from datetime import datetime

                entries: list[dict[str, Any]] = []
                for line in tail:
                    ts = (
                        datetime.now(timezone.utc).isoformat()
                        if not local_time
                        else datetime.now().astimezone().isoformat()
                    )
                    entries.append({"time": ts, "line": line})
                await conn.send_ok("logs.tail", {"lines": entries, "count": len(entries), "path": str(log_path)})
            else:
                await conn.send_ok("logs.tail", {"lines": tail, "count": len(tail), "path": str(log_path)})

        except Exception as exc:
            logger.warning("logs.tail failed: %s", exc)
            await conn.send_error("logs.tail", "internal", str(exc))

    return {
        "logs.tail": handle_logs_tail,
    }


def _resolve_log_path() -> Path:
    return resolve_state_dir() / "logs" / LOG_FILENAME
