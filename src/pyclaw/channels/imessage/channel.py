"""iMessage channel plugin — message monitoring and sending via ``imsg rpc``."""

from __future__ import annotations

import asyncio
import logging
import re
from typing import Any

from pyclaw.channels.base import ChannelMessage, ChannelPlugin, ChannelReply
from pyclaw.channels.imessage.client import (
    IMessageRpcClient,
    create_imessage_rpc_client,
    probe_imessage,
)

logger = logging.getLogger(__name__)

# iMessage target formats: chat_id:123, chat_guid:x, imessage:+1..., sms:+1..., +1...
_TARGET_RE = re.compile(
    r"^(?:chat_id:(\d+)|chat_guid:(.+)|(?:imessage|sms):(.+)|(\+\d+))$",
)


def _parse_target(target: str) -> dict[str, str]:
    """Parse an iMessage target string into RPC params."""
    m = _TARGET_RE.match(target.strip())
    if not m:
        return {"to": target}
    if m.group(1):
        return {"chat_id": m.group(1)}
    if m.group(2):
        return {"chat_guid": m.group(2)}
    if m.group(3):
        phone = m.group(3)
        service = "iMessage" if target.startswith("imessage:") else "SMS"
        return {"to": phone, "service": service}
    return {"to": m.group(4), "service": "iMessage"}


class IMessageChannel(ChannelPlugin):
    """iMessage channel using ``imsg rpc`` bridge."""

    name = "imessage"

    def __init__(
        self,
        *,
        allow_from: list[str] | None = None,
        db_path: str | None = None,
        subscribe_attachments: bool = False,
    ) -> None:
        self._allow_from = set(allow_from) if allow_from else None
        self._db_path = db_path
        self._subscribe_attachments = subscribe_attachments
        self._client: IMessageRpcClient | None = None
        self._handler: Any = None

    async def start(self) -> None:
        if not probe_imessage():
            raise RuntimeError("imsg CLI not found — install via: brew install steipete/tap/imsg")

        self._client = await create_imessage_rpc_client(db_path=self._db_path)
        self._client.on_notification(self._on_notification)

        # Subscribe to incoming messages
        await self._client.request(
            "watch.subscribe",
            {
                "attachments": self._subscribe_attachments,
            },
        )
        logger.info("iMessage channel started")

    async def stop(self) -> None:
        if self._client:
            await self._client.stop()
            self._client = None
        logger.info("iMessage channel stopped")

    async def send(self, reply: ChannelReply) -> None:
        if not self._client:
            raise RuntimeError("iMessage client not started")

        params = _parse_target(reply.recipient)
        params["text"] = reply.text

        if reply.media_url:
            params["file"] = reply.media_url

        await self._client.request("send", params)

    def on_message(self, handler: Any) -> None:
        self._handler = handler

    async def _on_notification(self, method: str, params: dict[str, Any]) -> None:
        if method == "error":
            logger.error("iMessage error: %s", params)
            return

        if method != "message":
            return

        msg_data = params.get("message", params)
        sender = msg_data.get("sender", "")

        if self._allow_from and sender not in self._allow_from:
            return

        msg = ChannelMessage(
            channel="imessage",
            sender_id=sender,
            text=msg_data.get("text", ""),
            raw=msg_data,
            is_group=bool(msg_data.get("isGroup")),
            group_id=msg_data.get("chatId", ""),
            display_name=msg_data.get("senderName", sender),
        )

        if self._handler:
            result = self._handler(msg)
            if asyncio.iscoroutine(result):
                await result
