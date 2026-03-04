"""Pairing challenge flow — issue and verify pairing codes."""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable

from pyclaw.pairing.store import PairingRequest, upsert_pairing_request

logger = logging.getLogger(__name__)

SendReplyFn = Callable[[str, str], Awaitable[None] | None]


def build_pairing_reply(code: str) -> str:
    """Build a user-friendly pairing reply message."""
    return (
        f"To pair this device, run the following command on your gateway host:\n\n"
        f"  pyclaw pair approve {code}\n\n"
        f"This code expires in 1 hour."
    )


async def issue_pairing_challenge(
    channel: str,
    sender_id: str,
    display_name: str = "",
    send_reply: SendReplyFn | None = None,
) -> PairingRequest:
    """Issue a pairing challenge for a new sender.

    Creates or retrieves a pairing code and optionally sends the reply.
    """
    request = upsert_pairing_request(
        channel=channel,
        sender_id=sender_id,
        display_name=display_name,
    )

    if send_reply:
        reply_text = build_pairing_reply(request.code)
        import asyncio

        result = send_reply(sender_id, reply_text)
        if asyncio.iscoroutine(result):
            await result

    return request
