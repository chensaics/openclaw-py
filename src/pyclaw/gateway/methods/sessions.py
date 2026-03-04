"""sessions.* — session list/preview/reset handlers."""

from __future__ import annotations

import json
import time
import uuid
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pyclaw.gateway.server import GatewayConnection, MethodHandler


def create_session_handlers() -> dict[str, MethodHandler]:
    async def handle_sessions_list(params: dict[str, Any] | None, conn: GatewayConnection) -> None:
        from pyclaw.config.paths import resolve_agents_dir

        agents_dir = resolve_agents_dir()
        sessions: list[dict[str, Any]] = []

        if agents_dir.exists():
            for agent_dir in sorted(agents_dir.iterdir()):
                if not agent_dir.is_dir():
                    continue
                sessions_dir = agent_dir / "sessions"
                if not sessions_dir.exists():
                    continue
                for sf in sorted(sessions_dir.glob("*.jsonl")):
                    sessions.append(
                        {
                            "agentId": agent_dir.name,
                            "file": sf.name,
                            "path": str(sf),
                            "size": sf.stat().st_size,
                        }
                    )

        await conn.send_ok("sessions.list", {"sessions": sessions})

    async def handle_sessions_preview(params: dict[str, Any] | None, conn: GatewayConnection) -> None:
        if not params or "path" not in params:
            await conn.send_error("sessions.preview", "invalid_params", "Missing 'path'.")
            return

        path = Path(params["path"])
        if not path.exists():
            await conn.send_error("sessions.preview", "not_found", f"Session file not found: {path}")
            return

        limit = params.get("limit", 50)
        messages: list[dict[str, Any]] = []

        try:
            with open(path, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    entry = json.loads(line)
                    if entry.get("type") == "message":
                        msg = entry.get("message", {})
                        role = msg.get("role", "")
                        content = msg.get("content", "")
                        # Truncate content for preview
                        if isinstance(content, str) and len(content) > 200:
                            content = content[:200] + "..."
                        messages.append({"role": role, "content": content})
                        if len(messages) >= limit:
                            break
        except Exception as e:
            await conn.send_error("sessions.preview", "read_error", str(e))
            return

        await conn.send_ok("sessions.preview", {"messages": messages})

    async def handle_sessions_delete(params: dict[str, Any] | None, conn: GatewayConnection) -> None:
        if not params or "path" not in params:
            await conn.send_error("sessions.delete", "invalid_params", "Missing 'path'.")
            return

        path = Path(params["path"])
        if not path.exists():
            await conn.send_ok("sessions.delete", {"deleted": False})
            return

        try:
            path.unlink()
            # Also remove lock file if present
            lock = path.with_suffix(path.suffix + ".lock")
            lock.unlink(missing_ok=True)
            await conn.send_ok("sessions.delete", {"deleted": True})
        except Exception as e:
            await conn.send_error("sessions.delete", "delete_error", str(e))

    async def handle_sessions_reset(params: dict[str, Any] | None, conn: GatewayConnection) -> None:
        """Reset a session (clear its contents but keep the file)."""
        if not params or "path" not in params:
            await conn.send_error("sessions.reset", "invalid_params", "Missing 'path'.")
            return

        path = Path(params["path"])
        try:
            from pyclaw.agents.session import SessionManager

            # Overwrite with a fresh session header
            if path.exists():
                path.unlink()
            mgr = SessionManager(path=path)
            mgr.write_header()
            await conn.send_ok("sessions.reset", {"reset": True})
        except Exception as e:
            await conn.send_error("sessions.reset", "reset_error", str(e))

    async def handle_sessions_get(params: dict[str, Any] | None, conn: GatewayConnection) -> None:
        if not params or "sessionId" not in params:
            await conn.send_error("sessions.get", "invalid_params", "Missing 'sessionId'.")
            return

        agent_id = params.get("agentId", "main")
        session_id = params["sessionId"]

        from pyclaw.agents.session import SessionManager
        from pyclaw.config.paths import resolve_sessions_dir

        sessions_dir = resolve_sessions_dir(agent_id)
        session_file = sessions_dir / f"{session_id}.jsonl"

        if not session_file.exists():
            await conn.send_error("sessions.get", "not_found", f"Session not found: {session_id}")
            return

        try:
            session = SessionManager.open(session_file)
            messages = session.get_messages_as_dicts()
            await conn.send_ok(
                "sessions.get",
                {
                    "id": session.session_id,
                    "agentId": agent_id,
                    "path": str(session_file),
                    "messages": messages,
                },
            )
        except Exception as e:
            await conn.send_error("sessions.get", "read_error", str(e))

    async def handle_sessions_create(params: dict[str, Any] | None, conn: GatewayConnection) -> None:
        p = params or {}
        agent_id = p.get("agentId", "main")

        from pyclaw.agents.session import SessionManager
        from pyclaw.config.paths import resolve_sessions_dir

        sessions_dir = resolve_sessions_dir(agent_id)
        session_id = uuid.uuid4().hex[:12]
        session_file = sessions_dir / f"{session_id}.jsonl"

        try:
            sessions_dir.mkdir(parents=True, exist_ok=True)
            mgr = SessionManager(path=session_file)
            mgr.session_id = session_id
            mgr.write_header()
            await conn.send_ok("sessions.create", {"id": session_id})
        except Exception as e:
            await conn.send_error("sessions.create", "create_error", str(e))

    async def handle_sessions_cleanup(params: dict[str, Any] | None, conn: GatewayConnection) -> None:
        params = params or {}
        older_than_days = params.get("olderThanDays", 30)
        dry_run = params.get("dryRun", False)
        active_key = params.get("activeKey")

        from pyclaw.config.paths import resolve_agents_dir

        agents_dir = resolve_agents_dir()
        cutoff = time.time() - (older_than_days * 86400)
        removed = 0
        skipped = 0

        if agents_dir.exists():
            for agent_dir in sorted(agents_dir.iterdir()):
                if not agent_dir.is_dir():
                    continue
                sessions_dir = agent_dir / "sessions"
                if not sessions_dir.exists():
                    continue
                for sf in sessions_dir.glob("*.jsonl"):
                    try:
                        mtime = sf.stat().st_mtime
                        path_str = str(sf)
                        if active_key and path_str == active_key:
                            skipped += 1
                            continue
                        if mtime < cutoff:
                            if not dry_run:
                                sf.unlink()
                                lock = sf.with_suffix(sf.suffix + ".lock")
                                lock.unlink(missing_ok=True)
                            removed += 1
                        else:
                            skipped += 1
                    except Exception:
                        skipped += 1

        await conn.send_ok(
            "sessions.cleanup",
            {"removed": removed, "skipped": skipped, "dryRun": dry_run},
        )

    return {
        "sessions.list": handle_sessions_list,
        "sessions.preview": handle_sessions_preview,
        "sessions.delete": handle_sessions_delete,
        "sessions.reset": handle_sessions_reset,
        "sessions.get": handle_sessions_get,
        "sessions.create": handle_sessions_create,
        "sessions.cleanup": handle_sessions_cleanup,
    }
