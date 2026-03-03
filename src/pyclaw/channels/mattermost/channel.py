"""Mattermost channel -- webhook + WebSocket event stream.

Receives messages via Mattermost WebSocket API and sends replies via
the REST API (``/api/v4/posts``).
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

import aiohttp

from pyclaw.channels.base import ChannelMessage, ChannelPlugin, ChannelReply

logger = logging.getLogger(__name__)


class MattermostChannel(ChannelPlugin):
    """Mattermost integration using REST API + WebSocket events."""

    def __init__(
        self,
        server_url: str,
        token: str,
        *,
        on_message: Any = None,
    ) -> None:
        self._server_url = server_url.rstrip("/")
        self._token = token
        self._on_message = on_message
        self._ws_task: asyncio.Task[None] | None = None
        self._bot_user_id: str = ""
        self._running = False

    @property
    def id(self) -> str:
        return "mattermost"

    async def start(self) -> None:
        self._running = True
        await self._fetch_bot_user()
        self._ws_task = asyncio.create_task(self._ws_loop())
        logger.info("Mattermost channel started (server: %s)", self._server_url)

    async def stop(self) -> None:
        self._running = False
        if self._ws_task and not self._ws_task.done():
            self._ws_task.cancel()

    async def _fetch_bot_user(self) -> None:
        async with (
            aiohttp.ClientSession() as session,
            session.get(
                f"{self._server_url}/api/v4/users/me",
                headers=self._headers(),
            ) as resp,
        ):
            if resp.status == 200:
                data = await resp.json()
                self._bot_user_id = data.get("id", "")
            else:
                logger.warning("Failed to fetch bot user: %d", resp.status)

    async def _ws_loop(self) -> None:
        ws_url = self._server_url.replace("https://", "wss://").replace("http://", "ws://")
        ws_url += "/api/v4/websocket"

        while self._running:
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.ws_connect(ws_url) as ws:
                        auth_msg = json.dumps(
                            {
                                "seq": 1,
                                "action": "authentication_challenge",
                                "data": {"token": self._token},
                            }
                        )
                        await ws.send_str(auth_msg)

                        async for raw_msg in ws:
                            if raw_msg.type == aiohttp.WSMsgType.TEXT:
                                await self._handle_ws_event(json.loads(raw_msg.data))
                            elif raw_msg.type in (
                                aiohttp.WSMsgType.CLOSED,
                                aiohttp.WSMsgType.ERROR,
                            ):
                                break
            except asyncio.CancelledError:
                return
            except Exception:
                logger.error("Mattermost WebSocket error, reconnecting...", exc_info=True)
                await asyncio.sleep(5)

    async def _handle_ws_event(self, event: dict[str, Any]) -> None:
        if event.get("event") != "posted":
            return

        post_data = event.get("data", {})
        post_json = post_data.get("post", "")
        if isinstance(post_json, str):
            try:
                post = json.loads(post_json)
            except json.JSONDecodeError:
                return
        else:
            post = post_json

        user_id = post.get("user_id", "")
        if user_id == self._bot_user_id:
            return

        text = post.get("message", "")
        channel_id = post.get("channel_id", "")
        if not text:
            return

        msg = ChannelMessage(
            channel_id="mattermost",
            sender_id=user_id,
            sender_name=user_id,
            text=text,
            chat_id=channel_id,
            raw={"post": post, "channel_id": channel_id},
        )

        if self._on_message:
            result = self._on_message(msg)
            if asyncio.iscoroutine(result):
                await result

    async def send_reply(self, reply: ChannelReply) -> None:
        channel_id = reply.raw.get("channel_id", "") if reply.raw else ""
        if not channel_id:
            logger.warning("No channel_id in reply context")
            return

        payload = {"channel_id": channel_id, "message": reply.text}
        async with (
            aiohttp.ClientSession() as session,
            session.post(
                f"{self._server_url}/api/v4/posts",
                json=payload,
                headers=self._headers(),
            ) as resp,
        ):
            if resp.status not in (200, 201):
                logger.warning("Mattermost send failed: %d", resp.status)

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._token}",
            "Content-Type": "application/json",
        }
