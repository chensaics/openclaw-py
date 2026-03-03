"""Discord channel implementation using discord.py."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from pyclaw.channels.base import ChannelMessage, ChannelPlugin, ChannelReply

logger = logging.getLogger("pyclaw.channels.discord")

# discord.py limits messages to 2000 chars
_MAX_MESSAGE_LEN = 2000


class DiscordChannel(ChannelPlugin):
    """Discord messaging channel using discord.py."""

    def __init__(
        self,
        *,
        token: str,
        owner_ids: list[int] | None = None,
        allowed_channel_ids: list[int] | None = None,
    ) -> None:
        self._token = token
        self._owner_ids = set(owner_ids or [])
        self._allowed_channel_ids = set(allowed_channel_ids or [])
        self._running = False
        self._client: Any = None
        self._task: asyncio.Task[None] | None = None

    @property
    def id(self) -> str:
        return "discord"

    @property
    def name(self) -> str:
        return "Discord"

    @property
    def is_running(self) -> bool:
        return self._running

    async def start(self) -> None:
        import discord

        intents = discord.Intents.default()
        intents.message_content = True

        self._client = discord.Client(intents=intents)
        self._register_handlers()

        self._running = True
        logger.info("Discord channel starting")
        self._task = asyncio.create_task(self._run())

    async def _run(self) -> None:
        try:
            await self._client.start(self._token)
        except asyncio.CancelledError:
            pass
        except Exception:
            logger.exception("Discord client error")
        finally:
            self._running = False

    async def stop(self) -> None:
        self._running = False
        if self._client:
            await self._client.close()
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Discord channel stopped")

    async def send_reply(self, reply: ChannelReply) -> None:
        if not self._client:
            raise RuntimeError("Discord client not started")

        channel = self._client.get_channel(int(reply.chat_id))
        if not channel:
            channel = await self._client.fetch_channel(int(reply.chat_id))

        text = reply.text
        # Split long messages
        while text:
            chunk = text[:_MAX_MESSAGE_LEN]
            text = text[_MAX_MESSAGE_LEN:]
            await channel.send(chunk)

    def _register_handlers(self) -> None:
        import discord

        @self._client.event  # type: ignore[untyped-decorator]
        async def on_ready() -> None:
            logger.info("Discord bot ready: %s", self._client.user)

        @self._client.event  # type: ignore[untyped-decorator]
        async def on_message(message: discord.Message) -> None:
            if message.author == self._client.user:
                return
            if message.author.bot:
                return

            # Channel allowlist
            if self._allowed_channel_ids and message.channel.id not in self._allowed_channel_ids:
                return

            # Only respond when mentioned in guild channels, or always in DMs
            is_dm = isinstance(message.channel, discord.DMChannel)
            if not is_dm and self._client.user not in message.mentions:
                return

            text = message.content
            # Strip the bot mention from the text
            if self._client.user:
                text = text.replace(f"<@{self._client.user.id}>", "").strip()

            if not text:
                return

            is_owner = message.author.id in self._owner_ids

            msg = ChannelMessage(
                channel_id=self.id,
                sender_id=str(message.author.id),
                sender_name=str(message.author),
                text=text,
                chat_id=str(message.channel.id),
                message_id=str(message.id),
                is_group=not is_dm,
                is_owner=is_owner,
                raw=message,
            )

            if self.message_callback:
                await self.message_callback(msg)
