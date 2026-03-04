"""Tlon/Urbit channel -- SSE event stream + REST API.

Connects to a Tlon/Urbit ship via SSE (Server-Sent Events) to receive
chat messages and uses the ship's HTTP API for replies.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

import aiohttp

from pyclaw.channels.base import ChannelMessage, ChannelPlugin, ChannelReply

logger = logging.getLogger(__name__)


class TlonChannel(ChannelPlugin):
    """Tlon/Urbit integration via SSE + REST."""

    def __init__(
        self,
        ship_url: str,
        ship_name: str,
        ship_code: str,
        channel_path: str = "/chat",
        *,
        on_message: Any = None,
    ) -> None:
        self._ship_url = ship_url.rstrip("/")
        self._ship_name = ship_name
        self._ship_code = ship_code
        self._channel_path = channel_path
        self._on_message = on_message
        self._sse_task: asyncio.Task[None] | None = None
        self._running = False
        self._cookie: str = ""
        self._event_id = 0

    @property
    def id(self) -> str:
        return "tlon"

    async def start(self) -> None:
        self._running = True
        await self._authenticate()
        self._sse_task = asyncio.create_task(self._sse_loop())
        logger.info("Tlon channel started (ship: %s)", self._ship_name)

    async def stop(self) -> None:
        self._running = False
        if self._sse_task and not self._sse_task.done():
            self._sse_task.cancel()

    async def _authenticate(self) -> None:
        async with (
            aiohttp.ClientSession() as session,
            session.post(
                f"{self._ship_url}/~/login",
                data={"password": self._ship_code},
            ) as resp,
        ):
            if resp.status == 204 or resp.status == 200:
                cookie = resp.cookies.get("urbauth-~" + self._ship_name)
                if cookie:
                    self._cookie = f"urbauth-~{self._ship_name}={cookie.value}"
            else:
                logger.error("Tlon auth failed: %d", resp.status)

    async def _sse_loop(self) -> None:
        channel_uid = f"pyclaw-{int(asyncio.get_event_loop().time() * 1000)}"
        url = f"{self._ship_url}/~/channel/{channel_uid}"

        while self._running:
            try:
                self._event_id += 1
                sub_body = json.dumps(
                    [
                        {
                            "id": self._event_id,
                            "action": "subscribe",
                            "ship": self._ship_name,
                            "app": "chat-store",
                            "path": self._channel_path,
                        }
                    ]
                )

                headers = {"Cookie": self._cookie, "Content-Type": "application/json"}
                async with aiohttp.ClientSession() as session:
                    await session.put(url, data=sub_body, headers=headers)

                    async with session.get(url, headers=headers) as resp:
                        async for line in resp.content:
                            decoded = line.decode("utf-8", errors="replace").strip()
                            if decoded.startswith("data:"):
                                data_str = decoded[5:].strip()
                                await self._handle_event(json.loads(data_str))
            except asyncio.CancelledError:
                return
            except Exception:
                logger.error("Tlon SSE error, reconnecting...", exc_info=True)
                await asyncio.sleep(5)

    async def _handle_event(self, event: dict[str, Any]) -> None:
        json_data = event.get("json", {})
        if "chat-update" not in json_data:
            return

        update = json_data["chat-update"]
        message = update.get("message", {})
        author = message.get("author", "")
        if author == f"~{self._ship_name}":
            return

        letter = message.get("letter", {})
        text = letter.get("text", "") if isinstance(letter, dict) else str(letter)
        if not text:
            return

        chat = update.get("chat")
        chat_id = str((chat or {}).get("path", author)) if isinstance(chat, dict) else author
        msg = ChannelMessage(
            channel_id="tlon",
            sender_id=author,
            sender_name=author,
            text=text,
            chat_id=chat_id,
            raw=event,
        )

        if self._on_message:
            result = self._on_message(msg)
            if asyncio.iscoroutine(result):
                await result

        self._event_id += 1
        ack_body = json.dumps([{"id": self._event_id, "action": "ack", "event-id": event.get("id", 0)}])
        headers = {"Cookie": self._cookie, "Content-Type": "application/json"}
        async with aiohttp.ClientSession() as session:
            await session.put(
                f"{self._ship_url}/~/channel/pyclaw-ack",
                data=ack_body,
                headers=headers,
            )

    async def send_reply(self, reply: ChannelReply) -> None:
        self._event_id += 1
        poke_body = json.dumps(
            [
                {
                    "id": self._event_id,
                    "action": "poke",
                    "ship": self._ship_name,
                    "app": "chat-hook",
                    "mark": "chat-action",
                    "json": {
                        "message": {
                            "path": self._channel_path,
                            "envelope": {
                                "uid": f"pyclaw-{self._event_id}",
                                "number": 1,
                                "author": f"~{self._ship_name}",
                                "when": int(asyncio.get_event_loop().time() * 1000),
                                "letter": {"text": reply.text},
                            },
                        },
                    },
                }
            ]
        )

        headers = {"Cookie": self._cookie, "Content-Type": "application/json"}
        async with (
            aiohttp.ClientSession() as session,
            session.put(
                f"{self._ship_url}/~/channel/pyclaw-send",
                data=poke_body,
                headers=headers,
            ) as resp,
        ):
            if resp.status >= 400:
                logger.warning("Tlon send failed: %d", resp.status)
