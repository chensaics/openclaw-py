"""BlueBubbles channel plugin — HTTP webhook + REST API.

Ported from ``extensions/bluebubbles/``. Communicates with a BlueBubbles
server for iMessage access.
"""

from __future__ import annotations

import logging
from typing import Any

from pyclaw.channels.base import ChannelMessage, ChannelPlugin, ChannelReply

logger = logging.getLogger(__name__)


class BlueBubblesChannel(ChannelPlugin):
    """BlueBubbles iMessage channel via REST + webhook."""

    name = "bluebubbles"

    def __init__(
        self,
        *,
        server_url: str = "http://localhost:1234",
        password: str = "",
        webhook_port: int = 9001,
        allow_from: list[str] | None = None,
    ) -> None:
        self._server_url = server_url.rstrip("/")
        self._password = password
        self._webhook_port = webhook_port
        self._allow_from = set(allow_from) if allow_from else None
        self._handler: Any = None
        self._server: Any = None

    async def start(self) -> None:
        try:
            from aiohttp import web
        except ImportError:
            raise RuntimeError("aiohttp required: pip install aiohttp")

        app = web.Application()
        app.router.add_post("/bluebubbles/webhook", self._handle_webhook)
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, "0.0.0.0", self._webhook_port)
        await site.start()
        self._server = runner
        logger.info("BlueBubbles webhook on port %d", self._webhook_port)

    async def stop(self) -> None:
        if self._server:
            await self._server.cleanup()
            self._server = None

    async def send(self, reply: ChannelReply) -> None:
        await self._send_message(reply.recipient or "", reply.text, reply.media_url)

    def on_message(self, handler: Any) -> None:
        self._handler = handler

    async def _handle_webhook(self, request: Any) -> Any:
        from aiohttp import web

        try:
            body = await request.json()
        except Exception:
            return web.Response(status=400)

        event_type = body.get("type", "")
        if event_type != "new-message":
            return web.Response(status=200)

        data = body.get("data", {})
        if data.get("isFromMe"):
            return web.Response(status=200)

        sender = data.get("handle", {}).get("address", "")
        text = data.get("text", "").strip()
        chat_guid = data.get("chats", [{}])[0].get("guid", "") if data.get("chats") else ""
        is_group = data.get("isGroup", False)

        if self._allow_from and sender not in self._allow_from:
            return web.Response(status=200)

        sender_name = data.get("handle", {}).get("displayName") or sender
        msg = ChannelMessage(
            channel_id="bluebubbles",
            sender_id=sender,
            sender_name=sender_name,
            text=text,
            chat_id=chat_guid or sender,
            raw=body,
            is_group=is_group,
            group_id=chat_guid if is_group else "",
            display_name=sender_name,
        )

        if self._handler:
            await self._handler(msg)

        return web.Response(status=200)

    async def _send_message(
        self,
        chat_guid: str,
        text: str,
        media_url: str | None = None,
    ) -> None:
        try:
            import aiohttp
        except ImportError:
            return

        url = f"{self._server_url}/api/v1/message/text"
        headers = {"Content-Type": "application/json"}
        payload: dict[str, Any] = {
            "chatGuid": chat_guid,
            "message": text,
            "method": "private-api",
        }
        params = {"password": self._password}

        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, headers=headers, params=params) as resp:
                if resp.status >= 400:
                    logger.error("BlueBubbles send error: %d", resp.status)
