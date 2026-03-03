"""LINE Messaging API channel.

Receives messages via webhook and sends replies using the LINE
Messaging API v2 (push/reply). Uses aiohttp for HTTP handling.
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import logging
from base64 import b64encode
from typing import Any

import aiohttp
from aiohttp import web

from pyclaw.channels.base import ChannelMessage, ChannelPlugin, ChannelReply

logger = logging.getLogger(__name__)

LINE_API_BASE = "https://api.line.me/v2/bot"


class LINEChannel(ChannelPlugin):
    """LINE Messaging API integration."""

    def __init__(
        self,
        channel_access_token: str,
        channel_secret: str,
        *,
        port: int = 8069,
        on_message: Any = None,
    ) -> None:
        self._access_token = channel_access_token
        self._channel_secret = channel_secret
        self._port = port
        self._on_message = on_message
        self._runner: web.AppRunner | None = None

    @property
    def id(self) -> str:
        return "line"

    async def start(self) -> None:
        app = web.Application()
        app.router.add_post("/line/webhook", self._handle_webhook)
        self._runner = web.AppRunner(app)
        await self._runner.setup()
        site = web.TCPSite(self._runner, "0.0.0.0", self._port)
        await site.start()
        logger.info("LINE webhook listening on port %d", self._port)

    async def stop(self) -> None:
        if self._runner:
            await self._runner.cleanup()

    def _verify_signature(self, body: bytes, signature: str) -> bool:
        """Verify X-Line-Signature header."""
        mac = hmac.new(
            self._channel_secret.encode("utf-8"),
            body,
            hashlib.sha256,
        )
        expected = b64encode(mac.digest()).decode("utf-8")
        return hmac.compare_digest(expected, signature)

    async def _handle_webhook(self, request: web.Request) -> web.Response:
        body = await request.read()
        signature = request.headers.get("X-Line-Signature", "")

        if not self._verify_signature(body, signature):
            return web.Response(status=403, text="Invalid signature")

        try:
            data = json.loads(body)
        except json.JSONDecodeError:
            return web.Response(status=400, text="Invalid JSON")

        events = data.get("events", [])
        for event in events:
            await self._process_event(event)

        return web.Response(status=200, text="ok")

    async def _process_event(self, event: dict[str, Any]) -> None:
        event_type = event.get("type", "")
        if event_type != "message":
            return

        message = event.get("message", {})
        if message.get("type") != "text":
            return

        text = message.get("text", "")
        source = event.get("source", {})
        user_id = source.get("userId", "unknown")
        reply_token = event.get("replyToken", "")
        group_id = source.get("groupId", "")
        room_id = source.get("roomId", "")
        chat_id = group_id or room_id or reply_token or user_id

        if not text:
            return

        msg = ChannelMessage(
            channel_id="line",
            sender_id=user_id,
            sender_name=user_id,
            text=text,
            chat_id=chat_id,
            raw={
                "event": event,
                "reply_token": reply_token,
                "group_id": group_id,
                "room_id": room_id,
            },
            is_group=bool(group_id or room_id),
        )

        if self._on_message:
            result = self._on_message(msg)
            if asyncio.iscoroutine(result):
                await result

    async def send_reply(self, reply: ChannelReply) -> None:
        reply_token = reply.raw.get("reply_token", "") if reply.raw else ""
        to = reply.raw.get("sender_id", "") if reply.raw else ""

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self._access_token}",
        }

        if reply_token:
            # Use reply API (preferred, free)
            payload = {
                "replyToken": reply_token,
                "messages": [{"type": "text", "text": reply.text}],
            }
            url = f"{LINE_API_BASE}/message/reply"
        elif to:
            # Fall back to push API (paid)
            payload = {
                "to": to,
                "messages": [{"type": "text", "text": reply.text}],
            }
            url = f"{LINE_API_BASE}/message/push"
        else:
            logger.warning("No reply_token or recipient for LINE reply")
            return

        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, headers=headers) as resp:
                if resp.status != 200:
                    body = await resp.text()
                    logger.warning("LINE send failed (%d): %s", resp.status, body[:200])

    async def get_profile(self, user_id: str) -> dict[str, str]:
        """Fetch a user's LINE profile."""
        headers = {"Authorization": f"Bearer {self._access_token}"}
        async with (
            aiohttp.ClientSession() as session,
            session.get(
                f"{LINE_API_BASE}/profile/{user_id}",
                headers=headers,
            ) as resp,
        ):
            if resp.status == 200:
                data = await resp.json()
                return {
                    "display_name": data.get("displayName", ""),
                    "user_id": data.get("userId", user_id),
                    "picture_url": data.get("pictureUrl", ""),
                    "status_message": data.get("statusMessage", ""),
                }
            return {"display_name": "", "user_id": user_id}

    async def get_group_member_ids(self, group_id: str) -> list[str]:
        """Fetch member IDs in a group."""
        headers = {"Authorization": f"Bearer {self._access_token}"}
        member_ids: list[str] = []
        next_token: str | None = None

        while True:
            url = f"{LINE_API_BASE}/group/{group_id}/members/ids"
            if next_token:
                url += f"?start={next_token}"
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers) as resp:
                    if resp.status != 200:
                        break
                    data = await resp.json()
                    member_ids.extend(data.get("memberIds", []))
                    next_token = data.get("next")
                    if not next_token:
                        break

        return member_ids

    async def leave_group(self, group_id: str) -> None:
        """Leave a group chat."""
        headers = {"Authorization": f"Bearer {self._access_token}"}
        async with aiohttp.ClientSession() as session:
            await session.post(
                f"{LINE_API_BASE}/group/{group_id}/leave",
                headers=headers,
            )
