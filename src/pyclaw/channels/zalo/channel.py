"""Zalo Bot channel -- Zalo Official Account API.

Receives messages via webhook and sends replies via Zalo OA Send API.
Requires OA access token from Zalo Business.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import aiohttp
from aiohttp import web

from pyclaw.channels.base import ChannelMessage, ChannelPlugin, ChannelReply

logger = logging.getLogger(__name__)

ZALO_API_BASE = "https://openapi.zalo.me/v3.0/oa"


class ZaloChannel(ChannelPlugin):
    """Zalo Bot integration via OA API."""

    def __init__(
        self,
        access_token: str,
        webhook_secret: str = "",
        *,
        port: int = 8068,
        on_message: Any = None,
    ) -> None:
        self._access_token = access_token
        self._webhook_secret = webhook_secret
        self._port = port
        self._on_message = on_message
        self._runner: web.AppRunner | None = None

    @property
    def id(self) -> str:
        return "zalo"

    async def start(self) -> None:
        app = web.Application()
        app.router.add_post("/zalo/webhook", self._handle_webhook)
        self._runner = web.AppRunner(app)
        await self._runner.setup()
        site = web.TCPSite(self._runner, "0.0.0.0", self._port)
        await site.start()
        logger.info("Zalo webhook listening on port %d", self._port)

    async def stop(self) -> None:
        if self._runner:
            await self._runner.cleanup()

    async def _handle_webhook(self, request: web.Request) -> web.Response:
        try:
            data = await request.json()
        except Exception:
            return web.Response(status=400)

        event_name = data.get("event_name", "")
        if event_name != "user_send_text":
            return web.Response(status=200, text="ok")

        sender = data.get("sender", {})
        sender_id = sender.get("id", "unknown")
        message = data.get("message", {})
        text = message.get("text", "")
        if not text:
            return web.Response(status=200, text="ok")

        msg = ChannelMessage(
            channel="zalo",
            sender_id=str(sender_id),
            text=text,
            raw=data,
        )

        if self._on_message:
            result = self._on_message(msg)
            if asyncio.iscoroutine(result):
                await result

        return web.Response(status=200, text="ok")

    async def send_reply(self, reply: ChannelReply) -> None:
        recipient_id = reply.raw.get("sender", {}).get("id", "") if reply.raw else ""
        if not recipient_id:
            logger.warning("No recipient for Zalo reply")
            return

        payload = {
            "recipient": {"user_id": recipient_id},
            "message": {"text": reply.text},
        }
        headers = {
            "Content-Type": "application/json",
            "access_token": self._access_token,
        }

        async with (
            aiohttp.ClientSession() as session,
            session.post(
                f"{ZALO_API_BASE}/message/text",
                json=payload,
                headers=headers,
            ) as resp,
        ):
            if resp.status != 200:
                logger.warning("Zalo send failed: %d", resp.status)
