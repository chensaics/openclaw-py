"""Gateway methods: channels.list/status — channel management."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pyclaw.gateway.server import GatewayConnection


# Module-level reference set by gateway startup
_channel_manager: Any = None


def set_channel_manager(manager: Any) -> None:
    """Set the channel manager reference for gateway methods."""
    global _channel_manager
    _channel_manager = manager


async def handle_channels_list(conn: GatewayConnection, params: dict[str, Any]) -> dict[str, Any]:
    """List registered channels and their status."""
    if not _channel_manager:
        return {"channels": []}

    channels: list[dict[str, Any]] = []
    for channel in _channel_manager.channels:
        channels.append({
            "id": channel.id,
            "name": channel.name,
            "running": channel.is_running,
        })

    return {"channels": channels}


async def handle_channels_status(conn: GatewayConnection, params: dict[str, Any]) -> dict[str, Any]:
    """Get detailed status for a specific channel."""
    channel_id = params.get("channel_id", "")
    if not _channel_manager:
        return {"error": "No channel manager"}

    for channel in _channel_manager.channels:
        if channel.id == channel_id:
            return {
                "channel_id": channel.id,
                "name": channel.name,
                "running": channel.is_running,
            }

    return {"error": f"Channel '{channel_id}' not found"}


def create_channels_handlers() -> dict[str, Any]:
    return {
        "channels.list": handle_channels_list,
        "channels.status": handle_channels_status,
    }
