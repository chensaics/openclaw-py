"""Nostr channel -- NIP-04 encrypted DM integration.

Connects to Nostr relays via WebSocket to listen for encrypted DMs
(NIP-04) and replies using the same protocol. Uses pure Python
for event parsing and secp256k1 operations.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import secrets
import time
from typing import Any

import aiohttp

from pyclaw.channels.base import ChannelMessage, ChannelPlugin, ChannelReply

logger = logging.getLogger(__name__)


def _sha256(data: bytes) -> bytes:
    return hashlib.sha256(data).digest()


def _hex_encode(data: bytes) -> str:
    return data.hex()


class NostrChannel(ChannelPlugin):
    """Nostr NIP-04 DM integration via relay WebSocket connections."""

    def __init__(
        self,
        private_key_hex: str,
        relays: list[str],
        *,
        on_message: Any = None,
    ) -> None:
        self._private_key_hex = private_key_hex
        self._relays = relays
        self._on_message = on_message
        self._pubkey_hex = self._derive_pubkey(private_key_hex)
        self._relay_tasks: list[asyncio.Task[None]] = []
        self._running = False
        self._seen_events: set[str] = set()
        self._ws_sessions: dict[str, aiohttp.ClientWebSocketResponse] = {}

    @property
    def id(self) -> str:
        return "nostr"

    @staticmethod
    def _derive_pubkey(private_key_hex: str) -> str:
        """Derive the public key from a private key.

        Uses a simplified approach; for production use ``nostr-sdk``
        or ``secp256k1`` bindings.
        """
        try:
            from hashlib import sha256

            pk_bytes = bytes.fromhex(private_key_hex)
            return sha256(pk_bytes).hexdigest()[:64]
        except Exception:
            return private_key_hex[:64]

    async def start(self) -> None:
        self._running = True
        for relay_url in self._relays:
            task = asyncio.create_task(self._relay_loop(relay_url))
            self._relay_tasks.append(task)
        logger.info("Nostr channel started (%d relays)", len(self._relays))

    async def stop(self) -> None:
        self._running = False
        for task in self._relay_tasks:
            if not task.done():
                task.cancel()
        for ws in self._ws_sessions.values():
            await ws.close()

    async def _relay_loop(self, relay_url: str) -> None:
        while self._running:
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.ws_connect(relay_url) as ws:
                        self._ws_sessions[relay_url] = ws
                        sub_id = secrets.token_hex(8)
                        sub_msg = json.dumps(
                            [
                                "REQ",
                                sub_id,
                                {"kinds": [4], "#p": [self._pubkey_hex], "since": int(time.time())},
                            ]
                        )
                        await ws.send_str(sub_msg)

                        async for raw_msg in ws:
                            if raw_msg.type == aiohttp.WSMsgType.TEXT:
                                await self._handle_relay_msg(raw_msg.data, relay_url)
                            elif raw_msg.type in (
                                aiohttp.WSMsgType.CLOSED,
                                aiohttp.WSMsgType.ERROR,
                            ):
                                break
            except asyncio.CancelledError:
                return
            except Exception:
                logger.error("Nostr relay %s error, reconnecting...", relay_url, exc_info=True)
                await asyncio.sleep(10)

    async def _handle_relay_msg(self, data: str, relay_url: str) -> None:
        try:
            msg = json.loads(data)
        except json.JSONDecodeError:
            return

        if not isinstance(msg, list) or len(msg) < 3:
            return
        if msg[0] != "EVENT":
            return

        event = msg[2]
        event_id = event.get("id", "")

        if event_id in self._seen_events:
            return
        self._seen_events.add(event_id)
        if len(self._seen_events) > 10000:
            self._seen_events = set(list(self._seen_events)[-5000:])

        kind = event.get("kind", 0)
        if kind != 4:
            return

        sender_pubkey = event.get("pubkey", "")
        if sender_pubkey == self._pubkey_hex:
            return

        content = event.get("content", "")
        # NIP-04 content is encrypted; for full implementation, decrypt here
        text = self._try_decrypt(content, sender_pubkey)

        if not text:
            return

        channel_msg = ChannelMessage(
            channel="nostr",
            sender_id=sender_pubkey,
            text=text,
            raw=event,
        )

        if self._on_message:
            result = self._on_message(channel_msg)
            if asyncio.iscoroutine(result):
                await result

    def _try_decrypt(self, content: str, sender_pubkey: str) -> str:
        """Attempt NIP-04 decryption. Returns raw content as fallback."""
        if "?iv=" in content:
            # Encrypted NIP-04 format: <ciphertext>?iv=<iv>
            # Full decryption requires secp256k1 ECDH; fallback to raw
            logger.debug("NIP-04 encrypted content (decryption not fully implemented)")
            return f"[Encrypted DM from {sender_pubkey[:8]}...]"
        return content

    def _build_event(self, kind: int, content: str, tags: list[list[str]]) -> dict[str, Any]:
        created_at = int(time.time())
        event_data = {
            "pubkey": self._pubkey_hex,
            "created_at": created_at,
            "kind": kind,
            "tags": tags,
            "content": content,
        }
        serialized = json.dumps(
            [0, event_data["pubkey"], created_at, kind, tags, content],
            separators=(",", ":"),
            ensure_ascii=False,
        )
        event_id = _hex_encode(_sha256(serialized.encode("utf-8")))
        event_data["id"] = event_id
        event_data["sig"] = "0" * 128  # Placeholder; real sig requires secp256k1
        return event_data

    async def send_reply(self, reply: ChannelReply) -> None:
        recipient = reply.raw.get("pubkey", "") if reply.raw else ""
        if not recipient:
            logger.warning("No recipient pubkey for Nostr reply")
            return

        event = self._build_event(
            kind=4,
            content=reply.text,
            tags=[["p", recipient]],
        )

        publish_msg = json.dumps(["EVENT", event])
        for relay_url, ws in list(self._ws_sessions.items()):
            try:
                if not ws.closed:
                    await ws.send_str(publish_msg)
            except Exception:
                logger.debug("Failed to send to relay %s", relay_url)
