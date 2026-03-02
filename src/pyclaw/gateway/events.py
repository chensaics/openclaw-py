"""Gateway event definitions and helpers.

Defines all WebSocket event names and payload constructors for
broadcasting state changes to connected clients.
"""

from __future__ import annotations

import time
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from pyclaw.gateway.server import GatewayServer


# ---------------------------------------------------------------------------
# Event name constants
# ---------------------------------------------------------------------------

# Chat / agent
EVENT_CHAT_MESSAGE = "chat.message"
EVENT_CHAT_DELTA = "chat.delta"
EVENT_CHAT_TOOL_CALL = "chat.toolCall"
EVENT_CHAT_TOOL_RESULT = "chat.toolResult"
EVENT_CHAT_COMPLETE = "chat.complete"
EVENT_CHAT_ERROR = "chat.error"
EVENT_CHAT_ABORT = "chat.abort"

# Agent state
EVENT_AGENT_STATE = "agent.state"
EVENT_AGENT_STARTED = "agent.started"
EVENT_AGENT_STOPPED = "agent.stopped"
EVENT_AGENT_ERROR = "agent.error"

# Presence
EVENT_PRESENCE = "presence"

# Health / heartbeat
EVENT_HEALTH = "health"
EVENT_HEARTBEAT = "heartbeat"

# Shutdown
EVENT_SHUTDOWN = "shutdown"

# Cron
EVENT_CRON_FIRED = "cron.fired"
EVENT_CRON_UPDATED = "cron.updated"

# Device pairing
EVENT_NODE_PAIR_REQUEST = "node.pair.request"
EVENT_NODE_PAIR_COMPLETE = "node.pair.complete"
EVENT_NODE_PAIR_REJECTED = "node.pair.rejected"
EVENT_DEVICE_PAIR_REQUEST = "device.pair.request"
EVENT_DEVICE_PAIR_COMPLETE = "device.pair.complete"

# Exec approval
EVENT_EXEC_APPROVAL_REQUEST = "exec.approval.request"
EVENT_EXEC_APPROVAL_GRANTED = "exec.approval.granted"
EVENT_EXEC_APPROVAL_DENIED = "exec.approval.denied"

# Progress
EVENT_PROGRESS = "progress"

# Updates
EVENT_UPDATE_AVAILABLE = "update_available"

# Session
EVENT_SESSION_CREATED = "session.created"
EVENT_SESSION_DELETED = "session.deleted"


# ---------------------------------------------------------------------------
# Payload builders
# ---------------------------------------------------------------------------

def agent_state_payload(
    agent_id: str,
    state: str,
    *,
    session_id: str | None = None,
    model: str | None = None,
) -> dict[str, Any]:
    d: dict[str, Any] = {"agentId": agent_id, "state": state}
    if session_id:
        d["sessionId"] = session_id
    if model:
        d["model"] = model
    return d


def presence_payload(
    *,
    online: bool = True,
    channels: list[str] | None = None,
    uptime_seconds: float | None = None,
) -> dict[str, Any]:
    d: dict[str, Any] = {"online": online}
    if channels is not None:
        d["channels"] = channels
    if uptime_seconds is not None:
        d["uptimeSeconds"] = uptime_seconds
    return d


def shutdown_payload(*, reason: str = "shutdown", grace_seconds: int = 5) -> dict[str, Any]:
    return {"reason": reason, "graceSeconds": grace_seconds, "timestamp": time.time()}


def health_payload(
    *,
    status: str = "ok",
    uptime_seconds: float = 0.0,
    connections: int = 0,
    agents_active: int = 0,
) -> dict[str, Any]:
    return {
        "status": status,
        "uptimeSeconds": uptime_seconds,
        "connections": connections,
        "agentsActive": agents_active,
    }


def heartbeat_payload(*, seq: int = 0) -> dict[str, Any]:
    return {"seq": seq, "timestamp": time.time()}


def cron_fired_payload(*, job_name: str, system_event: str = "") -> dict[str, Any]:
    return {"jobName": job_name, "systemEvent": system_event, "firedAt": time.time()}


def exec_approval_payload(
    *,
    approval_id: str,
    command: str,
    agent_id: str = "",
    session_id: str = "",
) -> dict[str, Any]:
    return {
        "approvalId": approval_id,
        "command": command,
        "agentId": agent_id,
        "sessionId": session_id,
        "requestedAt": time.time(),
    }


def update_available_payload(
    *,
    current_version: str,
    latest_version: str,
    url: str = "",
) -> dict[str, Any]:
    return {
        "currentVersion": current_version,
        "latestVersion": latest_version,
        "url": url,
    }


# ---------------------------------------------------------------------------
# Broadcast helpers
# ---------------------------------------------------------------------------

async def broadcast_agent_state(
    server: GatewayServer,
    agent_id: str,
    state: str,
    **kwargs: Any,
) -> None:
    await server.broadcast_event(EVENT_AGENT_STATE, agent_state_payload(agent_id, state, **kwargs))


async def broadcast_presence(server: GatewayServer, **kwargs: Any) -> None:
    await server.broadcast_event(EVENT_PRESENCE, presence_payload(**kwargs))


async def broadcast_shutdown(server: GatewayServer, **kwargs: Any) -> None:
    await server.broadcast_event(EVENT_SHUTDOWN, shutdown_payload(**kwargs))


async def broadcast_heartbeat(server: GatewayServer, seq: int = 0) -> None:
    await server.broadcast_event(EVENT_HEARTBEAT, heartbeat_payload(seq=seq))


async def broadcast_cron_fired(server: GatewayServer, job_name: str, system_event: str = "") -> None:
    await server.broadcast_event(EVENT_CRON_FIRED, cron_fired_payload(job_name=job_name, system_event=system_event))


async def broadcast_progress(server: GatewayServer, event: dict[str, Any]) -> None:
    await server.broadcast_event(EVENT_PROGRESS, event)
