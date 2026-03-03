"""Slack channel implementation using slack-bolt."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from pyclaw.channels.base import ChannelMessage, ChannelPlugin, ChannelReply

logger = logging.getLogger("pyclaw.channels.slack")


def _markdown_to_slack_mrkdwn(text: str) -> str:
    """Convert markdown to Slack mrkdwn (bold **x** -> *x*, italic *x* -> _x_, code preserved)."""
    try:
        from pyclaw.markdown.channel_formats import markdown_to_slack_mrkdwn

        return markdown_to_slack_mrkdwn(text)
    except ImportError:
        import re

        blocks: list[tuple[str, str]] = []
        inlines: list[tuple[str, str]] = []
        c = 0

        def _protect_block(m: re.Match[str]) -> str:
            nonlocal c
            ph = f"\x00B{c}\x00"
            blocks.append((ph, m.group(0)))
            c += 1
            return ph

        def _protect_inline(m: re.Match[str]) -> str:
            nonlocal c
            ph = f"\x00I{c}\x00"
            inlines.append((ph, m.group(0)))
            c += 1
            return ph

        result = re.sub(r"```[\s\S]*?```", _protect_block, text)
        result = re.sub(r"`[^`\n]+?`", _protect_inline, result)
        result = re.sub(r"\*\*(.+?)\*\*", r"*\1*", result)
        result = re.sub(r"\*(.+?)\*", r"_\1_", result)
        for ph, orig in inlines:
            result = result.replace(ph, orig, 1)
        for ph, orig in blocks:
            result = result.replace(ph, orig, 1)
        return result


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

        text = _markdown_to_slack_mrkdwn(reply.text)
        kwargs: dict[str, Any] = {
            "channel": reply.chat_id,
            "text": text,
        }
        if reply.reply_to_message_id:
            kwargs["thread_ts"] = reply.reply_to_message_id

        await self._app.client.chat_postMessage(**kwargs)

    def _register_handlers(self) -> None:
        @self._app.event("message")  # type: ignore[untyped-decorator]
        async def on_message(event: dict[str, Any], say: Any) -> None:
            if event.get("bot_id"):
                return
            subtype = event.get("subtype")
            if subtype == "message_changed" and "previous_message" in event:
                return
            if subtype:
                return

            text = event.get("text", "")
            if not text:
                return

            channel_type = event.get("channel_type")
            channel_id = event.get("channel", "")
            is_dm = channel_type == "im" or (channel_id and channel_id.startswith("D"))
            is_group = not is_dm

            user_id = event.get("user", "")
            ts = event.get("ts", "")
            thread_ts = event.get("thread_ts")
            is_owner = user_id in self._owner_ids

            msg = ChannelMessage(
                channel_id=self.id,
                sender_id=user_id,
                sender_name=user_id,  # Slack doesn't include name in events
                text=text,
                chat_id=channel_id,
                message_id=ts,
                reply_to_message_id=thread_ts if thread_ts else None,
                is_group=is_group,
                is_owner=is_owner,
                raw=event,
            )

            if self.message_callback:
                await self.message_callback(msg)

        @self._app.event("app_mention")  # type: ignore[untyped-decorator]
        async def on_mention(event: dict[str, Any], say: Any) -> None:
            if event.get("channel_type") == "im":
                return
            await on_message(event, say)
