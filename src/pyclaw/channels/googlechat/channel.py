"""Google Chat channel plugin — HTTP webhook + REST API with OAuth.

Ported from ``extensions/googlechat/``.
"""

from __future__ import annotations

import logging
from typing import Any

from pyclaw.channels.base import ChannelMessage, ChannelPlugin, ChannelReply

logger = logging.getLogger(__name__)


class GoogleChatChannel(ChannelPlugin):
    """Google Chat channel via webhook and REST API."""

    name = "googlechat"

    def __init__(
        self,
        *,
        service_account_key: str = "",
        webhook_port: int = 9002,
        allow_from: list[str] | None = None,
    ) -> None:
        self._service_account_key = service_account_key
        self._webhook_port = webhook_port
        self._allow_from = set(allow_from) if allow_from else None
        self._handler: Any = None
        self._server: Any = None
        self._access_token: str = ""

    async def start(self) -> None:
        try:
            from aiohttp import web
        except ImportError:
            raise RuntimeError("aiohttp required: pip install aiohttp")

        app = web.Application()
        app.router.add_post("/googlechat/webhook", self._handle_webhook)
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, "0.0.0.0", self._webhook_port)
        await site.start()
        self._server = runner
        logger.info("Google Chat webhook on port %d", self._webhook_port)

    async def stop(self) -> None:
        if self._server:
            await self._server.cleanup()
            self._server = None

    async def send(self, reply: ChannelReply) -> None:
        await self._send_message(reply.recipient or "", reply.text)

    def on_message(self, handler: Any) -> None:
        self._handler = handler

    async def _handle_webhook(self, request: Any) -> Any:
        from aiohttp import web

        try:
            body = await request.json()
        except Exception:
            return web.Response(status=400)

        event_type = body.get("type", "")
        if event_type != "MESSAGE":
            return web.Response(status=200)

        message = body.get("message", {})
        sender = message.get("sender", {})
        sender_name = sender.get("displayName", "")
        sender_email = sender.get("email", "")
        text = message.get("argumentText", message.get("text", "")).strip()

        space = body.get("space", {})
        space_type = space.get("type", "")
        space_name = space.get("name", "")
        is_group = space_type != "DM"

        sender_id = sender_email or sender.get("name", "")
        if self._allow_from and sender_id not in self._allow_from:
            return web.Response(status=200)

        thread_name = message.get("thread", {}).get("name", "")

        msg = ChannelMessage(
            channel_id="googlechat",
            sender_id=sender_id,
            sender_name=sender_name or sender_id,
            text=text,
            chat_id=space_name if is_group else sender_id,
            raw=body,
            is_group=is_group,
            group_id=space_name if is_group else "",
            display_name=sender_name,
        )

        if self._handler:
            await self._handler(msg)

        return web.Response(status=200)

    async def _send_message(self, space_name: str, text: str) -> None:
        try:
            import aiohttp
        except ImportError:
            return

        url = f"https://chat.googleapis.com/v1/{space_name}/messages"
        headers = {
            "Authorization": f"Bearer {self._access_token}",
            "Content-Type": "application/json",
        }
        payload = {"text": text}

        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, headers=headers) as resp:
                if resp.status >= 400:
                    logger.error("Google Chat send error: %d", resp.status)
