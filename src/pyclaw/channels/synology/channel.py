"""Synology Chat channel -- incoming/outgoing webhook integration.

Uses aiohttp for webhook reception and HTTP POST for outgoing messages
to the Synology Chat incoming webhook URL.
"""

from __future__ import annotations

import logging
from typing import Any

import aiohttp
from aiohttp import web

from pyclaw.channels.base import ChannelMessage, ChannelPlugin, ChannelReply

logger = logging.getLogger(__name__)


class SynologyChannel(ChannelPlugin):
    """Synology Chat integration via incoming/outgoing webhooks."""

    def __init__(
        self,
        incoming_url: str,
        outgoing_token: str,
        *,
        port: int = 8067,
        on_message: Any = None,
    ) -> None:
        self._incoming_url = incoming_url
        self._outgoing_token = outgoing_token
        self._port = port
        self._on_message = on_message
        self._app: web.Application | None = None
        self._runner: web.AppRunner | None = None

    @property
    def id(self) -> str:
        return "synology"

    async def start(self) -> None:
        self._app = web.Application()
        self._app.router.add_post("/synology/webhook", self._handle_webhook)
        self._runner = web.AppRunner(self._app)
        await self._runner.setup()
        site = web.TCPSite(self._runner, "0.0.0.0", self._port)
        await site.start()
        logger.info("Synology Chat webhook listening on port %d", self._port)

    async def stop(self) -> None:
        if self._runner:
            await self._runner.cleanup()

    async def _handle_webhook(self, request: web.Request) -> web.Response:
        try:
            data = await request.json()
        except Exception:
            return web.Response(status=400, text="Invalid JSON")

        token = data.get("token", "")
        if token != self._outgoing_token:
            return web.Response(status=403, text="Invalid token")

        user_id = str(data.get("user_id", data.get("username", "unknown")))
        text = data.get("text", "")
        if not text:
            return web.Response(status=200, text="ok")

        msg = ChannelMessage(
            channel="synology",
            sender_id=user_id,
            text=text,
            raw=data,
        )

        if self._on_message:
            import asyncio

            result = self._on_message(msg)
            if asyncio.iscoroutine(result):
                await result

        return web.Response(status=200, text="ok")

    async def send_reply(self, reply: ChannelReply) -> None:
        payload = {"text": reply.text}
        async with (
            aiohttp.ClientSession() as session,
            session.post(
                self._incoming_url,
                json=payload,
                headers={"Content-Type": "application/json"},
            ) as resp,
        ):
            if resp.status != 200:
                logger.warning("Synology send failed: %d", resp.status)
