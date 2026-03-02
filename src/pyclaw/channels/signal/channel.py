"""Signal channel implementation using signal-cli JSON-RPC and SSE."""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from typing import Any

from pyclaw.channels.base import ChannelMessage, ChannelPlugin, ChannelReply

logger = logging.getLogger(__name__)

_DEFAULT_BASE_URL = "http://127.0.0.1:8080"


class SignalChannel(ChannelPlugin):
    """Signal messaging channel via signal-cli daemon's REST/SSE API."""

    def __init__(
        self,
        *,
        base_url: str = _DEFAULT_BASE_URL,
        account: str = "",
        owner_number: str = "",
        allowed_numbers: list[str] | None = None,
        group_policy: str = "ignore",
        group_allowlist: list[str] | None = None,
        dm_policy: str = "allowlist",
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._account = account
        self._owner_number = owner_number
        self._allowed_numbers = set(allowed_numbers or [])
        self._group_policy = group_policy
        self._group_allowlist = set(group_allowlist or [])
        self._dm_policy = dm_policy
        self._running = False
        self._task: asyncio.Task[None] | None = None

    @property
    def id(self) -> str:
        return "signal"

    @property
    def name(self) -> str:
        return "Signal"

    @property
    def is_running(self) -> bool:
        return self._running

    async def start(self) -> None:
        if self._running:
            return

        # Verify signal-cli is reachable
        if not await self._health_check():
            logger.error("signal-cli not reachable at %s", self._base_url)
            return

        self._running = True
        self._task = asyncio.create_task(self._event_loop())
        logger.info("Signal channel started (SSE at %s)", self._base_url)

    async def stop(self) -> None:
        self._running = False
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Signal channel stopped")

    async def send_reply(self, reply: ChannelReply) -> None:
        """Send a message via signal-cli JSON-RPC."""
        target = _parse_target(reply.chat_id)
        params: dict[str, Any] = {"message": reply.text}

        if target.get("type") == "group":
            params["groupId"] = target["id"]
        else:
            params["recipient"] = [target["id"]]

        if self._account:
            params["account"] = self._account

        await self._rpc_request("send", params)

    async def _health_check(self) -> bool:
        """Check if signal-cli daemon is running."""
        import aiohttp  # type: ignore[import-untyped]

        try:
            async with (
                aiohttp.ClientSession() as session,
                session.get(
                    f"{self._base_url}/api/v1/check", timeout=aiohttp.ClientTimeout(total=5)
                ) as resp,
            ):
                return resp.status == 200
        except Exception:
            return False

    async def _rpc_request(self, method: str, params: dict[str, Any]) -> Any:
        """Send a JSON-RPC 2.0 request to signal-cli."""
        import aiohttp

        payload = {
            "jsonrpc": "2.0",
            "id": str(uuid.uuid4()),
            "method": method,
            "params": params,
        }
        try:
            async with (
                aiohttp.ClientSession() as session,
                session.post(
                    f"{self._base_url}/api/v1/rpc",
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=30),
                ) as resp,
            ):
                data = await resp.json()
                if "error" in data:
                    logger.error("Signal RPC error: %s", data["error"])
                return data.get("result")
        except Exception as e:
            logger.error("Signal RPC request failed: %s", e)
            return None

    async def _event_loop(self) -> None:
        """Stream SSE events from signal-cli and dispatch messages."""
        import aiohttp

        url = f"{self._base_url}/api/v1/events"
        if self._account:
            url += f"?account={self._account}"

        while self._running:
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(url, timeout=aiohttp.ClientTimeout(total=0)) as resp:
                        async for line in resp.content:
                            if not self._running:
                                break
                            decoded = line.decode("utf-8", errors="replace").strip()
                            if decoded.startswith("data:"):
                                data_str = decoded[5:].strip()
                                if data_str:
                                    await self._handle_event(data_str)
            except asyncio.CancelledError:
                break
            except Exception as e:
                if self._running:
                    logger.warning("Signal SSE connection error: %s, reconnecting...", e)
                    await asyncio.sleep(5)

    async def _handle_event(self, data_str: str) -> None:
        """Parse and dispatch a Signal event."""
        try:
            event = json.loads(data_str)
        except json.JSONDecodeError:
            return

        envelope = event.get("envelope", {})
        data_msg = envelope.get("dataMessage")
        if not data_msg:
            return

        text = data_msg.get("message", "")
        if not text:
            return

        source = envelope.get("source", "")
        source_name = envelope.get("sourceName", "")
        group_info = data_msg.get("groupInfo")
        is_group = group_info is not None
        chat_id = group_info.get("groupId", "") if group_info else source

        if not self._check_access(source, chat_id, is_group):
            return

        if not self.message_callback:
            return

        msg = ChannelMessage(
            channel_id="signal",
            sender_id=source,
            sender_name=source_name,
            text=text,
            chat_id=chat_id,
            message_id=str(envelope.get("timestamp", "")),
            is_group=is_group,
            is_owner=source == self._owner_number,
            raw=event,
        )

        try:
            await self.message_callback(msg)
        except Exception as e:
            logger.error("Signal message handler error: %s", e)

    def _check_access(self, sender: str, chat_id: str, is_group: bool) -> bool:
        if sender == self._owner_number:
            return True

        if is_group:
            if self._group_policy == "ignore":
                return False
            if self._group_policy == "allowlist":
                return chat_id in self._group_allowlist
            return True

        if self._dm_policy == "allowlist":
            return sender in self._allowed_numbers
        if self._dm_policy == "owner":
            return sender == self._owner_number
        return True


def _parse_target(raw: str) -> dict[str, str]:
    """Parse a recipient string: 'group:ID', 'username:USER', or E.164 number."""
    if raw.startswith("group:"):
        return {"type": "group", "id": raw[6:]}
    if raw.startswith("username:") or raw.startswith("u:"):
        prefix = "username:" if raw.startswith("username:") else "u:"
        return {"type": "username", "id": raw[len(prefix) :]}
    return {"type": "number", "id": raw}
