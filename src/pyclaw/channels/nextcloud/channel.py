"""Nextcloud Talk channel -- webhook + polling integration.

Polls the Nextcloud Talk API for new messages and sends replies via
``/ocs/v2.php/apps/spreed/api/v1/chat/{token}``.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import aiohttp

from pyclaw.channels.base import ChannelMessage, ChannelPlugin, ChannelReply

logger = logging.getLogger(__name__)


class NextcloudChannel(ChannelPlugin):
    """Nextcloud Talk integration via REST API polling."""

    def __init__(
        self,
        server_url: str,
        username: str,
        password: str,
        room_token: str,
        *,
        poll_interval: float = 5.0,
        on_message: Any = None,
    ) -> None:
        self._server_url = server_url.rstrip("/")
        self._username = username
        self._password = password
        self._room_token = room_token
        self._poll_interval = poll_interval
        self._on_message = on_message
        self._poll_task: asyncio.Task[None] | None = None
        self._running = False
        self._last_known_id = 0

    @property
    def id(self) -> str:
        return "nextcloud"

    async def start(self) -> None:
        self._running = True
        self._poll_task = asyncio.create_task(self._poll_loop())
        logger.info("Nextcloud Talk channel started (room: %s)", self._room_token)

    async def stop(self) -> None:
        self._running = False
        if self._poll_task and not self._poll_task.done():
            self._poll_task.cancel()

    async def _poll_loop(self) -> None:
        while self._running:
            try:
                await self._poll_messages()
            except asyncio.CancelledError:
                return
            except Exception:
                logger.error("Nextcloud poll error", exc_info=True)
            await asyncio.sleep(self._poll_interval)

    async def _poll_messages(self) -> None:
        url = (
            f"{self._server_url}/ocs/v2.php/apps/spreed/api/v1/chat/{self._room_token}"
            f"?lookIntoFuture=1&limit=50&lastKnownMessageId={self._last_known_id}"
            f"&timeout=30"
        )
        auth = aiohttp.BasicAuth(self._username, self._password)
        headers = {"OCS-APIRequest": "true", "Accept": "application/json"}

        async with aiohttp.ClientSession(auth=auth) as session:
            async with session.get(url, headers=headers) as resp:
                if resp.status != 200:
                    return
                data = await resp.json()

        messages = data.get("ocs", {}).get("data", [])
        for msg_data in messages:
            msg_id = msg_data.get("id", 0)
            if msg_id <= self._last_known_id:
                continue
            self._last_known_id = msg_id

            actor_type = msg_data.get("actorType", "")
            if actor_type == "bots":
                continue

            text = msg_data.get("message", "")
            sender_id = msg_data.get("actorId", "unknown")
            if not text:
                continue

            msg = ChannelMessage(
                channel="nextcloud",
                sender_id=sender_id,
                text=text,
                raw=msg_data,
            )

            if self._on_message:
                result = self._on_message(msg)
                if asyncio.iscoroutine(result):
                    await result

    async def send_reply(self, reply: ChannelReply) -> None:
        url = f"{self._server_url}/ocs/v2.php/apps/spreed/api/v1/chat/{self._room_token}"
        auth = aiohttp.BasicAuth(self._username, self._password)
        headers = {"OCS-APIRequest": "true", "Content-Type": "application/json"}
        payload = {"message": reply.text}

        async with aiohttp.ClientSession(auth=auth) as session:
            async with session.post(url, json=payload, headers=headers) as resp:
                if resp.status not in (200, 201):
                    logger.warning("Nextcloud send failed: %d", resp.status)
