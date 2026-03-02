"""DingTalk channel plugin — Stream Mode (WebSocket long-connection).

Uses DingTalk Open Platform Stream SDK for receiving messages
and OpenAPI for sending replies. No public IP required.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from pyclaw.channels.base import ChannelMessage, ChannelPlugin, ChannelReply

logger = logging.getLogger(__name__)

_API_BASE = "https://api.dingtalk.com"


class DingTalkChannel(ChannelPlugin):
    """DingTalk channel using Stream Mode (WebSocket) for message reception."""

    name = "dingtalk"

    def __init__(
        self,
        *,
        client_id: str = "",
        client_secret: str = "",
        allow_from: list[str] | None = None,
    ) -> None:
        self._client_id = client_id
        self._client_secret = client_secret
        self._allow_from = set(allow_from) if allow_from else None
        self._handler: Any = None
        self._access_token: str = ""
        self._token_expires: float = 0
        self._ws_task: asyncio.Task[None] | None = None
        self._running = False

    @property
    def id(self) -> str:
        return "dingtalk"

    @property
    def is_running(self) -> bool:
        return self._running

    async def start(self) -> None:
        if not self._client_id or not self._client_secret:
            raise ValueError("DingTalk: clientId and clientSecret are required")

        await self._refresh_token()
        self._ws_task = asyncio.create_task(self._stream_loop())
        self._running = True
        logger.info("DingTalk channel started (Stream Mode)")

    async def stop(self) -> None:
        self._running = False
        if self._ws_task:
            self._ws_task.cancel()
            try:
                await self._ws_task
            except asyncio.CancelledError:
                pass
            self._ws_task = None

    async def send_reply(self, reply: ChannelReply) -> None:
        await self._ensure_token()
        await self._send_message(reply.chat_id, reply.text)

    def on_message(self, handler: Any) -> None:
        self._handler = handler

    async def _stream_loop(self) -> None:
        """Connect to DingTalk Stream endpoint and process messages."""
        try:
            while self._running:
                try:
                    endpoint = await self._get_stream_endpoint()
                    if not endpoint:
                        logger.error("DingTalk: failed to get stream endpoint")
                        await asyncio.sleep(10)
                        continue

                    await self._run_stream(endpoint)
                except asyncio.CancelledError:
                    raise
                except Exception:
                    logger.exception("DingTalk stream error, reconnecting in 5s")
                    await asyncio.sleep(5)
        except asyncio.CancelledError:
            pass

    async def _get_stream_endpoint(self) -> str | None:
        """Register stream connection and get WebSocket endpoint."""
        try:
            import httpx
        except ImportError:
            raise RuntimeError("httpx required for DingTalk channel")

        await self._ensure_token()

        url = f"{_API_BASE}/v1.0/gateway/connections/open"
        headers = {
            "Content-Type": "application/json",
            "x-acs-dingtalk-access-token": self._access_token,
        }
        payload = {
            "clientId": self._client_id,
            "clientSecret": self._client_secret,
            "subscriptions": [{"type": "EVENT", "topic": "/v1.0/im/bot/messages/get"}],
        }

        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(url, json=payload, headers=headers)
            if resp.status_code != 200:
                logger.error("DingTalk stream register failed: %d %s", resp.status_code, resp.text)
                return None
            data = resp.json()
            endpoint = data.get("endpoint", "")
            ticket = data.get("ticket", "")
            if endpoint and ticket:
                sep = "&" if "?" in endpoint else "?"
                return f"{endpoint}{sep}ticket={ticket}"
            return endpoint or None

    async def _run_stream(self, endpoint: str) -> None:
        """Maintain WebSocket connection to stream endpoint."""
        try:
            import websockets
        except ImportError:
            raise RuntimeError("websockets required for DingTalk Stream Mode")

        async with websockets.connect(endpoint) as ws:  # type: ignore[attr-defined]
            logger.info("DingTalk stream connected")
            async for raw in ws:
                try:
                    data = json.loads(raw)
                    await self._handle_stream_event(data, ws)
                except Exception:
                    logger.exception("DingTalk: error processing stream event")

    async def _handle_stream_event(self, data: dict[str, Any], ws: Any) -> None:
        """Process a stream event from DingTalk."""
        msg_type = data.get("type", "")

        if msg_type == "SYSTEM":
            topic = data.get("headers", {}).get("topic", "")
            if topic == "PING":
                pong = {
                    "code": 200,
                    "headers": data.get("headers", {}),
                    "message": "OK",
                    "data": "",
                }
                await ws.send(json.dumps(pong))
            return

        if msg_type == "CALLBACK":
            await self._handle_callback(data)
            ack = {"code": 200, "headers": data.get("headers", {}), "message": "OK", "data": ""}
            await ws.send(json.dumps(ack))

    async def _handle_callback(self, data: dict[str, Any]) -> None:
        """Handle a callback event (bot message)."""
        payload_str = data.get("data", "")
        if not payload_str:
            return

        try:
            payload = json.loads(payload_str) if isinstance(payload_str, str) else payload_str
        except json.JSONDecodeError:
            return

        text = payload.get("text", {}).get("content", "").strip()
        if not text:
            return

        sender_id = payload.get("senderStaffId", "") or payload.get("senderId", "")
        sender_nick = payload.get("senderNick", "")
        conversation_id = payload.get("conversationId", "")
        conversation_type = payload.get("conversationType", "")
        is_group = conversation_type == "2"

        if self._allow_from and sender_id not in self._allow_from:
            return

        webhook_url = payload.get("sessionWebhook", "")

        msg = ChannelMessage(
            channel_id="dingtalk",
            sender_id=sender_id,
            sender_name=sender_nick or sender_id,
            text=text,
            chat_id=conversation_id,
            message_id=payload.get("msgId", ""),
            is_group=is_group,
            raw={"webhook": webhook_url, **payload},
        )

        if self._handler:
            await self._handler(msg)

    async def _refresh_token(self) -> None:
        import time

        try:
            import httpx
        except ImportError:
            return

        url = f"{_API_BASE}/v1.0/oauth2/accessToken"
        payload = {"appKey": self._client_id, "appSecret": self._client_secret}

        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(url, json=payload)
            if resp.status_code == 200:
                data = resp.json()
                self._access_token = data.get("accessToken", "")
                expire_in = data.get("expireIn", 7200)
                self._token_expires = time.time() + expire_in - 300
            else:
                logger.error("DingTalk token refresh failed: %d", resp.status_code)

    async def _ensure_token(self) -> None:
        import time

        if time.time() >= self._token_expires:
            await self._refresh_token()

    async def _send_message(self, conversation_id: str, text: str) -> None:
        try:
            import httpx
        except ImportError:
            return

        await self._ensure_token()
        url = f"{_API_BASE}/v1.0/robot/oToMessages/batchSend"
        headers = {
            "Content-Type": "application/json",
            "x-acs-dingtalk-access-token": self._access_token,
        }
        payload = {
            "robotCode": self._client_id,
            "userIds": [conversation_id],
            "msgKey": "sampleText",
            "msgParam": json.dumps({"content": text}),
        }

        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(url, json=payload, headers=headers)
            if resp.status_code >= 400:
                logger.error("DingTalk send error: %d %s", resp.status_code, resp.text)
