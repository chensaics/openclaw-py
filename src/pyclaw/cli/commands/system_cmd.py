"""CLI system commands (event, heartbeat, presence) — RPC-first with explicit fallback warnings.

Phase 56: CLI now tells the user explicitly when it falls back to local execution
instead of silently degrading.
"""

from __future__ import annotations

import json
import time
from typing import Any

import typer

from pyclaw.infra.system_events import (
    EventBus,
    EventType,
    PresenceManager,
    PresenceState,
    SystemEvent,
)

_BUS = EventBus()
_PRESENCE = PresenceManager(idle_timeout_s=300.0)
_HEARTBEAT_ENABLED = True
_LAST_HEARTBEAT_AT = 0.0

_FALLBACK_MSG = "[warn] Gateway unreachable — using local-only fallback."


def _try_rpc(method: str, params: dict[str, Any] | None = None) -> dict[str, Any] | None:
    """Attempt a Gateway RPC call; returns None if unreachable."""
    try:
        import asyncio

        from pyclaw.cli.commands.gateway_cmd import _default_gateway_url, _rpc_call

        gw_url = _default_gateway_url()
        return asyncio.run(
            _rpc_call(
                gw_url,
                method=method,
                params=params or {},
                token=None,
                password=None,
                timeout_s=5.0,
            )
        )
    except Exception:
        return None


def system_event_command(*, text: str, mode: str = "next-heartbeat", output_json: bool = False) -> None:
    """Enqueue a system event via RPC (fallback: local EventBus)."""
    global _LAST_HEARTBEAT_AT

    rpc_result = _try_rpc("system.event", {"text": text, "mode": mode})
    if rpc_result is not None:
        if output_json:
            typer.echo(json.dumps(rpc_result, ensure_ascii=False))
        else:
            typer.echo(f"System event queued via Gateway ({mode}).")
        return

    typer.echo(_FALLBACK_MSG, err=True)

    event = SystemEvent(
        event_type=EventType.HEALTH_CHECK,
        source="pyclaw",
        data={"text": text, "mode": mode},
    )
    _BUS.emit(event)
    _PRESENCE.heartbeat("system")
    if mode == "now" and _HEARTBEAT_ENABLED:
        _LAST_HEARTBEAT_AT = time.time()

    payload = {
        "ok": True,
        "eventType": event.event_type.value,
        "mode": mode,
        "heartbeatTriggered": bool(mode == "now" and _HEARTBEAT_ENABLED),
        "source": "local",
    }
    if output_json:
        typer.echo(json.dumps(payload, ensure_ascii=False))
        return
    typer.echo(f"System event queued locally ({mode}).")


def system_heartbeat_last_command(*, output_json: bool = False) -> None:
    """Show latest heartbeat timestamp (RPC first, local fallback)."""
    rpc_result = _try_rpc("system.heartbeat.last")
    if rpc_result is not None:
        if output_json:
            typer.echo(json.dumps(rpc_result, ensure_ascii=False))
        else:
            ts = rpc_result.get("lastHeartbeatAt")
            typer.echo(f"Last heartbeat: {int(ts)}" if ts else "No heartbeat yet.")
        return

    typer.echo(_FALLBACK_MSG, err=True)

    payload = {
        "enabled": _HEARTBEAT_ENABLED,
        "lastHeartbeatAt": _LAST_HEARTBEAT_AT or None,
        "source": "local",
    }
    if output_json:
        typer.echo(json.dumps(payload, ensure_ascii=False))
        return
    if _LAST_HEARTBEAT_AT:
        typer.echo(f"Last heartbeat (local): {int(_LAST_HEARTBEAT_AT)}")
    else:
        typer.echo("No heartbeat yet (local).")


def system_heartbeat_enable_command(*, output_json: bool = False) -> None:
    """Enable heartbeat processing."""
    global _HEARTBEAT_ENABLED
    _HEARTBEAT_ENABLED = True
    _PRESENCE.update("system", PresenceState.ONLINE)
    _emit_enabled_payload(output_json=output_json)


def system_heartbeat_disable_command(*, output_json: bool = False) -> None:
    """Disable heartbeat processing."""
    global _HEARTBEAT_ENABLED
    _HEARTBEAT_ENABLED = False
    _PRESENCE.update("system", PresenceState.IDLE)
    _emit_enabled_payload(output_json=output_json)


def system_presence_command(*, output_json: bool = False) -> None:
    """List tracked presence entries (RPC first, local fallback)."""
    rpc_result = _try_rpc("system.presence")
    if rpc_result is not None:
        if output_json:
            typer.echo(json.dumps(rpc_result, ensure_ascii=False))
        else:
            entries = rpc_result.get("entries", [])
            if not entries:
                typer.echo("No presence entries.")
            else:
                for entry in entries:
                    typer.echo(f"{entry.get('componentId', '?')}: {entry.get('state', '?')}")
        return

    typer.echo(_FALLBACK_MSG, err=True)

    _PRESENCE.check_idle()
    entries = [
        {
            "componentId": cid,
            "state": info.state.value,
            "lastSeenAt": info.last_seen_at,
        }
        for cid, info in _PRESENCE._entries.items()
    ]
    if output_json:
        typer.echo(json.dumps({"entries": entries, "source": "local"}, ensure_ascii=False))
        return
    if not entries:
        typer.echo("No presence entries (local).")
        return
    for entry in entries:
        typer.echo(f"{entry['componentId']}: {entry['state']}")


def _emit_enabled_payload(*, output_json: bool) -> None:
    payload = {"enabled": _HEARTBEAT_ENABLED}
    if output_json:
        typer.echo(json.dumps(payload, ensure_ascii=False))
        return
    typer.echo(f"Heartbeat {'enabled' if _HEARTBEAT_ENABLED else 'disabled'}.")
