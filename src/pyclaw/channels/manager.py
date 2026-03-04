"""Channel manager — starts/stops channels and routes messages to agent."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from pyclaw.channels.base import ChannelMessage, ChannelPlugin, ChannelReply

logger = logging.getLogger("pyclaw.channels")


def _record_metric(channel_id: str, event: str) -> None:
    """Record a metric event if the gateway channels module is loaded."""
    try:
        from pyclaw.gateway.methods.channels import record_channel_metric

        record_channel_metric(channel_id, event)
    except Exception:
        logger.warning("Failed to record channel metric for %s event %s", channel_id, event, exc_info=True)


class ChannelManager:
    """Manages lifecycle and message routing for all registered channels."""

    def __init__(self) -> None:
        self._channels: dict[str, ChannelPlugin] = {}
        self._message_handler: Any = None

    @property
    def channels(self) -> list[ChannelPlugin]:
        """All registered channel plugins (iterable by gateway methods)."""
        return list(self._channels.values())

    def register(self, channel: ChannelPlugin) -> None:
        self._channels[channel.id] = channel
        channel.on_message(self._dispatch_message)

    def set_message_handler(self, handler: Any) -> None:
        """Set the handler for incoming messages.

        Signature: async def handler(msg: ChannelMessage) -> str | None
        Returns the reply text, or None if no reply.
        """
        self._message_handler = handler

    async def start_all(self) -> None:
        """Start all registered channels concurrently."""
        tasks = []
        for ch in self._channels.values():
            logger.info("Starting channel: %s", ch.id)
            tasks.append(asyncio.create_task(self._start_channel(ch)))
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    async def _start_channel(self, ch: ChannelPlugin) -> None:
        try:
            await ch.start()
            _record_metric(ch.id, "connect")
        except Exception:
            logger.exception("Failed to start channel %s", ch.id)

    async def stop_all(self) -> None:
        """Stop all running channels."""
        for ch in self._channels.values():
            if ch.is_running:
                logger.info("Stopping channel: %s", ch.id)
                try:
                    await ch.stop()
                    _record_metric(ch.id, "disconnect")
                except Exception:
                    logger.exception("Error stopping channel %s", ch.id)

    def get(self, channel_id: str) -> ChannelPlugin | None:
        return self._channels.get(channel_id)

    def list_channels(self) -> list[dict[str, Any]]:
        return [{"id": ch.id, "name": ch.name, "running": ch.is_running} for ch in self._channels.values()]

    async def _dispatch_message(self, msg: ChannelMessage) -> None:
        """Route an incoming message to the handler and send back a reply."""
        if not self._message_handler:
            logger.warning("No message handler set, dropping message from %s", msg.channel_id)
            return

        try:
            reply_text = await self._message_handler(msg)
        except Exception:
            logger.exception("Error handling message from %s", msg.channel_id)
            reply_text = "An error occurred while processing your message."

        if reply_text:
            channel = self._channels.get(msg.channel_id)
            if channel:
                raw: dict[str, Any] = {}
                if msg.channel_id == "feishu" and msg.raw and isinstance(msg.raw, dict):
                    if msg.raw.get("root_id"):
                        raw["root_id"] = msg.raw["root_id"]
                reply = ChannelReply(
                    text=reply_text,
                    chat_id=msg.chat_id,
                    reply_to_message_id=msg.reply_to_message_id or msg.message_id,
                    message_thread_id=msg.message_thread_id,
                    raw=raw if raw else None,
                )
                try:
                    await channel.send_reply(reply)
                    _record_metric(msg.channel_id, "msg_sent")
                except Exception:
                    logger.exception("Error sending reply on %s", msg.channel_id)
                    _record_metric(msg.channel_id, "msg_failed")
