"""QQ channel plugin — QQ Bot via OpenAPI + WebSocket.

Uses QQ Open Platform bot SDK for receiving private/group messages
via WebSocket. No public IP required.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, cast

from pyclaw.channels.base import ChannelMessage, ChannelPlugin, ChannelReply

logger = logging.getLogger(__name__)

_API_BASE = "https://api.sgroup.qq.com"
_SANDBOX_API_BASE = "https://sandbox.api.sgroup.qq.com"


class QQChannel(ChannelPlugin):
    """QQ Bot channel using WebSocket for message reception."""

    name = "qq"

    def __init__(
        self,
        *,
        app_id: str = "",
        secret: str = "",
        sandbox: bool = False,
        allow_from: list[str] | None = None,
    ) -> None:
        self._app_id = app_id
        self._secret = secret
        self._sandbox = sandbox
        self._allow_from = set(allow_from) if allow_from else None
        self._handler: Any = None
        self._access_token: str = ""
        self._token_expires: float = 0
        self._ws_task: asyncio.Task[None] | None = None
        self._running = False
        self._session_id: str = ""
        self._seq: int = 0
        self._heartbeat_interval: int = 40

    @property
    def id(self) -> str:
        return "qq"

    @property
    def _api_base(self) -> str:
        return _SANDBOX_API_BASE if self._sandbox else _API_BASE

    @property
    def is_running(self) -> bool:
        return self._running

    async def start(self) -> None:
        if not self._app_id or not self._secret:
            raise ValueError("QQ: appId and secret are required")

        await self._refresh_token()
        self._ws_task = asyncio.create_task(self._ws_loop())
        self._running = True
        logger.info("QQ channel started (sandbox=%s)", self._sandbox)

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
        await self._send_message(reply.chat_id, reply.text, reply.reply_to_message_id)

    def on_message(self, handler: Any) -> None:
        self._handler = handler

    async def _ws_loop(self) -> None:
        """Connect to QQ WebSocket gateway and process events."""
        try:
            while self._running:
                try:
                    gateway_url = await self._get_ws_gateway()
                    if not gateway_url:
                        logger.error("QQ: failed to get WebSocket gateway URL")
                        await asyncio.sleep(10)
                        continue
                    await self._run_ws(gateway_url)
                except asyncio.CancelledError:
                    raise
                except Exception:
                    logger.exception("QQ WebSocket error, reconnecting in 5s")
                    await asyncio.sleep(5)
        except asyncio.CancelledError:
            pass

    async def _get_ws_gateway(self) -> str | None:
        try:
            import httpx
        except ImportError:
            raise RuntimeError("httpx required for QQ channel")

        await self._ensure_token()
        url = f"{self._api_base}/gateway"
        headers = {"Authorization": f"QQBot {self._access_token}"}

        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(url, headers=headers)
            if resp.status_code == 200:
                return cast(str | None, resp.json().get("url"))
            logger.error("QQ gateway request failed: %d", resp.status_code)
            return None

    async def _run_ws(self, gateway_url: str) -> None:
        try:
            import websockets
        except ImportError:
            raise RuntimeError("websockets required for QQ channel")

        async with websockets.connect(gateway_url) as ws:
            logger.info("QQ WebSocket connected")

            hello = json.loads(await ws.recv())
            if hello.get("op") == 10:
                self._heartbeat_interval = hello.get("d", {}).get("heartbeat_interval", 40000) // 1000

            identify = {
                "op": 2,
                "d": {
                    "token": f"QQBot {self._access_token}",
                    "intents": 0 | (1 << 25) | (1 << 30),
                    "shard": [0, 1],
                },
            }
            if self._session_id:
                identify = {
                    "op": 6,
                    "d": {
                        "token": f"QQBot {self._access_token}",
                        "session_id": self._session_id,
                        "seq": self._seq,
                    },
                }
            await ws.send(json.dumps(identify))

            heartbeat_task = asyncio.create_task(self._heartbeat(ws))
            try:
                async for raw in ws:
                    try:
                        data = json.loads(raw)
                        await self._handle_event(data)
                    except Exception:
                        logger.exception("QQ: error processing event")
            finally:
                heartbeat_task.cancel()

    async def _heartbeat(self, ws: Any) -> None:
        try:
            while True:
                await asyncio.sleep(self._heartbeat_interval)
                await ws.send(json.dumps({"op": 1, "d": self._seq or None}))
        except asyncio.CancelledError:
            pass

    async def _handle_event(self, data: dict[str, Any]) -> None:
        op = data.get("op")
        t = data.get("t", "")
        d = data.get("d", {})

        if data.get("s"):
            self._seq = data["s"]

        if op == 0 and t == "READY":
            self._session_id = d.get("session_id", "")
            logger.info("QQ bot ready, session=%s", self._session_id)
            return

        if op == 0 and t in ("C2C_MESSAGE_CREATE", "DIRECT_MESSAGE_CREATE"):
            await self._handle_message(d, is_group=False)
        elif op == 0 and t in ("GROUP_AT_MESSAGE_CREATE", "AT_MESSAGE_CREATE"):
            await self._handle_message(d, is_group=True)

    async def _handle_message(self, d: dict[str, Any], *, is_group: bool) -> None:
        text = d.get("content", "").strip()
        if not text:
            return

        author = d.get("author", {})
        sender_id = author.get("member_openid", "") or author.get("id", "")
        sender_name = author.get("username", "") or sender_id

        if self._allow_from and sender_id not in self._allow_from:
            return

        chat_id = d.get("group_openid", "") or d.get("channel_id", "") or sender_id
        msg_id = d.get("id", "")

        msg = ChannelMessage(
            channel_id="qq",
            sender_id=sender_id,
            sender_name=sender_name,
            text=text,
            chat_id=chat_id,
            message_id=msg_id,
            is_group=is_group,
            raw=d,
        )

        if self._handler:
            await self._handler(msg)

    async def _refresh_token(self) -> None:
        import time

        try:
            import httpx
        except ImportError:
            return

        url = f"{_API_BASE}/app/getAppAccessToken"
        payload = {"appId": self._app_id, "clientSecret": self._secret}

        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(url, json=payload)
            if resp.status_code == 200:
                data = resp.json()
                self._access_token = data.get("access_token", "")
                expires_in = int(data.get("expires_in", 7200))
                self._token_expires = time.time() + expires_in - 300
            else:
                logger.error("QQ token refresh failed: %d", resp.status_code)

    async def _ensure_token(self) -> None:
        import time

        if time.time() >= self._token_expires:
            await self._refresh_token()

    async def _send_message(
        self,
        chat_id: str,
        text: str,
        reply_to: str | None = None,
    ) -> None:
        try:
            import httpx
        except ImportError:
            return

        await self._ensure_token()
        headers = {
            "Authorization": f"QQBot {self._access_token}",
            "Content-Type": "application/json",
        }

        if len(chat_id) > 20:
            url = f"{self._api_base}/v2/groups/{chat_id}/messages"
            payload: dict[str, Any] = {
                "content": text,
                "msg_type": 0,
            }
        else:
            url = f"{self._api_base}/v2/users/{chat_id}/messages"
            payload = {
                "content": text,
                "msg_type": 0,
            }

        if reply_to:
            payload["msg_id"] = reply_to

        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(url, json=payload, headers=headers)
            if resp.status_code >= 400:
                logger.error("QQ send error: %d %s", resp.status_code, resp.text)
