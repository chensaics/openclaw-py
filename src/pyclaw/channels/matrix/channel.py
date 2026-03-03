"""Matrix channel plugin — homeserver sync via matrix-nio.

Ported from ``extensions/matrix/``.
Requires ``matrix-nio``.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from pyclaw.channels.base import ChannelMessage, ChannelPlugin, ChannelReply

logger = logging.getLogger(__name__)


class MatrixChannel(ChannelPlugin):
    """Matrix channel using matrix-nio async client."""

    name = "matrix"

    def __init__(
        self,
        *,
        homeserver: str = "https://matrix.org",
        user_id: str = "",
        access_token: str = "",
        password: str = "",
        allow_from: list[str] | None = None,
        auto_join: bool = True,
    ) -> None:
        self._homeserver = homeserver
        self._user_id = user_id
        self._access_token = access_token
        self._password = password
        self._allow_from = set(allow_from) if allow_from else None
        self._auto_join = auto_join
        self._handler: Any = None
        self._client: Any = None
        self._task: asyncio.Task[None] | None = None

    async def start(self) -> None:
        try:
            from nio import AsyncClient, InviteMemberEvent, RoomMessageText
        except ImportError:
            raise RuntimeError("matrix-nio required: pip install matrix-nio")

        self._client = AsyncClient(self._homeserver, self._user_id)

        if self._access_token:
            self._client.access_token = self._access_token
            self._client.user_id = self._user_id
        elif self._password:
            resp = await self._client.login(self._password)
            if hasattr(resp, "access_token"):
                logger.info("Matrix login successful")
            else:
                raise RuntimeError(f"Matrix login failed: {resp}")

        # Register event callbacks
        self._client.add_event_callback(self._on_message, RoomMessageText)
        if self._auto_join:
            self._client.add_event_callback(self._on_invite, InviteMemberEvent)

        self._task = asyncio.ensure_future(self._client.sync_forever(timeout=30000))
        logger.info("Matrix channel connected to %s", self._homeserver)

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()
            self._task = None
        if self._client:
            await self._client.close()
            self._client = None

    async def send(self, reply: ChannelReply) -> None:
        if not self._client:
            return

        try:
            from nio import RoomSendResponse
        except ImportError:
            return

        content = {"msgtype": "m.text", "body": reply.text}
        # Support basic HTML formatting
        if "<" in reply.text and ">" in reply.text:
            content["format"] = "org.matrix.custom.html"
            content["formatted_body"] = reply.text

        await self._client.room_send(
            room_id=reply.recipient,
            message_type="m.room.message",
            content=content,
        )

    def on_message(self, handler: Any) -> None:
        self._handler = handler

    async def _on_message(self, room: Any, event: Any) -> None:
        # Skip our own messages
        if event.sender == self._user_id:
            return

        if self._allow_from and event.sender not in self._allow_from:
            return

        is_group = (
            len(getattr(room, "member_count", []) or []) > 2
            if hasattr(room, "member_count")
            else True
        )

        display_name = (
            room.user_name(event.sender) if hasattr(room, "user_name") else event.sender
        )
        msg = ChannelMessage(
            channel_id="matrix",
            sender_id=event.sender,
            sender_name=display_name,
            text=event.body,
            chat_id=room.room_id,
            raw={"room_id": room.room_id, "sender": event.sender, "body": event.body},
            is_group=is_group,
            group_id=room.room_id,
            display_name=display_name,
        )

        if self._handler:
            await self._handler(msg)

    async def _on_invite(self, room: Any, event: Any) -> None:
        if self._auto_join and self._client:
            await self._client.join(room.room_id)
            logger.info("Auto-joined room %s", room.room_id)
