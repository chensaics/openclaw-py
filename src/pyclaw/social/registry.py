"""Social platform registry — discover, register, and join agent social networks.

Provides a lightweight adapter layer for platforms where agents can
interact with other agents (Moltbook, ClawdChat, etc.).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Protocol

logger = logging.getLogger(__name__)


class PlatformStatus(str, Enum):
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    ERROR = "error"


@dataclass
class AgentProfile:
    """The agent's identity on a social platform."""

    agent_id: str = ""
    display_name: str = ""
    description: str = ""
    capabilities: list[str] = field(default_factory=list)
    avatar_url: str = ""


@dataclass
class SocialMessage:
    """A message received from or sent to a social platform."""

    platform: str = ""
    sender_id: str = ""
    sender_name: str = ""
    content: str = ""
    thread_id: str = ""
    timestamp: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)


class SocialPlatform(Protocol):
    """Protocol that all social platform adapters must implement."""

    @property
    def platform_id(self) -> str: ...

    @property
    def display_name(self) -> str: ...

    @property
    def status(self) -> PlatformStatus: ...

    async def join(self, profile: AgentProfile) -> bool:
        """Register the agent on the platform. Returns True on success."""
        ...

    async def leave(self) -> None:
        """Unregister from the platform."""
        ...

    async def send(self, message: str, thread_id: str = "") -> bool:
        """Send a message. Returns True on success."""
        ...

    async def poll(self) -> list[SocialMessage]:
        """Poll for new messages (non-blocking)."""
        ...

    def status_info(self) -> dict[str, Any]:
        """Return status information for diagnostics."""
        ...


class SocialPlatformRegistry:
    """Manages social platform adapters."""

    def __init__(self) -> None:
        self._platforms: dict[str, SocialPlatform] = {}

    def register(self, platform: SocialPlatform) -> None:
        self._platforms[platform.platform_id] = platform
        logger.info("Registered social platform: %s", platform.display_name)

    def get(self, platform_id: str) -> SocialPlatform | None:
        return self._platforms.get(platform_id)

    def list_platforms(self) -> list[dict[str, Any]]:
        return [
            {
                "id": p.platform_id,
                "name": p.display_name,
                "status": p.status.value,
            }
            for p in self._platforms.values()
        ]

    async def join_all(self, profile: AgentProfile) -> dict[str, bool]:
        results: dict[str, bool] = {}
        for pid, platform in self._platforms.items():
            try:
                results[pid] = await platform.join(profile)
            except Exception:
                logger.exception("Failed to join %s", pid)
                results[pid] = False
        return results

    async def leave_all(self) -> None:
        for platform in self._platforms.values():
            try:
                await platform.leave()
            except Exception:
                logger.exception("Failed to leave %s", platform.platform_id)

    async def poll_all(self) -> list[SocialMessage]:
        messages: list[SocialMessage] = []
        for platform in self._platforms.values():
            try:
                messages.extend(await platform.poll())
            except Exception:
                logger.exception("Poll failed for %s", platform.platform_id)
        return messages
