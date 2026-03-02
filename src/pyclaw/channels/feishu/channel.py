"""Feishu/Lark channel plugin — WebSocket or webhook via Open Platform API.

Ported from ``extensions/feishu/``.
Requires ``requests`` or ``aiohttp`` for API calls.
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any

from pyclaw.channels.base import ChannelMessage, ChannelPlugin, ChannelReply

logger = logging.getLogger(__name__)


class FeishuChannel(ChannelPlugin):
    """Feishu/Lark channel using Open Platform API."""

    name = "feishu"

    def __init__(
        self,
        *,
        app_id: str = "",
        app_secret: str = "",
        verification_token: str = "",
        encrypt_key: str = "",
        webhook_port: int = 9000,
        connection_mode: str = "webhook",  # "webhook" | "websocket"
        domain: str = "feishu",  # "feishu" | "lark"
        allow_from: list[str] | None = None,
    ) -> None:
        self._app_id = app_id
        self._app_secret = app_secret
        self._verification_token = verification_token
        self._encrypt_key = encrypt_key
        self._webhook_port = webhook_port
        self._connection_mode = connection_mode
        self._domain = domain
        self._allow_from = set(allow_from) if allow_from else None
        self._handler: Any = None
        self._server: Any = None
        self._access_token: str = ""
        self._token_expires: float = 0

    @property
    def _api_base(self) -> str:
        return (
            "https://open.feishu.cn" if self._domain == "feishu" else "https://open.larksuite.com"
        )

    async def start(self) -> None:
        await self._refresh_token()

        if self._connection_mode == "webhook":
            await self._start_webhook()
        else:
            logger.warning("Feishu WebSocket mode not yet implemented; falling back to webhook")
            await self._start_webhook()

        logger.info(
            "Feishu channel started (mode=%s, domain=%s)", self._connection_mode, self._domain
        )

    async def _start_webhook(self) -> None:
        try:
            from aiohttp import web
        except ImportError:
            raise RuntimeError("aiohttp required: pip install aiohttp")

        app = web.Application()
        app.router.add_post("/feishu/webhook", self._handle_webhook)
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, "0.0.0.0", self._webhook_port)
        await site.start()
        self._server = runner

    async def stop(self) -> None:
        if self._server:
            await self._server.cleanup()
            self._server = None

    async def send(self, reply: ChannelReply) -> None:
        await self._ensure_token()
        await self._send_message(reply.recipient, reply.text)

    def on_message(self, handler: Any) -> None:
        self._handler = handler

    async def _handle_webhook(self, request: Any) -> Any:
        from aiohttp import web

        try:
            body = await request.json()
        except Exception:
            return web.Response(status=400)

        # URL verification challenge
        if body.get("type") == "url_verification":
            challenge = body.get("challenge", "")
            return web.json_response({"challenge": challenge})

        # Verify token
        token = body.get("token", "")
        if self._verification_token and token != self._verification_token:
            return web.Response(status=403)

        event = body.get("event", {})
        msg_type = event.get("message", {}).get("message_type", "")

        if msg_type != "text":
            return web.Response(status=200)

        content = json.loads(event.get("message", {}).get("content", "{}"))
        text = content.get("text", "").strip()

        sender = event.get("sender", {})
        sender_id = sender.get("sender_id", {}).get("open_id", "")
        sender_name = sender.get("sender_id", {}).get("name", "")

        if self._allow_from and sender_id not in self._allow_from:
            return web.Response(status=200)

        chat_id = event.get("message", {}).get("chat_id", "")
        chat_type = event.get("message", {}).get("chat_type", "")
        is_group = chat_type == "group"

        msg = ChannelMessage(
            channel="feishu",
            sender_id=sender_id,
            text=text,
            raw=body,
            is_group=is_group,
            group_id=chat_id if is_group else "",
            display_name=sender_name or sender_id,
        )

        if self._handler:
            await self._handler(msg)

        return web.Response(status=200)

    async def _refresh_token(self) -> None:
        try:
            import aiohttp
        except ImportError:
            return

        url = f"{self._api_base}/open-apis/auth/v3/tenant_access_token/internal"
        payload = {"app_id": self._app_id, "app_secret": self._app_secret}

        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    self._access_token = data.get("tenant_access_token", "")
                    self._token_expires = time.time() + data.get("expire", 7200) - 300

    async def _ensure_token(self) -> None:
        if time.time() >= self._token_expires:
            await self._refresh_token()

    async def _send_message(self, chat_id: str, text: str) -> None:
        try:
            import aiohttp
        except ImportError:
            return

        url = f"{self._api_base}/open-apis/im/v1/messages"
        headers = {
            "Authorization": f"Bearer {self._access_token}",
            "Content-Type": "application/json",
        }
        payload = {
            "receive_id": chat_id,
            "msg_type": "text",
            "content": json.dumps({"text": text}),
        }
        params = {"receive_id_type": "chat_id"}

        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, headers=headers, params=params) as resp:
                if resp.status >= 400:
                    logger.error("Feishu send error: %d", resp.status)
