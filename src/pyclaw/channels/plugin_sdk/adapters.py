"""Channel adapter protocols — 20+ adapter Protocol definitions for plugin SDK.

Ported from ``src/channels/channel-plugin-sdk/adapters/*.ts``.

Each protocol defines an optional capability a channel plugin can implement.
The gateway checks for protocol conformance at runtime via ``hasattr``/duck-typing.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

# ---------------------------------------------------------------------------
# Shared types
# ---------------------------------------------------------------------------


@dataclass
class ChannelIdentity:
    """Identity of a channel instance."""

    channel_id: str
    channel_type: str
    display_name: str = ""
    bot_user_id: str = ""


@dataclass
class InboundTurn:
    """A normalized inbound message turn."""

    text: str
    sender_id: str
    chat_id: str
    message_id: str = ""
    thread_id: str = ""
    is_group: bool = False
    is_mention: bool = False
    reply_to_id: str = ""
    media: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class OutboundPayload:
    """Outbound message payload."""

    chat_id: str
    text: str = ""
    media: list[dict[str, Any]] = field(default_factory=list)
    reply_to: str = ""
    thread_id: str = ""
    parse_mode: str = ""
    buttons: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class SendResult:
    """Result from sending a message."""

    success: bool
    message_id: str = ""
    error: str = ""


# ---------------------------------------------------------------------------
# Adapter Protocols
# ---------------------------------------------------------------------------


@runtime_checkable
class ConfigAdapter(Protocol):
    """Provides channel configuration schema and validation."""

    def get_config_schema(self) -> dict[str, Any]: ...
    def validate_config(self, config: dict[str, Any]) -> list[str]: ...


@runtime_checkable
class AuthAdapter(Protocol):
    """Handles channel authentication."""

    async def authenticate(self, credentials: dict[str, Any]) -> bool: ...
    async def refresh_auth(self) -> bool: ...
    def is_authenticated(self) -> bool: ...


@runtime_checkable
class PairingAdapter(Protocol):
    """Handles device/account pairing for the channel."""

    async def initiate_pairing(self, code: str) -> dict[str, Any]: ...
    async def complete_pairing(self, response: str) -> bool: ...
    def is_paired(self) -> bool: ...


@runtime_checkable
class SecurityAdapter(Protocol):
    """Channel-level security checks."""

    def is_sender_allowed(self, sender_id: str, chat_id: str) -> bool: ...
    def is_group_allowed(self, chat_id: str) -> bool: ...
    def get_security_policy(self) -> dict[str, Any]: ...


@runtime_checkable
class GroupsAdapter(Protocol):
    """Group/channel management."""

    async def list_groups(self) -> list[dict[str, Any]]: ...
    async def get_group_info(self, chat_id: str) -> dict[str, Any]: ...
    def supports_threads(self) -> bool: ...


@runtime_checkable
class MentionsAdapter(Protocol):
    """@mention detection and handling."""

    def is_bot_mentioned(self, message: InboundTurn) -> bool: ...
    def extract_mention_text(self, message: InboundTurn) -> str: ...
    def get_bot_mention_pattern(self) -> str: ...


@runtime_checkable
class OutboundAdapter(Protocol):
    """Outbound message sending."""

    async def send_text(self, payload: OutboundPayload) -> SendResult: ...
    async def send_media(self, payload: OutboundPayload) -> SendResult: ...
    async def edit_message(self, chat_id: str, message_id: str, text: str) -> SendResult: ...
    async def delete_message(self, chat_id: str, message_id: str) -> bool: ...


@runtime_checkable
class StatusAdapter(Protocol):
    """Channel status and health reporting."""

    async def get_status(self) -> dict[str, Any]: ...
    async def probe(self) -> bool: ...
    def get_issues(self) -> list[str]: ...


@runtime_checkable
class StreamingAdapter(Protocol):
    """Draft/streaming message support."""

    def supports_streaming(self) -> bool: ...
    async def start_draft(self, chat_id: str, thread_id: str) -> str: ...
    async def update_draft(self, draft_id: str, text: str) -> bool: ...
    async def finalize_draft(self, draft_id: str, text: str) -> SendResult: ...


@runtime_checkable
class ThreadingAdapter(Protocol):
    """Thread management."""

    def supports_threads(self) -> bool: ...
    async def create_thread(self, chat_id: str, message_id: str) -> str: ...
    async def get_thread_messages(self, thread_id: str, limit: int) -> list[dict[str, Any]]: ...


@runtime_checkable
class ActionsAdapter(Protocol):
    """Post-message actions (reactions, buttons, pins)."""

    async def add_reaction(self, chat_id: str, message_id: str, emoji: str) -> bool: ...
    async def remove_reaction(self, chat_id: str, message_id: str, emoji: str) -> bool: ...
    async def pin_message(self, chat_id: str, message_id: str) -> bool: ...


@runtime_checkable
class CommandsAdapter(Protocol):
    """Channel-level command registration."""

    async def register_commands(self, commands: list[dict[str, str]]) -> bool: ...
    async def unregister_commands(self) -> bool: ...


@runtime_checkable
class HeartbeatAdapter(Protocol):
    """Connection heartbeat/keepalive."""

    async def send_heartbeat(self) -> bool: ...
    def get_last_heartbeat(self) -> float: ...
    def is_alive(self) -> bool: ...


@runtime_checkable
class DirectoryAdapter(Protocol):
    """User/contact directory."""

    async def lookup_user(self, user_id: str) -> dict[str, Any] | None: ...
    async def search_users(self, query: str) -> list[dict[str, Any]]: ...


@runtime_checkable
class ResolverAdapter(Protocol):
    """Resolve channel-specific identifiers."""

    def resolve_chat_id(self, identifier: str) -> str: ...
    def resolve_user_id(self, identifier: str) -> str: ...


@runtime_checkable
class ElevatedAdapter(Protocol):
    """Elevated permissions handling."""

    def is_elevated(self, sender_id: str) -> bool: ...
    def grant_elevated(self, sender_id: str, duration_s: int) -> bool: ...
    def revoke_elevated(self, sender_id: str) -> bool: ...


@runtime_checkable
class AgentPromptAdapter(Protocol):
    """Channel-specific agent prompt customization."""

    def get_system_prompt_suffix(self) -> str: ...
    def get_channel_context(self) -> dict[str, Any]: ...


@runtime_checkable
class AgentToolsAdapter(Protocol):
    """Channel-specific tool provisioning."""

    def get_channel_tools(self) -> list[dict[str, Any]]: ...
    def filter_tools(self, tools: list[str]) -> list[str]: ...


@runtime_checkable
class TypingAdapter(Protocol):
    """Typing indicator management."""

    async def send_typing(self, chat_id: str) -> bool: ...
    async def stop_typing(self, chat_id: str) -> bool: ...


@runtime_checkable
class WebhookAdapter(Protocol):
    """Webhook registration and management."""

    async def register_webhook(self, url: str) -> bool: ...
    async def unregister_webhook(self) -> bool: ...
    def get_webhook_url(self) -> str | None: ...


# ---------------------------------------------------------------------------
# Adapter capability detection
# ---------------------------------------------------------------------------

ALL_ADAPTER_PROTOCOLS = {
    "config": ConfigAdapter,
    "auth": AuthAdapter,
    "pairing": PairingAdapter,
    "security": SecurityAdapter,
    "groups": GroupsAdapter,
    "mentions": MentionsAdapter,
    "outbound": OutboundAdapter,
    "status": StatusAdapter,
    "streaming": StreamingAdapter,
    "threading": ThreadingAdapter,
    "actions": ActionsAdapter,
    "commands": CommandsAdapter,
    "heartbeat": HeartbeatAdapter,
    "directory": DirectoryAdapter,
    "resolver": ResolverAdapter,
    "elevated": ElevatedAdapter,
    "agent_prompt": AgentPromptAdapter,
    "agent_tools": AgentToolsAdapter,
    "typing": TypingAdapter,
    "webhook": WebhookAdapter,
}


def detect_capabilities(plugin: Any) -> list[str]:
    """Detect which adapter protocols a channel plugin implements."""
    caps: list[str] = []
    for name, protocol in ALL_ADAPTER_PROTOCOLS.items():
        if isinstance(plugin, protocol):
            caps.append(name)
    return caps


def has_capability(plugin: Any, capability: str) -> bool:
    """Check if a plugin has a specific capability."""
    protocol = ALL_ADAPTER_PROTOCOLS.get(capability)
    if not protocol:
        return False
    return isinstance(plugin, protocol)
