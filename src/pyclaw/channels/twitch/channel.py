"""Twitch channel plugin — connect via Twitch IRC (TMI).

Ported from ``extensions/twitch/``. Uses raw IRC over TLS to irc.chat.twitch.tv.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from pyclaw.channels.base import ChannelMessage, ChannelPlugin, ChannelReply

logger = logging.getLogger(__name__)

TWITCH_IRC_HOST = "irc.chat.twitch.tv"
TWITCH_IRC_PORT = 6697
TEXT_CHUNK_LIMIT = 500


class TwitchChannel(ChannelPlugin):
    """Twitch channel — group-only via Twitch IRC chat."""

    name = "twitch"

    def __init__(
        self,
        *,
        oauth_token: str = "",
        nick: str = "",
        channels: list[str] | None = None,
        allow_from: list[str] | None = None,
    ) -> None:
        self._oauth_token = oauth_token
        self._nick = nick.lower()
        self._channels = [c.lower().lstrip("#") for c in (channels or [])]
        self._allow_from = set(allow_from) if allow_from else None
        self._handler: Any = None
        self._reader: asyncio.StreamReader | None = None
        self._writer: asyncio.StreamWriter | None = None
        self._task: asyncio.Task[None] | None = None

    async def start(self) -> None:
        import ssl
        ssl_ctx = ssl.create_default_context()
        self._reader, self._writer = await asyncio.open_connection(
            TWITCH_IRC_HOST, TWITCH_IRC_PORT, ssl=ssl_ctx,
        )
        await self._send(f"PASS oauth:{self._oauth_token}")
        await self._send(f"NICK {self._nick}")
        for ch in self._channels:
            await self._send(f"JOIN #{ch}")
        self._task = asyncio.ensure_future(self._read_loop())
        logger.info("Twitch channel connected as %s", self._nick)

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()
            self._task = None
        if self._writer:
            try:
                self._writer.close()
            except Exception:
                pass
            self._writer = None

    async def send(self, reply: ChannelReply) -> None:
        channel = reply.recipient.lstrip("#")
        text = reply.text
        for i in range(0, len(text), TEXT_CHUNK_LIMIT):
            chunk = text[i:i + TEXT_CHUNK_LIMIT]
            await self._send(f"PRIVMSG #{channel} :{chunk}")

    def on_message(self, handler: Any) -> None:
        self._handler = handler

    async def _send(self, line: str) -> None:
        if self._writer:
            self._writer.write((line + "\r\n").encode("utf-8"))
            await self._writer.drain()

    async def _read_loop(self) -> None:
        if not self._reader:
            return
        while True:
            try:
                line_bytes = await self._reader.readline()
                if not line_bytes:
                    break
                line = line_bytes.decode("utf-8", errors="replace").strip()
                if line.startswith("PING"):
                    await self._send(f"PONG {line[5:]}")
                    continue
                if " PRIVMSG " in line:
                    self._handle_privmsg(line)
            except asyncio.CancelledError:
                break
            except Exception:
                logger.exception("Twitch read error")
                break

    def _handle_privmsg(self, line: str) -> None:
        try:
            prefix, _, rest = line.partition(" PRIVMSG ")
            target, _, text = rest.partition(" :")
            sender = prefix.lstrip(":").split("!")[0]

            if self._allow_from and sender not in self._allow_from:
                return

            msg = ChannelMessage(
                channel="twitch",
                sender_id=sender,
                text=text,
                raw={"sender": sender, "target": target, "text": text},
                is_group=True,
                group_id=target.lstrip("#"),
                display_name=sender,
            )
            if self._handler:
                asyncio.ensure_future(self._handler(msg))
        except Exception:
            pass
