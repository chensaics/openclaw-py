"""Gmail watcher hook — monitors Gmail for new messages.

Triggered via heartbeat or cron. Uses Gmail API (OAuth2) to check
for unread messages and can forward summaries to the agent.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from pyclaw.hooks.types import HookEvent

logger = logging.getLogger(__name__)


async def handle(event: HookEvent) -> None:
    """Check Gmail for new messages on heartbeat/cron trigger."""
    context = event.context or {}
    credentials_path = context.get("gmail_credentials", "")
    label = context.get("gmail_label", "INBOX")
    max_results = context.get("gmail_max_results", 5)

    if not credentials_path:
        logger.debug("Gmail watcher: no credentials configured")
        return

    try:
        unread = await _fetch_unread_messages(credentials_path, label, max_results)
    except Exception as exc:
        logger.warning("Gmail watcher error: %s", exc)
        return

    if not unread:
        return

    summary = _build_summary(unread)
    logger.info("Gmail: %d new messages", len(unread))

    # If a reply callback is provided, forward the summary
    reply_fn = context.get("reply_fn")
    if reply_fn and callable(reply_fn):
        await reply_fn(summary)


async def _fetch_unread_messages(
    credentials_path: str,
    label: str = "INBOX",
    max_results: int = 5,
) -> list[dict[str, Any]]:
    """Fetch unread Gmail messages using the Gmail API."""
    try:
        import aiohttp
    except ImportError:
        logger.warning("aiohttp required for Gmail watcher")
        return []

    # Load OAuth2 credentials
    with open(credentials_path) as f:
        creds = json.load(f)

    access_token = creds.get("access_token", "")
    if not access_token:
        logger.warning("Gmail: no access_token in credentials")
        return []

    url = "https://gmail.googleapis.com/gmail/v1/users/me/messages"
    params = {
        "q": f"is:unread label:{label}",
        "maxResults": str(max_results),
    }
    headers = {"Authorization": f"Bearer {access_token}"}

    async with aiohttp.ClientSession() as session:
        async with session.get(url, params=params, headers=headers) as resp:
            if resp.status != 200:
                logger.warning("Gmail API error: %d", resp.status)
                return []
            data = await resp.json()

    messages = data.get("messages", [])
    results: list[dict[str, Any]] = []

    for msg_ref in messages[:max_results]:
        msg_id = msg_ref.get("id", "")
        detail = await _fetch_message_detail(access_token, msg_id)
        if detail:
            results.append(detail)

    return results


async def _fetch_message_detail(access_token: str, message_id: str) -> dict[str, Any] | None:
    try:
        import aiohttp
    except ImportError:
        return None

    url = f"https://gmail.googleapis.com/gmail/v1/users/me/messages/{message_id}"
    headers = {"Authorization": f"Bearer {access_token}"}
    params = {"format": "metadata", "metadataHeaders": "Subject,From,Date"}

    async with aiohttp.ClientSession() as session:
        async with session.get(url, params=params, headers=headers) as resp:
            if resp.status != 200:
                return None
            data = await resp.json()

    headers_data = data.get("payload", {}).get("headers", [])
    result: dict[str, Any] = {"id": message_id, "snippet": data.get("snippet", "")}
    for h in headers_data:
        name = h.get("name", "").lower()
        if name in ("subject", "from", "date"):
            result[name] = h.get("value", "")

    return result


def _build_summary(messages: list[dict[str, Any]]) -> str:
    lines = [f"📧 {len(messages)} new Gmail message(s):\n"]
    for msg in messages:
        subject = msg.get("subject", "(no subject)")
        sender = msg.get("from", "unknown")
        snippet = msg.get("snippet", "")[:100]
        lines.append(f"• **{subject}** from {sender}")
        if snippet:
            lines.append(f"  {snippet}")
    return "\n".join(lines)
