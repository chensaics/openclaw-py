"""MCP config watcher — hot-reload MCP clients when configuration changes."""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
from collections.abc import Callable
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

ConfigLoader = Callable[[], dict[str, Any]]


class McpConfigWatcher:
    """Watches MCP configuration for changes and reconnects affected clients.

    Polls the config file at a fixed interval, compares the MCP section hash,
    and triggers reconnection when changes are detected.
    """

    def __init__(
        self,
        *,
        registry: Any,
        config_path: Path,
        config_loader: ConfigLoader,
        poll_interval_s: float = 5.0,
    ) -> None:
        self._registry = registry
        self._config_path = config_path
        self._config_loader = config_loader
        self._poll_interval = poll_interval_s
        self._last_hash: str = ""
        self._task: asyncio.Task[None] | None = None

    async def start(self) -> None:
        self._last_hash = self._compute_hash()
        self._task = asyncio.ensure_future(self._poll_loop())
        logger.debug("MCP config watcher started (interval=%.1fs)", self._poll_interval)

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        logger.debug("MCP config watcher stopped")

    def _compute_hash(self) -> str:
        try:
            if not self._config_path.is_file():
                return ""
            raw = json.loads(self._config_path.read_text(encoding="utf-8"))
            mcp_section = raw.get("tools", {}).get("mcpServers", {})
            content = json.dumps(mcp_section, sort_keys=True)
            return hashlib.sha256(content.encode()).hexdigest()
        except Exception:
            return ""

    async def _poll_loop(self) -> None:
        while True:
            try:
                await asyncio.sleep(self._poll_interval)
                current_hash = self._compute_hash()

                if current_hash and current_hash != self._last_hash:
                    logger.info("MCP config changed, reconnecting servers...")
                    self._last_hash = current_hash
                    await self._reload()
            except asyncio.CancelledError:
                break
            except Exception:
                logger.exception("MCP config watcher error")

    async def _reload(self) -> None:
        try:
            await self._registry.disconnect_all()

            config = self._config_loader()
            mcp_servers = config.get("tools", {}).get("mcpServers", {})
            if mcp_servers:
                await self._registry.connect_all(mcp_servers)
                logger.info(
                    "MCP servers reloaded: %d servers, %d tools",
                    self._registry.server_count,
                    self._registry.tool_count,
                )
            else:
                logger.info("MCP config cleared, all servers disconnected")
        except Exception:
            logger.exception("MCP reload failed")
