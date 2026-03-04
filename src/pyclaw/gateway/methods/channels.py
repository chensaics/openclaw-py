"""Gateway methods: channels.list/status — channel management.

When no ChannelManager is injected at runtime, falls back to reading
the local config file so that the UI always receives a meaningful
channel list (with catalog metadata and capability flags).
"""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pyclaw.gateway.server import GatewayConnection

logger = logging.getLogger("pyclaw.gateway.channels")

_channel_manager: Any = None
_config_path: str | None = None

# Per-channel runtime metrics (populated by channel_health or message dispatch)
_channel_metrics: dict[str, dict[str, Any]] = {}


def set_channel_manager(manager: Any) -> None:
    """Set the channel manager reference for gateway methods."""
    global _channel_manager
    _channel_manager = manager


def set_config_path(path: str | None) -> None:
    """Set the config path for fallback channel discovery."""
    global _config_path
    _config_path = path


def record_channel_metric(channel_id: str, event: str) -> None:
    """Record a metric event for a channel (msg_sent, msg_failed, connect, disconnect)."""
    if channel_id not in _channel_metrics:
        _channel_metrics[channel_id] = {
            "messages_sent": 0,
            "messages_failed": 0,
            "last_message_at": None,
            "connected_since": None,
        }
    m = _channel_metrics[channel_id]
    now = time.time()
    if event == "msg_sent":
        m["messages_sent"] += 1
        m["last_message_at"] = now
    elif event == "msg_failed":
        m["messages_failed"] += 1
    elif event == "connect":
        m["connected_since"] = now
    elif event == "disconnect":
        m["connected_since"] = None


def _get_catalog_entry(channel_type: str) -> dict[str, Any]:
    """Return catalog metadata for a channel type."""
    try:
        from pyclaw.channels.plugins.catalog import BUILTIN_CATALOG
        entry = BUILTIN_CATALOG.get(channel_type)
        if entry:
            spec = entry.action_spec
            return {
                "display_name": entry.display_name,
                "category": entry.category.value,
                "color": entry.color,
                "icon": entry.icon,
                "capabilities": {
                    "typing": spec.supports_typing,
                    "reactions": spec.supports_reactions,
                    "threads": spec.supports_threads,
                    "editing": spec.supports_editing,
                    "deletion": spec.supports_deletion,
                    "buttons": spec.supports_buttons,
                    "pins": spec.supports_pins,
                    "read_receipts": spec.supports_read_receipts,
                },
                "media_limits": {
                    "max_message_length": entry.media_limits.max_message_length,
                    "max_file_size_mb": entry.media_limits.max_file_size_mb,
                },
                "supports_dm": entry.supports_dm,
                "supports_groups": entry.supports_groups,
            }
    except Exception:
        pass
    return {}


def _channels_from_config() -> list[dict[str, Any]]:
    """Read configured channels from the local config file as fallback."""
    if not _config_path:
        return []
    try:
        from pyclaw.config.io import load_config
        from pathlib import Path
        config = load_config(Path(_config_path))
        ch_cfg = config.channels
        if not ch_cfg:
            return []

        results: list[dict[str, Any]] = []
        cfg_dict = ch_cfg.model_dump(by_alias=True, exclude_none=True)
        for name, val in cfg_dict.items():
            if name == "defaults" or not isinstance(val, dict):
                continue
            enabled = val.get("enabled", True)
            entry_meta = _get_catalog_entry(name)
            info: dict[str, Any] = {
                "id": name,
                "name": entry_meta.get("display_name", name.title()),
                "running": False,
                "enabled": enabled,
                "status": "configured" if enabled else "disabled",
                "source": "config",
            }
            info.update(entry_meta)
            results.append(info)
        return results
    except Exception:
        logger.debug("Config-based channel discovery failed", exc_info=True)
        return []


async def handle_channels_list(params: dict[str, Any] | None, conn: Any) -> None:
    """List registered channels and their status with catalog metadata."""
    channels: list[dict[str, Any]] = []

    if _channel_manager:
        ch_list = (
            _channel_manager.list_channels()
            if hasattr(_channel_manager, "list_channels")
            else []
        )
        seen: set[str] = set()
        for ch_info in ch_list:
            cid = ch_info.get("id", "")
            entry_meta = _get_catalog_entry(cid)
            merged: dict[str, Any] = {
                "id": cid,
                "name": ch_info.get("name", cid),
                "running": ch_info.get("running", False),
                "enabled": True,
                "status": "running" if ch_info.get("running") else "stopped",
                "source": "runtime",
            }
            merged.update(entry_meta)
            # Overlay runtime-detected capabilities on top of catalog
            ch_plugin = (
                _channel_manager.get(cid)
                if hasattr(_channel_manager, "get")
                else None
            )
            if ch_plugin:
                try:
                    from pyclaw.channels.base import detect_capabilities
                    runtime_caps = detect_capabilities(ch_plugin).to_dict()
                    catalog_caps = merged.get("capabilities", {})
                    for k, v in runtime_caps.items():
                        if v:
                            catalog_caps[k] = True
                    merged["capabilities"] = catalog_caps
                except Exception:
                    pass
            metrics = _channel_metrics.get(cid)
            if metrics:
                merged["metrics"] = dict(metrics)
            channels.append(merged)
            seen.add(cid)

        # Merge config-only channels not yet started at runtime
        for cfg_ch in _channels_from_config():
            if cfg_ch["id"] not in seen:
                channels.append(cfg_ch)
    else:
        channels = _channels_from_config()

    await conn.send_ok("channels.list", {"channels": channels})


async def handle_channels_status(params: dict[str, Any] | None, conn: Any) -> None:
    """Get detailed status for a specific channel."""
    p = params or {}
    channel_id = p.get("channel_id", p.get("channelId", ""))

    entry_meta = _get_catalog_entry(channel_id)
    metrics = _channel_metrics.get(channel_id)

    if _channel_manager:
        ch = (
            _channel_manager.get(channel_id)
            if hasattr(_channel_manager, "get")
            else None
        )
        if ch:
            result: dict[str, Any] = {
                "channel_id": ch.id,
                "name": ch.name,
                "running": ch.is_running,
                "status": "running" if ch.is_running else "stopped",
            }
            result.update(entry_meta)
            if metrics:
                result["metrics"] = dict(metrics)
            await conn.send_ok("channels.status", result)
            return

    for cfg_ch in _channels_from_config():
        if cfg_ch["id"] == channel_id:
            if metrics:
                cfg_ch["metrics"] = dict(metrics)
            await conn.send_ok("channels.status", cfg_ch)
            return

    await conn.send_error(
        "channels.status",
        "not_found",
        f"Channel '{channel_id}' not found",
    )


def create_channels_handlers() -> dict[str, Any]:
    return {
        "channels.list": handle_channels_list,
        "channels.status": handle_channels_status,
    }
