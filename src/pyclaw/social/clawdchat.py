"""ClawdChat social platform adapter.

ClawdChat is a real-time chat platform for agents to form groups,
collaborate, and exchange structured messages.
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

CLAWDCHAT_API = "https://clawdchat.ai/api/v1"


@dataclass
class ClawdChatConfig:
    api_url: str = CLAWDCHAT_API
    poll_interval_s: float = 15.0
    default_room: str = "lobby"


class ClawdChatPlatform:
    """Adapter for the ClawdChat agent-to-agent messaging platform."""

    def __init__(self, config: ClawdChatConfig | None = None) -> None:
        self._config = config or ClawdChatConfig()
        self._status = PlatformStatus.DISCONNECTED
        self._session_token: str = ""
        self._profile: AgentProfile | None = None
        self._last_poll: float = 0.0
        self._rooms: list[str] = []

    @property
    def platform_id(self) -> str:
        return "clawdchat"

    @property
    def display_name(self) -> str:
        return "ClawdChat"

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
            "room": self._config.default_room,
        }

        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.post(
                    f"{self._config.api_url}/join",
                    json=payload,
                )
                if resp.status_code in (200, 201):
                    data = resp.json()
                    self._session_token = data.get("sessionToken", "")
                    self._rooms = data.get("rooms", [self._config.default_room])
                    self._status = PlatformStatus.CONNECTED
                    logger.info("Joined ClawdChat room %s", self._config.default_room)
                    return True
                self._status = PlatformStatus.ERROR
                return False
        except httpx.HTTPError as exc:
            logger.warning("ClawdChat join error: %s", exc)
            self._status = PlatformStatus.ERROR
            return False

    async def leave(self) -> None:
        if self._session_token:
            import httpx

            try:
                async with httpx.AsyncClient(timeout=10) as client:
                    await client.post(
                        f"{self._config.api_url}/leave",
                        headers={"Authorization": f"Bearer {self._session_token}"},
                    )
            except httpx.HTTPError:
                pass
        self._status = PlatformStatus.DISCONNECTED
        self._session_token = ""
        self._rooms = []

    async def send(self, message: str, thread_id: str = "") -> bool:
        if not self._session_token:
            return False

        import httpx

        payload: dict[str, Any] = {
            "content": message,
            "room": thread_id or self._config.default_room,
        }

        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(
                    f"{self._config.api_url}/send",
                    headers={"Authorization": f"Bearer {self._session_token}"},
                    json=payload,
                )
                return resp.status_code in (200, 201)
        except httpx.HTTPError:
            return False

    async def poll(self) -> list[SocialMessage]:
        if not self._session_token:
            return []

        now = time.time()
        if now - self._last_poll < self._config.poll_interval_s:
            return []
        self._last_poll = now

        import httpx

        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(
                    f"{self._config.api_url}/messages",
                    headers={"Authorization": f"Bearer {self._session_token}"},
                    params={"rooms": ",".join(self._rooms)},
                )
                if resp.status_code != 200:
                    return []
                data = resp.json()
                return [
                    SocialMessage(
                        platform="clawdchat",
                        sender_id=m.get("agentId", ""),
                        sender_name=m.get("displayName", ""),
                        content=m.get("content", ""),
                        thread_id=m.get("room", ""),
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
            "rooms": self._rooms,
            "agentId": self._profile.agent_id if self._profile else "",
        }
