"""Account helpers — list accounts, resolve IDs, and manage identities per channel.

Provides a unified interface for channels that support account/contact
listing and ID resolution (e.g., mapping usernames to internal IDs).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class ChannelAccount:
    """Represents an account / bot identity on a channel."""

    channel_type: str
    account_id: str
    display_name: str = ""
    username: str = ""
    avatar_url: str = ""
    is_bot: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class AccountCapabilities:
    """What account-related features a channel supports."""

    list_contacts: bool = False
    resolve_username: bool = False
    get_profile: bool = False
    set_profile: bool = False
    get_bot_id: bool = False


CHANNEL_ACCOUNT_CAPS: dict[str, AccountCapabilities] = {
    "telegram": AccountCapabilities(
        list_contacts=True,
        resolve_username=True,
        get_profile=True,
        set_profile=True,
        get_bot_id=True,
    ),
    "discord": AccountCapabilities(
        list_contacts=True,
        resolve_username=True,
        get_profile=True,
        set_profile=True,
        get_bot_id=True,
    ),
    "slack": AccountCapabilities(
        list_contacts=True,
        resolve_username=True,
        get_profile=True,
        set_profile=True,
        get_bot_id=True,
    ),
    "matrix": AccountCapabilities(
        resolve_username=True,
        get_profile=True,
        get_bot_id=True,
    ),
    "whatsapp": AccountCapabilities(
        list_contacts=True,
        get_profile=True,
        get_bot_id=True,
    ),
    "signal": AccountCapabilities(get_bot_id=True),
    "feishu": AccountCapabilities(
        list_contacts=True,
        resolve_username=True,
        get_profile=True,
        get_bot_id=True,
    ),
    "msteams": AccountCapabilities(
        list_contacts=True,
        get_profile=True,
        get_bot_id=True,
    ),
    "mattermost": AccountCapabilities(
        list_contacts=True,
        resolve_username=True,
        get_profile=True,
        get_bot_id=True,
    ),
    "dingtalk": AccountCapabilities(get_bot_id=True),
    "irc": AccountCapabilities(resolve_username=True),
    "googlechat": AccountCapabilities(get_bot_id=True),
    "line": AccountCapabilities(get_profile=True, get_bot_id=True),
    "qq": AccountCapabilities(list_contacts=True, get_bot_id=True),
    "twitch": AccountCapabilities(resolve_username=True, get_bot_id=True),
    "nostr": AccountCapabilities(get_profile=True),
}


def get_account_capabilities(channel_type: str) -> AccountCapabilities:
    return CHANNEL_ACCOUNT_CAPS.get(channel_type, AccountCapabilities())


class AccountHelper:
    """Unified helper for channel account operations."""

    def __init__(self, channel_type: str, client: Any = None) -> None:
        self._channel_type = channel_type
        self._client = client
        self._caps = get_account_capabilities(channel_type)
        self._cache: dict[str, ChannelAccount] = {}

    @property
    def capabilities(self) -> AccountCapabilities:
        return self._caps

    async def get_bot_identity(self) -> ChannelAccount | None:
        """Get the bot's own account info on this channel."""
        if not self._caps.get_bot_id or not self._client:
            return None
        try:
            if hasattr(self._client, "get_me"):
                me = await self._client.get_me()
                return ChannelAccount(
                    channel_type=self._channel_type,
                    account_id=str(getattr(me, "id", "")),
                    display_name=getattr(me, "first_name", "") or getattr(me, "name", ""),
                    username=getattr(me, "username", ""),
                    is_bot=True,
                )
        except Exception as exc:
            logger.debug("Failed to get bot identity for %s: %s", self._channel_type, exc)
        return None

    async def list_contacts(self, limit: int = 100) -> list[ChannelAccount]:
        """List contacts / members visible to the bot."""
        if not self._caps.list_contacts or not self._client:
            return []
        results: list[ChannelAccount] = []
        try:
            if hasattr(self._client, "get_contacts"):
                contacts = await self._client.get_contacts()
                for c in contacts[:limit]:
                    acc = ChannelAccount(
                        channel_type=self._channel_type,
                        account_id=str(getattr(c, "id", "")),
                        display_name=getattr(c, "name", ""),
                        username=getattr(c, "username", ""),
                        is_bot=bool(getattr(c, "is_bot", False)),
                    )
                    results.append(acc)
                    self._cache[acc.account_id] = acc
        except Exception as exc:
            logger.debug("Failed to list contacts for %s: %s", self._channel_type, exc)
        return results

    async def resolve_username(self, username: str) -> ChannelAccount | None:
        """Resolve a username to an account."""
        if not self._caps.resolve_username:
            return None
        for acc in self._cache.values():
            if acc.username == username:
                return acc
        return None

    def get_cached(self, account_id: str) -> ChannelAccount | None:
        """Get a cached account by ID."""
        return self._cache.get(account_id)
