"""Feishu/Lark channel plugin — WebSocket or webhook via Open Platform API.

Ported from ``extensions/feishu/``.
Requires ``requests`` or ``aiohttp`` for API calls.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
import urllib.parse
from typing import Any

from pyclaw.channels.base import ChannelMessage, ChannelPlugin, ChannelReply
from pyclaw.channels.feishu.messages import parse_feishu_message
from pyclaw.channels.feishu.routing import (
    FeishuRoutingConfig,
    resolve_feishu_session_key,
    is_sender_allowed_in_group,
    resolve_reply_params,
)

logger = logging.getLogger(__name__)

DEDUP_TTL_SEC = 300  # 5 minutes


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
        routing: dict[str, Any] | None = None,
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
        self._routing_config = (
            FeishuRoutingConfig.from_dict(routing) if routing else FeishuRoutingConfig()
        )
        self._dedup_cache: dict[str, float] = {}
        self._dedup_lock = asyncio.Lock()

    @property
    def id(self) -> str:
        return "feishu"

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

    async def send_reply(self, reply: ChannelReply) -> None:
        await self._ensure_token()
        await self._send_message(reply)

    def on_message(self, handler: Any) -> None:
        super().on_message(handler)
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
        message = event.get("message", {})
        if not message:
            return web.Response(status=200)

        message_id = message.get("message_id", "")
        msg_type = message.get("message_type", "")

        # Support all message types: text, post, share_chat, merge_forward, image, audio, file, sticker
        parsed = parse_feishu_message(body)
        if not parsed.text.strip() and parsed.message_type not in (
            "image",
            "audio",
            "media",
            "file",
            "sticker",
        ):
            return web.Response(status=200)

        # Message dedup: skip if seen in last 5 minutes
        async with self._dedup_lock:
            now = time.time()
            if message_id in self._dedup_cache and self._dedup_cache[message_id] > now:
                return web.Response(status=200)
            self._dedup_cache[message_id] = now + DEDUP_TTL_SEC
            # Evict expired entries
            self._dedup_cache = {k: v for k, v in self._dedup_cache.items() if v > now}

        # Global allow_from filter
        if self._allow_from and parsed.sender_id not in self._allow_from:
            return web.Response(status=200)

        # Group sender filtering via routing config
        if parsed.chat_type == "group":
            if not is_sender_allowed_in_group(
                parsed.sender_id, parsed.chat_id, self._routing_config
            ):
                return web.Response(status=200)

        session_key = resolve_feishu_session_key(
            chat_id=parsed.chat_id,
            sender_id=parsed.sender_id,
            root_id=parsed.root_id,
            chat_type=parsed.chat_type,
            config=self._routing_config,
        )

        # Build raw with root_id and session_key for normalize/topic routing
        raw_with_root = dict(body)
        if parsed.root_id:
            raw_with_root["root_id"] = parsed.root_id
        raw_with_root["session_key"] = session_key
        # Handle non-ASCII file names for file/media messages
        if parsed.media_type:
            event_msg = body.get("event", {}).get("message", {})
            raw_content = event_msg.get("content", "{}")
            try:
                content = json.loads(raw_content) if isinstance(raw_content, str) else raw_content
            except json.JSONDecodeError:
                content = {}
            file_name = content.get("file_name", "")
            if file_name:
                raw_with_root["file_name_safe"] = self._safe_filename_for_url(file_name)

        msg = ChannelMessage(
            channel_id=self.id,
            sender_id=parsed.sender_id,
            sender_name=parsed.sender_name or parsed.sender_id,
            text=parsed.text,
            chat_id=parsed.chat_id or parsed.sender_id,
            message_id=parsed.message_id or None,
            raw=raw_with_root,
            is_group=parsed.chat_type == "group",
            group_id=parsed.chat_id if parsed.chat_type == "group" else "",
            display_name=parsed.sender_name or parsed.sender_id,
        )

        if self.message_callback:
            await self.message_callback(msg)
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

    def _safe_filename_for_url(self, filename: str) -> str:
        """Quote non-ASCII and special chars for use in URLs."""
        return urllib.parse.quote(filename, safe="")

    def _markdown_to_post_content(self, text: str) -> dict[str, Any]:
        """Convert markdown text to Feishu post format (minimal)."""
        return {
            "zh_cn": {
                "title": "",
                "content": [[{"tag": "text", "text": text}]],
            }
        }

    async def _send_message(self, reply: ChannelReply) -> None:
        try:
            import aiohttp
        except ImportError:
            return

        chat_id = reply.recipient or reply.chat_id
        text = reply.text
        parse_mode = reply.parse_mode or ""

        raw = reply.raw or {}
        root_id = raw.get("root_id", "")
        message_id = reply.reply_to_message_id or raw.get("message_id", "")

        reply_params = resolve_reply_params(
            chat_id=chat_id,
            root_id=root_id,
            message_id=message_id,
            config=self._routing_config,
        )

        use_post = parse_mode == "markdown" and text
        msg_type = "post" if use_post else "text"
        if use_post:
            content = json.dumps(self._markdown_to_post_content(text))
        else:
            content = json.dumps({"text": text})

        headers = {
            "Authorization": f"Bearer {self._access_token}",
            "Content-Type": "application/json",
        }

        async with aiohttp.ClientSession() as session:
            if message_id and reply_params.get("message_id"):
                # Use reply API: POST /im/v1/messages/:message_id/reply
                url = f"{self._api_base}/open-apis/im/v1/messages/{message_id}/reply"
                payload = {"msg_type": msg_type, "content": content}
                if reply_params.get("reply_in_thread") and reply_params.get("root_id"):
                    payload["root_id"] = reply_params["root_id"]
                async with session.post(url, json=payload, headers=headers) as resp:
                    if resp.status >= 400:
                        err_text = await resp.text()
                        logger.error("Feishu reply error: %d %s", resp.status, err_text)
            else:
                # Use create message API
                url = f"{self._api_base}/open-apis/im/v1/messages"
                payload = {
                    "receive_id": chat_id,
                    "msg_type": msg_type,
                    "content": content,
                }
                if reply_params.get("reply_in_thread") and reply_params.get("root_id"):
                    payload["root_id"] = reply_params["root_id"]
                params = {"receive_id_type": "chat_id"}
                async with session.post(
                    url, json=payload, headers=headers, params=params
                ) as resp:
                    if resp.status >= 400:
                        err_text = await resp.text()
                        logger.error("Feishu send error: %d %s", resp.status, err_text)
