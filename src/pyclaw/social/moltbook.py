"""Moltbook social platform adapter.

Moltbook is an agent-to-agent social network where AI agents can
register profiles, discover peers, and exchange messages.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Any

from pyclaw.social.registry import (
    AgentProfile,
    PlatformStatus,
    SocialMessage,
)

logger = logging.getLogger(__name__)

MOLTBOOK_API = "https://moltbook.ai/api/v1"


@dataclass
class MoltbookConfig:
    api_url: str = MOLTBOOK_API
    poll_interval_s: float = 30.0
    auto_reply: bool = True


class MoltbookPlatform:
    """Adapter for the Moltbook agent social network."""

    def __init__(self, config: MoltbookConfig | None = None) -> None:
        self._config = config or MoltbookConfig()
        self._status = PlatformStatus.DISCONNECTED
        self._agent_token: str = ""
        self._profile: AgentProfile | None = None
        self._last_poll: float = 0.0

    @property
    def platform_id(self) -> str:
        return "moltbook"

    @property
    def display_name(self) -> str:
        return "Moltbook"

    @property
    def status(self) -> PlatformStatus:
        return self._status

    async def join(self, profile: AgentProfile) -> bool:
        import httpx

        self._status = PlatformStatus.CONNECTING
        self._profile = profile

        payload = {
            "agentId": profile.agent_id,
            "displayName": profile.display_name,
            "description": profile.description,
            "capabilities": profile.capabilities,
        }
        if profile.avatar_url:
            payload["avatarUrl"] = profile.avatar_url

        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.post(
                    f"{self._config.api_url}/agents/register",
                    json=payload,
                )
                if resp.status_code in (200, 201):
                    data = resp.json()
                    self._agent_token = data.get("token", "")
                    self._status = PlatformStatus.CONNECTED
                    logger.info("Joined Moltbook as %s", profile.display_name)
                    return True
                logger.warning("Moltbook register failed: %s", resp.status_code)
                self._status = PlatformStatus.ERROR
                return False
        except httpx.HTTPError as exc:
            logger.warning("Moltbook join error: %s", exc)
            self._status = PlatformStatus.ERROR
            return False

    async def leave(self) -> None:
        if not self._agent_token:
            self._status = PlatformStatus.DISCONNECTED
            return

        import httpx

        try:
            async with httpx.AsyncClient(timeout=10) as client:
                await client.post(
                    f"{self._config.api_url}/agents/unregister",
                    headers={"Authorization": f"Bearer {self._agent_token}"},
                )
        except httpx.HTTPError:
            pass
        finally:
            self._status = PlatformStatus.DISCONNECTED
            self._agent_token = ""

    async def send(self, message: str, thread_id: str = "") -> bool:
        if not self._agent_token:
            return False

        import httpx

        payload: dict[str, Any] = {"content": message}
        if thread_id:
            payload["threadId"] = thread_id

        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(
                    f"{self._config.api_url}/messages/send",
                    headers={"Authorization": f"Bearer {self._agent_token}"},
                    json=payload,
                )
                return resp.status_code in (200, 201)
        except httpx.HTTPError:
            return False

    async def poll(self) -> list[SocialMessage]:
        if not self._agent_token:
            return []

        now = time.time()
        if now - self._last_poll < self._config.poll_interval_s:
            return []
        self._last_poll = now

        import httpx

        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(
                    f"{self._config.api_url}/messages/inbox",
                    headers={"Authorization": f"Bearer {self._agent_token}"},
                )
                if resp.status_code != 200:
                    return []
                data = resp.json()
                return [
                    SocialMessage(
                        platform="moltbook",
                        sender_id=m.get("senderId", ""),
                        sender_name=m.get("senderName", ""),
                        content=m.get("content", ""),
                        thread_id=m.get("threadId", ""),
                        timestamp=m.get("timestamp", 0.0),
                    )
                    for m in data.get("messages", [])
                ]
        except httpx.HTTPError:
            return []

    def status_info(self) -> dict[str, Any]:
        return {
            "platform": self.platform_id,
            "status": self._status.value,
            "apiUrl": self._config.api_url,
            "agentId": self._profile.agent_id if self._profile else "",
        }
