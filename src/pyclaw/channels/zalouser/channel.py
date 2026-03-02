"""Zalo User channel -- personal account integration via zca-cli subprocess.

Spawns the ``zca-cli`` binary to send/receive messages from a personal
Zalo account. Communicates via the subprocess stdin/stdout (NDJSON).
"""

from __future__ import annotations

import asyncio
import json
import logging
import shutil
from typing import Any

from pyclaw.channels.base import ChannelMessage, ChannelPlugin, ChannelReply

logger = logging.getLogger(__name__)


class ZaloUserChannel(ChannelPlugin):
    """Zalo personal account integration via zca-cli bridge."""

    def __init__(
        self,
        zca_binary: str = "zca-cli",
        *,
        on_message: Any = None,
    ) -> None:
        self._zca_binary = zca_binary
        self._on_message = on_message
        self._proc: asyncio.subprocess.Process | None = None
        self._read_task: asyncio.Task[None] | None = None
        self._running = False

    @property
    def id(self) -> str:
        return "zalouser"

    async def start(self) -> None:
        binary = shutil.which(self._zca_binary) or self._zca_binary
        self._running = True
        self._proc = await asyncio.create_subprocess_exec(
            binary,
            "listen",
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        self._read_task = asyncio.create_task(self._read_loop())
        logger.info("ZaloUser channel started (binary: %s)", binary)

    async def stop(self) -> None:
        self._running = False
        if self._read_task and not self._read_task.done():
            self._read_task.cancel()
        if self._proc:
            self._proc.terminate()
            try:
                await asyncio.wait_for(self._proc.wait(), timeout=5)
            except TimeoutError:
                self._proc.kill()

    async def _read_loop(self) -> None:
        if not self._proc or not self._proc.stdout:
            return
        while self._running:
            try:
                line = await self._proc.stdout.readline()
                if not line:
                    break
                data = json.loads(line.decode("utf-8", errors="replace"))
                await self._handle_event(data)
            except asyncio.CancelledError:
                return
            except json.JSONDecodeError:
                continue
            except Exception:
                logger.error("ZaloUser read error", exc_info=True)

    async def _handle_event(self, data: dict[str, Any]) -> None:
        event_type = data.get("type", "")
        if event_type != "message":
            return

        sender_id = str(data.get("sender_id", "unknown"))
        text = data.get("text", "")
        if not text:
            return

        msg = ChannelMessage(
            channel="zalouser",
            sender_id=sender_id,
            text=text,
            raw=data,
        )

        if self._on_message:
            result = self._on_message(msg)
            if asyncio.iscoroutine(result):
                await result

    async def send_reply(self, reply: ChannelReply) -> None:
        if not self._proc or not self._proc.stdin:
            logger.warning("ZaloUser process not running")
            return

        recipient = reply.raw.get("sender_id", "") if reply.raw else ""
        payload = json.dumps({"action": "send", "to": recipient, "text": reply.text}) + "\n"
        self._proc.stdin.write(payload.encode("utf-8"))
        await self._proc.stdin.drain()
