"""WhatsApp channel implementation.

Uses neonize (Python Baileys wrapper) for WhatsApp Web multi-device.
Falls back to a subprocess bridge with whatsapp-web.js if neonize is unavailable.
"""

from __future__ import annotations

import asyncio
import logging
import time
from pathlib import Path
from typing import Any

from pyclaw.channels.base import ChannelMessage, ChannelPlugin, ChannelReply

logger = logging.getLogger(__name__)


class WhatsAppChannel(ChannelPlugin):
    """WhatsApp Web channel using neonize or subprocess bridge."""

    HEARTBEAT_INTERVAL_S = 30.0
    HEARTBEAT_TIMEOUT_S = 10.0

    def __init__(
        self,
        *,
        auth_dir: str | Path | None = None,
        owner_jid: str = "",
        allowed_jids: list[str] | None = None,
        group_policy: str = "ignore",  # "ignore" | "allowlist" | "all"
        group_allowlist: list[str] | None = None,
    ) -> None:
        self._auth_dir = Path(auth_dir) if auth_dir else None
        self._owner_jid = owner_jid
        self._allowed_jids = set(allowed_jids or [])
        self._group_policy = group_policy
        self._group_allowlist = set(group_allowlist or [])
        self._running = False
        self._client: Any = None
        self._task: asyncio.Task[None] | None = None
        self._heartbeat_task: asyncio.Task[None] | None = None
        self._last_heartbeat: float = 0.0
        self._heartbeat_ok: bool = False

    @property
    def id(self) -> str:
        return "whatsapp"

    @property
    def name(self) -> str:
        return "WhatsApp"

    @property
    def is_running(self) -> bool:
        return self._running

    async def start(self) -> None:
        if self._running:
            return

        try:
            await self._start_neonize()
        except ImportError:
            logger.warning("neonize not installed, trying subprocess bridge")
            await self._start_bridge()

    async def stop(self) -> None:
        self._running = False
        if self._heartbeat_task and not self._heartbeat_task.done():
            self._heartbeat_task.cancel()
            try:
                await self._heartbeat_task
            except asyncio.CancelledError:
                pass
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        if self._client and hasattr(self._client, "disconnect"):
            try:
                await self._client.disconnect()
            except Exception:
                pass
        self._client = None
        self._heartbeat_ok = False
        logger.info("WhatsApp channel stopped")

    async def send_reply(self, reply: ChannelReply) -> None:
        if not self._client:
            logger.error("WhatsApp client not connected")
            return

        try:
            if hasattr(self._client, "send_message"):
                await self._client.send_message(reply.chat_id, reply.text)
            else:
                logger.warning("WhatsApp send_message not available")
        except Exception as e:
            logger.error("WhatsApp send error: %s", e)

    async def _start_neonize(self) -> None:
        """Start using neonize library."""
        import neonize  # type: ignore[import-untyped]

        auth_path = self._auth_dir or Path.home() / ".pyclaw" / "whatsapp"
        auth_path.mkdir(parents=True, exist_ok=True)

        client = neonize.NewClient(str(auth_path / "session.db"))

        @client.event
        def on_message(client_ref: Any, message: Any) -> None:
            if not self.message_callback:
                return

            text = _extract_text(message)
            if not text:
                return

            sender = _extract_sender(message)
            chat_id = _extract_chat_id(message)
            is_group = _is_group_message(message)

            if not self._check_access(sender, chat_id, is_group):
                return

            msg = ChannelMessage(
                channel_id="whatsapp",
                sender_id=sender,
                sender_name=_extract_sender_name(message),
                text=text,
                chat_id=chat_id,
                message_id=_extract_message_id(message),
                is_group=is_group,
                is_owner=sender == self._owner_jid,
                raw=message,
            )

            asyncio.get_event_loop().create_task(self.message_callback(msg))

        self._client = client
        self._running = True
        self._task = asyncio.create_task(self._run_neonize(client))
        self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())
        logger.info("WhatsApp channel started (neonize)")

    async def _run_neonize(self, client: Any) -> None:
        """Run neonize client in background."""
        try:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, client.connect)
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error("WhatsApp neonize error: %s", e)
            self._running = False

    async def _start_bridge(self) -> None:
        """Fallback: use a subprocess bridge (whatsapp-web.js via Node)."""
        logger.warning(
            "WhatsApp subprocess bridge not yet implemented. Install neonize: pip install neonize"
        )
        self._running = False

    async def _heartbeat_loop(self) -> None:
        """Periodic connection health check.

        Pings the WhatsApp server at ``HEARTBEAT_INTERVAL_S`` intervals.
        If the ping fails, marks the connection as unhealthy and attempts
        reconnection after a short delay.
        """
        while self._running:
            try:
                await asyncio.sleep(self.HEARTBEAT_INTERVAL_S)
                if not self._running:
                    break
                ok = await self._ping()
                self._heartbeat_ok = ok
                self._last_heartbeat = time.time()
                if not ok:
                    logger.warning("WhatsApp heartbeat failed — connection may be stale")
                    await self._attempt_reconnect()
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.error("WhatsApp heartbeat error: %s", exc)
                self._heartbeat_ok = False

    async def _ping(self) -> bool:
        """Send a lightweight ping to verify the connection is alive."""
        if not self._client:
            return False
        try:
            if hasattr(self._client, "is_connected"):
                return bool(self._client.is_connected)
            if hasattr(self._client, "get_contacts"):
                loop = asyncio.get_event_loop()
                await asyncio.wait_for(
                    loop.run_in_executor(None, lambda: self._client.get_contacts()),
                    timeout=self.HEARTBEAT_TIMEOUT_S,
                )
                return True
        except Exception:
            pass
        return False

    async def _attempt_reconnect(self) -> None:
        """Try to reconnect the neonize client after a heartbeat failure."""
        logger.info("Attempting WhatsApp reconnection...")
        try:
            if self._client and hasattr(self._client, "reconnect"):
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(None, self._client.reconnect)
                self._heartbeat_ok = True
                logger.info("WhatsApp reconnected successfully")
            else:
                logger.warning("Client has no reconnect method; manual restart required")
        except Exception as exc:
            logger.error("WhatsApp reconnection failed: %s", exc)

    @property
    def heartbeat_healthy(self) -> bool:
        """Whether the last heartbeat was successful."""
        return self._heartbeat_ok

    @property
    def last_heartbeat_at(self) -> float:
        """Unix timestamp of the last heartbeat."""
        return self._last_heartbeat

    def _check_access(self, sender: str, chat_id: str, is_group: bool) -> bool:
        """Check if the sender/group is allowed."""
        if sender == self._owner_jid:
            return True
        if self._allowed_jids and sender not in self._allowed_jids:
            return False
        if is_group:
            if self._group_policy == "ignore":
                return False
            if self._group_policy == "allowlist":
                return chat_id in self._group_allowlist
        return True


