"""Thread ownership plugin — enforce per-thread agent ownership on Slack.

Ported from ``extensions/thread-ownership/index.ts``.
Tracks @-mentions in threads and prevents other agents from replying in
owned threads by checking ownership via an HTTP API.
"""

from __future__ import annotations

import logging
import time

import httpx

logger = logging.getLogger(__name__)

MENTION_TTL_S = 5 * 60  # 5 minutes


class ThreadOwnershipTracker:
    """Tracks Slack thread ownership via @-mentions and ownership API."""

    def __init__(
        self,
        agent_id: str = "main",
        agent_name: str = "",
        bot_user_id: str = "",
        forwarder_url: str = "http://slack-forwarder:8750",
        ab_test_channels: set[str] | None = None,
    ) -> None:
        self._agent_id = agent_id
        self._agent_name = agent_name
        self._bot_user_id = bot_user_id
        self._forwarder_url = forwarder_url.rstrip("/")
        self._ab_test_channels = ab_test_channels or set()
        # {channel_id}:{thread_ts} -> timestamp
        self._mentioned_threads: dict[str, float] = {}

    def _clean_expired(self) -> None:
        now = time.time()
        expired = [k for k, ts in self._mentioned_threads.items() if now - ts > MENTION_TTL_S]
        for k in expired:
            del self._mentioned_threads[k]

    def on_message_received(
        self,
        text: str,
        channel_id: str,
        thread_ts: str,
        msg_channel: str,
    ) -> None:
        """Track @-mentions in Slack threads."""
        if msg_channel != "slack" or not thread_ts or not channel_id:
            return

        mentioned = False
        if self._agent_name and f"@{self._agent_name}" in text:
            mentioned = True
        if self._bot_user_id and f"<@{self._bot_user_id}>" in text:
            mentioned = True

        if mentioned:
            self._clean_expired()
            self._mentioned_threads[f"{channel_id}:{thread_ts}"] = time.time()

    async def should_cancel_send(
        self,
        channel_id: str,
        thread_ts: str,
        msg_channel: str,
    ) -> bool:
        """Check if sending to this thread should be cancelled.

        Returns True if another agent owns the thread and we should not send.
        """
        if msg_channel != "slack" or not thread_ts:
            return False

        if self._ab_test_channels and channel_id not in self._ab_test_channels:
            return False

        self._clean_expired()
        if f"{channel_id}:{thread_ts}" in self._mentioned_threads:
            return False

        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                resp = await client.post(
                    f"{self._forwarder_url}/api/v1/ownership/{channel_id}/{thread_ts}",
                    json={"agent_id": self._agent_id},
                )
                if resp.status_code == 200:
                    return False  # We own it
                if resp.status_code == 409:
                    body = resp.json()
                    logger.info(
                        "thread-ownership: cancelled send to %s:%s — owned by %s",
                        channel_id,
                        thread_ts,
                        body.get("owner", "unknown"),
                    )
                    return True
                logger.warning(
                    "thread-ownership: unexpected status %d, allowing send",
                    resp.status_code,
                )
        except Exception as exc:
            logger.warning("thread-ownership: ownership check failed (%s), allowing send", exc)

        return False
