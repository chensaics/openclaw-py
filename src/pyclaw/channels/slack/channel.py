"""Slack channel implementation using slack-bolt."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from pyclaw.channels.base import ChannelMessage, ChannelPlugin, ChannelReply

logger = logging.getLogger("pyclaw.channels.slack")


class SlackChannel(ChannelPlugin):
    """Slack messaging channel using slack-bolt (Socket Mode)."""

    def __init__(
        self,
        *,
        bot_token: str,
        app_token: str,
        owner_ids: list[str] | None = None,
    ) -> None:
        self._bot_token = bot_token
        self._app_token = app_token
        self._owner_ids = set(owner_ids or [])
        self._running = False
        self._app: Any = None
        self._handler: Any = None
        self._task: asyncio.Task[None] | None = None

    @property
    def id(self) -> str:
        return "slack"

    @property
    def name(self) -> str:
        return "Slack"

    @property
    def is_running(self) -> bool:
        return self._running

    async def start(self) -> None:
        from slack_bolt.adapter.socket_mode.async_handler import AsyncSocketModeHandler
        from slack_bolt.async_app import AsyncApp

        self._app = AsyncApp(token=self._bot_token)
        self._register_handlers()

        self._handler = AsyncSocketModeHandler(self._app, self._app_token)
        self._running = True
        logger.info("Slack channel starting (socket mode)")
        self._task = asyncio.create_task(self._run())

    async def _run(self) -> None:
        try:
            await self._handler.start_async()
        except asyncio.CancelledError:
            pass
        except Exception:
            logger.exception("Slack handler error")
        finally:
            self._running = False

    async def stop(self) -> None:
        self._running = False
        if self._handler:
            try:
                await self._handler.close_async()
            except Exception:
                pass
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Slack channel stopped")

    async def send_reply(self, reply: ChannelReply) -> None:
        if not self._app:
            raise RuntimeError("Slack app not started")

        kwargs: dict[str, Any] = {
            "channel": reply.chat_id,
            "text": reply.text,
        }
        if reply.reply_to_message_id:
            kwargs["thread_ts"] = reply.reply_to_message_id

        await self._app.client.chat_postMessage(**kwargs)

    def _register_handlers(self) -> None:
        @self._app.event("message")  # type: ignore[untyped-decorator]
        async def on_message(event: dict[str, Any], say: Any) -> None:
            # Ignore bot messages
            if event.get("bot_id") or event.get("subtype"):
                return

            text = event.get("text", "")
            if not text:
                return

            user_id = event.get("user", "")
            channel_id = event.get("channel", "")
            ts = event.get("ts", "")
            thread_ts = event.get("thread_ts")
            is_owner = user_id in self._owner_ids

            msg = ChannelMessage(
                channel_id=self.id,
                sender_id=user_id,
                sender_name=user_id,  # Slack doesn't include name in events
                text=text,
                chat_id=channel_id,
                message_id=thread_ts or ts,
                is_group=True,  # Slack messages are always in channels
                is_owner=is_owner,
                raw=event,
            )

            if self.message_callback:
                await self.message_callback(msg)

        @self._app.event("app_mention")  # type: ignore[untyped-decorator]
        async def on_mention(event: dict[str, Any], say: Any) -> None:
            # Same processing as message
            await on_message(event, say)