def _extract_text(message: Any) -> str:
    """Extract text from a neonize message."""
    if hasattr(message, "Message") and message.Message:
        msg = message.Message
        if hasattr(msg, "conversation") and msg.conversation:
            return msg.conversation
        if hasattr(msg, "extendedTextMessage") and msg.extendedTextMessage:
            return msg.extendedTextMessage.text or ""
    return ""


def _extract_sender(message: Any) -> str:
    if hasattr(message, "Info") and hasattr(message.Info, "MessageSource"):
        src = message.Info.MessageSource
        return getattr(src, "Sender", "") or getattr(src, "Chat", "")
    return ""


def _extract_sender_name(message: Any) -> str:
    if hasattr(message, "Info") and hasattr(message.Info, "PushName"):
        return message.Info.PushName or ""
    return ""


def _extract_chat_id(message: Any) -> str:
    if hasattr(message, "Info") and hasattr(message.Info, "MessageSource"):
        return getattr(message.Info.MessageSource, "Chat", "")
    return ""


def _extract_message_id(message: Any) -> str:
    if hasattr(message, "Info") and hasattr(message.Info, "ID"):
        return message.Info.ID
    return ""


def _is_group_message(message: Any) -> bool:
    if hasattr(message, "Info") and hasattr(message.Info, "MessageSource"):
        return getattr(message.Info.MessageSource, "IsGroup", False)
    return False
