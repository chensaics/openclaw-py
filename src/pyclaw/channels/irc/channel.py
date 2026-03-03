"""IRC channel plugin — connect to IRC servers via raw TCP/TLS.

Ported from ``extensions/irc/``.
"""

from __future__ import annotations

import asyncio
import logging
import ssl
from typing import Any

from pyclaw.channels.base import ChannelMessage, ChannelPlugin, ChannelReply

logger = logging.getLogger(__name__)

TEXT_CHUNK_LIMIT = 350


class IrcClient:
    """Minimal async IRC client over TCP/TLS."""

    def __init__(
        self,
        host: str,
        port: int = 6697,
        use_tls: bool = True,
        nick: str = "pyclaw",
        password: str | None = None,
        nickserv_password: str | None = None,
    ) -> None:
        self.host = host
        self.port = port
        self.use_tls = use_tls
        self.nick = nick
        self.password = password
        self.nickserv_password = nickserv_password
        self._reader: asyncio.StreamReader | None = None
        self._writer: asyncio.StreamWriter | None = None
        self.on_privmsg: Any = None

    async def connect(self) -> None:
        ssl_ctx = ssl.create_default_context() if self.use_tls else None
        self._reader, self._writer = await asyncio.open_connection(
            self.host,
            self.port,
            ssl=ssl_ctx,
        )
        if self.password:
            await self._send(f"PASS {self.password}")
        await self._send(f"NICK {self.nick}")
        await self._send(f"USER {self.nick} 0 * :pyclaw Bot")

    async def _send(self, line: str) -> None:
        if self._writer:
            self._writer.write((line + "\r\n").encode("utf-8"))
            await self._writer.drain()

    async def join(self, channel: str) -> None:
        await self._send(f"JOIN {channel}")

    async def send_privmsg(self, target: str, text: str) -> None:
        for chunk in _chunk_text(text, TEXT_CHUNK_LIMIT):
            await self._send(f"PRIVMSG {target} :{chunk}")

    async def run(self) -> None:
        """Read loop — parse IRC lines and dispatch."""
        if not self._reader:
            return

        while True:
            try:
                line_bytes = await self._reader.readline()
                if not line_bytes:
                    break
                line = line_bytes.decode("utf-8", errors="replace").strip()
                if not line:
                    continue

                if line.startswith("PING"):
                    token = line.split(" ", 1)[1] if " " in line else ""
                    await self._send(f"PONG {token}")
                    continue

                # NickServ identify after welcome (001)
                if " 001 " in line and self.nickserv_password:
                    await self._send(f"PRIVMSG NickServ :IDENTIFY {self.nickserv_password}")

                # Parse PRIVMSG
                if " PRIVMSG " in line:
                    self._handle_privmsg(line)

            except asyncio.CancelledError:
                break
            except Exception:
                logger.exception("IRC read error")
                break

    def _handle_privmsg(self, line: str) -> None:
        # :nick!user@host PRIVMSG #channel :message
        try:
            prefix, _, rest = line.partition(" PRIVMSG ")
            target, _, text = rest.partition(" :")
            sender = prefix.lstrip(":").split("!")[0]
            if self.on_privmsg:
                self.on_privmsg(sender, target, text)
        except Exception:
            pass

    async def disconnect(self) -> None:
        if self._writer:
            try:
                await self._send("QUIT :Bye")
                self._writer.close()
            except Exception:
                pass
            self._writer = None


def _chunk_text(text: str, limit: int) -> list[str]:
    if len(text) <= limit:
        return [text]
    chunks: list[str] = []
    for i in range(0, len(text), limit):
        chunks.append(text[i : i + limit])
    return chunks


class IrcChannel(ChannelPlugin):
    """IRC channel using raw TCP/TLS."""

    name = "irc"

    def __init__(
        self,
        *,
        host: str,
        port: int = 6697,
        use_tls: bool = True,
        nick: str = "pyclaw",
        password: str | None = None,
        nickserv_password: str | None = None,
        channels: list[str] | None = None,
        allow_from: list[str] | None = None,
    ) -> None:
        self._host = host
        self._port = port
        self._use_tls = use_tls
        self._nick = nick
        self._password = password
        self._nickserv_password = nickserv_password
        self._channels = channels or []
        self._allow_from = set(allow_from) if allow_from else None
        self._client: IrcClient | None = None
        self._handler: Any = None
        self._task: asyncio.Task[None] | None = None

    async def start(self) -> None:
        self._client = IrcClient(
            host=self._host,
            port=self._port,
            use_tls=self._use_tls,
            nick=self._nick,
            password=self._password,
            nickserv_password=self._nickserv_password,
        )
        self._client.on_privmsg = self._on_privmsg
        await self._client.connect()
        for ch in self._channels:
            await self._client.join(ch)
        self._task = asyncio.ensure_future(self._client.run())
        logger.info("IRC channel connected to %s:%d", self._host, self._port)

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()
            self._task = None
        if self._client:
            await self._client.disconnect()
            self._client = None

    async def send(self, reply: ChannelReply) -> None:
        if self._client and reply.recipient:
            await self._client.send_privmsg(reply.recipient, reply.text)

    def on_message(self, handler: Any) -> None:
        self._handler = handler

    def _on_privmsg(self, sender: str, target: str, text: str) -> None:
        if self._allow_from and sender not in self._allow_from:
            return

        is_group = target.startswith("#")
        msg = ChannelMessage(
            channel_id="irc",
            sender_id=sender,
            sender_name=sender,
            text=text,
            chat_id=target,
            raw={"sender": sender, "target": target, "text": text},
            is_group=is_group,
            group_id=target if is_group else "",
            display_name=sender,
        )
        if self._handler:
            asyncio.ensure_future(self._handler(msg))
